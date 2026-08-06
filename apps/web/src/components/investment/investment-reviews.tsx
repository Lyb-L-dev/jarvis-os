import type {
  InvestmentAsset,
  InvestmentReview,
} from "@/lib/api";

import {
  assessmentLabels,
  dateLabel,
} from "@/components/investment/investment-utils";

export function InvestmentReviews({
  reviews,
  assets,
  busy,
  reviewAssetId,
  reviewType,
  onAssetChange,
  onTypeChange,
  onCreate,
  onConfirm,
}: {
  reviews: InvestmentReview[];
  assets: InvestmentAsset[];
  busy: boolean;
  reviewAssetId: string;
  reviewType: InvestmentReview["review_type"];
  onAssetChange: (assetId: string) => void;
  onTypeChange: (reviewType: InvestmentReview["review_type"]) => void;
  onCreate: () => void;
  onConfirm: (review: InvestmentReview) => void;
}) {
  return (
    <section className="investment-section">
      <div className="investment-section-head review-section-head">
        <div>
          <div className="eyebrow">FACT-BASED REVIEW</div>
          <h2>周度与月度复盘</h2>
        </div>
        <div>
          <select
            onChange={(event) => onAssetChange(event.target.value)}
            value={reviewAssetId}
          >
            {assets.map((asset) => (
              <option key={asset.id} value={asset.id}>
                {asset.name} · {asset.symbol}
              </option>
            ))}
          </select>
          <select
            onChange={(event) =>
              onTypeChange(
                event.target.value as InvestmentReview["review_type"],
              )
            }
            value={reviewType}
          >
            <option value="weekly">本周复盘</option>
            <option value="monthly">本月复盘</option>
            <option value="manual">今日复盘</option>
          </select>
          <button
            className="primary-button"
            disabled={busy || !reviewAssetId}
            onClick={() => void onCreate()}
            type="button"
          >
            生成事实草稿
          </button>
        </div>
      </div>
      {reviews.length === 0 ? (
        <div className="investment-empty compact">
          <strong>暂无投资复盘</strong>
          <p>系统只根据你的交易、手动价格、原始理由和关联情报生成事实草稿。</p>
        </div>
      ) : (
        <div className="review-list">
          {reviews.map((review) => (
            <article className="review-card" key={review.id}>
              <header>
                <div>
                  <span>
                    {review.asset.symbol} · {review.review_type}
                  </span>
                  <h3>
                    {dateLabel(review.period_start)} —{" "}
                    {dateLabel(review.period_end)}
                  </h3>
                </div>
                <i className={review.status === "confirmed" ? "confirmed" : ""}>
                  {review.status === "confirmed" ? "已确认" : "事实草稿"}
                </i>
              </header>
              <p>{review.summary}</p>
              <div className="review-columns">
                <section>
                  <strong>风险与失效条件</strong>
                  <ul>
                    {review.risks.length ? (
                      review.risks.map((item) => <li key={item}>{item}</li>)
                    ) : (
                      <li>本期未自动识别</li>
                    )}
                  </ul>
                </section>
                <section>
                  <strong>待确认问题</strong>
                  <ul>
                    {review.questions.length ? (
                      review.questions.map((item) => (
                        <li key={item}>{item}</li>
                      ))
                    ) : (
                      <li>暂无</li>
                    )}
                  </ul>
                </section>
              </div>
              {review.user_note ? (
                <blockquote>{review.user_note}</blockquote>
              ) : null}
              <footer>
                <span>
                  {assessmentLabels[review.thesis_assessment]} ·{" "}
                  {review.generated_by === "rules" ? "规则整理" : review.generated_by}
                </span>
                {review.status === "draft" ? (
                  <button
                    className="primary-button"
                    disabled={busy}
                    onClick={() => void onConfirm(review)}
                    type="button"
                  >
                    检查并确认
                  </button>
                ) : null}
              </footer>
              <small>{review.disclaimer}</small>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
