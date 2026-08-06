import type { EnglishMistake, EnglishMistakeStatus } from "@/lib/api";

import {
  formatDateTime,
  statusLabels,
} from "@/components/english/english-utils";

export function EnglishMistakeBook({
  mistakes,
  filteredMistakes,
  busy,
  mistakeQuery,
  setMistakeQuery,
  mistakeStatus,
  setMistakeStatus,
  editingMistakeId,
  setEditingMistakeId,
  editCorrection,
  setEditCorrection,
  editExplanation,
  setEditExplanation,
  onBeginEdit,
  onSaveMistake,
  onConfirm,
  onChangeStatus,
  onRemove,
  onStartPractice,
}: {
  mistakes: EnglishMistake[];
  filteredMistakes: EnglishMistake[];
  busy: string | null;
  mistakeQuery: string;
  setMistakeQuery: (value: string) => void;
  mistakeStatus: EnglishMistakeStatus | "all";
  setMistakeStatus: (value: EnglishMistakeStatus | "all") => void;
  editingMistakeId: string | null;
  setEditingMistakeId: (value: string | null) => void;
  editCorrection: string;
  setEditCorrection: (value: string) => void;
  editExplanation: string;
  setEditExplanation: (value: string) => void;
  onBeginEdit: (mistake: EnglishMistake) => void;
  onSaveMistake: (mistake: EnglishMistake) => void;
  onConfirm: (mistake: EnglishMistake) => void;
  onChangeStatus: (
    mistake: EnglishMistake,
    action: "reject" | "master" | "dispute",
  ) => void;
  onRemove: (mistake: EnglishMistake) => void;
  onStartPractice: () => void;
}) {
  return (
    <section className="english-mistakes-view">
      <div className="english-view-toolbar">
        <div>
          <span>MISTAKE BOOK</span>
          <h2>错题本</h2>
          <p>同类错误会自动合并并累计次数，只有你确认后才会进入复习。</p>
        </div>
        <div className="english-mistake-filters">
          <input
            onChange={(event) => setMistakeQuery(event.target.value)}
            placeholder="搜索原句、改写或解释…"
            value={mistakeQuery}
          />
          <select
            onChange={(event) =>
              setMistakeStatus(
                event.target.value as EnglishMistakeStatus | "all",
              )
            }
            value={mistakeStatus}
          >
            <option value="all">全部状态</option>
            <option value="pending">待确认</option>
            <option value="learning">学习中</option>
            <option value="mastered">已掌握</option>
            <option value="disputed">解释待修正</option>
            <option value="rejected">已忽略</option>
          </select>
        </div>
      </div>

      <div className="english-mistake-list">
        {filteredMistakes.map((mistake) => (
          <article
            className={`english-mistake-card mistake-${mistake.status}`}
            key={mistake.id}
          >
            <header>
              <div>
                <span className="mistake-category">{mistake.category}</span>
                <span className={`mistake-status status-${mistake.status}`}>
                  {statusLabels[mistake.status]}
                </span>
                <small>{mistake.cefr}</small>
              </div>
              <strong>出现 {mistake.occurrence_count} 次</strong>
            </header>

            {editingMistakeId === mistake.id ? (
              <div className="english-mistake-editor">
                <label>
                  <span>正确表达</span>
                  <textarea
                    onChange={(event) =>
                      setEditCorrection(event.target.value)
                    }
                    value={editCorrection}
                  />
                </label>
                <label>
                  <span>解释</span>
                  <textarea
                    onChange={(event) =>
                      setEditExplanation(event.target.value)
                    }
                    value={editExplanation}
                  />
                </label>
                <div>
                  <button
                    onClick={() => setEditingMistakeId(null)}
                    type="button"
                  >
                    取消
                  </button>
                  <button
                    disabled={busy === `edit-mistake-${mistake.id}`}
                    onClick={() => void onSaveMistake(mistake)}
                    type="button"
                  >
                    保存修改
                  </button>
                </div>
              </div>
            ) : (
              <>
                <div className="english-correction-pair">
                  <div>
                    <span>你的原句</span>
                    <p>{mistake.original_text}</p>
                  </div>
                  <div>
                    <span>更自然的表达</span>
                    <p>{mistake.corrected_text}</p>
                  </div>
                </div>
                <p className="english-mistake-explanation">
                  {mistake.explanation}
                </p>
                <div className="english-mistake-meta">
                  <span>最近出现：{formatDateTime(mistake.last_seen_at)}</span>
                  <span>
                    下次复习：{formatDateTime(mistake.next_review_at)}
                  </span>
                </div>
              </>
            )}

            <footer>
              <button onClick={() => onBeginEdit(mistake)} type="button">
                修改纠错
              </button>
              {mistake.status === "pending" && (
                <>
                  <button
                    onClick={() =>
                      void onChangeStatus(mistake, "reject")
                    }
                    type="button"
                  >
                    忽略
                  </button>
                  <button
                    className="mistake-primary-action"
                    onClick={() => void onConfirm(mistake)}
                    type="button"
                  >
                    确认并加入复习
                  </button>
                </>
              )}
              {mistake.status === "disputed" && (
                <button
                  className="mistake-primary-action"
                  onClick={() => void onConfirm(mistake)}
                  type="button"
                >
                  修正后重新确认
                </button>
              )}
              {mistake.status === "learning" && (
                <>
                  <button
                    onClick={() =>
                      void onChangeStatus(mistake, "dispute")
                    }
                    type="button"
                  >
                    解释有误
                  </button>
                  <button
                    className="mistake-primary-action"
                    onClick={() =>
                      void onChangeStatus(mistake, "master")
                    }
                    type="button"
                  >
                    标记掌握
                  </button>
                </>
              )}
              {mistake.status === "rejected" && (
                <button
                  className="mistake-primary-action"
                  onClick={() => void onConfirm(mistake)}
                  type="button"
                >
                  恢复并加入复习
                </button>
              )}
              <button
                className="mistake-delete-action"
                onClick={() => void onRemove(mistake)}
                type="button"
              >
                删除
              </button>
            </footer>
          </article>
        ))}
        {filteredMistakes.length === 0 && (
          <div className="english-large-empty">
            <div>Aa</div>
            <strong>
              {mistakes.length ? "没有符合条件的错题" : "错题本还是空的"}
            </strong>
            <p>开始英语对话后，关键纠错会先来到这里等你确认。</p>
            <button
              className="primary-button"
              onClick={onStartPractice}
              type="button"
            >
              开始一次练习
            </button>
          </div>
        )}
      </div>
    </section>
  );
}
