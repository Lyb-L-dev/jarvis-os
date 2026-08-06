from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.core.config import PROJECT_ROOT

CASES_PATH = PROJECT_ROOT / "evals" / "personal_benchmark_cases.json"


@dataclass(frozen=True, slots=True)
class PersonalEvaluationCase:
    id: str
    version: int
    title: str
    description: str
    category: str
    prompt: str
    required_all: list[str]
    required_any: list[str]
    forbidden: list[str]
    min_chars: int
    max_chars: int

    def public_metadata(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "version": self.version,
            "title": self.title,
            "description": self.description,
            "category": self.category,
        }


@lru_cache(maxsize=1)
def load_personal_evaluation_cases() -> tuple[PersonalEvaluationCase, ...]:
    raw_cases = json.loads(Path(CASES_PATH).read_text(encoding="utf-8"))
    return tuple(PersonalEvaluationCase(**item) for item in raw_cases)


def find_personal_evaluation_case(case_id: str) -> PersonalEvaluationCase | None:
    return next(
        (case for case in load_personal_evaluation_cases() if case.id == case_id),
        None,
    )


def score_evaluation_response(
    case: PersonalEvaluationCase,
    response: str,
) -> tuple[float, list[dict[str, object]]]:
    normalized = response.strip()
    checks: list[dict[str, object]] = []

    for phrase in case.required_all:
        checks.append(
            {
                "label": f"包含必要信息：{phrase}",
                "passed": phrase.lower() in normalized.lower(),
            }
        )
    if case.required_any:
        checks.append(
            {
                "label": "包含至少一项关键补充",
                "passed": any(
                    phrase.lower() in normalized.lower()
                    for phrase in case.required_any
                ),
            }
        )
    for phrase in case.forbidden:
        checks.append(
            {
                "label": f"未出现风险表述：{phrase}",
                "passed": phrase.lower() not in normalized.lower(),
            }
        )
    checks.append(
        {
            "label": f"长度在 {case.min_chars}–{case.max_chars} 字之间",
            "passed": case.min_chars <= len(normalized) <= case.max_chars,
        }
    )
    passed = sum(1 for check in checks if check["passed"])
    score = round((passed / len(checks)) * 100, 1) if checks else 0.0
    return score, checks


def tokens_per_second(
    completion_tokens: object,
    latency_ms: int,
    first_token_ms: int | None,
) -> float | None:
    if not isinstance(completion_tokens, int) or completion_tokens <= 0:
        return None
    generation_ms = latency_ms - (first_token_ms or 0)
    if generation_ms <= 0:
        return None
    return round(completion_tokens / (generation_ms / 1000), 2)
