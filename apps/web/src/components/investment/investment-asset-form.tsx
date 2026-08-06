import type {
  InvestmentAssetType,
  InvestmentRisk,
  PortfolioPosition,
} from "@/lib/api";

import {
  assetTypeOptions,
  riskLabels,
} from "@/components/investment/investment-utils";
import type { useInvestmentAssetForm } from "@/components/investment/use-investment-asset-form";

export function InvestmentAssetForm({
  form,
  positionByAsset,
  busy,
}: {
  form: ReturnType<typeof useInvestmentAssetForm>;
  positionByAsset: Map<string, PortfolioPosition>;
  busy: boolean;
}) {
  const {
    editingAssetId,
    setShowAssetForm,
    assetName,
    setAssetName,
    assetSymbol,
    setAssetSymbol,
    assetMarket,
    setAssetMarket,
    assetType,
    setAssetType,
    assetCurrency,
    setAssetCurrency,
    assetPrice,
    setAssetPrice,
    assetPriceDate,
    setAssetPriceDate,
    assetNotes,
    setAssetNotes,
    initialQuantity,
    setInitialQuantity,
    initialCost,
    setInitialCost,
    initialFees,
    setInitialFees,
    initialDate,
    setInitialDate,
    initialReason,
    setInitialReason,
    positionRisk,
    setPositionRisk,
    targetAllocation,
    setTargetAllocation,
    resetAssetForm,
    saveAsset,
  } = form;

  return (
    <section className="panel investment-form-panel">
      <div className="investment-form-head">
        <div>
          <div className="eyebrow">ASSET & POSITION</div>
          <h2>{editingAssetId ? "更新资产与持仓设置" : "建立资产档案"}</h2>
        </div>
        <button
          className="quiet-button"
          onClick={() => setShowAssetForm(false)}
          type="button"
        >
          收起
        </button>
      </div>
      <div className="investment-form-grid asset-form-grid">
        <label>
          资产名称
          <input
            onChange={(event) => setAssetName(event.target.value)}
            placeholder="例如：沪深300 ETF"
            value={assetName}
          />
        </label>
        <label>
          资产代码
          <input
            onChange={(event) => setAssetSymbol(event.target.value)}
            placeholder="510300"
            value={assetSymbol}
          />
        </label>
        <label>
          市场
          <input
            onChange={(event) => setAssetMarket(event.target.value)}
            placeholder="SSE / NASDAQ"
            value={assetMarket}
          />
        </label>
        <label>
          类型
          <select
            onChange={(event) =>
              setAssetType(event.target.value as InvestmentAssetType)
            }
            value={assetType}
          >
            {assetTypeOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          币种
          <input
            disabled={Boolean(editingAssetId && positionByAsset.get(editingAssetId))}
            maxLength={8}
            onChange={(event) =>
              setAssetCurrency(event.target.value.toUpperCase())
            }
            value={assetCurrency}
          />
        </label>
        <label>
          手动最新价格
          <input
            min="0"
            onChange={(event) => setAssetPrice(event.target.value)}
            placeholder="未填写就不计算市值"
            step="any"
            type="number"
            value={assetPrice}
          />
        </label>
        <label>
          价格日期
          <input
            disabled={!assetPrice}
            onChange={(event) => setAssetPriceDate(event.target.value)}
            type="date"
            value={assetPriceDate}
          />
        </label>
        <label>
          风险等级
          <select
            onChange={(event) =>
              setPositionRisk(event.target.value as InvestmentRisk)
            }
            value={positionRisk}
          >
            {Object.entries(riskLabels).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label>
          目标仓位 %
          <input
            max="100"
            min="0"
            onChange={(event) => setTargetAllocation(event.target.value)}
            step="0.1"
            type="number"
            value={targetAllocation}
          />
        </label>
        <label className="investment-wide-field">
          备注
          <textarea
            onChange={(event) => setAssetNotes(event.target.value)}
            placeholder="账户名称等身份信息不要写入这里。"
            rows={2}
            value={assetNotes}
          />
        </label>
      </div>
      {!editingAssetId ? (
        <div className="initial-position-box">
          <div>
            <strong>可选：同时录入初始持仓</strong>
            <span>系统会生成一笔“初始持仓”交易，之后所有成本都从它重算。</span>
          </div>
          <div className="investment-form-grid">
            <label>
              持仓数量
              <input
                min="0"
                onChange={(event) => setInitialQuantity(event.target.value)}
                step="any"
                type="number"
                value={initialQuantity}
              />
            </label>
            <label>
              平均成本
              <input
                min="0"
                onChange={(event) => setInitialCost(event.target.value)}
                step="any"
                type="number"
                value={initialCost}
              />
            </label>
            <label>
              手续费
              <input
                min="0"
                onChange={(event) => setInitialFees(event.target.value)}
                step="any"
                type="number"
                value={initialFees}
              />
            </label>
            <label>
              建仓日期
              <input
                onChange={(event) => setInitialDate(event.target.value)}
                type="date"
                value={initialDate}
              />
            </label>
            <label className="investment-wide-field">
              当时的原始理由
              <textarea
                onChange={(event) => setInitialReason(event.target.value)}
                placeholder="写下当时真实的事实、判断和目标，避免事后改写记忆。"
                rows={2}
                value={initialReason}
              />
            </label>
          </div>
        </div>
      ) : null}
      <div className="investment-form-actions">
        <button
          className="primary-button"
          disabled={
            busy ||
            !assetName.trim() ||
            !assetSymbol.trim() ||
            !assetMarket.trim()
          }
          onClick={() => void saveAsset()}
          type="button"
        >
          {busy ? "保存中…" : editingAssetId ? "保存修改" : "保存资产"}
        </button>
        <button
          className="quiet-button"
          onClick={() => {
            resetAssetForm();
            setShowAssetForm(false);
          }}
          type="button"
        >
          取消
        </button>
      </div>
    </section>
  );
}
