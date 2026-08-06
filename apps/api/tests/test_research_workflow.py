from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import Settings
from app.db.base import Base
from app.db.models import (
    AgentApprovalRecord,
    AgentRunRecord,
    NewsItem,
    ResearchReport,
    ResearchSource,
    User,
)
from app.schemas.research import (
    GeneratedResearchReport,
    ResearchFact,
    ResearchInference,
    ResearchWorkflowCreateRequest,
)
from app.services.intelligence import fingerprint, normalized_content
from app.services.research_workflow import (
    ResearchReportFormatError,
    ResearchWorkflowService,
    ResearchWorkflowState,
    ResearchWorkflowUnavailableError,
)


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        session.add(User(name="研究测试用户", timezone="Asia/Shanghai"))
        await session.commit()
        yield session
    await engine.dispose()


def settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "database_url": "sqlite+aiosqlite:///:memory:",
        "v2_workflow_runtime_enabled": True,
        "v2_research_workflow_enabled": True,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


async def add_news_item(
    db: AsyncSession,
    user: User,
    *,
    title: str,
    url: str,
    excerpt: str,
    content_hash: str | None = None,
    relevance: float = 0.9,
) -> NewsItem:
    item = NewsItem(
        user_id=user.id,
        source_id=None,
        duplicate_of_id=None,
        source_name="官方测试来源",
        title=title,
        url=url,
        canonical_url=url,
        url_fingerprint=fingerprint(url),
        guid=None,
        content_fingerprint=content_hash
        or fingerprint(normalized_content(title, excerpt)),
        published_at=datetime.now(UTC),
        fetched_at=datetime.now(UTC),
        source_excerpt=excerpt,
        summary=excerpt,
        analysis_text="",
        suggestion_text="",
        category="technology",
        tags=["AI", "agent"],
        relevance_score=relevance,
        trust_score=5,
        language="zh",
        status="new",
        investment_related=False,
        portfolio_related=False,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


async def install_fake_generator(
    service: ResearchWorkflowService,
    monkeypatch: pytest.MonkeyPatch,
) -> list[str]:
    providers: list[str] = []

    async def fake_generate(
        db: AsyncSession,
        runtime_settings: Settings,
        run: AgentRunRecord,
        selected_provider: str,
    ) -> ResearchReport:
        del runtime_settings
        providers.append(selected_provider)
        sources = list(
            await db.scalars(
                select(ResearchSource)
                .where(ResearchSource.request_id == run.request_id)
                .order_by(ResearchSource.citation_key.asc())
            )
        )
        report = ResearchReport(
            run_id=run.id,
            request_id=run.request_id,
            user_id=run.user_id,
            title="多来源 AI Agent 研究",
            executive_summary="两个公开来源共同支持核心事实。",
            facts=[
                {
                    "statement": "来源一与来源二均提供了可核验信息。",
                    "source_refs": [sources[0].citation_key, sources[1].citation_key],
                }
            ],
            viewpoints=[
                {
                    "statement": "来源一认为生态正在加速。",
                    "attribution": sources[0].source_name,
                    "source_refs": [sources[0].citation_key],
                }
            ],
            inferences=[
                {
                    "statement": "短期内仍需继续核验落地案例。",
                    "basis_refs": [sources[0].citation_key, sources[1].citation_key],
                    "confidence": "medium",
                }
            ],
            uncertainties=["尚缺少长期效果数据。"],
            recommended_actions=["继续收集官方发布和实际案例。"],
            status="draft",
            provider_used=selected_provider,
            model_used=f"{selected_provider}-test-model",
        )
        db.add(report)
        run.selected_provider = selected_provider
        run.provider_used = selected_provider
        run.model_used = report.model_used
        await db.commit()
        await db.refresh(report)
        return report

    monkeypatch.setattr(service, "generate_report", fake_generate)
    return providers


async def test_research_requires_deepseek_approval_then_separate_report_confirmation(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = ResearchWorkflowService()
    providers = await install_fake_generator(service, monkeypatch)
    user = await db_session.scalar(select(User))
    assert user is not None
    first = await add_news_item(
        db_session,
        user,
        title="AI Agent 官方发布",
        url="https://example.com/agent-release",
        excerpt="官方发布了新的 AI Agent 能力和公开技术说明。",
    )
    second = await add_news_item(
        db_session,
        user,
        title="AI Agent 行业观察",
        url="https://example.org/agent-analysis",
        excerpt="独立研究机构发布了 AI Agent 采用情况分析。",
    )

    run = await service.start(
        db_session,
        settings(),
        user,
        ResearchWorkflowCreateRequest(
            question="AI Agent 目前有哪些重要变化？",
            source_item_ids=[first.id, second.id],
            model_preference="auto",
        ),
    )

    assert run.status == "waiting_for_model_approval"
    assert run.pending_kind == "deepseek_approval"
    assert run.pending_payload["covered_steps"] == [
        "synthesize_report",
        "validate_citations",
    ]
    assert run.pending_payload["data_categories"] == [
        "research_question",
        "research_scope",
        "public_source_excerpts",
    ]
    assert providers == []
    assert await db_session.scalar(select(func.count(ResearchReport.id))) == 0

    run = await service.resume(db_session, settings(), run, "approve_deepseek")

    assert providers == ["deepseek"]
    assert run.status == "waiting_for_report_review"
    assert run.paid_model_confirmed is True
    report = await db_session.scalar(
        select(ResearchReport).where(ResearchReport.run_id == run.id)
    )
    approval = await db_session.scalar(
        select(AgentApprovalRecord).where(AgentApprovalRecord.run_id == run.id)
    )
    assert report is not None
    assert report.status == "draft"
    assert report.archive_path is None
    assert approval is not None
    assert approval.status == "approved"

    run = await service.resume(db_session, settings(), run, "approve_report")

    assert run.status == "completed"
    await db_session.refresh(report)
    assert report.status == "confirmed"
    assert report.confirmed_at is not None
    assert report.archived_at is None
    assert report.archive_path is None


async def test_insufficient_unique_sources_pause_without_model_call(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = ResearchWorkflowService()
    providers = await install_fake_generator(service, monkeypatch)
    user = await db_session.scalar(select(User))
    assert user is not None
    shared_hash = fingerprint("same source fact")
    first = await add_news_item(
        db_session,
        user,
        title="重复内容 A",
        url="https://example.com/a",
        excerpt="这是同一来源事实的转载内容，不能作为独立来源。",
        content_hash=shared_hash,
    )
    second = await add_news_item(
        db_session,
        user,
        title="重复内容 B",
        url="https://example.org/b",
        excerpt="这是同一来源事实的转载内容，不能作为独立来源。",
        content_hash=shared_hash,
    )

    run = await service.start(
        db_session,
        settings(),
        user,
        ResearchWorkflowCreateRequest(
            question="请研究这两篇重复内容",
            source_item_ids=[first.id, second.id],
            model_preference="local",
        ),
    )

    assert run.status == "waiting_for_sources"
    assert run.pending_payload["source_count"] == 1
    assert providers == []
    assert await db_session.scalar(select(func.count(ResearchSource.id))) == 1

    third = await add_news_item(
        db_session,
        user,
        title="独立来源 C",
        url="https://independent.example.net/c",
        excerpt="另一个独立来源给出了不同的公开事实和证据。",
    )
    await service.add_intelligence_source(db_session, run, third.id)
    run = await service.resume(db_session, settings(), run, "sources_ready")

    assert run.status == "waiting_for_report_review"
    assert providers == ["ollama"]


async def test_user_can_choose_mimo_instead_of_paid_deepseek(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = ResearchWorkflowService()
    providers = await install_fake_generator(service, monkeypatch)
    user = await db_session.scalar(select(User))
    assert user is not None
    items = [
        await add_news_item(
            db_session,
            user,
            title=f"AI Agent 来源 {index}",
            url=f"https://source{index}.example.com/item",
            excerpt=f"第 {index} 个独立公开来源提供了相关事实。",
        )
        for index in (1, 2)
    ]
    run = await service.start(
        db_session,
        settings(),
        user,
        ResearchWorkflowCreateRequest(
            question="研究 AI Agent 的公开信息",
            source_item_ids=[item.id for item in items],
        ),
    )

    run = await service.resume(db_session, settings(), run, "use_mimo")

    assert run.status == "waiting_for_report_review"
    assert providers == ["mimo"]
    assert run.paid_model_confirmed is False
    approval = await db_session.scalar(select(AgentApprovalRecord))
    assert approval is not None
    assert approval.status == "rejected"


async def test_explicit_sources_are_not_lost_outside_automatic_top_eighty(
    db_session: AsyncSession,
) -> None:
    service = ResearchWorkflowService()
    user = await db_session.scalar(select(User))
    assert user is not None
    selected = [
        await add_news_item(
            db_session,
            user,
            title=f"用户明确选择的来源 {index}",
            url=f"https://selected.example.com/{index}",
            excerpt=f"用户明确选择的低相关度公开来源 {index}。",
            relevance=0.01,
        )
        for index in (1, 2)
    ]
    for index in range(81):
        await add_news_item(
            db_session,
            user,
            title=f"自动排名更高但无关的条目 {index}",
            url=f"https://distractor.example.com/{index}",
            excerpt=f"自动排名更高的无关公开内容 {index}。",
            relevance=1.0,
        )

    run = await service.start(
        db_session,
        settings(),
        user,
        ResearchWorkflowCreateRequest(
            question="研究用户明确选择的两个来源",
            source_item_ids=[item.id for item in selected],
        ),
    )
    sources = list(
        await db_session.scalars(
            select(ResearchSource)
            .where(ResearchSource.request_id == run.request_id)
            .order_by(ResearchSource.citation_key.asc())
        )
    )

    assert run.status == "waiting_for_model_approval"
    assert [source.news_item_id for source in sources[:2]] == [
        item.id for item in selected
    ]


async def test_rejected_report_is_not_confirmed_or_archived(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = ResearchWorkflowService()
    await install_fake_generator(service, monkeypatch)
    user = await db_session.scalar(select(User))
    assert user is not None
    items = [
        await add_news_item(
            db_session,
            user,
            title=f"研究来源 {index}",
            url=f"https://research.example.com/{index}",
            excerpt=f"来源 {index} 提供了一组可核验的公开信息。",
        )
        for index in (1, 2)
    ]
    run = await service.start(
        db_session,
        settings(),
        user,
        ResearchWorkflowCreateRequest(
            question="分析两个独立公开来源",
            source_item_ids=[item.id for item in items],
            model_preference="local",
        ),
    )

    run = await service.resume(db_session, settings(), run, "reject_report")

    assert run.status == "rejected"
    report = await db_session.scalar(select(ResearchReport))
    assert report is not None
    assert report.status == "rejected"
    assert report.confirmed_at is None
    assert report.archived_at is None


async def test_report_references_must_exist_and_use_two_sources(
    db_session: AsyncSession,
) -> None:
    service = ResearchWorkflowService()
    user = await db_session.scalar(select(User))
    assert user is not None
    items = [
        await add_news_item(
            db_session,
            user,
            title=f"核验来源 {index}",
            url=f"https://verify.example.com/{index}",
            excerpt=f"核验来源 {index} 的公开原文摘录。",
        )
        for index in (1, 2)
    ]
    run = await service.start(
        db_session,
        settings(),
        user,
        ResearchWorkflowCreateRequest(
            question="核验引用规则",
            source_item_ids=[item.id for item in items],
            model_preference="auto",
        ),
    )

    unknown = GeneratedResearchReport(
        title="无效引用",
        executive_summary="测试无效引用。",
        facts=[ResearchFact(statement="错误事实", source_refs=["S99"])],
    )
    with pytest.raises(ResearchReportFormatError, match="invalid source citation"):
        await service.validate_report_references(db_session, unknown, run.request_id)

    one_source = GeneratedResearchReport(
        title="单来源",
        executive_summary="只使用一个来源。",
        facts=[ResearchFact(statement="单来源事实", source_refs=["S1"])],
        inferences=[
            ResearchInference(
                statement="仍是单来源推断",
                basis_refs=["S1"],
                confidence="low",
            )
        ],
    )
    with pytest.raises(ResearchReportFormatError, match="at least two sources"):
        await service.validate_report_references(db_session, one_source, run.request_id)


def test_checkpoint_state_keeps_references_not_private_content() -> None:
    fields = set(ResearchWorkflowState.__annotations__)

    assert "request_ref" in fields
    assert "report_ref" in fields
    assert "question" not in fields
    assert "scope" not in fields
    assert "excerpt" not in fields
    assert "prompt" not in fields


async def test_disabled_research_workflow_does_not_create_run(
    db_session: AsyncSession,
) -> None:
    service = ResearchWorkflowService()
    user = await db_session.scalar(select(User))
    assert user is not None

    with pytest.raises(ResearchWorkflowUnavailableError):
        await service.start(
            db_session,
            settings(v2_research_workflow_enabled=False),
            user,
            ResearchWorkflowCreateRequest(question="这个研究请求不应启动"),
        )

    assert await db_session.scalar(select(func.count(AgentRunRecord.id))) == 0
