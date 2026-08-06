import {
  generateWeeklyReview,
  updateWeeklyReview,
  type WeeklyReview,
} from "@/lib/api";

import { formatDate } from "@/lib/utils";

import { formatMinutes } from "@/components/growth/growth-utils";

export function GrowthReviewView({
  review,
  busy,
  reviewNote,
  setReviewNote,
  doAction,
}: {
  review: WeeklyReview | null;
  busy: string | null;
  reviewNote: string;
  setReviewNote: (value: string) => void;
  doAction: (
    key: string,
    action: () => Promise<unknown>,
    success: string,
  ) => void;
}) {
  return (
    <section className="growth-review-view">
      <div className="growth-review-toolbar">
        <div>
          <div className="eyebrow">REAL DATA REVIEW</div>
          <h2>本周执行复盘</h2>
          <p>所有数字都来自已确认的任务日期、完成状态和计时事件。</p>
        </div>
        <button
          className="primary-button"
          disabled={busy === "review"}
          onClick={() =>
            void doAction(
              "review",
              () => generateWeeklyReview(),
              "本周复盘已按最新真实记录重新计算。",
            )
          }
          type="button"
        >
          {review ? "重新计算" : "生成本周复盘"}
        </button>
      </div>

      {review ? (
        <>
          <div className="growth-review-stats">
            <article>
              <span>计划任务</span>
              <strong>{review.snapshot.planned_tasks ?? 0}</strong>
            </article>
            <article>
              <span>完成任务</span>
              <strong>{review.snapshot.completed_tasks ?? 0}</strong>
            </article>
            <article>
              <span>完成率</span>
              <strong>{review.snapshot.completion_rate ?? 0}%</strong>
            </article>
            <article>
              <span>实际投入</span>
              <strong>
                {formatMinutes(review.snapshot.actual_minutes ?? 0)}
              </strong>
            </article>
          </div>
          <article className="panel growth-review-card">
            <div className="growth-section-head">
              <div>
                <div className="eyebrow">WEEK SUMMARY</div>
                <h2>
                  {formatDate(review.week_start)} —{" "}
                  {formatDate(review.week_end)}
                </h2>
              </div>
              <span>
                {review.status === "confirmed" ? "已确认" : "待确认"}
              </span>
            </div>
            <p className="growth-review-summary">{review.summary}</p>
            {(review.snapshot.blockers?.length ?? 0) > 0 ? (
              <div className="growth-review-blockers">
                <strong>未完成与阻塞</strong>
                {review.snapshot.blockers?.map((item) => (
                  <p key={`${item.task}-${item.reason}`}>
                    <span>{item.task}</span>
                    {item.reason}
                  </p>
                ))}
              </div>
            ) : null}
            <label className="growth-review-note">
              我的复盘记录
              <textarea
                onChange={(event) => setReviewNote(event.target.value)}
                placeholder="本周做得好的地方、困难，以及下周需要调整的重点"
                rows={5}
                value={reviewNote}
              />
            </label>
            <div className="growth-review-actions">
              <button
                onClick={() =>
                  void doAction(
                    review.id,
                    () =>
                      updateWeeklyReview(review.id, {
                        user_note: reviewNote,
                      }),
                    "复盘记录已保存。",
                  )
                }
                type="button"
              >
                保存记录
              </button>
              <button
                className="primary-button"
                onClick={() =>
                  void doAction(
                    review.id,
                    () =>
                      updateWeeklyReview(review.id, {
                        user_note: reviewNote,
                        status: "confirmed",
                      }),
                    "本周复盘已确认。",
                  )
                }
                type="button"
              >
                确认本周复盘
              </button>
            </div>
          </article>
        </>
      ) : (
        <div className="growth-large-empty">
          <strong>本周还没有复盘</strong>
          <p>完成或暂停任务后，在这里生成基于真实记录的周复盘。</p>
        </div>
      )}
    </section>
  );
}
