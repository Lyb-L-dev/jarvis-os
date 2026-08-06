from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import Settings
from app.db.base import Base
from app.db.models import (
    AgentApprovalRecord,
    AgentRunRecord,
    Goal,
    GrowthPlanDraft,
    GrowthTask,
    User,
)
from app.schemas.growth import GrowthWorkflowCreateRequest
from app.services.growth_workflow import (
    GrowthWorkflowService,
    GrowthWorkflowState,
    WorkflowCheckpointerProvider,
    WorkflowUnavailableError,
)


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        session.add(User(name="测试用户", timezone="Asia/Shanghai"))
        await session.commit()
        yield session
    await engine.dispose()


def settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "database_url": "sqlite+aiosqlite:///:memory:",
        "v2_workflow_runtime_enabled": True,
        "v2_growth_workflow_enabled": True,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


async def install_fake_generator(
    service: GrowthWorkflowService,
    monkeypatch: pytest.MonkeyPatch,
) -> list[str]:
    providers: list[str] = []

    async def fake_generate(
        db: AsyncSession,
        runtime_settings: Settings,
        run: AgentRunRecord,
        selected_provider: str,
    ) -> GrowthPlanDraft:
        del runtime_settings
        providers.append(selected_provider)
        draft = GrowthPlanDraft(
            run_id=run.id,
            user_id=run.user_id,
            title="AI 应用工程师成长路线",
            summary="用三个阶段完成核心能力建设。",
            milestones=[
                {
                    "title": "基础",
                    "description": "补齐 Python 与工程基础",
                    "order_index": 0,
                },
                {
                    "title": "项目",
                    "description": "完成可展示 Agent 项目",
                    "order_index": 1,
                },
            ],
            tasks=[
                {
                    "title": "完成 Python 训练",
                    "description": "完成练习并记录总结",
                    "milestone_index": 0,
                    "priority": 4,
                    "estimated_minutes": 120,
                },
                {
                    "title": "实现 Agent Router",
                    "description": "完成代码、测试和文档",
                    "milestone_index": 1,
                    "priority": 5,
                    "estimated_minutes": 180,
                },
            ],
            status="draft",
            provider_used=selected_provider,
            model_used=f"{selected_provider}-test-model",
        )
        db.add(draft)
        run.selected_provider = selected_provider
        run.provider_used = selected_provider
        run.model_used = draft.model_used
        await db.commit()
        await db.refresh(draft)
        return draft

    monkeypatch.setattr(service, "generate_plan_draft", fake_generate)
    return providers


