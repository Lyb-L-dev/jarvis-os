from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import os
import tempfile
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from urllib.parse import parse_qsl, urlparse

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.config import PROJECT_ROOT, Settings
from app.services import browser_provider, computer_use, n8n_provider
from app.services.agent_core.contracts import ActionKind, AgentId, RiskLevel
from app.services.agent_core.policy import RiskPolicy


class ToolCatalogError(RuntimeError):
    """A tool definition or local execution boundary is invalid."""


class ToolInputModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SystemStatusInput(ToolInputModel):
    include_features: bool = True


class TextDraftInput(ToolInputModel):
    title: str = Field(min_length=1, max_length=160)
    body: str = Field(min_length=1, max_length=20_000)
    purpose: str = Field(default="general", min_length=1, max_length=80)


class WorkspaceFileWriteInput(ToolInputModel):
    relative_path: str = Field(min_length=1, max_length=240)
    content: str = Field(max_length=20_000)
    overwrite: bool = False


class ComputerScreenInfoInput(ToolInputModel):
    include_windows: bool = True


class WorkspaceFileReadInput(ToolInputModel):
    relative_path: str = Field(min_length=1, max_length=240)


class CalendarEventInput(ToolInputModel):
    title: str = Field(min_length=1, max_length=200)
    starts_at: datetime
    ends_at: datetime
    timezone: str = Field(default="Asia/Shanghai", min_length=1, max_length=80)
    notes: str = Field(default="", max_length=4_000)


class EmailActionInput(ToolInputModel):
    to: str = Field(min_length=3, max_length=320)
    subject: str = Field(min_length=1, max_length=300)
    body: str = Field(min_length=1, max_length=20_000)


class ExternalAccountInput(ToolInputModel):
    provider: str = Field(min_length=1, max_length=80)
    resource: str = Field(min_length=1, max_length=200)
    change_summary: str = Field(min_length=1, max_length=2_000)


class BrowserSubmitInput(ToolInputModel):
    url: str = Field(pattern=r"^https://", max_length=2_000)
    action_summary: str = Field(min_length=1, max_length=2_000)


class N8nProviderStatusInput(ToolInputModel):
    include_workflows: bool = True


class CalendarEventsReadInput(ToolInputModel):
    account_alias: str = Field(default="jarvis_sandbox", pattern=r"^jarvis_sandbox$")
    starts_at: datetime
    ends_at: datetime
    max_results: int = Field(default=10, ge=1, le=20)

    @model_validator(mode="after")
    def validate_window(self) -> CalendarEventsReadInput:
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        if (self.ends_at - self.starts_at).days > 31:
            raise ValueError("calendar read window cannot exceed 31 days")
        return self


class EmailDraftPrepareInput(ToolInputModel):
    account_alias: str = Field(default="jarvis_sandbox", pattern=r"^jarvis_sandbox$")
    to: str = Field(
        min_length=3,
        max_length=320,
        pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$",
    )
    subject: str = Field(min_length=1, max_length=300)
    body: str = Field(min_length=1, max_length=20_000)


