from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import (
    Asset,
    InvestmentReview,
    InvestmentThesis,
    InvestmentTransaction,
    NewsItem,
    NewsItemLink,
    PortfolioPosition,
)
from app.schemas.investment import (
    AssetResponse,
    CurrencyTotal,
    PositionResponse,
    TransactionResponse,
)

ZERO = Decimal("0")
HUNDRED = Decimal("100")
INVESTMENT_DISCLAIMER = (
    "本页面只整理你手动录入的事实与复盘，不构成投资建议，"
    "不承诺收益，也不会自动执行任何交易。"
)


class InvestmentCalculationError(ValueError):
    pass


def decimal_or_zero(value: Decimal | None) -> Decimal:
    return value if value is not None else ZERO


def display_decimal(value: Decimal) -> str:
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


async def recalculate_position(
    db: AsyncSession,
    user_id: uuid.UUID,
    asset: Asset,
) -> PortfolioPosition:
    transactions = list(
        await db.scalars(
            select(InvestmentTransaction)
            .where(
                InvestmentTransaction.user_id == user_id,
                InvestmentTransaction.asset_id == asset.id,
                InvestmentTransaction.deleted_at.is_(None),
            )
            .order_by(
                InvestmentTransaction.transaction_date.asc(),
                InvestmentTransaction.created_at.asc(),
                InvestmentTransaction.id.asc(),
            )
        )
    )
    position = await db.scalar(
        select(PortfolioPosition).where(
            PortfolioPosition.user_id == user_id,
            PortfolioPosition.asset_id == asset.id,
        )
    )
    if position is None:
        position = PortfolioPosition(
            user_id=user_id,
            asset_id=asset.id,
            quantity=ZERO,
            average_cost=ZERO,
            cost_basis=ZERO,
            realized_pnl=ZERO,
            dividend_income=ZERO,
            risk_level="medium",
        )
        db.add(position)
        await db.flush()

    quantity = ZERO
    cost_basis = ZERO
    average_cost = ZERO
    total_realized = ZERO
    dividend_income = ZERO
    opened_on: date | None = None
    closed_on: date | None = None

    for transaction in transactions:
        fees = decimal_or_zero(transaction.fees)
        transaction.realized_pnl = ZERO

        if transaction.transaction_type in {"opening", "buy"}:
            tx_quantity = decimal_or_zero(transaction.quantity)
            unit_price = decimal_or_zero(transaction.unit_price)
            if tx_quantity <= ZERO:
                raise InvestmentCalculationError(
                    f"{transaction.transaction_type} quantity must be greater than zero"
                )
            if unit_price < ZERO:
                raise InvestmentCalculationError("Unit price cannot be negative")
            calculated = tx_quantity * unit_price + fees
            quantity += tx_quantity
            cost_basis += calculated
            average_cost = cost_basis / quantity if quantity else ZERO
            transaction.calculated_amount = calculated
            opened_on = opened_on or transaction.transaction_date
            closed_on = None
        elif transaction.transaction_type == "sell":
            tx_quantity = decimal_or_zero(transaction.quantity)
            unit_price = decimal_or_zero(transaction.unit_price)
            if tx_quantity <= ZERO:
                raise InvestmentCalculationError("Sell quantity must be greater than zero")
            if tx_quantity > quantity:
                raise InvestmentCalculationError(
                    "Sell quantity exceeds the available position at that date"
                )
            proceeds = tx_quantity * unit_price - fees
            removed_basis = average_cost * tx_quantity
            transaction.calculated_amount = proceeds
            transaction.realized_pnl = proceeds - removed_basis
            total_realized += transaction.realized_pnl
            quantity -= tx_quantity
            cost_basis -= removed_basis
            if quantity == ZERO:
                quantity = ZERO
                cost_basis = ZERO
                average_cost = ZERO
                closed_on = transaction.transaction_date
            else:
                average_cost = cost_basis / quantity
        elif transaction.transaction_type == "dividend":
            cash_amount = decimal_or_zero(transaction.cash_amount)
            if cash_amount <= ZERO:
                raise InvestmentCalculationError(
                    "Dividend cash amount must be greater than zero"
                )
            transaction.calculated_amount = cash_amount - fees
            transaction.realized_pnl = cash_amount - fees
            dividend_income += transaction.realized_pnl
        else:
            raise InvestmentCalculationError(
                f"Unsupported transaction type: {transaction.transaction_type}"
            )

        transaction.quantity_after = quantity
        transaction.average_cost_after = average_cost
        transaction.cost_basis_after = cost_basis

    position.quantity = quantity
    position.average_cost = average_cost
    position.cost_basis = cost_basis
    position.realized_pnl = total_realized
    position.dividend_income = dividend_income
    position.opened_on = opened_on
    position.closed_on = closed_on
    position.deleted_at = None
    await db.flush()
    return position


