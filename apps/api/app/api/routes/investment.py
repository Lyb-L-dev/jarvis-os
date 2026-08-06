from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import IntegrityError
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
    User,
)
from app.db.session import get_db_session
from app.schemas.investment import (
    AssetCreate,
    AssetResponse,
    AssetUpdate,
    CurrencyPerformanceSeries,
    InvestmentOverviewResponse,
    InvestmentPerformancePoint,
    InvestmentPerformanceResponse,
    NewsLinkCreate,
    PositionCreate,
    PositionResponse,
    PositionUpdate,
    RelatedNewsResponse,
    ReviewGenerateRequest,
    ReviewResponse,
    ReviewUpdate,
    ThesisCreate,
    ThesisResponse,
    ThesisUpdate,
    TransactionCreate,
    TransactionResponse,
    TransactionUpdate,
)
from app.services.investment import (
    INVESTMENT_DISCLAIMER,
    InvestmentCalculationError,
    build_review,
    position_response,
    recalculate_position,
    related_news_counts,
    totals_by_currency,
    transaction_response,
)

router = APIRouter(prefix="/investment")
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]


async def current_user(db: AsyncSession) -> User:
    user = await db.scalar(select(User).order_by(User.created_at.asc()).limit(1))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Complete onboarding before using the investment assistant",
        )
    return user


