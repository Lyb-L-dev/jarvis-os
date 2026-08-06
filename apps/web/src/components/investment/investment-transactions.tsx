import type { InvestmentTransaction } from "@/lib/api";

import {
  amount,
  compactNumber,
  dateLabel,
  numeric,
  transactionLabels,
} from "@/components/investment/investment-utils";

export function InvestmentTransactions({
  transactions,
  busy,
  onNew,
  onEdit,
  onRemove,
}: {
  transactions: InvestmentTransaction[];
  busy: boolean;
  onNew: () => void;
  onEdit: (transaction: InvestmentTransaction) => void;
  onRemove: (transaction: InvestmentTransaction) => void;
}) {
  return (
    <section className="investment-section">
      <div className="investment-section-head">
        <div>
          <div className="eyebrow">LEDGER</div>
          <h2>交易流水</h2>
        </div>
        <button
          className="primary-button"
          onClick={onNew}
          type="button"
        >
          + 记录交易
        </button>
      </div>
      {transactions.length === 0 ? (
        <div className="investment-empty compact">
          <strong>暂无交易记录</strong>
          <p>建立初始持仓后，所有成本变化都会在这里保留。</p>
        </div>
      ) : (
        <div className="transaction-table-wrap">
          <table className="transaction-table">
            <thead>
              <tr>
                <th>日期 / 类型</th>
                <th>资产</th>
                <th>数量</th>
                <th>单价 / 金额</th>
                <th>手续费</th>
                <th>交易后数量</th>
                <th>交易后均价</th>
                <th>已实现</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {transactions.map((transaction) => (
                <tr key={transaction.id}>
                  <td>
                    <strong>
                      {transactionLabels[transaction.transaction_type]}
                    </strong>
                    <span>{dateLabel(transaction.transaction_date)}</span>
                  </td>
                  <td>
                    <b>{transaction.asset.symbol}</b>
                    <span>{transaction.asset.name}</span>
                  </td>
                  <td>{compactNumber(transaction.quantity)}</td>
                  <td>
                    {transaction.transaction_type === "dividend"
                      ? amount(transaction.cash_amount, transaction.currency)
                      : amount(transaction.unit_price, transaction.currency)}
                  </td>
                  <td>{amount(transaction.fees)}</td>
                  <td>{compactNumber(transaction.quantity_after)}</td>
                  <td>{amount(transaction.average_cost_after)}</td>
                  <td
                    className={
                      numeric(transaction.realized_pnl) &&
                      Number(transaction.realized_pnl) < 0
                        ? "negative"
                        : "positive"
                    }
                  >
                    {amount(transaction.realized_pnl)}
                  </td>
                  <td>
                    <button
                      onClick={() => onEdit(transaction)}
                      type="button"
                    >
                      编辑
                    </button>
                    <button
                      className="danger-text-button"
                      disabled={busy}
                      onClick={() => void onRemove(transaction)}
                      type="button"
                    >
                      删除
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
