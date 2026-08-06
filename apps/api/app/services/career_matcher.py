from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class CareerMatch:
    score: int
    level: str
    reasons: list[str]
    missing_skills: list[str]


def _strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            if isinstance(item, str):
                result.append(item)
            elif isinstance(item, dict):
                result.extend(
                    str(candidate) for candidate in item.values() if isinstance(candidate, str)
                )
        return result
    return []


def _terms(values: list[str]) -> list[str]:
    terms: list[str] = []
    for value in values:
        for token in re.findall(r"[A-Za-z][A-Za-z0-9.+#-]{1,30}|[\u4e00-\u9fff]{2,10}", value):
            normalized = token.casefold()
            if normalized not in terms:
                terms.append(normalized)
    return terms[:80]


def match_opportunity(profile: Any | None, opportunity: dict[str, Any]) -> CareerMatch:
    if profile is None:
        return CareerMatch(0, "unknown", ["尚未录入职业档案"], [])
    current_skills = _strings(profile.current_skills)
    goals = _strings(profile.career_goals)
    extra = profile.extra if isinstance(profile.extra, dict) else {}
    preferred_locations = []
    for key in ("preferred_locations", "locations", "location", "city"):
        preferred_locations.extend(_strings(extra.get(key)))
    major = str(profile.major or "").strip()
    education = str(profile.education_level or "").strip()
    if not any((current_skills, goals, preferred_locations, major, education)):
        return CareerMatch(0, "unknown", ["职业档案信息不足，暂不推断匹配度"], [])

    title = str(opportunity.get("title") or "")
    location = str(opportunity.get("location") or "")
    description = str(opportunity.get("description") or "")
    requirements = str(opportunity.get("requirements") or "")
    job_skills = [str(item) for item in opportunity.get("skills", []) if str(item)]
    haystack = f"{title}\n{description}\n{requirements}".casefold()
    reasons: list[str] = []
    score = 0

    normalized_user_skills = {item.casefold(): item for item in current_skills}
    matched_skills = [
        original
        for normalized, original in normalized_user_skills.items()
        if normalized in haystack
    ]
    if normalized_user_skills:
        skill_score = round(50 * len(matched_skills) / len(normalized_user_skills))
        score += skill_score
        if matched_skills:
            reasons.append(f"已有技能命中：{'、'.join(matched_skills[:6])}")

    goal_terms = _terms(goals)
    matched_goals = [term for term in goal_terms if term in haystack]
    if goal_terms:
        goal_score = round(30 * min(1, len(matched_goals) / max(1, min(3, len(goal_terms)))))
        score += goal_score
        if matched_goals:
            reasons.append("岗位内容与职业目标关键词相符")

    if preferred_locations and any(
        item.casefold() in location.casefold() for item in preferred_locations
    ):
        score += 10
        reasons.append("工作地点符合偏好")

    education_terms = _terms([major, education])
    if education_terms and any(term in haystack for term in education_terms):
        score += 10
        reasons.append("专业或教育背景与岗位描述相关")

    missing_skills = [
        skill for skill in job_skills if skill.casefold() not in normalized_user_skills
    ][:12]
    score = min(100, score)
    level = "high" if score >= 70 else "medium" if score >= 40 else "low"
    if not reasons:
        reasons.append("当前档案与岗位的直接证据较少")
    return CareerMatch(score, level, reasons[:8], missing_skills)
