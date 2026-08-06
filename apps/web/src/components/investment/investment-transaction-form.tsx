import type {
  InvestmentAsset,
  InvestmentTransactionType,
} from "@/lib/api";

import type { useInvestmentTransactionForm } from "@/components/investment/use-investment-transaction-form";

export function InvestmentTransactionForm({
  form,
  assets,
  busy,
}: {
  form: ReturnType<typeof useInvestmentTransactionForm>;
  assets: InvestmentAsset[];
  busy: boolean;
}) {
  const {
    editingTransactionId,
    setShowTransactionForm,
    txAssetId,
    setTxAssetId,
    txType,
    setTxType,
    txDate,
    setTxDate,
    txQuantity,
    setTxQuantity,
    txPrice,
    setTxPrice,
    txCash,
    setTxCash,
    txFees,
    setTxFees,
    txReason,
    setTxReason,
    txNotes,
    setTxNotes,
    resetTransactionForm,
    saveTransaction,
  } = form;

  return (
    <section className="panel investment-form-panel">
      <div className="investment-form-head">
        <div>
          <div className="eyebrow">TRANSACTION LEDGER</div>
          <h2>{editingTransactionId ? "修改历史交易" : "记录一笔交易"}</h2>
        </div>
        <span>保存后自动重算之后的全部成本</span>
      </div>
      <div className="investment-form-grid transaction-form-grid">
        <label>
          资产
          <select
            disabled={Boolean(editingTransactionId)}
            onChange={(event) => setTxAssetId(event.target.value)}
            value={txAssetId}
          >
            <option value="">选择资产</option>
            {assets.map((asset) => (
              <option key={asset.id} value={asset.id}>
                {asset.name} · {asset.symbol}
              </option>
            ))}
          </select>
        </label>
        <label>
          类型
          <select
            disabled={txType === "opening"}
            onChange={(event) =>
              setTxType(event.target.value as InvestmentTransactionType)
            }
            value={txType}
          >
            <option value="buy">买入记录</option>
            <option value="sell">卖出记录</option>
            <option value="dividend">分红</option>
            {txType === "opening" ? (
              <option value="opening">初始持仓</option>
            ) : null}
          </select>
        </label>
        <label>
          日期
          <input
            onChange={(event) => setTxDate(event.target.value)}
            type="date"
            value={txDate}
          />
        </label>
        {txType === "dividend" ? (
          <label>
            分红金额
            <input
              min="0"
              onChange={(event) => setTxCash(event.target.value)}
              step="any"
              type="number"
              value={txCash}
            />
          </label>
        ) : (
          <>
            <label>
              数量
              <input
                min="0"
                onChange={(event) => setTxQuantity(event.target.value)}
                step="any"
                type="number"
                value={txQuantity}
              />
            </label>
            <label>
              成交单价
              <input
                min="0"
                onChange={(event) => setTxPrice(event.target.value)}
                step="any"
                type="number"
                value={txPrice}
              />
            </label>
          </>
        )}
        <label>
          手续费
          <input
            min="0"
            onChange={(event) => setTxFees(event.target.value)}
            step="any"
            type="number"
            value={txFees}
          />
        </label>
        <label className="investment-wide-field">
          这笔交易当时的理由
          <textarea
            onChange={(event) => setTxReason(event.target.value)}
            placeholder="只记录事实和当时的真实判断。"
            rows={2}
            value={txReason}
          />
        </label>
        <label className="investment-wide-field">
          补充备注
          <textarea
            onChange={(event) => setTxNotes(event.target.value)}
            rows={2}
            value={txNotes}
          />
        </label>
      </div>
      <div className="investment-form-actions">
        <button
          className="primary-button"
          disabled={busy || !txAssetId}
          onClick={() => void saveTransaction()}
          type="button"
        >
          {busy ? "重算中…" : editingTransactionId ? "保存并重算" : "记录交易"}
        </button>
        <button
          className="quiet-button"
          onClick={() => {
            resetTransactionForm();
            setShowTransactionForm(false);
          }}
          type="button"
        >
          取消
        </button>
      </div>
    </section>
  );
}