async def test_growth_workflow_pauses_for_input_then_deepseek_then_review(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = GrowthWorkflowService()
    providers = await install_fake_generator(service, monkeypatch)
    user = await db_session.scalar(select(User))
    assert user is not None

    run = await service.start(
        db_session,
        settings(),
        user,
        GrowthWorkflowCreateRequest(
            objective="成为 AI 应用工程师",
            weekly_hours=None,
            model_preference="auto",
        ),
    )

    assert run.status == "waiting_for_input"
    assert run.pending_kind == "missing_information"
    assert run.pending_payload["fields"] == ["weekly_hours"]
    assert providers == []

    run = await service.supplement(
        db_session,
        settings(),
        run,
        constraints="优先实践项目",
        target_date=None,
        weekly_hours=12,
    )

    assert run.status == "waiting_for_model_approval"
    assert run.pending_kind == "deepseek_approval"
    assert run.pending_payload["covered_steps"] == ["generate_plan", "validate_plan"]
    assert providers == []

    run = await service.resume(
        db_session,
        settings(),
        run,
        "approve_deepseek",
    )

    assert providers == ["deepseek"]
    assert run.status == "waiting_for_draft_review"
    assert run.paid_model_confirmed is True
    draft = await db_session.scalar(
        select(GrowthPlanDraft).where(GrowthPlanDraft.run_id == run.id)
    )
    approval = await db_session.scalar(
        select(AgentApprovalRecord).where(AgentApprovalRecord.run_id == run.id)
    )
    assert draft is not None
    assert draft.status == "draft"
    assert approval is not None
    assert approval.status == "approved"
    assert await db_session.scalar(select(func.count(GrowthTask.id))) == 0

    run = await service.resume(
        db_session,
        settings(),
        run,
        "approve_draft",
    )

    assert run.status == "completed"
    assert await db_session.scalar(select(func.count(Goal.id))) == 1
    assert await db_session.scalar(select(func.count(GrowthTask.id))) == 2
    tasks = list(await db_session.scalars(select(GrowthTask)))
    assert {task.source_type for task in tasks} == {"growth_workflow"}
    await db_session.refresh(draft)
    assert draft.status == "confirmed"
    assert draft.created_goal_id is not None
    assert len(draft.created_task_ids) == 2


async def test_user_can_choose_local_without_deepseek_approval(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = GrowthWorkflowService()
    providers = await install_fake_generator(service, monkeypatch)
    user = await db_session.scalar(select(User))
    assert user is not None

    run = await service.start(
        db_session,
        settings(),
        user,
        GrowthWorkflowCreateRequest(
            objective="完成个人 Agent 项目",
            weekly_hours=8,
            model_preference="local",
        ),
    )

    assert run.status == "waiting_for_draft_review"
    assert run.selected_provider == "ollama"
    assert run.paid_model_confirmed is False
    assert providers == ["ollama"]
    assert await db_session.scalar(select(func.count(AgentApprovalRecord.id))) == 0


async def test_rejected_draft_does_not_create_formal_growth_records(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = GrowthWorkflowService()
    await install_fake_generator(service, monkeypatch)
    user = await db_session.scalar(select(User))
    assert user is not None
    run = await service.start(
        db_session,
        settings(),
        user,
        GrowthWorkflowCreateRequest(
            objective="制定职业成长计划",
            weekly_hours=6,
            model_preference="mimo",
        ),
    )

    run = await service.resume(db_session, settings(), run, "reject_draft")

    assert run.status == "rejected"
    assert await db_session.scalar(select(func.count(Goal.id))) == 0
    assert await db_session.scalar(select(func.count(GrowthTask.id))) == 0
    draft = await db_session.scalar(select(GrowthPlanDraft))
    assert draft is not None
    assert draft.status == "rejected"


async def test_confirmed_draft_application_is_idempotent(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = GrowthWorkflowService()
    await install_fake_generator(service, monkeypatch)
    user = await db_session.scalar(select(User))
    assert user is not None
    run = await service.start(
        db_session,
        settings(),
        user,
        GrowthWorkflowCreateRequest(
            objective="完成职业成长路线",
            weekly_hours=10,
            model_preference="local",
        ),
    )

    await service.apply_confirmed_draft(db_session, run)
    await service.apply_confirmed_draft(db_session, run)

    assert await db_session.scalar(select(func.count(Goal.id))) == 1
    assert await db_session.scalar(select(func.count(GrowthTask.id))) == 2


def test_checkpoint_state_schema_contains_references_not_private_bodies() -> None:
    fields = set(GrowthWorkflowState.__annotations__)

    assert "request_ref" in fields
    assert "draft_ref" in fields
    assert "objective" not in fields
    assert "constraints" not in fields
    assert "content" not in fields
    assert "prompt" not in fields


def test_postgres_checkpointer_url_uses_psycopg_scheme() -> None:
    converted = WorkflowCheckpointerProvider.postgres_url(
        "postgresql+asyncpg://jarvis:secret@127.0.0.1:5432/jarvis"
    )

    assert converted == "postgresql://jarvis:secret@127.0.0.1:5432/jarvis"


async def test_disabled_workflow_does_not_create_run(db_session: AsyncSession) -> None:
    service = GrowthWorkflowService()
    user = await db_session.scalar(select(User))
    assert user is not None

    with pytest.raises(WorkflowUnavailableError):
        await service.start(
            db_session,
            settings(v2_growth_workflow_enabled=False),
            user,
            GrowthWorkflowCreateRequest(
                objective="这个请求不应启动",
                weekly_hours=4,
            ),
        )

    assert await db_session.scalar(select(func.count(AgentRunRecord.id))) == 0
