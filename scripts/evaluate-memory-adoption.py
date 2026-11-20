"""V3-1 memory-network candidate adoption rate.

Outputs the legacy V3-1 delivery metric recorded in
docs/JARVIS_OS_V3_DELIVERY_LOG.md:

    adoption rate = confirmed / (confirmed + ignored + merged)

Rule extraction (structured sources: growth / english / intelligence /
investment) and Qwen extraction (unstructured sources: conversation /
confirmed memory) are reported separately so the two pipelines can be
baselined independently during the 2-week V3-1 observation window.
The v1.2 roadmap reports effective-candidate and deduplication rates
separately; this script remains for reproducibility of the original sample.

Usage:
    python scripts/evaluate-memory-adoption.py [--db-url URL]

The URL defaults to ``DATABASE_URL`` from the app settings (reads .env).
Exit code is 0 even when tables are empty (prints zero rates).
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import create_async_engine

RULE_SOURCE_KINDS = ("growth", "english", "intelligence", "investment")
QWEN_SOURCE_KINDS = ("conversation", "memory")
STATUS_CONFIRMED = "active"
STATUS_IGNORED = ("archived", "ignored")
STATUS_MERGED = "merged"

TABLE_NAMES = ("memory_entities", "memory_relations", "memory_events")


@dataclass(frozen=True)
class PathStats:
    label: str
    confirmed: int = 0
    ignored: int = 0
    merged: int = 0

    @property
    def decisions(self) -> int:
        return self.confirmed + self.ignored + self.merged

    @property
    def adoption_rate(self) -> float:
        if self.decisions == 0:
            return 0.0
        return self.confirmed / self.decisions


async def collect_stats(db_url: str) -> tuple[PathStats, PathStats]:
    engine = create_async_engine(db_url, pool_pre_ping=True)
    try:
        async with engine.begin() as connection:
            await connection.execute(text("SELECT 1"))
        rows_by_path: dict[str, list[tuple[str, int]]] = {
            "rule": [],
            "qwen": [],
        }
        async with engine.connect() as connection:
            for table in TABLE_NAMES:
                result = await connection.execute(
                    select(
                        text(f"{table}.source_kind"),
                        text(f"{table}.status"),
                        func.count().label("n"),
                    )
                    .select_from(text(table))
                    .group_by(text(f"{table}.source_kind"), text(f"{table}.status"))
                )
                for source_kind, status, count in result:
                    if source_kind in RULE_SOURCE_KINDS:
                        rows_by_path["rule"].append((status, int(count)))
                    elif source_kind in QWEN_SOURCE_KINDS:
                        rows_by_path["qwen"].append((status, int(count)))
    finally:
        await engine.dispose()

    stats: list[PathStats] = []
    for label in ("rule", "qwen"):
        confirmed = sum(n for s, n in rows_by_path[label] if s == STATUS_CONFIRMED)
        ignored = sum(
            n for s, n in rows_by_path[label] if s in STATUS_IGNORED
        )
        merged = sum(n for s, n in rows_by_path[label] if s == STATUS_MERGED)
        stats.append(PathStats(label=label, confirmed=confirmed, ignored=ignored, merged=merged))
    return stats[0], stats[1]


def _print_stats(path: PathStats) -> None:
    rate = f"{path.adoption_rate:.1%}"
    print(
        f"{path.label:<6} confirmed={path.confirmed:<4} "
        f"ignored={path.ignored:<4} merged={path.merged:<4} "
        f"decisions={path.decisions:<4} adoption_rate={rate}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db-url",
        default=None,
        help="SQLAlchemy async database URL (default: app DATABASE_URL from .env)",
    )
    args = parser.parse_args()

    db_url = args.db_url
    if not db_url:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api"))
        from app.core.config import get_settings

        db_url = get_settings().database_url

    rule, qwen = asyncio.run(collect_stats(db_url))
    print("memory-network candidate adoption (V3-1 baseline)")
    _print_stats(rule)
    _print_stats(qwen)
    combined = PathStats(
        label="total",
        confirmed=rule.confirmed + qwen.confirmed,
        ignored=rule.ignored + qwen.ignored,
        merged=rule.merged + qwen.merged,
    )
    _print_stats(combined)
    print("note: candidates still pending (status=candidate) are not decisions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
