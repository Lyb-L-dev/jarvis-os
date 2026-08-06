from __future__ import annotations

from app.core.config import Settings
from app.db.checkpoint import WorkflowCheckpointerProvider


def settings(**overrides: object) -> Settings:
    values: dict[str, object] = {"database_url": "sqlite+aiosqlite:///:memory:"}
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_backend_selects_postgres_only_for_postgres_urls() -> None:
    assert (
        WorkflowCheckpointerProvider.backend(
            settings(database_url="postgresql+asyncpg://u:p@localhost/db")
        )
        == "postgres"
    )
    assert (
        WorkflowCheckpointerProvider.backend(
            settings(database_url="sqlite+aiosqlite:///:memory:")
        )
        == "memory"
    )


def test_postgres_url_uses_psycopg_scheme() -> None:
    converted = WorkflowCheckpointerProvider.postgres_url(
        "postgresql+asyncpg://jarvis:secret@127.0.0.1:5432/jarvis"
    )
    assert converted == "postgresql://jarvis:secret@127.0.0.1:5432/jarvis"


async def test_open_returns_in_memory_saver_for_sqlite() -> None:
    provider = WorkflowCheckpointerProvider()
    async with provider.open(settings()) as (saver, backend):
        assert backend == "memory"
        assert saver is provider._memory


def test_moved_provider_matches_legacy_workflow_provider_behavior() -> None:
    from app.services.growth_workflow import (
        WorkflowCheckpointerProvider as LegacyProvider,
    )

    database_url = "postgresql+asyncpg://jarvis:secret@127.0.0.1:5432/jarvis"
    assert (
        WorkflowCheckpointerProvider.postgres_url(database_url)
        == LegacyProvider.postgres_url(database_url)
    )
    assert (
        WorkflowCheckpointerProvider.backend(settings())
        == LegacyProvider.backend(settings())
    )