class BrowserJobResearchInput(ToolInputModel):
    run_id: uuid.UUID
    source_kind: Literal["official", "sandbox"]
    source_name: str = Field(min_length=1, max_length=160)
    company_name: str = Field(default="", max_length=240)
    start_url: str = Field(pattern=r"^https://", max_length=2_000)
    allowed_hosts: list[str] = Field(min_length=1, max_length=8)
    query: str = Field(default="", max_length=200)
    max_pages: int = Field(default=3, ge=1, le=5)
    fixture_id: Literal["career_prompt_injection_v1"] | None = None
    confirmed_read_only_scope: Literal[True]

    @model_validator(mode="after")
    def validate_public_source(self) -> BrowserJobResearchInput:
        parsed = urlparse(self.start_url)
        hostname = (parsed.hostname or "").rstrip(".").lower()
        if (
            parsed.scheme != "https"
            or not hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.fragment
        ):
            raise ValueError("Source must be a credential-free HTTPS URL")
        try:
            ipaddress.ip_address(hostname)
        except ValueError:
            pass
        else:
            raise ValueError("IP-literal sources are not allowed")
        sensitive_query_keys = {
            "access_token",
            "api_key",
            "apikey",
            "auth",
            "key",
            "password",
            "session",
            "token",
        }
        if any(key.casefold() in sensitive_query_keys for key, _ in parse_qsl(parsed.query)):
            raise ValueError("Source URL cannot contain credential-like query parameters")
        normalized_hosts: list[str] = []
        for value in self.allowed_hosts:
            host = value.strip().rstrip(".").lower()
            if not host or "*" in host or "/" in host or ":" in host:
                raise ValueError("Only exact DNS hostnames are allowed")
            try:
                ipaddress.ip_address(host)
            except ValueError:
                pass
            else:
                raise ValueError("IP literals are not allowed in source allowlists")
            if host not in normalized_hosts:
                normalized_hosts.append(host)
        if hostname not in normalized_hosts:
            raise ValueError("The start URL host must be explicitly allowlisted")
        self.allowed_hosts = normalized_hosts
        if self.source_kind == "sandbox":
            if self.fixture_id != "career_prompt_injection_v1":
                raise ValueError("Sandbox research requires the security fixture")
        elif self.fixture_id is not None:
            raise ValueError("Security fixtures cannot be used with real sources")
        return self


@dataclass(frozen=True, slots=True)
class ToolHandlerResult:
    output: dict[str, Any]
    side_effect_proof: dict[str, Any] | None = None


ToolHandler = Callable[[BaseModel, Settings], Awaitable[ToolHandlerResult]]
PreviewBuilder = Callable[[BaseModel, Settings], dict[str, Any]]


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    tool_id: str
    version: str
    display_name: str
    description: str
    action_kind: ActionKind
    input_model: type[BaseModel]
    output_schema: dict[str, Any]
    scope: str
    data_sensitivity: str
    external_side_effect: bool
    idempotency_strategy: str
    timeout_seconds: int
    max_retries: int
    allowed_agents: frozenset[AgentId]
    credential_scope: str | None
    audit_fields: tuple[str, ...]
    failure_policy: str
    available: bool
    unavailable_reason: str | None
    preview_builder: PreviewBuilder
    handler: ToolHandler | None

    @property
    def risk_level(self) -> RiskLevel:
        return RiskPolicy().classify(self.action_kind).risk

    @property
    def requires_approval(self) -> bool:
        return self.risk_level is RiskLevel.CONFIRMED_WRITE


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, definition: ToolDefinition) -> None:
        policy = RiskPolicy().classify(definition.action_kind)
        if policy.risk is RiskLevel.NEVER_AUTOMATE:
            raise ToolCatalogError("R3 actions cannot be registered as Agent tools")
        if definition.tool_id in self._tools:
            raise ToolCatalogError(f"Tool already registered: {definition.tool_id}")
        if definition.available and definition.handler is None:
            raise ToolCatalogError("Available tools require an execution handler")
        self._tools[definition.tool_id] = definition

    def resolve(self, tool_id: str) -> ToolDefinition:
        try:
            return self._tools[tool_id]
        except KeyError as exc:
            raise ToolCatalogError(f"Unknown or prohibited tool: {tool_id}") from exc

    def list(self) -> tuple[ToolDefinition, ...]:
        return tuple(self._tools.values())


def _workspace_root(settings: Settings) -> Path:
    configured = Path(settings.tool_sandbox_root)
    root = configured if configured.is_absolute() else PROJECT_ROOT / configured
    return root.resolve()


