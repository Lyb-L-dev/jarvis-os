"""Base repository contract.

Repositories are the only layer allowed to touch the ORM ``Session``
directly. Services depend on repositories (via a :class:`UnitOfWork`) and must
not commit or roll back by themselves; the caller controls the transaction.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession


class BaseRepository:
    """Thin wrapper that owns an :class:`AsyncSession` reference.

    Subclasses expose domain-shaped read/write helpers (e.g. ``get``,
    ``add``, ``find_duplicate``, ``mark_status``). Mutators only stage changes
    on the session; persistence is decided by the UnitOfWork / caller commit.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @property
    def session(self) -> AsyncSession:
        return self._session
