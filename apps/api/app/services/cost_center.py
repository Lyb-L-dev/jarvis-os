from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.models import AgentRunRecord, ModelCallLog
from app.schemas.cost import (
    CostCallItem,
    CostDailyPoint,
    CostOverview,
    CostPriceRule,
    CostProviderSummary,
    OllamaModelMetric,
    OllamaResourceStatus,
)
from app.services.resource_metrics import find_process_id, process_metrics

PROVIDERS = ("mimo", "deepseek", "ollama")


def price_rules(settings: Settings) -> list[CostPriceRule]:
    currency = settings.cost_estimate_currency
    return [
        CostPriceRule(
            provider="mimo",
            model_pattern="mimo-*",
            input_per_million=0,
            output_per_million=0,
            currency=currency,
            is_estimate=False,
            note="Token Plan 套餐内，不计入估算费用",
        ),
        CostPriceRule(
            provider="deepseek",
            model_pattern="deepseek-*",
            input_per_million=settings.deepseek_input_price_per_million,
            output_per_million=settings.deepseek_output_price_per_million,
            currency=currency,
            is_estimate=True,
            note="本地估算单价，可在 .env 调整，不代表供应商账单",
        ),
        CostPriceRule(
            provider="ollama",
            model_pattern="*",
            input_per_million=0,
            output_per_million=0,
            currency=currency,
            is_estimate=False,
            note="本地模型，无供应商费用",
        ),
    ]


def estimate_cost(
    settings: Settings,
    *,
    prompt_tokens: int | None,
    completion_tokens: int | None,
    provider: str,
) -> float:
    if provider != "deepseek":
        return 0.0
    prompt = max(prompt_tokens or 0, 0)
    completion = max(completion_tokens or 0, 0)
    cost = (
        prompt * settings.deepseek_input_price_per_million
        + completion * settings.deepseek_output_price_per_million
    ) / 1_000_000
    return round(cost, 4)


def provider_note(provider: str) -> str:
    if provider == "mimo":
        return "套餐内调用，不计费"
    if provider == "deepseek":
        return "按本地估算单价计算"
    return "本地模型，无供应商费用"


@dataclass(slots=True)
class _Entry:
    id: uuid.UUID
    source: Literal["chat", "workflow"]
    provider: str
    model: str
    success: bool
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    latency_ms: int | None
    tokens_per_second: float | None
    user_confirmed: bool
    created_at: datetime


def _entries_from_logs(logs: list[ModelCallLog]) -> list[_Entry]:
    return [
        _Entry(
            id=item.id,
            source="chat",
            provider=item.provider_used,
            model=item.model_used,
            success=item.success,
            prompt_tokens=item.prompt_tokens,
            completion_tokens=item.completion_tokens,
            total_tokens=item.total_tokens,
            latency_ms=item.latency_ms,
            tokens_per_second=item.tokens_per_second,
            user_confirmed=item.user_confirmed,
            created_at=item.created_at,
        )
        for item in logs
    ]


def _entries_from_runs(runs: list[AgentRunRecord]) -> list[_Entry]:
    return [
        _Entry(
            id=run.id,
            source="workflow",
            provider=str(run.provider_used or ""),
            model=str(run.model_used or ""),
            success=run.status == "completed",
            prompt_tokens=run.prompt_tokens,
            completion_tokens=run.completion_tokens,
            total_tokens=run.total_tokens,
            latency_ms=None,
            tokens_per_second=None,
            user_confirmed=run.paid_model_confirmed,
            created_at=run.created_at,
        )
        for run in runs
        if run.provider_used and run.total_tokens is not None
    ]


def _average(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 1)


def _provider_summary(
    settings: Settings,
    provider: str,
    items: list[_Entry],
) -> CostProviderSummary:
    successful = [item for item in items if item.success]
    prompt = sum(item.prompt_tokens or 0 for item in items)
    completion = sum(item.completion_tokens or 0 for item in items)
    total = sum(item.total_tokens or 0 for item in items)
    cost = sum(
        estimate_cost(
            settings,
            prompt_tokens=item.prompt_tokens,
            completion_tokens=item.completion_tokens,
            provider=item.provider,
        )
        for item in successful
    )
    return CostProviderSummary(
        provider=provider,
        calls=len(items),
        successful_calls=len(successful),
        confirmed_calls=sum(1 for item in items if item.user_confirmed),
        prompt_tokens=prompt,
        completion_tokens=completion,
        total_tokens=total,
        avg_latency_ms=_average(
            [item.latency_ms for item in items if item.latency_ms is not None]
        ),
        avg_tokens_per_second=_average(
            [
                item.tokens_per_second
                for item in items
                if item.tokens_per_second is not None
            ]
        ),
        estimated_cost=round(cost, 4),
        cost_note=provider_note(provider),
    )


async def ollama_resource_status(settings: Settings) -> OllamaResourceStatus:
    loaded_models: list[OllamaModelMetric] = []
    try:
        root = settings.ollama_base_url.removesuffix("/v1").rstrip("/")
        async with httpx.AsyncClient(timeout=4) as client:
            response = await client.get(f"{root}/api/ps")
            response.raise_for_status()
        for item in response.json().get("models", []):
            loaded_models.append(
                OllamaModelMetric(
                    name=str(item.get("name", "")),
                    size_bytes=int(item.get("size", 0) or 0),
                    size_vram_bytes=int(item.get("size_vram", 0) or 0),
                    processor=str(item.get("processor", "") or ""),
                )
            )
    except Exception as exc:  # pragma: no cover - local infrastructure
        return OllamaResourceStatus(
            status="offline",
            loaded_models=[],
            detail=type(exc).__name__,
        )
    pid = find_process_id("ollama")
    process = process_metrics(pid) if pid else None
    return OllamaResourceStatus(
        status="ready",
        process_cpu_percent=(
            round(process["cpu_percent"], 1) if process else None
        ),
        process_memory_mb=(
            round(process["memory_mb"], 1) if process else None
        ),
        loaded_models=loaded_models,
    )