async def owned_asset(
    db: AsyncSession,
    asset_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Asset:
    asset = await db.scalar(
        select(Asset).where(
            Asset.id == asset_id,
            Asset.user_id == user_id,
            Asset.deleted_at.is_(None),
        )
    )
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset


async def owned_position(
    db: AsyncSession,
    position_id: uuid.UUID,
    user_id: uuid.UUID,
) -> PortfolioPosition:
    position = await db.scalar(
        select(PortfolioPosition)
        .where(
            PortfolioPosition.id == position_id,
            PortfolioPosition.user_id == user_id,
            PortfolioPosition.deleted_at.is_(None),
        )
        .options(selectinload(PortfolioPosition.asset))
    )
    if position is None or position.asset.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Position not found")
    return position


async def owned_transaction(
    db: AsyncSession,
    transaction_id: uuid.UUID,
    user_id: uuid.UUID,
) -> InvestmentTransaction:
    transaction = await db.scalar(
        select(InvestmentTransaction)
        .where(
            InvestmentTransaction.id == transaction_id,
            InvestmentTransaction.user_id == user_id,
            InvestmentTransaction.deleted_at.is_(None),
        )
        .options(selectinload(InvestmentTransaction.asset))
    )
    if transaction is None or transaction.asset.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return transaction


async def owned_thesis(
    db: AsyncSession,
    thesis_id: uuid.UUID,
    user_id: uuid.UUID,
) -> InvestmentThesis:
    thesis = await db.scalar(
        select(InvestmentThesis)
        .where(
            InvestmentThesis.id == thesis_id,
            InvestmentThesis.user_id == user_id,
            InvestmentThesis.deleted_at.is_(None),
        )
        .options(selectinload(InvestmentThesis.asset))
    )
    if thesis is None or thesis.asset.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Investment thesis not found")
    return thesis


async def owned_review(
    db: AsyncSession,
    review_id: uuid.UUID,
    user_id: uuid.UUID,
) -> InvestmentReview:
    review = await db.scalar(
        select(InvestmentReview)
        .where(
            InvestmentReview.id == review_id,
            InvestmentReview.user_id == user_id,
            InvestmentReview.deleted_at.is_(None),
        )
        .options(selectinload(InvestmentReview.asset))
    )
    if review is None or review.asset.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Investment review not found")
    return review


def thesis_response(thesis: InvestmentThesis) -> ThesisResponse:
    return ThesisResponse(
        id=thesis.id,
        asset=AssetResponse.model_validate(thesis.asset),
        title=thesis.title,
        original_reason=thesis.original_reason,
        current_view=thesis.current_view,
        key_assumptions=thesis.key_assumptions,
        watch_events=thesis.watch_events,
        invalidation_conditions=thesis.invalidation_conditions,
        risk_level=thesis.risk_level,
        status=thesis.status,
        is_current=thesis.is_current,
        cloud_allowed=thesis.cloud_allowed,
        created_at=thesis.created_at,
        updated_at=thesis.updated_at,
    )


def review_response(review: InvestmentReview) -> ReviewResponse:
    return ReviewResponse(
        id=review.id,
        asset=AssetResponse.model_validate(review.asset),
        thesis_id=review.thesis_id,
        review_type=review.review_type,
        period_start=review.period_start,
        period_end=review.period_end,
        status=review.status,
        thesis_assessment=review.thesis_assessment,
        summary=review.summary,
        risks=review.risks,
        questions=review.questions,
        user_note=review.user_note,
        snapshot=review.snapshot,
        generated_by=review.generated_by,
        disclaimer=review.disclaimer,
        created_at=review.created_at,
        updated_at=review.updated_at,
    )


async def load_position(
    db: AsyncSession,
    position_id: uuid.UUID,
) -> PortfolioPosition:
    position = await db.scalar(
        select(PortfolioPosition)
        .where(PortfolioPosition.id == position_id)
        .options(selectinload(PortfolioPosition.asset))
        .execution_options(populate_existing=True)
    )
    assert position is not None
    return position


def validate_transaction_values(transaction: InvestmentTransaction) -> None:
    if transaction.transaction_type in {"opening", "buy", "sell"}:
        if transaction.quantity is None or transaction.unit_price is None:
            raise HTTPException(
                status_code=422,
                detail="Quantity and unit price are required for this transaction",
            )
        transaction.cash_amount = None
    elif transaction.transaction_type == "dividend":
        if transaction.cash_amount is None:
            raise HTTPException(
                status_code=422,
                detail="Cash amount is required for a dividend",
            )
        transaction.quantity = None
        transaction.unit_price = None


@router.get("/overview", response_model=InvestmentOverviewResponse)
async def investment_overview(db: DatabaseSession) -> InvestmentOverviewResponse:
    user = await current_user(db)
    positions = list(
        await db.scalars(
            select(PortfolioPosition)
            .join(Asset, Asset.id == PortfolioPosition.asset_id)
            .where(
                PortfolioPosition.user_id == user.id,
                PortfolioPosition.deleted_at.is_(None),
                Asset.deleted_at.is_(None),
            )
            .options(selectinload(PortfolioPosition.asset))
            .order_by(PortfolioPosition.quantity.desc(), Asset.name.asc())
        )
    )
    news_counts = await related_news_counts(db, user.id)
    responses = [
        position_response(item, related_count=news_counts.get(item.asset_id, 0))
        for item in positions
    ]
    recent_transactions = list(
        await db.scalars(
            select(InvestmentTransaction)
            .join(Asset, Asset.id == InvestmentTransaction.asset_id)
            .where(
                InvestmentTransaction.user_id == user.id,
                InvestmentTransaction.deleted_at.is_(None),
                Asset.deleted_at.is_(None),
            )
            .options(selectinload(InvestmentTransaction.asset))
            .order_by(
                InvestmentTransaction.transaction_date.desc(),
                InvestmentTransaction.created_at.desc(),
            )
            .limit(10)
        )
    )
    asset_count = await db.scalar(
        select(func.count(Asset.id)).where(
            Asset.user_id == user.id,
            Asset.deleted_at.is_(None),
        )
    )
    transaction_count = await db.scalar(
        select(func.count(InvestmentTransaction.id)).where(
            InvestmentTransaction.user_id == user.id,
            InvestmentTransaction.deleted_at.is_(None),
        )
    )
    current_theses = await db.scalar(
        select(func.count(InvestmentThesis.id)).where(
            InvestmentThesis.user_id == user.id,
            InvestmentThesis.is_current.is_(True),
            InvestmentThesis.deleted_at.is_(None),
        )
    )
    linked_news = await db.scalar(
        select(func.count(func.distinct(NewsItemLink.news_item_id))).where(
            NewsItemLink.user_id == user.id,
            NewsItemLink.link_type == "asset",
        )
    )
    return InvestmentOverviewResponse(
        active_positions=sum(item.quantity > 0 for item in positions),
        closed_positions=sum(
            item.quantity == 0 and item.opened_on is not None for item in positions
        ),
        asset_count=asset_count or 0,
        transaction_count=transaction_count or 0,
        current_theses=current_theses or 0,
        linked_news=linked_news or 0,
        totals_by_currency=totals_by_currency(responses),
        positions=responses,
        recent_transactions=[transaction_response(item) for item in recent_transactions],
        disclaimer=INVESTMENT_DISCLAIMER,
    )


@router.get("/performance", response_model=InvestmentPerformanceResponse)
async def investment_performance(
    db: DatabaseSession,
) -> InvestmentPerformanceResponse:
    """投资表现：按币种累计投入成本序列 + 当前成本/市值。只读。"""
    user = await current_user(db)
    transactions = await db.scalars(
        select(InvestmentTransaction)
        .join(Asset, Asset.id == InvestmentTransaction.asset_id)
        .where(
            Asset.user_id == user.id,
            InvestmentTransaction.deleted_at.is_(None),
        )
        .order_by(
            InvestmentTransaction.transaction_date.asc(),
            InvestmentTransaction.created_at.asc(),
        )
    )

    cumulative: dict[str, float] = {}
    last_by_date: dict[str, dict[date, float]] = {}
    for txn in transactions.all():
        amount = float(txn.calculated_amount or 0)
        if txn.transaction_type in {"opening", "buy"}:
            cumulative[txn.currency] = cumulative.get(txn.currency, 0.0) + amount
        elif txn.transaction_type == "sell":
            cumulative[txn.currency] = cumulative.get(txn.currency, 0.0) - amount
        else:
            continue
        last_by_date.setdefault(txn.currency, {})[txn.transaction_date] = round(
            cumulative[txn.currency],
            2,
        )

    positions = await db.scalars(
        select(PortfolioPosition)
        .options(selectinload(PortfolioPosition.asset))
        .join(Asset, Asset.id == PortfolioPosition.asset_id)
        .where(
            Asset.user_id == user.id,
            PortfolioPosition.deleted_at.is_(None),
            PortfolioPosition.closed_on.is_(None),
        )
    )
    cost_by_currency: dict[str, float] = {}
    market_by_currency: dict[str, float] = {}
    for position in positions.all():
        currency = position.asset.currency
        cost_by_currency[currency] = cost_by_currency.get(currency, 0.0) + float(
            position.cost_basis or 0
        )
        if position.asset.latest_price is not None:
            market_by_currency[currency] = market_by_currency.get(currency, 0.0) + float(
                position.quantity * position.asset.latest_price
            )

    series = [
        CurrencyPerformanceSeries(
            currency=currency,
            points=[
                InvestmentPerformancePoint(date=day, cost=value)
                for day, value in sorted(last_by_date.get(currency, {}).items())
            ],
            current_cost_basis=round(cost_by_currency.get(currency, 0.0), 2),
            current_market_value=round(market_by_currency[currency], 2)
            if currency in market_by_currency
            else None,
        )
        for currency in sorted(set(last_by_date) | set(cost_by_currency))
    ]

    return InvestmentPerformanceResponse(
        series=series,
        disclaimer=INVESTMENT_DISCLAIMER,
    )


@router.get("/assets", response_model=list[AssetResponse])
async def list_assets(db: DatabaseSession) -> list[AssetResponse]:
    user = await current_user(db)
    assets = await db.scalars(
        select(Asset)
        .where(Asset.user_id == user.id, Asset.deleted_at.is_(None))
        .order_by(Asset.name.asc())
    )
    return [AssetResponse.model_validate(asset) for asset in assets]


@router.post(
    "/assets",
    response_model=AssetResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_asset(payload: AssetCreate, db: DatabaseSession) -> AssetResponse:
    user = await current_user(db)
    asset = await db.scalar(
        select(Asset).where(
            Asset.user_id == user.id,
            Asset.market == payload.market,
            Asset.symbol == payload.symbol,
        )
    )
    if asset is not None and asset.deleted_at is None:
        raise HTTPException(
            status_code=409,
            detail="This asset symbol already exists in the selected market",
        )
    if asset is None:
        asset = Asset(user_id=user.id)
        db.add(asset)
    asset.name = payload.name
    asset.symbol = payload.symbol
    asset.market = payload.market
    asset.asset_type = payload.asset_type
    asset.currency = payload.currency
    asset.latest_price = payload.latest_price
    asset.latest_price_date = payload.latest_price_date
    asset.notes = payload.notes
    asset.deleted_at = None
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="This asset symbol already exists in the selected market",
        ) from exc
    await db.refresh(asset)
    return AssetResponse.model_validate(asset)


@router.patch("/assets/{asset_id}", response_model=AssetResponse)
async def update_asset(
    asset_id: uuid.UUID,
    payload: AssetUpdate,
    db: DatabaseSession,
) -> AssetResponse:
    user = await current_user(db)
    asset = await owned_asset(db, asset_id, user.id)
    if payload.currency is not None and payload.currency != asset.currency:
        transaction_count = await db.scalar(
            select(func.count(InvestmentTransaction.id)).where(
                InvestmentTransaction.asset_id == asset.id,
                InvestmentTransaction.deleted_at.is_(None),
            )
        )
        if transaction_count:
            raise HTTPException(
                status_code=409,
                detail="Currency cannot change after transactions have been recorded",
            )
    for field in (
        "name",
        "symbol",
        "market",
        "asset_type",
        "currency",
        "notes",
    ):
        if field in payload.model_fields_set:
            setattr(asset, field, getattr(payload, field))
    if "latest_price" in payload.model_fields_set:
        asset.latest_price = payload.latest_price
        if payload.latest_price is None:
            asset.latest_price_date = None
        elif "latest_price_date" not in payload.model_fields_set:
            asset.latest_price_date = date.today()
    if "latest_price_date" in payload.model_fields_set and asset.latest_price is not None:
        asset.latest_price_date = payload.latest_price_date or date.today()
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="This asset symbol already exists in the selected market",
        ) from exc
    await db.refresh(asset)
    return AssetResponse.model_validate(asset)


