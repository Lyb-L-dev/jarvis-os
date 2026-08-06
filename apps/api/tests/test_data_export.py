from __future__ import annotations

import json
from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models import User
from app.services.data_export import build_user_data_export


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        session.add(User(name="数据导出测试用户", timezone="Asia/Shanghai"))
        await session.commit()
        yield session

    await engine.dispose()


async def test_user_data_export_is_serializable_and_excludes_runtime_secrets(
    db_session: AsyncSession,
) -> None:
    payload = await build_user_data_export(db_session)
    encoded = json.dumps(payload, ensure_ascii=False)

    assert payload["format"] == "jarvis-os-user-data"
    assert payload["format_version"] == 1
    assert payload["table_count"] >= 30
    assert payload["record_count"] == 1
    assert payload["tables"]["users"][0]["name"] == "数据导出测试用户"
    assert "mimo_api_key" not in encoded
    assert "deepseek_api_key" not in encoded
    assert "openclaw_shared_secret" not in encoded
