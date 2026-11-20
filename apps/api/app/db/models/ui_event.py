from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Computed, DateTime, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UiEventRecord(Base):
    """Content-free notification log; business tables remain authoritative."""

    __tablename__ = "ui_events"
    __table_args__ = (
        Index("ix_ui_events_expires_id", "expires_at", "id"),
        Index("ix_ui_events_aggregate", "aggregate_type", "aggregate_ref"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    aggregate_type: Mapped[str] = mapped_column(String(64), nullable=False)
    aggregate_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    # One database-generated sequence is both the replay cursor and the data
    # version. Keeping the duplicate named column makes the SSE contract clear.
    data_version: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        Computed("id", persisted=True),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