@router.delete("/assets/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_asset(
    asset_id: uuid.UUID,
    db: DatabaseSession,
) -> Response:
    user = await current_user(db)
    asset = await owned_asset(db, asset_id, user.id)
    deleted_at = datetime.now(UTC)
    linked_news_ids = set(
        await db.scalars(
            select(NewsItemLink.news_item_id).where(
                NewsItemLink.user_id == user.id,
                NewsItemLink.link_type == "asset",
                NewsItemLink.linked_id == asset.id,
            )
        )
    )
    asset.deleted_at = deleted_at
    position = await db.scalar(
        select(PortfolioPosition).where(PortfolioPosition.asset_id == asset.id)
    )
    if position is not None:
        position.deleted_at = deleted_at
    for model in (InvestmentTransaction, InvestmentThesis, InvestmentReview):
        rows = await db.scalars(
            select(model).where(
                model.user_id == user.id,
                model.asset_id == asset.id,
                model.deleted_at.is_(None),
            )
        )
        for row in rows:
            row.deleted_at = deleted_at
            if isinstance(row, InvestmentThesis):
                row.is_current = False
    await db.execute(
        delete(NewsItemLink).where(
            NewsItemLink.user_id == user.id,
            NewsItemLink.link_type == "asset",
            NewsItemLink.linked_id == asset.id,
        )
    )
    await db.flush()
    for news_item_id in linked_news_ids:
        remaining = await db.scalar(
            select(func.count(NewsItemLink.id)).where(
                NewsItemLink.user_id == user.id,
                NewsItemLink.news_item_id == news_item_id,
                NewsItemLink.link_type == "asset",
            )
        )
        if not remaining:
            item = await db.get(NewsItem, news_item_id)
            if item is not None:
                item.portfolio_related = False
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/positions", response_model=list[PositionResponse])
async def list_positions(
    db: DatabaseSession,
    include_closed: bool = Query(default=True),
) -> list[PositionResponse]:
    user = await current_user(db)
    query = (
        select(PortfolioPosition)
        .join(Asset, Asset.id == PortfolioPosition.asset_id)
        .where(
            PortfolioPosition.user_id == user.id,
            PortfolioPosition.deleted_at.is_(None),
            Asset.deleted_at.is_(None),
        )
        .options(selectinload(PortfolioPosition.asset))
    )
    if not include_closed:
        query = query.where(PortfolioPosition.quantity > 0)
    positions = list(
        await db.scalars(
            query.order_by(PortfolioPosition.quantity.desc(), Asset.name.asc())
        )
    )
    counts = await related_news_counts(db, user.id)
    return [
        position_response(item, related_count=counts.get(item.asset_id, 0))
        for item in positions
    ]


