import type {
  InvestmentAsset,
  InvestmentRisk,
  InvestmentThesis,
} from "@/lib/api";

import { riskLabels } from "@/components/investment/investment-utils";
import type { useInvestmentThesisForm } from "@/components/investment/use-investment-thesis-form";

export function InvestmentTheses({
  theses,
  assets,
  busy,
  form,
}: {
  theses: InvestmentThesis[];
  assets: InvestmentAsset[];
  busy: boolean;
  form: ReturnType<typeof useInvestmentThesisForm>;
}) {
  const {
    showThesisForm,
    setShowThesisForm,
    thesisAssetId,
    setThesisAssetId,
    thesisTitle,
    setThesisTitle,
    originalReason,
    setOriginalReason,
    currentView,
    setCurrentView,
    assumptions,
    setAssumptions,
    watchEvents,
    setWatchEvents,
    invalidations,
    setInvalidations,
    thesisRisk,
    setThesisRisk,
    thesisCloud,
    setThesisCloud,
    saveThesis,
    changeThesis,
  } = form;

  return (
    <section className="investment-section">
      <div className="investment-section-head">
        <div>
          <div className="eyebrow">INVESTMENT THESES</div>
          <h2>投资理由与失效条件</h2>
        </div>
        <button
          className="primary-button"
          onClick={() => setShowThesisForm((current) => !current)}
          type="button"
        >
          + 记录新理由
        </button>
      </div>
      {showThesisForm ? (
        <div className="panel investment-form-panel thesis-form">
          <div className="investment-form-grid">
            <label>
              资产
              <select
                onChange={(event) => setThesisAssetId(event.target.value)}
                value={thesisAssetId}
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
              标题
              <input
                onChange={(event) => setThesisTitle(event.target.value)}
                placeholder="例如：2026 年初始投资假设"
                value={thesisTitle}
              />
            </label>
            <label>
              风险等级
              <select
                onChange={(event) =>
                  setThesisRisk(event.target.value as InvestmentRisk)
                }
                value={thesisRisk}
              >
                {Object.entries(riskLabels).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <label className="investment-wide-field">
              原始投资理由
              <textarea
                onChange={(event) => setOriginalReason(event.target.value)}
                placeholder="保存后不会被后续版本覆盖。"
                rows={4}
                value={originalReason}
              />
            </label>
            <label className="investment-wide-field">
              当前看法
              <textarea
                onChange={(event) => setCurrentView(event.target.value)}
                rows={3}
                value={currentView}
              />
            </label>
            <label>
              关键假设（每行一条）
              <textarea
                onChange={(event) => setAssumptions(event.target.value)}
                rows={4}
                value={assumptions}
              />
            </label>
            <label>
              关注事件（每行一条）
              <textarea
                onChange={(event) => setWatchEvents(event.target.value)}
                rows={4}
                value={watchEvents}
              />
            </label>
            <label>
              失效条件（每行一条）
              <textarea
                onChange={(event) => setInvalidations(event.target.value)}
                rows={4}
                value={invalidations}
              />
            </label>
          </div>
          <label className="investment-cloud-control">
            <input
              checked={thesisCloud}
              onChange={(event) => setThesisCloud(event.target.checked)}
              type="checkbox"
            />
            允许相关分析把这份理由发送给云端模型
          </label>
          <div className="investment-form-actions">
            <button
              className="primary-button"
              disabled={
                busy ||
                !thesisAssetId ||
                !thesisTitle.trim() ||
                !originalReason.trim()
              }
              onClick={() => void saveThesis()}
              type="button"
            >
              保存新版本
            </button>
            <button
              className="quiet-button"
              onClick={() => setShowThesisForm(false)}
              type="button"
            >
              取消
            </button>
          </div>
        </div>
      ) : null}
      {theses.length === 0 ? (
        <div className="investment-empty compact">
          <strong>还没有完整投资理由</strong>
          <p>建议记录事实依据、关键假设、关注事件和明确的失效条件。</p>
        </div>
      ) : (
        <div className="thesis-list">
          {theses.map((thesis) => (
            <article
              className={`thesis-card ${thesis.is_current ? "current" : ""}`}
              key={thesis.id}
            >
              <header>
                <div>
                  <span>
                    {thesis.asset.symbol} ·{" "}
                    {thesis.is_current ? "当前版本" : "历史版本"}
                  </span>
                  <h3>{thesis.title}</h3>
                </div>
                <div>
                  <i>{riskLabels[thesis.risk_level]}风险</i>
                  <i>{thesis.cloud_allowed ? "云端可用" : "仅本机"}</i>
                </div>
              </header>
              <section>
                <strong>原始投资理由</strong>
                <p>{thesis.original_reason}</p>
              </section>
              {thesis.current_view ? (
                <section>
                  <strong>当前看法</strong>
                  <p>{thesis.current_view}</p>
                </section>
              ) : null}
              <div className="thesis-columns">
                <div>
                  <strong>关键假设</strong>
                  <ul>
                    {thesis.key_assumptions.length ? (
                      thesis.key_assumptions.map((item) => (
                        <li key={item}>{item}</li>
                      ))
                    ) : (
                      <li>未记录</li>
                    )}
                  </ul>
                </div>
                <div>
                  <strong>关注事件</strong>
                  <ul>
                    {thesis.watch_events.length ? (
                      thesis.watch_events.map((item) => (
                        <li key={item}>{item}</li>
                      ))
                    ) : (
                      <li>未记录</li>
                    )}
                  </ul>
                </div>
                <div>
                  <strong>失效条件</strong>
                  <ul>
                    {thesis.invalidation_conditions.length ? (
                      thesis.invalidation_conditions.map((item) => (
                        <li key={item}>{item}</li>
                      ))
                    ) : (
                      <li>未记录</li>
                    )}
                  </ul>
                </div>
              </div>
              <footer>
                <span>
                  {new Date(thesis.created_at).toLocaleDateString("zh-CN")} ·{" "}
                  {thesis.status}
                </span>
                <div>
                  <button
                    disabled={busy}
                    onClick={() => void changeThesis(thesis, "cloud")}
                    type="button"
                  >
                    {thesis.cloud_allowed ? "改为仅本机" : "允许云端"}
                  </button>
                  {thesis.is_current ? (
                    <>
                      <button
                        disabled={busy}
                        onClick={() =>
                          void changeThesis(thesis, "invalidated")
                        }
                        type="button"
                      >
                        标记失效
                      </button>
                      <button
                        disabled={busy}
                        onClick={() => void changeThesis(thesis, "closed")}
                        type="button"
                      >
                        关闭
                      </button>
                    </>
                  ) : null}
                </div>
              </footer>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
