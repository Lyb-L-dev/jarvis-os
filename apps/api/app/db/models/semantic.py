from __future__ import annotations

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class SemanticIndexEntry(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Rebuildable vector index entry; never a canonical content store."""

    __tablename__ = "semantic_index_entries"
    __table_args__ = (
        Index(
            "ix_semantic_index_entries_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        UniqueConstraint(
            "user_id",
            "source_type",
            "source_id",
            "index_version",
            "chunk_index",
            name="uq_semantic_index_entries_source_chunk",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    source_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_start: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_end: Mapped[int] = mapped_column(Integer, nullable=False)
    index_version: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    embedding_model: Mapped[str] = mapped_column(String(160), nullable=False)
    embedding_dimensions: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(1024), nullable=False)


class SemanticIndexState(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "semantic_index_states"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="empty")
    index_version: Mapped[str] = mapped_column(String(80), nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(160), nullable=False)
    embedding_dimensions: Mapped[int] = mapped_column(Integer, nullable=False)
    memory_source_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    knowledge_source_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