async def related_news_counts(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> dict[uuid.UUID, int]:
    rows = (
        await db.execute(
            select(NewsItemLink.linked_id, func.count(NewsItemLink.id))
            .join(NewsItem, NewsItem.id == NewsItemLink.news_item_id)
            .where(
                NewsItemLink.user_id == user_id,
                NewsItemLink.link_type == "asset",
                NewsItem.deleted_at.is_(None),
            )
            .group_by(NewsItemLink.linked_id)
        )
    ).all()
    return {row[0]: row[1] for row in rows}


def position_response(
    position: PortfolioPosition,
    *,
    related_count: int = 0,
) -> PositionResponse:
    asset = position.asset
    market_value: Decimal | None = None
    unrealized_pnl: Decimal | None = None
    unrealized_percent: Decimal | None = None
    if asset.latest_price is not None:
        market_value = position.quantity * asset.latest_price
        unrealized_pnl = market_value - position.cost_basis
        if position.cost_basis > ZERO:
            unrealized_percent = unrealized_pnl / position.cost_basis * HUNDRED
    return PositionResponse(
        id=position.id,
        asset=AssetResponse.model_validate(asset),
        quantity=position.quantity,
        average_cost=position.average_cost,
        cost_basis=position.cost_basis,
        realized_pnl=position.realized_pnl,
        dividend_income=position.dividend_income,
        target_allocation=position.target_allocation,
        risk_level=position.risk_level,
        opened_on=position.opened_on,
        closed_on=position.closed_on,
        market_value=market_value,
        unrealized_pnl=unrealized_pnl,
        unrealized_pnl_percent=unrealized_percent,
        latest_price_missing=asset.latest_price is None,
        related_news_count=related_count,
        created_at=position.created_at,
        updated_at=position.updated_at,
    )


def transaction_response(transaction: InvestmentTransaction) -> TransactionResponse:
    return TransactionResponse(
        id=transaction.id,
        asset=AssetResponse.model_validate(transaction.asset),
        transaction_type=transaction.transaction_type,
        transaction_date=transaction.transaction_date,
        quantity=transaction.quantity,
        unit_price=transaction.unit_price,
        cash_amount=transaction.cash_amount,
        fees=transaction.fees,
        currency=transaction.currency,
        reason=transaction.reason,
        notes=transaction.notes,
        calculated_amount=transaction.calculated_amount,
        realized_pnl=transaction.realized_pnl,
        quantity_after=transaction.quantity_after,
        average_cost_after=transaction.average_cost_after,
        cost_basis_after=transaction.cost_basis_after,
        created_at=transaction.created_at,
        updated_at=transaction.updated_at,
    )


def totals_by_currency(
    positions: list[PositionResponse],
) -> list[CurrencyTotal]:
    buckets: dict[str, dict[str, Decimal | int]] = defaultdict(
        lambda: {
            "cost_basis": ZERO,
            "market_value": ZERO,
            "unrealized_pnl": ZERO,
            "realized_pnl": ZERO,
            "dividend_income": ZERO,
            "priced_positions": 0,
            "total_positions": 0,
        }
    )
    for position in positions:
        bucket = buckets[position.asset.currency]
        bucket["cost_basis"] += position.cost_basis
        bucket["realized_pnl"] += position.realized_pnl
        bucket["dividend_income"] += position.dividend_income
        bucket["total_positions"] += 1
        if position.market_value is not None and position.unrealized_pnl is not None:
            bucket["market_value"] += position.market_value
            bucket["unrealized_pnl"] += position.unrealized_pnl
            bucket["priced_positions"] += 1

    totals: list[CurrencyTotal] = []
    for currency, bucket in sorted(buckets.items()):
        all_priced = bucket["priced_positions"] == bucket["total_positions"]
        totals.append(
            CurrencyTotal(
                currency=currency,
                cost_basis=bucket["cost_basis"],
                market_value=bucket["market_value"] if all_priced else None,
                unrealized_pnl=bucket["unrealized_pnl"] if all_priced else None,
                realized_pnl=bucket["realized_pnl"],
                dividend_income=bucket["dividend_income"],
                priced_positions=bucket["priced_positions"],
                total_positions=bucket["total_positions"],
            )
        )
    return totals


def review_period(
    review_type: str,
    period_start: date | None,
    period_end: date | None,
) -> tuple[date, date]:
    end = period_end or date.today()
    if period_start is not None:
        return period_start, end
    if review_type == "monthly":
        return end.replace(day=1), end
    if review_type == "weekly":
        return end - timedelta(days=end.weekday()), end
    return end, end


async def build_review(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    asset: Asset,
    review_type: str,
    period_start: date | None,
    period_end: date | None,
) -> InvestmentReview:
    start, end = review_period(review_type, period_start, period_end)
    position = await db.scalar(
        select(PortfolioPosition)
        .where(
            PortfolioPosition.user_id == user_id,
            PortfolioPosition.asset_id == asset.id,
            PortfolioPosition.deleted_at.is_(None),
        )
        .options(selectinload(PortfolioPosition.asset))
    )
    thesis = await db.scalar(
        select(InvestmentThesis)
        .where(
            InvestmentThesis.user_id == user_id,
            InvestmentThesis.asset_id == asset.id,
            InvestmentThesis.is_current.is_(True),
            InvestmentThesis.deleted_at.is_(None),
        )
        .order_by(InvestmentThesis.created_at.desc())
        .limit(1)
    )
    transactions = list(
        await db.scalars(
            select(InvestmentTransaction).where(
                InvestmentTransaction.user_id == user_id,
                InvestmentTransaction.asset_id == asset.id,
                InvestmentTransaction.transaction_date >= start,
                InvestmentTransaction.transaction_date <= end,
                InvestmentTransaction.deleted_at.is_(None),
            )
        )
    )
    news = list(
        await db.scalars(
            select(NewsItem)
            .join(NewsItemLink, NewsItemLink.news_item_id == NewsItem.id)
            .where(
                NewsItemLink.user_id == user_id,
                NewsItemLink.link_type == "asset",
                NewsItemLink.linked_id == asset.id,
                NewsItem.deleted_at.is_(None),
            )
            .order_by(NewsItem.published_at.desc(), NewsItem.created_at.desc())
            .limit(10)
        )
    )

    quantity = position.quantity if position else ZERO
    average_cost = position.average_cost if position else ZERO
    transaction_counts: dict[str, int] = defaultdict(int)
    for transaction in transactions:
        transaction_counts[transaction.transaction_type] += 1

    summary_parts = [
        f"{asset.name}（{asset.symbol}）在 {start.isoformat()} 至 {end.isoformat()} 的事实复盘。",
        f"期末持仓数量 {display_decimal(quantity)}，"
        f"平均成本 {display_decimal(average_cost)} {asset.currency}。",
    ]
    if asset.latest_price is None:
        summary_parts.append("尚未录入最新价格，因此不计算浮动收益。")
    else:
        market_value = quantity * asset.latest_price
        summary_parts.append(
            f"手动价格为 {display_decimal(asset.latest_price)} {asset.currency}"
            f"（{asset.latest_price_date or '日期未记录'}），"
            f"对应持仓市值 {display_decimal(market_value)}。"
        )
    summary_parts.append(
        f"本期交易 {len(transactions)} 笔，已关联情报 {len(news)} 条。"
    )
    if thesis is not None:
        summary_parts.append(f"原始投资理由：{thesis.original_reason}")
    else:
        summary_parts.append("尚未记录原始投资理由，建议先补充事实依据和失效条件。")

    risks: list[str] = []
    questions: list[str] = []
    if asset.latest_price is None:
        risks.append("缺少手动最新价格，无法核对当前市值和浮动收益。")
    if thesis is None:
        risks.append("缺少原始投资理由，后续难以判断投资假设是否变化。")
    else:
        risks.extend(thesis.invalidation_conditions[:5])
        questions.extend(
            [f"关注事件是否发生变化：{event}" for event in thesis.watch_events[:5]]
        )
    if not news:
        questions.append("本期没有关联情报，是否存在尚未归档的重要外部事件？")

    snapshot = {
        "asset_id": str(asset.id),
        "symbol": asset.symbol,
        "currency": asset.currency,
        "quantity": str(quantity),
        "average_cost": str(average_cost),
        "cost_basis": str(position.cost_basis if position else ZERO),
        "latest_price": str(asset.latest_price) if asset.latest_price is not None else None,
        "latest_price_date": (
            asset.latest_price_date.isoformat() if asset.latest_price_date else None
        ),
        "transaction_counts": dict(transaction_counts),
        "related_news": [
            {"id": str(item.id), "title": item.title, "url": item.url} for item in news
        ],
        "original_reason": thesis.original_reason if thesis else None,
        "captured_at": datetime.now(UTC).isoformat(),
    }
    review = InvestmentReview(
        user_id=user_id,
        asset_id=asset.id,
        thesis_id=thesis.id if thesis else None,
        review_type=review_type,
        period_start=start,
        period_end=end,
        status="draft",
        thesis_assessment="uncertain",
        summary=" ".join(summary_parts),
        risks=risks,
        questions=questions,
        snapshot=snapshot,
        generated_by="rules",
        disclaimer=INVESTMENT_DISCLAIMER,
    )
    db.add(review)
    await db.flush()
    return review
