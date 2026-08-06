import type {
  InvestmentAsset,
  PortfolioPosition,
} from "@/lib/api";

import {
  amount,
  compactNumber,
  dateLabel,
  numeric,
  riskLabels,
} from "@/components/investment/investment-utils";

export function InvestmentPositions({
  positions,
  unpositionedAssets,
  busy,
  onEditPosition,
  onRemoveAsset,
  onRecordFirstBuy,
  onAddFirstAsset,
}: {
  positions: PortfolioPosition[];
  unpositionedAssets: InvestmentAsset[];
  busy: boolean;
  onEditPosition: (position: PortfolioPosition) => void;
  onRemoveAsset: (asset: InvestmentAsset) => void;
  onRecordFirstBuy: (asset: InvestmentAsset) => void;
  onAddFirstAsset: () => void;
}) {
  return (
    <section className="investment-section">
      <div className="investment-section-head">
        <div>
          <div className="eyebrow">POSITIONS</div>
          <h2>持仓与手动估值</h2>
        </div>
        <span>不同币种不会被直接相加</span>
      </div>
      {positions.length === 0 && unpositionedAssets.length === 0 ? (
        <div className="investment-empty">
          <div>◇</div>
          <strong>还没有资产和持仓</strong>
          <p>先添加一个资产，可选择同时录入初始数量、平均成本和原始理由。</p>
          <button
            className="primary-button"
            onClick={onAddFirstAsset}
            type="button"
          >
            添加第一个资产
          </button>
        </div>
      ) : (
        <div className="position-grid">
          {positions.map((position) => {
            const pnl = numeric(position.unrealized_pnl);
            return (
              <article className="position-card" key={position.id}>
                <header>
                  <div>
                    <span>{position.asset.symbol}</span>
                    <h3>{position.asset.name}</h3>
                    <small>
                      {position.asset.market} · {position.asset.currency}
                    </small>
                  </div>
                  <i className={`risk-${position.risk_level}`}>
                    {riskLabels[position.risk_level]}风险
                  </i>
                </header>
                <div className="position-main-value">
                  <span>手动市值</span>
                  <strong>
                    {amount(position.market_value, position.asset.currency)}
                  </strong>
                  {position.latest_price_missing ? (
                    <small>未录入最新价格，不计算浮动收益</small>
                  ) : (
                    <small>
                      价格 {amount(position.asset.latest_price)} ·{" "}
                      {dateLabel(position.asset.latest_price_date)}
                    </small>
                  )}
                </div>
                <div className="position-metrics">
                  <span>
                    数量 <b>{compactNumber(position.quantity)}</b>
                  </span>
                  <span>
                    平均成本 <b>{amount(position.average_cost)}</b>
                  </span>
                  <span>
                    成本合计 <b>{amount(position.cost_basis)}</b>
                  </span>
                  <span className={pnl !== null && pnl < 0 ? "negative" : "positive"}>
                    浮动{" "}
                    <b>
                      {amount(position.unrealized_pnl)}
                      {position.unrealized_pnl_percent !== null &&
                      position.unrealized_pnl_percent !== undefined
                        ? ` / ${Number(position.unrealized_pnl_percent).toFixed(2)}%`
                        : ""}
                    </b>
                  </span>
                  <span>
                    已实现 <b>{amount(position.realized_pnl)}</b>
                  </span>
                  <span>
                    分红 <b>{amount(position.dividend_income)}</b>
                  </span>
                </div>
                <footer>
                  <span>
                    目标仓位{" "}
                    {position.target_allocation !== null &&
                    position.target_allocation !== undefined
                      ? `${Number(position.target_allocation)}%`
                      : "未设置"}
                  </span>
                  <span>{position.related_news_count} 条关联情报</span>
                  <div>
                    <button onClick={() => onEditPosition(position)} type="button">
                      编辑 / 更新价格
                    </button>
                    <button
                      className="danger-text-button"
                      disabled={busy}
                      onClick={() => void onRemoveAsset(position.asset)}
                      type="button"
                    >
                      移除
                    </button>
                  </div>
                </footer>
              </article>
            );
          })}
          {unpositionedAssets.map((asset) => (
            <article className="position-card asset-only-card" key={asset.id}>
              <header>
                <div>
                  <span>{asset.symbol}</span>
                  <h3>{asset.name}</h3>
                  <small>
                    {asset.market} · 尚未建仓
                  </small>
                </div>
              </header>
              <p>资产档案已经保存，但还没有初始持仓或交易记录。</p>
              <footer>
                <button onClick={() => onRecordFirstBuy(asset)} type="button">
                  记录第一笔买入
                </button>
                <button
                  className="danger-text-button"
                  onClick={() => void onRemoveAsset(asset)}
                  type="button"
                >
                  移除
                </button>
              </footer>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
