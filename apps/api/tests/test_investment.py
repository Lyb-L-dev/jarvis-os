from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.routes import investment as investment_routes
from app.db.base import Base
from app.db.models import (
    InvestmentThesis,
    InvestmentTransaction,
    NewsItem,
    NewsItemLink,
    User,
)
from app.schemas.investment import (
    AssetCreate,
    AssetUpdate,
    NewsLinkCreate,
    PositionCreate,
    ReviewGenerateRequest,
    ThesisCreate,
    TransactionCreate,
    TransactionUpdate,
)


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        user = User(name="投资测试用户", timezone="Asia/Shanghai")
        session.add(user)
        await session.flush()
        session.add(
            NewsItem(
                user_id=user.id,
                source_name="测试来源",
                title="示例公司发布季度经营更新",
                url="https://example.com/investment-update",
                canonical_url="https://example.com/investment-update",
                url_fingerprint="a" * 64,
                content_fingerprint="b" * 64,
                published_at=datetime.now(UTC),
                fetched_at=datetime.now(UTC),
                source_excerpt="公司发布了季度经营数据。",
                summary="季度经营数据已经发布。",
                analysis_text="需要对照原投资假设。",
                suggestion_text="核对事实并记录复盘。",
                category="investment",
                tags=["投资"],
                relevance_score=4.5,
                trust_score=4,
                language="zh-CN",
                status="saved",
                investment_related=True,
                portfolio_related=False,
            )
        )
        await session.commit()
        yield session

    await engine.dispose()


async def test_transaction_recalculation_and_manual_price(
    db_session: AsyncSession,
) -> None:
    asset = await investment_routes.create_asset(
        AssetCreate(
            name="示例公司",
            symbol="demo",
            market="NASDAQ",
            asset_type="stock",
            currency="usd",
        ),
        db_session,
    )
    position = await investment_routes.create_position(
        PositionCreate(
            asset_id=asset.id,
            quantity=Decimal("10"),
            average_cost=Decimal("100"),
            fees=Decimal("10"),
            transaction_date=date(2026, 1, 1),
            reason="初始投资理由",
            target_allocation=Decimal("20"),
            risk_level="high",
        ),
        db_session,
    )
    assert position.quantity == Decimal("10")
    assert position.cost_basis == Decimal("1010")
    assert position.average_cost == Decimal("101")
    assert position.market_value is None
    assert position.latest_price_missing is True

    buy = await investment_routes.create_transaction(
        TransactionCreate(
            asset_id=asset.id,
            transaction_type="buy",
            transaction_date=date(2026, 2, 1),
            quantity=Decimal("10"),
            unit_price=Decimal("200"),
            fees=Decimal("0"),
            reason="验证第二批买入的成本计算",
        ),
        db_session,
    )
    assert buy.quantity_after == Decimal("20")
    assert buy.average_cost_after == Decimal("150.5")

    sold = await investment_routes.create_transaction(
        TransactionCreate(
            asset_id=asset.id,
            transaction_type="sell",
            transaction_date=date(2026, 3, 1),
            quantity=Decimal("5"),
            unit_price=Decimal("180"),
            fees=Decimal("5"),
            reason="手动记录部分卖出",
        ),
        db_session,
    )
    assert sold.quantity_after == Decimal("15")
    assert sold.cost_basis_after == Decimal("2257.5")
    assert sold.realized_pnl == Decimal("142.5")

    await investment_routes.create_transaction(
        TransactionCreate(
            asset_id=asset.id,
            transaction_type="dividend",
            transaction_date=date(2026, 3, 15),
            cash_amount=Decimal("100"),
            fees=Decimal("2"),
            reason="现金分红",
        ),
        db_session,
    )
    overview = await investment_routes.investment_overview(db_session)
    current = overview.positions[0]
    assert current.quantity == Decimal("15")
    assert current.dividend_income == Decimal("98")
    assert current.market_value is None

    await investment_routes.update_asset(
        asset.id,
        AssetUpdate(
            latest_price=Decimal("170"),
            latest_price_date=date(2026, 3, 20),
        ),
        db_session,
    )
    overview = await investment_routes.investment_overview(db_session)
    current = overview.positions[0]
    assert current.market_value == Decimal("2550")
    assert current.unrealized_pnl == Decimal("292.5")
    assert overview.totals_by_currency[0].currency == "USD"

    changed = await investment_routes.update_transaction(
        buy.id,
        TransactionUpdate(unit_price=Decimal("100")),
        db_session,
    )
    assert changed.average_cost_after == Decimal("100.5")
    transactions = await investment_routes.list_transactions(
        db_session,
        asset_id=asset.id,
        limit=200,
    )
    changed_sell = next(item for item in transactions if item.id == sold.id)
    assert changed_sell.realized_pnl == Decimal("392.5")

    with pytest.raises(HTTPException) as oversell:
        await investment_routes.create_transaction(
            TransactionCreate(
                asset_id=asset.id,
                transaction_type="sell",
                transaction_date=date(2026, 4, 1),
                quantity=Decimal("99"),
                unit_price=Decimal("170"),
                reason="不应被接受的超额卖出",
            ),
            db_session,
        )
    assert oversell.value.status_code == 422

    with pytest.raises(HTTPException) as currency_change:
        await investment_routes.update_asset(
            asset.id,
            AssetUpdate(currency="CNY"),
            db_session,
        )
    assert currency_change.value.status_code == 409
    assert (
        await db_session.scalar(
            select(func.count(InvestmentTransaction.id)).where(
                InvestmentTransaction.deleted_at.is_(None)
            )
        )
        == 4
    )


