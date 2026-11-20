"""Conversation-level proactive feed behind a small V3 interface."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.models import ProactiveCategoryPreference, ProactiveSuggestion
from app.schemas.proactive import (
    ConversationProactiveFeed,
    ConversationProactiveItem,
    ProactiveCategoryState,
    ProactiveFeedbackSummary,
    ProactiveSuggestionItem,
)
from app.services.notifications import get_or_create_preferences, quiet_hours_active
from app.services.proactive import ProactiveSuggestionStateError, decide_suggestion

PROACTIVE_CATEGORIES = ("task", "weekly_review", "intelligence", "habit")


class ConversationalProactiveUnavailableError(RuntimeError):
    pass


class ConversationalProactiveStateError(RuntimeError):
    pass


class ConversationalProactive:
    """Deep module for ranked feeds, feedback decisions, and category control."""

    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self._db = db
        self._settings = settings

    async def feed(
        self,
        user_id: uuid.UUID,
        *,
        limit: int = 3,
        now: datetime | None = None,
    ) -> ConversationProactiveFeed:
        self._require_enabled()
        if not 1 <= limit <= 10:
            raise ConversationalProactiveStateError("Feed limit must be between 1 and 10")
        generated_at = now or datetime.now(UTC)
        await self._expire_stale(user_id, generated_at)
        notification_preferences = await get_or_create_preferences(self._db, user_id)
        quiet = quiet_hours_active(notification_preferences, generated_at)
        categories = await self._category_states(user_id)
        feedback = await self._feedback(user_id)
        if quiet:
            return ConversationProactiveFeed(
                generated_at=generated_at,
                enabled=True,
                quiet_active=True,
                suggestions=[],
                categories=categories,
                feedback=feedback,
            )

        disabled = {item.category for item in categories if not item.enabled}
        query = select(ProactiveSuggestion).where(
            ProactiveSuggestion.user_id == user_id,
            ProactiveSuggestion.status == "suggested",
        )
        if disabled:
            query = query.where(ProactiveSuggestion.source_type.not_in(disabled))
        records = list(await self._db.scalars(query.limit(100)))
        feedback_by_type = {item.suggestion_type: item for item in feedback}

        def rank(record: ProactiveSuggestion) -> float:
            summary = feedback_by_type.get(record.suggestion_type)
            acceptance = (
                summary.acceptance_rate
                if summary is not None and summary.acceptance_rate is not None
                else 0.5
            )
            age_hours = max(
                0.0,
                (generated_at - self._utc(record.suggested_at)).total_seconds() / 3600,
            )
            return round(record.priority * 100 + acceptance * 20 - age_hours * 0.1, 3)

        ranked = sorted(
            records,
            key=lambda item: (rank(item), self._utc(item.suggested_at), str(item.id)),
            reverse=True,
        )[:limit]
        return ConversationProactiveFeed(
            generated_at=generated_at,
            enabled=True,
            quiet_active=False,
            suggestions=[
                ConversationProactiveItem(
                    id=item.id,
                    source_type=item.source_type,
                    source_id=item.source_id,
                    suggestion_type=item.suggestion_type,
                    title=item.title,
                    rationale=item.rationale,
                    priority=item.priority,
                    rank_score=rank(item),
                    suggested_at=item.suggested_at,
                    expires_at=item.expires_at,
                )
                for item in ranked
            ],
            categories=categories,
            feedback=feedback,
        )

    async def decide(
        self,
        user_id: uuid.UUID,
        suggestion_ref: uuid.UUID,
        action: str,
    ) -> ProactiveSuggestionItem:
        self._require_enabled()
        if action not in {"accept", "dismiss"}:
            raise ConversationalProactiveStateError("Invalid suggestion decision")
        try:
            result = await decide_suggestion(
                self._db,
                user_id,
                suggestion_ref,
                action=action,
                strict=True,
            )
        except ProactiveSuggestionStateError as error:
            raise ConversationalProactiveStateError(str(error)) from error
        if result is None:
            raise ConversationalProactiveStateError("Suggestion not found")
        if result.status == "expired":
            raise ConversationalProactiveStateError("Suggestion has expired")
        return result

    async def configure_category(
        self,
        user_id: uuid.UUID,
        category: str,
        *,
        enabled: bool,
        now: datetime | None = None,
    ) -> ProactiveCategoryState:
        self._require_enabled()
        if category not in PROACTIVE_CATEGORIES:
            raise ConversationalProactiveStateError("Unknown proactive category")
        decided_at = now or datetime.now(UTC)
        preference = await self._db.scalar(
            select(ProactiveCategoryPreference).where(
                ProactiveCategoryPreference.user_id == user_id,
                ProactiveCategoryPreference.category == category,
            ).with_for_update()
        )
        if preference is None:
            preference = ProactiveCategoryPreference(
                user_id=user_id,
                category=category,
                enabled=enabled,
                disabled_at=None if enabled else decided_at,
            )
            try:
                async with self._db.begin_nested():
                    self._db.add(preference)
                    await self._db.flush()
            except IntegrityError as error:
                preference = await self._db.scalar(
                    select(ProactiveCategoryPreference)
                    .where(
                        ProactiveCategoryPreference.user_id == user_id,
                        ProactiveCategoryPreference.category == category,
                    )
                    .with_for_update()
                )
                if preference is None:
                    raise ConversationalProactiveStateError(
                        "Category preference changed concurrently"
                    ) from error
                preference.enabled = enabled
                preference.disabled_at = None if enabled else decided_at
        else:
            preference.enabled = enabled
            preference.disabled_at = None if enabled else decided_at
        if not enabled:
            pending = await self._db.scalars(
                select(ProactiveSuggestion).where(
                    ProactiveSuggestion.user_id == user_id,
                    ProactiveSuggestion.source_type == category,
                    ProactiveSuggestion.status == "suggested",
                )
            )
            for suggestion in pending:
                suggestion.status = "expired"
                suggestion.expired_at = decided_at
                suggestion.decision_reason = "category_disabled"
        await self._db.commit()
        states = await self._category_states(user_id)
        return next(item for item in states if item.category == category)

    async def _expire_stale(self, user_id: uuid.UUID, now: datetime) -> None:
        stale = await self._db.scalars(
            select(ProactiveSuggestion).where(
                ProactiveSuggestion.user_id == user_id,
                ProactiveSuggestion.status == "suggested",
                ProactiveSuggestion.expires_at.is_not(None),
                ProactiveSuggestion.expires_at <= now,
            )
        )
        for suggestion in stale:
            suggestion.status = "expired"
            suggestion.expired_at = now
            suggestion.decision_reason = "expired"
        await self._db.commit()

    async def _category_states(
        self,
        user_id: uuid.UUID,
    ) -> list[ProactiveCategoryState]:
        preferences = {
            item.category: item
            for item in await self._db.scalars(
                select(ProactiveCategoryPreference).where(
                    ProactiveCategoryPreference.user_id == user_id
                )
            )
        }
        pending_counts = dict(
            (
                await self._db.execute(
                    select(
                        ProactiveSuggestion.source_type,
                        func.count(ProactiveSuggestion.id),
                    )
                    .where(
                        ProactiveSuggestion.user_id == user_id,
                        ProactiveSuggestion.status == "suggested",
                    )
                    .group_by(ProactiveSuggestion.source_type)
                )
            ).tuples().all()
        )
        return [
            ProactiveCategoryState(
                category=category,
                enabled=preferences.get(category).enabled
                if category in preferences
                else True,
                pending_count=int(pending_counts.get(category, 0)),
                disabled_at=preferences.get(category).disabled_at
                if category in preferences
                else None,
            )
            for category in PROACTIVE_CATEGORIES
        ]

    async def _feedback(self, user_id: uuid.UUID) -> list[ProactiveFeedbackSummary]:
        rows = (
            await self._db.execute(
                select(
                    ProactiveSuggestion.suggestion_type,
                    func.sum(case((ProactiveSuggestion.status == "accepted", 1), else_=0)),
                    func.sum(case((ProactiveSuggestion.status == "dismissed", 1), else_=0)),
                )
                .where(
                    ProactiveSuggestion.user_id == user_id,
                    ProactiveSuggestion.status.in_(["accepted", "dismissed"]),
                )
                .group_by(ProactiveSuggestion.suggestion_type)
            )
        ).tuples()
        results: list[ProactiveFeedbackSummary] = []
        for suggestion_type, accepted_value, dismissed_value in rows:
            accepted = int(accepted_value or 0)
            dismissed = int(dismissed_value or 0)
            total = accepted + dismissed
            results.append(
                ProactiveFeedbackSummary(
                    suggestion_type=suggestion_type,
                    accepted=accepted,
                    dismissed=dismissed,
                    acceptance_rate=round(accepted / total, 4) if total else None,
                )
            )
        return sorted(results, key=lambda item: item.suggestion_type)

    def _require_enabled(self) -> None:
        if not self._settings.v3_conversational_proactive_enabled:
            raise ConversationalProactiveUnavailableError(
                "V3 conversational proactive is disabled"
            )

    @staticmethod
    def _utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
