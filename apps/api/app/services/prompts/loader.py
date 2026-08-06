from __future__ import annotations

import json
import tomllib
from pathlib import Path

from app.services.prompts.schemas import PromptSpec

PROMPTS_PACKAGE_DIR = Path(__file__).resolve().parent
VERSIONS_PATH = PROMPTS_PACKAGE_DIR / "versions.json"


def load_prompt_registry_data() -> tuple[
    dict[tuple[str, str], PromptSpec],
    dict[str, str],
    dict[str, str],
]:
    """Load ``versions.json`` and every referenced template TOML file.

    Returns ``(specs_by_id_version, active_versions, agent_prompts)``.
    Template text is loaded from the repository, so a missing or malformed
    entry raises immediately at registry construction (fail fast).
    """

    payload = json.loads(VERSIONS_PATH.read_text(encoding="utf-8"))
    active: dict[str, str] = dict(payload.get("active", {}))
    agent_prompts: dict[str, str] = dict(payload.get("agent_prompts", {}))
    specs: dict[tuple[str, str], PromptSpec] = {}

    for entry in payload["prompts"]:
        prompt_id = entry["id"]
        version = entry["version"]
        content_ref = PROMPTS_PACKAGE_DIR / entry["content_ref"]
        with content_ref.open("rb") as handle:
            toml_data = tomllib.load(handle)
        content = dict(toml_data["content"])
        specs[(prompt_id, version)] = PromptSpec(
            prompt_id=prompt_id,
            version=version,
            kind=entry["kind"],
            agent_id=entry.get("agent_id"),
            purpose=entry["purpose"],
            status=entry["status"],
            variables=tuple(entry.get("variables", [])),
            safety_tags=tuple(entry.get("safety_tags", [])),
            content=content,
            created_at=entry["created_at"],
        )
    return specs, active, agent_prompts
