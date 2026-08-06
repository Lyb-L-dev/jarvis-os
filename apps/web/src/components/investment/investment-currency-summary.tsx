import type { InvestmentOverview } from "@/lib/api";

import {
  amount,
  numeric,
} from "@/components/investment/investment-utils";

export function InvestmentCurrencySummary({
  totals,
}: {
  totals: InvestmentOverview["totals_by_currency"];
}) {
  if (!totals.length) return null;
  return (
    <section className="currency-summary">
      {totals.map((total) => (
        <article key={total.currency}>
          <header>
            <strong>{total.currency}</strong>
            <span>
              {total.priced_positions}/{total.total_positions} 个持仓有价格
            </span>
          </header>
          <div>
            <span>
              成本 <b>{amount(total.cost_basis)}</b>
            </span>
            <span>
              手动市值 <b>{amount(total.market_value)}</b>
            </span>
            <span
              className={
                numeric(total.unrealized_pnl) &&
                Number(total.unrealized_pnl) < 0
                  ? "negative"
                  : "positive"
              }
            >
              浮动 <b>{amount(total.unrealized_pnl)}</b>
            </span>
            <span>
              已实现 <b>{amount(total.realized_pnl)}</b>
            </span>
            <span>
              分红 <b>{amount(total.dividend_income)}</b>
            </span>
          </div>
          {total.market_value === null || total.market_value === undefined ? (
            <p>部分持仓缺少手动价格，因此不展示合计市值和浮动收益。</p>
          ) : null}
        </article>
      ))}
    </section>
  );
}
