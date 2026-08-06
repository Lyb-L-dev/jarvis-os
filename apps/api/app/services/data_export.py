from __future__ import annotations

import base64
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import models as _models  # noqa: F401
from app.db.base import Base


def _export_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat() if value.tzinfo else value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Enum):
        return _export_value(value.value)
    if isinstance(value, bytes):
        return {
            "encoding": "base64",
            "value": base64.b64encode(value).decode("ascii"),
        }
    if isinstance(value, dict):
        return {str(key): _export_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_export_value(item) for item in value]
    return str(value)


async def build_user_data_export(session: AsyncSession) -> dict[str, Any]:
    tables: dict[str, list[dict[str, Any]]] = {}
    record_count = 0

    for table in Base.metadata.sorted_tables:
        result = await session.execute(select(table))
        rows = [
            {str(key): _export_value(value) for key, value in row.items()}
            for row in result.mappings()
        ]
        tables[table.name] = rows
        record_count += len(rows)

    schema_version = None
    try:
        schema_version = await session.scalar(text("SELECT version_num FROM alembic_version"))
    except SQLAlchemyError:
        # Unit-test and first-run SQLite databases may not use Alembic.
        schema_version = None

    return {
        "format": "jarvis-os-user-data",
        "format_version": 1,
        "exported_at": datetime.now(UTC).isoformat(),
        "database_schema": schema_version,
        "table_count": len(tables),
        "record_count": record_count,
        "tables": tables,
    }
