from __future__ import annotations

import hashlib
import json
import math
import uuid
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from time import perf_counter
from typing import Any

from app.core.config import PROJECT_ROOT, Settings
from app.services.memory import contains_sensitive_memory, memory_fingerprint
from app.services.memory_engines import ENGINE_REGISTRY, EngineCandidate
from app.services.semantic_index import SemanticIndexUnavailable, embed_texts

CASES_PATH = PROJECT_ROOT / "evals" / "memory_shadow_cases.json"
REDACTED_SENSITIVE_CANDIDATE = "[候选包含敏感信息，已拦截且未保存原文]"


@dataclass(frozen=True, slots=True)
class ExpectedMemory:
    memory_type: str
    keywords: list[str]


@dataclass(frozen=True, slots=True)
class MemoryShadowCase:
    id: str
    version: int
    title: str
    description: str
    category: str
    input: str
    expected: list[ExpectedMemory]

    def public_metadata(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "version": self.version,
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "input_preview": self.input,
            "expected_count": len(self.expected),
        }


@dataclass(frozen=True, slots=True)
class ScoredCandidate:
    content: str
    memory_type: str
    confidence: float | None
    external_id: str | None
    fingerprint: str
    expected_match: bool
    match_score: float
    blocked_reason: str | None


@lru_cache(maxsize=1)
def load_memory_shadow_cases() -> tuple[MemoryShadowCase, ...]:
    raw_cases = json.loads(Path(CASES_PATH).read_text(encoding="utf-8"))
    cases: list[MemoryShadowCase] = []
    for item in raw_cases:
        expected = [ExpectedMemory(**entry) for entry in item.pop("expected")]
        cases.append(MemoryShadowCase(**item, expected=expected))
    return tuple(cases)


def find_memory_shadow_case(case_id: str) -> MemoryShadowCase | None:
    return next((case for case in load_memory_shadow_cases() if case.id == case_id), None)


def case_source_hash(case: MemoryShadowCase) -> str:
    return hashlib.sha256(
        f"{case.id}|{case.version}|{case.input}".encode()
    ).hexdigest()


def _candidate_expected_score(
    candidate: EngineCandidate,
    expected: ExpectedMemory,
    semantic_score: float | None = None,
) -> float:
    content = candidate.content.casefold()
    if not expected.keywords:
        keyword_score = 1.0
    else:
        keyword_score = sum(
            1 for keyword in expected.keywords if keyword.casefold() in content
        ) / len(expected.keywords)
    type_score = 1.0 if candidate.memory_type == expected.memory_type else 0.5
    evidence_score = max(keyword_score, semantic_score or 0.0)
    return round(evidence_score * 0.8 + type_score * 0.2, 3)


def score_engine_candidates(
    case: MemoryShadowCase,
    candidates: list[EngineCandidate],
    *,
    semantic_scores: list[list[float]] | None = None,
) -> tuple[list[ScoredCandidate], dict[str, Any]]:
    expected_available = set(range(len(case.expected)))
    scored: list[ScoredCandidate] = []
    matched_count = 0
    sensitive_blocks = 0

    for candidate in candidates:
        sensitive = contains_sensitive_memory(candidate.content)
        blocked_reason = "sensitive_content" if sensitive else None
        if sensitive:
            sensitive_blocks += 1
        best_index: int | None = None
        best_score = 0.0
        for index in expected_available:
            semantic_score = (
                semantic_scores[len(scored)][index]
                if semantic_scores is not None
                else None
            )
            score = _candidate_expected_score(
                candidate,
                case.expected[index],
                semantic_score,
            )
            if score > best_score:
                best_score = score
                best_index = index
        expected_match = best_index is not None and best_score >= 0.65 and not sensitive
        if expected_match and best_index is not None:
            expected_available.remove(best_index)
            matched_count += 1
        stored_content = REDACTED_SENSITIVE_CANDIDATE if sensitive else candidate.content
        scored.append(
            ScoredCandidate(
                content=stored_content,
                memory_type=candidate.memory_type,
                confidence=candidate.confidence,
                external_id=candidate.external_id,
                fingerprint=memory_fingerprint(stored_content),
                expected_match=expected_match,
                match_score=best_score,
                blocked_reason=blocked_reason,
            )
        )

    candidate_count = len(candidates)
    expected_count = len(case.expected)
    if expected_count == 0:
        precision = 1.0 if candidate_count == 0 else 0.0
        recall = precision
    else:
        precision = matched_count / candidate_count if candidate_count else 0.0
        recall = matched_count / expected_count
    f1 = (
        (2 * precision * recall / (precision + recall))
        if precision + recall > 0
        else 0.0
    )
    negative_case_violations = candidate_count if expected_count == 0 else 0
    metrics = {
        "candidate_count": candidate_count,
        "expected_count": expected_count,
        "matched_count": matched_count,
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
        "sensitive_blocks": sensitive_blocks,
        "negative_case_violations": negative_case_violations,
    }
    return scored, metrics


def _cosine_similarity(first: list[float], second: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(first, second, strict=True))
    first_norm = math.sqrt(sum(value * value for value in first))
    second_norm = math.sqrt(sum(value * value for value in second))
    if not first_norm or not second_norm:
        return 0.0
    return max(-1.0, min(1.0, numerator / (first_norm * second_norm)))


async def _semantic_score_matrix(
    settings: Settings,
    case: MemoryShadowCase,
    candidates: list[EngineCandidate],
) -> list[list[float]] | None:
    if not candidates or not case.expected:
        return None
    expected_texts = [
        f"{case.input}\n记忆类型：{expected.memory_type}\n关键词：{'；'.join(expected.keywords)}"
        for expected in case.expected
    ]
    try:
        vectors = await embed_texts(
            settings,
            [candidate.content for candidate in candidates] + expected_texts,
        )
    except SemanticIndexUnavailable:
        return None
    candidate_vectors = vectors[: len(candidates)]
    expected_vectors = vectors[len(candidates) :]
    return [
        [
            round(_cosine_similarity(candidate_vector, expected_vector), 4)
            for expected_vector in expected_vectors
        ]
        for candidate_vector in candidate_vectors
    ]


async def execute_shadow_engine(
    engine_name: str,
    case: MemoryShadowCase,
    *,
    settings: Settings,
    shadow_run_id: uuid.UUID,
) -> tuple[list[ScoredCandidate], dict[str, Any]]:
    engine = ENGINE_REGISTRY[engine_name]
    source_attribution = f"memory_eval_case:{case.id}:v{case.version}"
    started = perf_counter()
    candidates = await engine.extract(
        case.input,
        settings=settings,
        shadow_run_id=shadow_run_id,
        source_attribution=source_attribution,
    )
    semantic_scores = await _semantic_score_matrix(settings, case, candidates)
    scored, metrics = score_engine_candidates(
        case,
        candidates,
        semantic_scores=semantic_scores,
    )
    metrics["latency_ms"] = round((perf_counter() - started) * 1000)
    metrics["status"] = "completed"
    metrics["model"] = (
        "rules-v1"
        if engine_name == "rule"
        else settings.mem0_shadow_llm_model
        if engine_name == "mem0"
        else settings.ollama_model
    )
    metrics["local_only"] = True
    metrics["scoring_mode"] = (
        "keyword+local_bge" if semantic_scores is not None else "keyword"
    )
    return scored, metrics
