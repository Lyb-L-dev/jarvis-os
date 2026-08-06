import type {
  EnglishReview,
  EnglishReviewResult,
} from "@/lib/api";

import {
  formatDateTime,
  reviewButtons,
} from "@/components/english/english-utils";

export function EnglishReviewView({
  dueReviews,
  upcomingReviews,
  busy,
  reviewAnswers,
  setReviewAnswers,
  revealedReviews,
  onReveal,
  onRate,
  onOpenMistakes,
}: {
  dueReviews: EnglishReview[];
  upcomingReviews: EnglishReview[];
  busy: string | null;
  reviewAnswers: Record<string, string>;
  setReviewAnswers: (updater: (current: Record<string, string>) => Record<string, string>) => void;
  revealedReviews: Set<string>;
  onReveal: (reviewId: string) => void;
  onRate: (review: EnglishReview, result: EnglishReviewResult) => void;
  onOpenMistakes: () => void;
}) {
  return (
    <section className="english-review-view">
      <div className="english-view-toolbar">
        <div>
          <span>SPACED REVIEW</span>
          <h2>今日复习</h2>
          <p>高频、最近重复的错误优先。先自己改写，再核对答案。</p>
        </div>
        <div className="english-reminder-badge">
          <i />
          已接入桌面与语音提醒
        </div>
      </div>

      {dueReviews.length > 0 ? (
        <div className="english-review-list">
          {dueReviews.map((review, index) => {
            const revealed = revealedReviews.has(review.id);
            return (
              <article className="english-review-card" key={review.id}>
                <header>
                  <span>REVIEW {String(index + 1).padStart(2, "0")}</span>
                  <div>
                    <small>{review.mistake.category}</small>
                    <strong>出现 {review.mistake.occurrence_count} 次</strong>
                  </div>
                </header>
                <h3>{review.prompt}</h3>
                <textarea
                  disabled={revealed}
                  onChange={(event) =>
                    setReviewAnswers((current) => ({
                      ...current,
                      [review.id]: event.target.value,
                    }))
                  }
                  placeholder="在这里写出你认为正确的句子…"
                  value={reviewAnswers[review.id] || ""}
                />
                {!revealed ? (
                  <button
                    className="primary-button review-reveal-button"
                    onClick={() => onReveal(review.id)}
                    type="button"
                  >
                    核对答案
                  </button>
                ) : (
                  <div className="english-review-answer">
                    <span>参考表达</span>
                    <strong>{review.expected_answer}</strong>
                    <p>{review.mistake.explanation}</p>
                    <small>你记得怎么样？</small>
                    <div className="english-review-ratings">
                      {reviewButtons.map((item) => (
                        <button
                          className={item.className || ""}
                          disabled={busy === `review-${review.id}`}
                          key={item.value}
                          onClick={() => void onRate(review, item.value)}
                          type="button"
                        >
                          {item.label}
                        </button>
                      ))}
                    </div>
                    <button
                      className="review-dispute-button"
                      disabled={busy === `review-${review.id}`}
                      onClick={() =>
                        void onRate(review, "incorrect_explanation")
                      }
                      type="button"
                    >
                      这条解释不正确，暂停复习
                    </button>
                  </div>
                )}
              </article>
            );
          })}
        </div>
      ) : (
        <div className="english-large-empty review-empty">
          <div>✓</div>
          <strong>今天的到期复习已清空</strong>
          <p>
            {upcomingReviews.length
              ? `下一次安排在 ${formatDateTime(upcomingReviews[0].scheduled_for)}。`
              : "确认一条错题后，首次复习会自动安排在明晚 19:00。"}
          </p>
          <button onClick={onOpenMistakes} type="button">
            去错题本看看
          </button>
        </div>
      )}

      {upcomingReviews.length > 0 && (
        <div className="english-upcoming">
          <div>
            <span>UPCOMING</span>
            <h3>接下来的复习</h3>
          </div>
          <div className="english-upcoming-list">
            {upcomingReviews.slice(0, 8).map((review) => (
              <article key={review.id}>
                <time>{formatDateTime(review.scheduled_for)}</time>
                <p>{review.mistake.original_text}</p>
                <span>
                  {review.mistake.status === "mastered"
                    ? "低频巩固"
                    : `间隔 ${review.mistake.interval_days} 天`}
                </span>
              </article>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
