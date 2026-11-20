from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.db.models import ProactiveSuggestion, User


async def test_active_source_kind_deduplication_is_concurrency_safe(
    pg_engine: AsyncEngine,
    pg_session: AsyncSession,
) -> None:
    user = User(name="PG Proactive", timezone="Asia/Shanghai")
    pg_session.add(user)
    await pg_session.commit()
    user_id = user.id
    source_id = uuid.uuid4()
    factory = async_sessionmaker(pg_engine, expire_on_commit=False)

    async def insert_suggestion() -> bool:
        async with factory() as session:
            session.add(
                ProactiveSuggestion(
                    user_id=user_id,
                    source_type="task",
                    source_id=source_id,
                    suggestion_type="act",
                    title="Concurrency-safe suggestion",
                    rationale="Only one active suggestion may exist for this source and kind.",
                    priority=3,
                    status="suggested",
                    suggested_at=datetime.now(UTC),
                )
            )
            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()
                return False
            return True

    outcomes = await asyncio.gather(insert_suggestion(), insert_suggestion())
    active_count = int(
        await pg_session.scalar(
            select(func.count(ProactiveSuggestion.id)).where(
                ProactiveSuggestion.user_id == user_id,
                ProactiveSuggestion.source_type == "task",
                ProactiveSuggestion.source_id == source_id,
                ProactiveSuggestion.suggestion_type == "act",
                ProactiveSuggestion.status == "suggested",
            )
        )
        or 0
    )

    assert sorted(outcomes) == [False, True]
    assert active_count == 1