async def build_cost_overview(
    db: AsyncSession,
    user_id: uuid.UUID,
    settings: Settings,
    *,
    days: int,
) -> CostOverview:
    now = datetime.now(UTC)
    cutoff = now - timedelta(days=days)
    logs = list(
        await db.scalars(
            select(ModelCallLog)
            .where(
                ModelCallLog.user_id == user_id,
                ModelCallLog.created_at >= cutoff,
            )
            .order_by(ModelCallLog.created_at.asc())
        )
    )
    runs = list(
        await db.scalars(
            select(AgentRunRecord)
            .where(
                AgentRunRecord.user_id == user_id,
                AgentRunRecord.created_at >= cutoff,
                AgentRunRecord.provider_used.is_not(None),
                AgentRunRecord.total_tokens.is_not(None),
            )
            .order_by(AgentRunRecord.created_at.asc())
        )
    )
    entries = _entries_from_logs(logs) + _entries_from_runs(runs)
    entries.sort(key=lambda item: item.created_at)

    providers = [
        _provider_summary(
            settings,
            provider,
            [item for item in entries if item.provider == provider],
        )
        for provider in PROVIDERS
    ]
    deepseek_items = [item for item in entries if item.provider == "deepseek"]
    deepseek_estimated_total = round(
        sum(
            estimate_cost(
                settings,
                prompt_tokens=item.prompt_tokens,
                completion_tokens=item.completion_tokens,
                provider=item.provider,
            )
            for item in deepseek_items
            if item.success
        ),
        4,
    )
    deepseek_confirmed_total = round(
        sum(
            estimate_cost(
                settings,
                prompt_tokens=item.prompt_tokens,
                completion_tokens=item.completion_tokens,
                provider=item.provider,
            )
            for item in deepseek_items
            if item.success and item.user_confirmed
        ),
        4,
    )

    daily: list[CostDailyPoint] = []
    today = now.date()
    for offset in range(days - 1, -1, -1):
        day = today - timedelta(days=offset)
        day_entries = [item for item in entries if item.created_at.date() == day]
        daily.append(
            CostDailyPoint(
                date=str(day),
                calls=len(day_entries),
                total_tokens=sum(item.total_tokens or 0 for item in day_entries),
                deepseek_estimated_cost=round(
                    sum(
                        estimate_cost(
                            settings,
                            prompt_tokens=item.prompt_tokens,
                            completion_tokens=item.completion_tokens,
                            provider=item.provider,
                        )
                        for item in day_entries
                        if item.provider == "deepseek" and item.success
                    ),
                    4,
                ),
            )
        )

    return CostOverview(
        generated_at=now,
        days=days,
        currency=settings.cost_estimate_currency,
        disclaimer=settings.cost_estimate_disclaimer,
        price_rules=price_rules(settings),
        total_calls=sum(item.calls for item in providers),
        total_successful_calls=sum(item.successful_calls for item in providers),
        total_tokens=sum(item.total_tokens for item in providers),
        deepseek_estimated_total=deepseek_estimated_total,
        deepseek_confirmed_estimated_total=deepseek_confirmed_total,
        providers=providers,
        daily=daily,
        local=await ollama_resource_status(settings),
    )


async def recent_cost_calls(
    db: AsyncSession,
    user_id: uuid.UUID,
    settings: Settings,
    *,
    limit: int,
) -> list[CostCallItem]:
    logs = list(
        await db.scalars(
            select(ModelCallLog)
            .where(ModelCallLog.user_id == user_id)
            .order_by(ModelCallLog.created_at.desc())
            .limit(limit)
        )
    )
    runs = list(
        await db.scalars(
            select(AgentRunRecord)
            .where(
                AgentRunRecord.user_id == user_id,
                AgentRunRecord.provider_used.is_not(None),
                AgentRunRecord.total_tokens.is_not(None),
            )
            .order_by(AgentRunRecord.created_at.desc())
            .limit(limit)
        )
    )
    entries = _entries_from_logs(logs) + _entries_from_runs(runs)
    entries.sort(key=lambda item: item.created_at, reverse=True)
    return [
        CostCallItem(
            id=item.id,
            source=item.source,
            provider_used=item.provider,
            model_used=item.model,
            success=item.success,
            prompt_tokens=item.prompt_tokens,
            completion_tokens=item.completion_tokens,
            total_tokens=item.total_tokens,
            latency_ms=item.latency_ms,
            tokens_per_second=item.tokens_per_second,
            user_confirmed=item.user_confirmed,
            estimated_cost=(
                estimate_cost(
                    settings,
                    prompt_tokens=item.prompt_tokens,
                    completion_tokens=item.completion_tokens,
                    provider=item.provider,
                )
                if item.success
                else 0.0
            ),
            created_at=item.created_at,
        )
        for item in entries[:limit]
    ]