@router.post(
    "/positions",
    response_model=PositionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_position(
    payload: PositionCreate,
    db: DatabaseSession,
) -> PositionResponse:
    user = await current_user(db)
    asset = await owned_asset(db, payload.asset_id, user.id)
    existing_transactions = await db.scalar(
        select(func.count(InvestmentTransaction.id)).where(
            InvestmentTransaction.user_id == user.id,
            InvestmentTransaction.asset_id == asset.id,
            InvestmentTransaction.deleted_at.is_(None),
        )
    )
    if existing_transactions:
        raise HTTPException(
            status_code=409,
            detail="This asset already has transactions; add a new transaction instead",
        )
    transaction = InvestmentTransaction(
        user_id=user.id,
        asset_id=asset.id,
        asset=asset,
        transaction_type="opening",
        transaction_date=payload.transaction_date,
        quantity=payload.quantity,
        unit_price=payload.average_cost,
        fees=payload.fees,
        currency=asset.currency,
        reason=payload.reason,
        notes="初始持仓",
        calculated_amount=Decimal("0"),
        realized_pnl=Decimal("0"),
        quantity_after=Decimal("0"),
        average_cost_after=Decimal("0"),
        cost_basis_after=Decimal("0"),
    )
    db.add(transaction)
    try:
        await db.flush()
        position = await recalculate_position(db, user.id, asset)
        position.target_allocation = payload.target_allocation
        position.risk_level = payload.risk_level
        await db.commit()
    except InvestmentCalculationError as exc:
        await db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    loaded = await load_position(db, position.id)
    return position_response(loaded)


@router.patch("/positions/{position_id}", response_model=PositionResponse)
async def update_position(
    position_id: uuid.UUID,
    payload: PositionUpdate,
    db: DatabaseSession,
) -> PositionResponse:
    user = await current_user(db)
    position = await owned_position(db, position_id, user.id)
    if "target_allocation" in payload.model_fields_set:
        position.target_allocation = payload.target_allocation
    if payload.risk_level is not None:
        position.risk_level = payload.risk_level
    await db.commit()
    loaded = await load_position(db, position.id)
    counts = await related_news_counts(db, user.id)
    return position_response(loaded, related_count=counts.get(position.asset_id, 0))


@router.get("/transactions", response_model=list[TransactionResponse])
async def list_transactions(
    db: DatabaseSession,
    asset_id: uuid.UUID | None = None,
    limit: int = Query(default=200, ge=1, le=500),
) -> list[TransactionResponse]:
    user = await current_user(db)
    query = (
        select(InvestmentTransaction)
        .join(Asset, Asset.id == InvestmentTransaction.asset_id)
        .where(
            InvestmentTransaction.user_id == user.id,
            InvestmentTransaction.deleted_at.is_(None),
            Asset.deleted_at.is_(None),
        )
        .options(selectinload(InvestmentTransaction.asset))
    )
    if asset_id is not None:
        query = query.where(InvestmentTransaction.asset_id == asset_id)
    transactions = await db.scalars(
        query.order_by(
            InvestmentTransaction.transaction_date.desc(),
            InvestmentTransaction.created_at.desc(),
        ).limit(limit)
    )
    return [transaction_response(item) for item in transactions]


@router.post(
    "/transactions",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_transaction(
    payload: TransactionCreate,
    db: DatabaseSession,
) -> TransactionResponse:
    user = await current_user(db)
    asset = await owned_asset(db, payload.asset_id, user.id)
    if payload.transaction_type == "opening":
        existing = await db.scalar(
            select(func.count(InvestmentTransaction.id)).where(
                InvestmentTransaction.asset_id == asset.id,
                InvestmentTransaction.deleted_at.is_(None),
            )
        )
        if existing:
            raise HTTPException(
                status_code=409,
                detail="Opening balance can only be the first transaction",
            )
    transaction = InvestmentTransaction(
        user_id=user.id,
        asset_id=asset.id,
        asset=asset,
        transaction_type=payload.transaction_type,
        transaction_date=payload.transaction_date,
        quantity=payload.quantity,
        unit_price=payload.unit_price,
        cash_amount=payload.cash_amount,
        fees=payload.fees,
        currency=asset.currency,
        reason=payload.reason,
        notes=payload.notes,
        calculated_amount=Decimal("0"),
        realized_pnl=Decimal("0"),
        quantity_after=Decimal("0"),
        average_cost_after=Decimal("0"),
        cost_basis_after=Decimal("0"),
    )
    db.add(transaction)
    try:
        await db.flush()
        await recalculate_position(db, user.id, asset)
        await db.commit()
    except InvestmentCalculationError as exc:
        await db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    loaded = await owned_transaction(db, transaction.id, user.id)
    return transaction_response(loaded)


@router.patch(
    "/transactions/{transaction_id}",
    response_model=TransactionResponse,
)
async def update_transaction(
    transaction_id: uuid.UUID,
    payload: TransactionUpdate,
    db: DatabaseSession,
) -> TransactionResponse:
    user = await current_user(db)
    transaction = await owned_transaction(db, transaction_id, user.id)
    for field in (
        "transaction_type",
        "transaction_date",
        "quantity",
        "unit_price",
        "cash_amount",
        "fees",
        "reason",
        "notes",
    ):
        if field in payload.model_fields_set:
            setattr(transaction, field, getattr(payload, field))
    validate_transaction_values(transaction)
    try:
        await db.flush()
        await recalculate_position(db, user.id, transaction.asset)
        await db.commit()
    except InvestmentCalculationError as exc:
        await db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    loaded = await owned_transaction(db, transaction.id, user.id)
    return transaction_response(loaded)


@router.delete(
    "/transactions/{transaction_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_transaction(
    transaction_id: uuid.UUID,
    db: DatabaseSession,
) -> Response:
    user = await current_user(db)
    transaction = await owned_transaction(db, transaction_id, user.id)
    transaction.deleted_at = datetime.now(UTC)
    try:
        await db.flush()
        await recalculate_position(db, user.id, transaction.asset)
        await db.commit()
    except InvestmentCalculationError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"Deleting this transaction would invalidate later history: {exc}",
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/theses", response_model=list[ThesisResponse])
async def list_theses(
    db: DatabaseSession,
    asset_id: uuid.UUID | None = None,
) -> list[ThesisResponse]:
    user = await current_user(db)
    query = (
        select(InvestmentThesis)
        .join(Asset, Asset.id == InvestmentThesis.asset_id)
        .where(
            InvestmentThesis.user_id == user.id,
            InvestmentThesis.deleted_at.is_(None),
            Asset.deleted_at.is_(None),
        )
        .options(selectinload(InvestmentThesis.asset))
    )
    if asset_id is not None:
        query = query.where(InvestmentThesis.asset_id == asset_id)
    theses = await db.scalars(
        query.order_by(
            InvestmentThesis.is_current.desc(),
            InvestmentThesis.created_at.desc(),
        )
    )
    return [thesis_response(item) for item in theses]


@router.post(
    "/theses",
    response_model=ThesisResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_thesis(
    payload: ThesisCreate,
    db: DatabaseSession,
) -> ThesisResponse:
    user = await current_user(db)
    asset = await owned_asset(db, payload.asset_id, user.id)
    current = await db.scalars(
        select(InvestmentThesis).where(
            InvestmentThesis.user_id == user.id,
            InvestmentThesis.asset_id == asset.id,
            InvestmentThesis.is_current.is_(True),
            InvestmentThesis.deleted_at.is_(None),
        )
    )
    for item in current:
        item.is_current = False
        if item.status in {"active", "changed"}:
            item.status = "superseded"
    thesis = InvestmentThesis(
        user_id=user.id,
        asset_id=asset.id,
        asset=asset,
        title=payload.title.strip(),
        original_reason=payload.original_reason.strip(),
        current_view=payload.current_view,
        key_assumptions=payload.key_assumptions,
        watch_events=payload.watch_events,
        invalidation_conditions=payload.invalidation_conditions,
        risk_level=payload.risk_level,
        status="active",
        is_current=True,
        cloud_allowed=payload.cloud_allowed,
    )
    db.add(thesis)
    await db.commit()
    loaded = await owned_thesis(db, thesis.id, user.id)
    return thesis_response(loaded)


@router.patch("/theses/{thesis_id}", response_model=ThesisResponse)
async def update_thesis(
    thesis_id: uuid.UUID,
    payload: ThesisUpdate,
    db: DatabaseSession,
) -> ThesisResponse:
    user = await current_user(db)
    thesis = await owned_thesis(db, thesis_id, user.id)
    for field in (
        "title",
        "current_view",
        "key_assumptions",
        "watch_events",
        "invalidation_conditions",
        "risk_level",
        "status",
        "cloud_allowed",
    ):
        if field in payload.model_fields_set:
            setattr(thesis, field, getattr(payload, field))
    if payload.status in {"invalidated", "closed", "superseded"}:
        thesis.is_current = False
    await db.commit()
    loaded = await owned_thesis(db, thesis.id, user.id)
    return thesis_response(loaded)


@router.delete("/theses/{thesis_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_thesis(
    thesis_id: uuid.UUID,
    db: DatabaseSession,
) -> Response:
    user = await current_user(db)
    thesis = await owned_thesis(db, thesis_id, user.id)
    thesis.deleted_at = datetime.now(UTC)
    thesis.is_current = False
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/reviews", response_model=list[ReviewResponse])
async def list_reviews(
    db: DatabaseSession,
    asset_id: uuid.UUID | None = None,
) -> list[ReviewResponse]:
    user = await current_user(db)
    query = (
        select(InvestmentReview)
        .join(Asset, Asset.id == InvestmentReview.asset_id)
        .where(
            InvestmentReview.user_id == user.id,
            InvestmentReview.deleted_at.is_(None),
            Asset.deleted_at.is_(None),
        )
        .options(selectinload(InvestmentReview.asset))
    )
    if asset_id is not None:
        query = query.where(InvestmentReview.asset_id == asset_id)
    reviews = await db.scalars(
        query.order_by(
            InvestmentReview.period_end.desc(),
            InvestmentReview.created_at.desc(),
        )
    )
    return [review_response(item) for item in reviews]


@router.post(
    "/reviews/generate",
    response_model=ReviewResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_review(
    payload: ReviewGenerateRequest,
    db: DatabaseSession,
) -> ReviewResponse:
    user = await current_user(db)
    asset = await owned_asset(db, payload.asset_id, user.id)
    review = await build_review(
        db,
        user_id=user.id,
        asset=asset,
        review_type=payload.review_type,
        period_start=payload.period_start,
        period_end=payload.period_end,
    )
    await db.commit()
    loaded = await owned_review(db, review.id, user.id)
    return review_response(loaded)


@router.patch("/reviews/{review_id}", response_model=ReviewResponse)
async def update_review(
    review_id: uuid.UUID,
    payload: ReviewUpdate,
    db: DatabaseSession,
) -> ReviewResponse:
    user = await current_user(db)
    review = await owned_review(db, review_id, user.id)
    for field in (
        "thesis_assessment",
        "summary",
        "risks",
        "questions",
        "user_note",
        "status",
    ):
        if field in payload.model_fields_set:
            setattr(review, field, getattr(payload, field))
    await db.commit()
    loaded = await owned_review(db, review.id, user.id)
    return review_response(loaded)


@router.delete("/reviews/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_review(
    review_id: uuid.UUID,
    db: DatabaseSession,
) -> Response:
    user = await current_user(db)
    review = await owned_review(db, review_id, user.id)
    review.deleted_at = datetime.now(UTC)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/assets/{asset_id}/news", response_model=list[RelatedNewsResponse])
async def list_asset_news(
    asset_id: uuid.UUID,
    db: DatabaseSession,
    candidates: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[RelatedNewsResponse]:
    user = await current_user(db)
    asset = await owned_asset(db, asset_id, user.id)
    links = list(
        await db.scalars(
            select(NewsItemLink).where(
                NewsItemLink.user_id == user.id,
                NewsItemLink.link_type == "asset",
                NewsItemLink.linked_id == asset.id,
            )
        )
    )
    link_by_item = {item.news_item_id: item for item in links}
    if candidates:
        query = select(NewsItem).where(
            NewsItem.user_id == user.id,
            NewsItem.deleted_at.is_(None),
            NewsItem.duplicate_of_id.is_(None),
            or_(
                NewsItem.investment_related.is_(True),
                NewsItem.category == "investment",
                NewsItem.title.ilike(f"%{asset.symbol}%"),
                NewsItem.title.ilike(f"%{asset.name}%"),
            ),
        )
    elif link_by_item:
        query = select(NewsItem).where(
            NewsItem.user_id == user.id,
            NewsItem.id.in_(link_by_item),
            NewsItem.deleted_at.is_(None),
        )
    else:
        return []
    items = await db.scalars(
        query.order_by(NewsItem.published_at.desc(), NewsItem.created_at.desc()).limit(
            limit
        )
    )
    return [
        RelatedNewsResponse(
            id=item.id,
            title=item.title,
            url=item.url,
            source_name=item.source_name,
            summary=item.summary,
            category=item.category,
            published_at=item.published_at,
            relationship_note=(
                link_by_item[item.id].relationship_note if item.id in link_by_item else None
            ),
            linked=item.id in link_by_item,
        )
        for item in items
    ]


@router.post(
    "/assets/{asset_id}/news/{news_item_id}",
    response_model=RelatedNewsResponse,
)
async def link_asset_news(
    asset_id: uuid.UUID,
    news_item_id: uuid.UUID,
    payload: NewsLinkCreate,
    db: DatabaseSession,
) -> RelatedNewsResponse:
    user = await current_user(db)
    asset = await owned_asset(db, asset_id, user.id)
    item = await db.scalar(
        select(NewsItem).where(
            NewsItem.id == news_item_id,
            NewsItem.user_id == user.id,
            NewsItem.deleted_at.is_(None),
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail="News item not found")
    link = await db.scalar(
        select(NewsItemLink).where(
            NewsItemLink.user_id == user.id,
            NewsItemLink.news_item_id == item.id,
            NewsItemLink.link_type == "asset",
            NewsItemLink.linked_id == asset.id,
        )
    )
    if link is None:
        link = NewsItemLink(
            user_id=user.id,
            news_item_id=item.id,
            link_type="asset",
            linked_id=asset.id,
            relationship_note=payload.relationship_note,
            created_at=datetime.now(UTC),
        )
        db.add(link)
    else:
        link.relationship_note = payload.relationship_note
    item.portfolio_related = True
    await db.commit()
    return RelatedNewsResponse(
        id=item.id,
        title=item.title,
        url=item.url,
        source_name=item.source_name,
        summary=item.summary,
        category=item.category,
        published_at=item.published_at,
        relationship_note=link.relationship_note,
        linked=True,
    )


@router.delete(
    "/assets/{asset_id}/news/{news_item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def unlink_asset_news(
    asset_id: uuid.UUID,
    news_item_id: uuid.UUID,
    db: DatabaseSession,
) -> Response:
    user = await current_user(db)
    await owned_asset(db, asset_id, user.id)
    link = await db.scalar(
        select(NewsItemLink).where(
            NewsItemLink.user_id == user.id,
            NewsItemLink.news_item_id == news_item_id,
            NewsItemLink.link_type == "asset",
            NewsItemLink.linked_id == asset_id,
        )
    )
    if link is None:
        raise HTTPException(status_code=404, detail="News link not found")
    await db.delete(link)
    await db.flush()
    remaining = await db.scalar(
        select(func.count(NewsItemLink.id)).where(
            NewsItemLink.user_id == user.id,
            NewsItemLink.news_item_id == news_item_id,
            NewsItemLink.link_type == "asset",
        )
    )
    item = await db.get(NewsItem, news_item_id)
    if item is not None and not remaining:
        item.portfolio_related = False
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
