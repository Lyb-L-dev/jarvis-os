from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.services.prompts.loader import load_prompt_registry_data
from app.services.prompts.schemas import PromptSpec


class PromptNotFoundError(LookupError):
    pass


class PromptValidationError(RuntimeError):
    pass


class PromptRenderError(RuntimeError):
    pass


class PromptRegistry:
    """Versioned prompt store with one explicit active version per id."""

    def __init__(
        self,
        specs: dict[tuple[str, str], PromptSpec],
        active: dict[str, str],
        agent_prompts: dict[str, str],
    ) -> None:
        self._specs = specs
        self._active = dict(active)
        self._agent_prompts = dict(agent_prompts)

    def has(self, prompt_id: str, version: str | None = None) -> bool:
        try:
            self.get(prompt_id, version)
            return True
        except PromptNotFoundError:
            return False

    def get(self, prompt_id: str, version: str | None = None) -> PromptSpec:
        selected = version or self._active.get(prompt_id)
        if selected is None:
            raise PromptNotFoundError(f"No active version for prompt: {prompt_id}")
        try:
            return self._specs[(prompt_id, selected)]
        except KeyError as exc:
            raise PromptNotFoundError(
                f"Unknown prompt: {prompt_id}@{selected}"
            ) from exc

    def active_version(self, prompt_id: str) -> str | None:
        return self._active.get(prompt_id)

    def render(
        self,
        prompt_id: str,
        version: str | None = None,
        **variables: Any,
    ) -> str:
        spec = self.get(prompt_id, version)
        unknown = set(variables) - set(spec.variables)
        if unknown:
            raise PromptRenderError(
                f"Unknown render variables for {prompt_id}: {sorted(unknown)}"
            )
        missing = [name for name in spec.variables if name not in variables]
        if missing:
            raise PromptRenderError(f"Missing render variables for {prompt_id}: {missing}")
        text = self._select_content(spec, variables)
        for key, value in variables.items():
            text = text.replace("{" + key + "}", str(value))
        return text

    @staticmethod
    def _select_content(spec: PromptSpec, variables: dict[str, Any]) -> str:
        language = variables.get("language")
        if language in spec.content:
            return spec.content[language]
        if "text" in spec.content:
            return spec.content["text"]
        raise PromptRenderError(
            f"Prompt has no renderable content variant: {spec.prompt_id}"
        )

    def list_active(self) -> tuple[PromptSpec, ...]:
        return tuple(self.get(prompt_id) for prompt_id in sorted(self._active))

    def agent_prompt_id(self, agent_id: str) -> str | None:
        """Map an AgentSpec agent_id to its canonical registry prompt id."""

        return self._agent_prompts.get(agent_id)

    def reconcile_agent_prompts(
        self,
        specs: list[PromptSpec] | tuple[PromptSpec, ...],
    ) -> list[str]:
        """Verify every AgentSpec prompt label resolves to registered content.

        Closes audit debt H4: ``AgentSpec.prompt_version`` is no longer a bare
        declaration - each label must map to an existing registry prompt whose
        version suffix matches the label.
        """

        problems: list[str] = []
        for spec in specs:
            prompt_id = self.agent_prompt_id(spec.agent_id)
            if prompt_id is None:
                problems.append(f"{spec.agent_id}: no registry prompt mapping")
                continue
            if not self.has(prompt_id):
                problems.append(
                    f"{spec.agent_id}: registry prompt missing: {prompt_id}"
                )
                continue
            registry_version = self.get(prompt_id).version
            label_version = spec.prompt_version.rsplit("-v", 1)[-1]
            if registry_version != label_version:
                problems.append(
                    f"{spec.agent_id}: prompt_version {spec.prompt_version} "
                    f"!= registry {prompt_id}@{registry_version}"
                )
        return problems


@lru_cache(maxsize=1)
def get_prompt_registry() -> PromptRegistry:
    specs, active, agent_prompts = load_prompt_registry_data()
    return PromptRegistry(specs, active, agent_prompts)


def render_prompt(
    prompt_id: str,
    version: str | None = None,
    **variables: Any,
) -> str:
    return get_prompt_registry().render(prompt_id, version, **variables)