def resolve_workspace_target(
    payload: WorkspaceFileWriteInput,
    settings: Settings,
) -> tuple[Path, Path]:
    relative = Path(payload.relative_path)
    if relative.is_absolute():
        raise ToolCatalogError("File path must be relative to the Jarvis tool sandbox")
    root = _workspace_root(settings)
    target = (root / relative).resolve()
    if not target.is_relative_to(root):
        raise ToolCatalogError("File path escaped the Jarvis tool sandbox")
    if target.suffix.casefold() not in {".md", ".txt", ".json"}:
        raise ToolCatalogError("Only .md, .txt, and .json files are allowed")
    if len(payload.content) > settings.tool_file_max_chars:
        raise ToolCatalogError("File content exceeds the configured safety limit")
    if target.exists() and target.is_dir():
        raise ToolCatalogError("File target points to a directory")
    if target.exists() and not payload.overwrite:
        raise ToolCatalogError("Existing files require overwrite=true and a new preview")
    return root, target


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(64 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def workspace_file_preview(model: BaseModel, settings: Settings) -> dict[str, Any]:
    payload = WorkspaceFileWriteInput.model_validate(model.model_dump())
    root, target = resolve_workspace_target(payload, settings)
    exists = target.exists()
    before_hash = _file_hash(target) if exists else None
    encoded = payload.content.encode()
    return {
        "operation": "replace_file" if exists else "create_file",
        "sandbox_relative_path": target.relative_to(root).as_posix(),
        "exists": exists,
        "overwrite": payload.overwrite,
        "before_sha256": before_hash,
        "after_sha256": hashlib.sha256(encoded).hexdigest(),
        "size_bytes": len(encoded),
        "content_preview": payload.content[:4_000],
        "preview_truncated": len(payload.content) > 4_000,
        "warning": "This file write requires a separate approval and execution step.",
    }


def simple_preview(model: BaseModel, _: Settings) -> dict[str, Any]:
    data = model.model_dump(mode="json")
    return {
        "operation": "read_or_internal_draft",
        "parameters": data,
        "warning": "No external side effect.",
    }


def unavailable_preview(model: BaseModel, _: Settings) -> dict[str, Any]:
    return {
        "operation": "provider_not_connected",
        "parameters": model.model_dump(mode="json"),
        "warning": "The external write provider is reserved but unavailable.",
    }


async def handle_system_status(
    model: BaseModel,
    settings: Settings,
) -> ToolHandlerResult:
    payload = SystemStatusInput.model_validate(model.model_dump())
    output: dict[str, Any] = {
        "status": "ready",
        "scope": "local_process",
        "checked_at": datetime.now(UTC).isoformat(),
    }
    if payload.include_features:
        output["features"] = {
            "tool_gateway": settings.v2_tool_gateway_enabled,
            "approval_center": settings.v2_approval_center_enabled,
            "n8n_provider": settings.v2_n8n_provider_enabled,
            "browser_research": settings.v2_browser_research_enabled,
            "semantic_memory": settings.v2_semantic_memory_enabled,
            "mem0_shadow": settings.v2_mem0_shadow_enabled,
        }
    return ToolHandlerResult(output=output)


async def handle_text_draft(model: BaseModel, _: Settings) -> ToolHandlerResult:
    payload = TextDraftInput.model_validate(model.model_dump())
    return ToolHandlerResult(
        output={
            "kind": "internal_text_draft",
            "title": payload.title.strip(),
            "body": payload.body,
            "purpose": payload.purpose,
            "content_sha256": hashlib.sha256(payload.body.encode()).hexdigest(),
        }
    )


async def handle_n8n_status(model: BaseModel, settings: Settings) -> ToolHandlerResult:
    payload = N8nProviderStatusInput.model_validate(model.model_dump())
    result = await n8n_provider.n8n_provider_status(settings)
    if not payload.include_workflows:
        result["workflows"] = []
    return ToolHandlerResult(output=result)


async def handle_calendar_read(
    model: BaseModel,
    settings: Settings,
) -> ToolHandlerResult:
    payload = CalendarEventsReadInput.model_validate(model.model_dump())
    result = await n8n_provider.call_n8n_provider(
        settings,
        path="/v1/calendar/read",
        payload=payload.model_dump(mode="json"),
    )
    if (
        result.get("status") != "completed"
        or result.get("read_only") is not True
        or result.get("account_alias") != "jarvis_sandbox"
        or not isinstance(result.get("events"), list)
    ):
        raise ToolCatalogError("n8n calendar workflow returned an invalid envelope")
    events = result["events"][: payload.max_results]
    return ToolHandlerResult(
        output={
            "status": "completed",
            "read_only": True,
            "account_alias": "jarvis_sandbox",
            "events": events,
            "event_count": len(events),
            "credential_exposed": False,
        }
    )


async def handle_email_draft(
    model: BaseModel,
    settings: Settings,
) -> ToolHandlerResult:
    payload = EmailDraftPrepareInput.model_validate(model.model_dump())
    result = await n8n_provider.call_n8n_provider(
        settings,
        path="/v1/email/draft",
        payload=payload.model_dump(mode="json"),
    )
    if (
        result.get("status") != "draft_only"
        or result.get("not_sent") is not True
        or result.get("account_alias") != "jarvis_sandbox"
        or not isinstance(result.get("draft"), dict)
    ):
        raise ToolCatalogError("n8n email draft workflow returned an invalid envelope")
    draft = result["draft"]
    if draft.get("to") != payload.to or draft.get("subject") != payload.subject:
        raise ToolCatalogError("n8n email draft changed the requested recipient or subject")
    return ToolHandlerResult(
        output={
            "status": "draft_only",
            "not_sent": True,
            "account_alias": "jarvis_sandbox",
            "draft": {
                "to": payload.to,
                "subject": payload.subject,
                "body": str(draft.get("body", ""))[:20_000],
            },
            "credential_exposed": False,
        }
    )


async def handle_browser_job_research(
    model: BaseModel,
    settings: Settings,
) -> ToolHandlerResult:
    payload = BrowserJobResearchInput.model_validate(model.model_dump())
    try:
        result = await browser_provider.call_browser_worker(
            settings,
            payload={
                "run_id": str(payload.run_id),
                "source": {
                    "source_kind": payload.source_kind,
                    "name": payload.source_name,
                    "company_name": payload.company_name,
                    "start_url": payload.start_url,
                    "allowed_hosts": payload.allowed_hosts,
                },
                "query": payload.query,
                "max_pages": payload.max_pages,
                "fixture_id": payload.fixture_id,
            },
        )
    except browser_provider.BrowserProviderError as exc:
        raise ToolCatalogError(str(exc)) from exc
    blocked_actions = set(result.get("blocked_actions", []))
    required_blocks = {
        "login",
        "form_submit",
        "file_upload",
        "download",
        "application_submit",
    }
    if (
        result.get("status") != "completed"
        or result.get("read_only") is not True
        or result.get("isolated_context") is not True
        or result.get("credentials_used") is not False
        or result.get("forms_submitted") is not False
        or result.get("files_uploaded") is not False
        or result.get("downloads_allowed") is not False
        or result.get("sessions_persisted") is not False
        or not required_blocks.issubset(blocked_actions)
        or not isinstance(result.get("pages"), list)
        or not isinstance(result.get("opportunities"), list)
    ):
        raise ToolCatalogError(
            "Browser Worker returned an envelope that violates read-only invariants"
        )
    pages = result["pages"][: payload.max_pages]
    opportunities = result["opportunities"][:100]
    return ToolHandlerResult(
        output={
            "status": "completed",
            "read_only": True,
            "isolated_context": True,
            "credentials_used": False,
            "forms_submitted": False,
            "files_uploaded": False,
            "downloads_allowed": False,
            "sessions_persisted": False,
            "blocked_actions": sorted(required_blocks),
            "pages": pages,
            "opportunities": opportunities,
            "page_count": len(pages),
            "opportunity_count": len(opportunities),
        }
    )


def _write_workspace_file(
    payload: WorkspaceFileWriteInput,
    settings: Settings,
) -> ToolHandlerResult:
    root, target = resolve_workspace_target(payload, settings)
    root.mkdir(parents=True, exist_ok=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    before_hash = _file_hash(target) if target.exists() else None
    encoded = payload.content.encode()
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=target.parent,
            prefix=".jarvis-tool-",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, target)
        temporary_path = None
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
    after_hash = _file_hash(target)
    proof = {
        "effect": "file_written",
        "sandbox_relative_path": target.relative_to(root).as_posix(),
        "before_sha256": before_hash,
        "after_sha256": after_hash,
        "size_bytes": target.stat().st_size,
        "completed_at": datetime.now(UTC).isoformat(),
    }
    return ToolHandlerResult(
        output={
            "status": "written",
            "sandbox_relative_path": proof["sandbox_relative_path"],
        },
        side_effect_proof=proof,
    )


async def handle_workspace_file(
    model: BaseModel,
    settings: Settings,
) -> ToolHandlerResult:
    payload = WorkspaceFileWriteInput.model_validate(model.model_dump())
    return await asyncio.to_thread(_write_workspace_file, payload, settings)


async def handle_computer_screen_info(
    model: BaseModel,
    settings: Settings,
) -> ToolHandlerResult:
    if settings.computer_use_stage < 1:
        raise ToolCatalogError("Computer-use stage 1 (read-only) is not enabled")
    payload = ComputerScreenInfoInput.model_validate(model.model_dump())
    info = await asyncio.to_thread(computer_use.screen_info)
    if not payload.include_windows:
        info["windows"] = []
    return ToolHandlerResult(output=info)


async def handle_workspace_file_read(
    model: BaseModel,
    settings: Settings,
) -> ToolHandlerResult:
    if settings.computer_use_stage < 1:
        raise ToolCatalogError("Computer-use stage 1 (read-only) is not enabled")
    payload = WorkspaceFileReadInput.model_validate(model.model_dump())
    try:
        result = await asyncio.to_thread(
            computer_use.read_workspace_file,
            settings,
            payload.relative_path,
        )
    except computer_use.ComputerUseError as exc:
        raise ToolCatalogError(str(exc)) from exc
    return ToolHandlerResult(output=result)


def _definition(
    *,
    tool_id: str,
    version: str,
    display_name: str,
    description: str,
    action_kind: ActionKind,
    input_model: type[BaseModel],
    scope: str,
    data_sensitivity: str,
    external_side_effect: bool,
    allowed_agents: frozenset[AgentId],
    preview_builder: PreviewBuilder,
    handler: ToolHandler | None,
    available: bool = True,
    unavailable_reason: str | None = None,
    credential_scope: str | None = None,
) -> ToolDefinition:
    return ToolDefinition(
        tool_id=tool_id,
        version=version,
        display_name=display_name,
        description=description,
        action_kind=action_kind,
        input_model=input_model,
        output_schema={"type": "object"},
        scope=scope,
        data_sensitivity=data_sensitivity,
        external_side_effect=external_side_effect,
        idempotency_strategy="user+tool+version+caller_key",
        timeout_seconds=30,
        max_retries=0 if external_side_effect else 1,
        allowed_agents=allowed_agents,
        credential_scope=credential_scope,
        audit_fields=(
            "tool_id",
            "tool_version",
            "agent_id",
            "risk_level",
            "parameters_hash",
            "idempotency_key",
            "status",
            "side_effect_proof",
        ),
        failure_policy="stop_and_require_review" if external_side_effect else "stop",
        available=available,
        unavailable_reason=unavailable_reason,
        preview_builder=preview_builder,
        handler=handler,
    )


TOOL_REGISTRY = ToolRegistry()
TOOL_REGISTRY.register(
    _definition(
        tool_id="browser.jobs.research",
        version="1.0.0",
        display_name="只读研究公开招聘页面",
        description=(
            "在一次性隔离浏览器环境中读取精确白名单内的公开招聘页面，"
            "保存来源时间与证据截图；不会登录、上传、下载或投递。"
        ),
        action_kind=ActionKind.READ_PUBLIC_SOURCE,
        input_model=BrowserJobResearchInput,
        scope="browser_public_jobs_read_only",
        data_sensitivity="public_source",
        external_side_effect=False,
        allowed_agents=frozenset({AgentId.RESEARCH, AgentId.GROWTH}),
        preview_builder=simple_preview,
        handler=handle_browser_job_research,
    )
)
TOOL_REGISTRY.register(
    _definition(
        tool_id="system.status.read",
        version="1.0.0",
        display_name="读取 Jarvis 状态",
        description="读取本地功能开关与服务状态，不包含私人正文或凭据。",
        action_kind=ActionKind.READ_LOCAL_DATA,
        input_model=SystemStatusInput,
        scope="local_system",
        data_sensitivity="internal_metadata",
        external_side_effect=False,
        allowed_agents=frozenset(
            {
                AgentId.CORE,
                AgentId.RESEARCH,
                AgentId.GROWTH,
                AgentId.LOCAL_DOCUMENT,
                AgentId.INVESTMENT_INTELLIGENCE,
            }
        ),
        preview_builder=simple_preview,
        handler=handle_system_status,
    )
)
TOOL_REGISTRY.register(
    _definition(
        tool_id="draft.text.prepare",
        version="1.0.0",
        display_name="生成内部文本草稿",
        description="把用户提供的内容保存为 Jarvis 内部草稿，不发送到外部服务。",
        action_kind=ActionKind.SAVE_INTERNAL_DRAFT,
        input_model=TextDraftInput,
        scope="jarvis_internal",
        data_sensitivity="personal",
        external_side_effect=False,
        allowed_agents=frozenset(AgentId),
        preview_builder=simple_preview,
        handler=handle_text_draft,
    )
)
TOOL_REGISTRY.register(
    _definition(
        tool_id="automation.provider.status",
        version="1.0.0",
        display_name="读取自动化 Provider 状态",
        description="通过签名入口检查 Jarvis 专用 n8n 和已发布工作流。",
        action_kind=ActionKind.READ_LOCAL_DATA,
        input_model=N8nProviderStatusInput,
        scope="n8n_provider",
        data_sensitivity="internal_metadata",
        external_side_effect=False,
        allowed_agents=frozenset({AgentId.CORE}),
        preview_builder=simple_preview,
        handler=handle_n8n_status,
    )
)
TOOL_REGISTRY.register(
    _definition(
        tool_id="calendar.events.read",
        version="1.0.0",
        display_name="读取沙箱日历",
        description="只读获取 Jarvis 测试日历事件，不连接或修改真实日历。",
        action_kind=ActionKind.READ_EXTERNAL_DATA,
        input_model=CalendarEventsReadInput,
        scope="n8n_sandbox_calendar",
        data_sensitivity="test_account",
        external_side_effect=False,
        allowed_agents=frozenset({AgentId.CORE, AgentId.GROWTH}),
        preview_builder=simple_preview,
        handler=handle_calendar_read,
    )
)
TOOL_REGISTRY.register(
    _definition(
        tool_id="email.draft.prepare",
        version="1.0.0",
        display_name="生成本地邮件草稿",
        description="通过 n8n 规范化邮件草稿，但不发送、不连接真实邮箱。",
        action_kind=ActionKind.SAVE_INTERNAL_DRAFT,
        input_model=EmailDraftPrepareInput,
        scope="n8n_sandbox_email",
        data_sensitivity="personal_draft",
        external_side_effect=False,
        allowed_agents=frozenset({AgentId.CORE, AgentId.RESEARCH, AgentId.GROWTH}),
        preview_builder=simple_preview,
        handler=handle_email_draft,
    )
)
TOOL_REGISTRY.register(
    _definition(
        tool_id="workspace.file.write",
        version="1.0.0",
        display_name="写入受控工作区文件",
        description="只允许写入 Jarvis .data/tool-sandbox 下的文本文件。",
        action_kind=ActionKind.MODIFY_FILE,
        input_model=WorkspaceFileWriteInput,
        scope="project_tool_sandbox",
        data_sensitivity="private_local",
        external_side_effect=True,
        allowed_agents=frozenset({AgentId.LOCAL_DOCUMENT}),
        preview_builder=workspace_file_preview,
        handler=handle_workspace_file,
    )
)
TOOL_REGISTRY.register(
    _definition(
        tool_id="computer.screen.info",
        version="1.0.0",
        display_name="读取屏幕元数据",
        description=(
            "只读返回本机分辨率、显示器数量与可见窗口标题；"
            "不采集画面内容，不读取剪贴板或按键。"
        ),
        action_kind=ActionKind.READ_LOCAL_DATA,
        input_model=ComputerScreenInfoInput,
        scope="local_screen_metadata",
        data_sensitivity="internal_metadata",
        external_side_effect=False,
        allowed_agents=frozenset({AgentId.CORE, AgentId.LOCAL_DOCUMENT}),
        preview_builder=simple_preview,
        handler=handle_computer_screen_info,
    )
)
TOOL_REGISTRY.register(
    _definition(
        tool_id="computer.file.read",
        version="1.0.0",
        display_name="读取受控工作区文件",
        description="只读返回 Jarvis .data/tool-sandbox 下的文本文件内容与哈希。",
        action_kind=ActionKind.READ_LOCAL_DATA,
        input_model=WorkspaceFileReadInput,
        scope="project_tool_sandbox",
        data_sensitivity="private_local",
        external_side_effect=False,
        allowed_agents=frozenset({AgentId.CORE, AgentId.LOCAL_DOCUMENT}),
        preview_builder=simple_preview,
        handler=handle_workspace_file_read,
    )
)

for reserved in (
    _definition(
        tool_id="calendar.event.upsert",
        version="0.1.0",
        display_name="修改日历事件",
        description="预留未来的真实日历写入；当前只有沙箱只读日历。",
        action_kind=ActionKind.MODIFY_CALENDAR,
        input_model=CalendarEventInput,
        scope="external_calendar",
        data_sensitivity="personal",
        external_side_effect=True,
        allowed_agents=frozenset({AgentId.GROWTH}),
        preview_builder=unavailable_preview,
        handler=None,
        available=False,
        unavailable_reason="Real calendar write provider is not connected",
        credential_scope="calendar_write",
    ),
    _definition(
        tool_id="email.send",
        version="0.1.0",
        display_name="发送邮件",
        description="预留真实邮件发送；当前只有本地草稿。",
        action_kind=ActionKind.EMAIL_ACTION,
        input_model=EmailActionInput,
        scope="external_email",
        data_sensitivity="personal",
        external_side_effect=True,
        allowed_agents=frozenset(),
        preview_builder=unavailable_preview,
        handler=None,
        available=False,
        unavailable_reason="Email provider is not connected",
        credential_scope="email_send",
    ),
    _definition(
        tool_id="external.account.update",
        version="0.1.0",
        display_name="修改外部账号",
        description="只登记风险边界，不连接任何真实账号。",
        action_kind=ActionKind.EXTERNAL_ACCOUNT_ACTION,
        input_model=ExternalAccountInput,
        scope="external_account",
        data_sensitivity="private",
        external_side_effect=True,
        allowed_agents=frozenset(),
        preview_builder=unavailable_preview,
        handler=None,
        available=False,
        unavailable_reason="External account providers are not connected",
        credential_scope="external_account_write",
    ),
    _definition(
        tool_id="browser.submit",
        version="0.1.0",
        display_name="浏览器提交",
        description="预留浏览器提交动作，当前没有 Browser Worker。",
        action_kind=ActionKind.BROWSER_SUBMIT,
        input_model=BrowserSubmitInput,
        scope="browser_sandbox",
        data_sensitivity="personal",
        external_side_effect=True,
        allowed_agents=frozenset(),
        preview_builder=unavailable_preview,
        handler=None,
        available=False,
        unavailable_reason="Browser Worker is not connected",
        credential_scope="browser_submit",
    ),
):
    TOOL_REGISTRY.register(reserved)


PERMANENTLY_BLOCKED_ACTIONS: tuple[ActionKind, ...] = (
    ActionKind.INVESTMENT_TRADE,
    ActionKind.PAYMENT,
    ActionKind.DELETE_DATA,
    ActionKind.CREDENTIAL_OPERATION,
)