async def test_thesis_news_link_review_and_soft_delete(
    db_session: AsyncSession,
) -> None:
    asset = await investment_routes.create_asset(
        AssetCreate(
            name="长期研究标的",
            symbol="LONG",
            market="SSE",
            asset_type="stock",
            currency="CNY",
            latest_price=Decimal("12"),
            latest_price_date=date(2026, 7, 29),
        ),
        db_session,
    )
    await investment_routes.create_position(
        PositionCreate(
            asset_id=asset.id,
            quantity=Decimal("100"),
            average_cost=Decimal("10"),
            transaction_date=date(2026, 7, 1),
            reason="盈利能力改善且现金流稳定",
        ),
        db_session,
    )
    first = await investment_routes.create_thesis(
        ThesisCreate(
            asset_id=asset.id,
            title="初始投资假设",
            original_reason="盈利能力改善且现金流稳定",
            key_assumptions=["主营收入保持增长"],
            watch_events=["下一次季度报告"],
            invalidation_conditions=["经营现金流连续恶化"],
            risk_level="medium",
            cloud_allowed=False,
        ),
        db_session,
    )
    second = await investment_routes.create_thesis(
        ThesisCreate(
            asset_id=asset.id,
            title="更新后的投资假设",
            original_reason="保留新的决策时点和依据",
            watch_events=["年度报告"],
            invalidation_conditions=["核心客户显著流失"],
            risk_level="high",
        ),
        db_session,
    )
    assert second.is_current is True
    stored_first = await db_session.get(InvestmentThesis, first.id)
    assert stored_first is not None
    assert stored_first.is_current is False
    assert stored_first.status == "superseded"
    assert stored_first.original_reason == "盈利能力改善且现金流稳定"

    news = await db_session.scalar(select(NewsItem))
    assert news is not None
    linked = await investment_routes.link_asset_news(
        asset.id,
        news.id,
        NewsLinkCreate(relationship_note="可能影响现金流假设"),
        db_session,
    )
    assert linked.linked is True
    assert linked.relationship_note == "可能影响现金流假设"
    await db_session.refresh(news)
    assert news.portfolio_related is True

    review = await investment_routes.generate_review(
        ReviewGenerateRequest(
            asset_id=asset.id,
            review_type="monthly",
            period_end=date(2026, 7, 29),
        ),
        db_session,
    )
    assert review.generated_by == "rules"
    assert "保留新的决策时点和依据" in review.summary
    assert review.snapshot["original_reason"] == "保留新的决策时点和依据"
    assert len(review.snapshot["related_news"]) == 1
    assert "不构成投资建议" in review.disclaimer

    await investment_routes.unlink_asset_news(asset.id, news.id, db_session)
    await db_session.refresh(news)
    assert news.portfolio_related is False
    assert await db_session.scalar(select(func.count(NewsItemLink.id))) == 0

    await investment_routes.link_asset_news(
        asset.id,
        news.id,
        NewsLinkCreate(relationship_note="删除资产时应同步清理"),
        db_session,
    )
    await db_session.refresh(news)
    assert news.portfolio_related is True

    deleted = await investment_routes.delete_asset(asset.id, db_session)
    assert deleted.status_code == 204
    await db_session.refresh(news)
    assert news.portfolio_related is False
    assert await db_session.scalar(select(func.count(NewsItemLink.id))) == 0
    assert await investment_routes.list_assets(db_session) == []
    assert await investment_routes.list_positions(db_session, include_closed=True) == []

    restored = await investment_routes.create_asset(
        AssetCreate(
            name="长期研究标的（恢复）",
            symbol="LONG",
            market="SSE",
            asset_type="stock",
            currency="CNY",
        ),
        db_session,
    )
    assert restored.id == asset.id
    assert restored.name == "长期研究标的（恢复）"
    await investment_routes.delete_asset(restored.id, db_session)
