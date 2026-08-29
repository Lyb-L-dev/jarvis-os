"use client";

import { useCallback, useEffect, useState } from "react";

import {
  answerLearningItem,
  createLearningModule,
  getLearningReadiness,
  getLearningReviewQueue,
  getLearningShadowSummary,
  type LearningGrade,
  type LearningGraderShadowSummary,
  type LearningGraderShadowView,
  type LearningModuleSummary,
  type LearningReviewCardView,
  type LearningVerificationView,
  listLearningModules,
  reviewLearningCard,
  runLearningShadowGrading,
  startLearningVerification,
} from "@/lib/api/learning";

const LEVEL_NAMES: Record<number, string> = {
  1: "基础理解",
  2: "原理理解",
  3: "实际应用",
  4: "面试追问",
};

const RATING_OPTIONS = [
  { rating: 1, label: "重来" },
  { rating: 2, label: "模糊" },
  { rating: 3, label: "记得" },
  { rating: 4, label: "轻松" },
];

const GRADE_META: Record<LearningGrade, { label: string; className: string }> = {
  green: { label: "已掌握", className: "learning-grade-green" },
  yellow: { label: "不稳定", className: "learning-grade-yellow" },
  red: { label: "未掌握", className: "learning-grade-red" },
};

type Phase = "loading" | "disabled" | "offline" | "ready";

function gradeChip(grade: LearningGrade) {
  const meta = GRADE_META[grade];
  return <span className={`learning-grade-chip ${meta.className}`}>{meta.label}</span>;
}

export function LearningCoach() {
  const [phase, setPhase] = useState<Phase>("loading");
  const [offlineMessage, setOfflineMessage] = useState("");
  const [modules, setModules] = useState<LearningModuleSummary[]>([]);
  const [queue, setQueue] = useState<LearningReviewCardView[]>([]);
  const [shadowSummary, setShadowSummary] =
    useState<LearningGraderShadowSummary | null>(null);
  const [shadows, setShadows] = useState<Record<string, LearningGraderShadowView>>({});

  const [newName, setNewName] = useState("");
  const [newConcepts, setNewConcepts] = useState("");

  const [selectedModuleId, setSelectedModuleId] = useState("");
  const [verification, setVerification] = useState<LearningVerificationView | null>(null);
  const [answerDraft, setAnswerDraft] = useState("");

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refreshCore = useCallback(async () => {
    const [moduleList, reviewQueue] = await Promise.all([
      listLearningModules(),
      getLearningReviewQueue(),
    ]);
    setModules(moduleList);
    setQueue(reviewQueue.cards);
  }, []);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        const readiness = await getLearningReadiness();
        if (cancelled) return;
        if (!readiness.enabled) {
          setPhase("disabled");
          return;
        }
        await refreshCore();
        const summary = await getLearningShadowSummary().catch(() => null);
        if (cancelled) return;
        setShadowSummary(summary);
        setPhase("ready");
      } catch (cause) {
        if (!cancelled) {
          setOfflineMessage(cause instanceof Error ? cause.message : "连接失败");
          setPhase("offline");
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [refreshCore]);

  async function run(action: () => Promise<void>) {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      await action();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "操作失败");
    } finally {
      setBusy(false);
    }
  }

  const activeItem = verification?.items.find((item) => item.answered_at === null) ?? null;
  const activeModule = modules.find((module) => module.id === selectedModuleId) ?? null;

  if (phase === "loading") {
    return <div className="learning-state">正在连接学习教练…</div>;
  }
  if (phase === "disabled") {
    return (
      <div className="learning-state">
        学习教练当前默认关闭（<code>v5_learning_coach_enabled</code>）。
        在 .env 中打开后重启 API 即可使用。
      </div>
    );
  }
  if (phase === "offline") {
    return <div className="learning-state learning-state-offline">连接失败：{offlineMessage}</div>;
  }

  return (
    <div className="learning-workspace">
      {error ? <div className="learning-error">{error}</div> : null}

      <section className="panel learning-panel">
        <div className="section-heading">
          <div>
            <div className="eyebrow">MODULES · MASTERY</div>
            <h3>知识模块与真实掌握度</h3>
          </div>
        </div>
        {modules.length === 0 ? (
          <p className="learning-hint">还没有知识模块。先添加一个，例如「HTTP / API」。</p>
        ) : (
          <ul className="learning-module-list">
            {modules.map((module) => (
              <li key={module.id} className="learning-module-row">
                <div className="learning-module-head">
                  <strong>{module.name}</strong>
                  <span className="learning-module-meta">
                    {module.mastery.mastery_percent}%
                    {module.mastery.low_confidence ? " · 样本不足" : ""}
                    {" · "}
                    {module.mastery.evidence_count} 条证据
                  </span>
                </div>
                <div className="progress">
                  <div
                    className="learning-mastery-fill"
                    style={{ width: `${Math.min(100, module.mastery.mastery_percent)}%` }}
                  />
                </div>
                {module.core_concepts.length > 0 ? (
                  <div className="learning-concepts">
                    {module.core_concepts.join(" · ")}
                  </div>
                ) : null}
              </li>
            ))}
          </ul>
        )}

        <div className="learning-create-form">
          <input
            className="learning-input"
            placeholder="模块名称，例如 HTTP / API"
            value={newName}
            onChange={(event) => setNewName(event.target.value)}
            maxLength={160}
          />
          <input
            className="learning-input"
            placeholder="核心概念，用逗号分隔：timeout, retry, exception"
            value={newConcepts}
            onChange={(event) => setNewConcepts(event.target.value)}
          />
          <button
            type="button"
            className="primary-button"
            disabled={busy || newName.trim().length === 0}
            onClick={() =>
              run(async () => {
                await createLearningModule({
                  name: newName.trim(),
                  core_concepts: newConcepts
                    .split(/[,，、]/)
                    .map((concept) => concept.trim())
                    .filter(Boolean),
                });
                setNewName("");
                setNewConcepts("");
                await refreshCore();
              })
            }
          >
            添加模块
          </button>
        </div>
      </section>

      <section className="panel learning-panel">
        <div className="section-heading">
          <div>
            <div className="eyebrow">VERIFY · L1-L4</div>
            <h3>学习验收</h3>
          </div>
          {verification ? (
            <span className="learning-verification-status">
              {verification.status === "completed" ? "已完成" : `${verification.item_count} 题`}
            </span>
          ) : null}
        </div>

        <div className="learning-verification-start">
          <select
            className="learning-input learning-select"
            value={selectedModuleId}
            onChange={(event) => setSelectedModuleId(event.target.value)}
          >
            <option value="">选择要验收的模块…</option>
            {modules.map((module) => (
              <option key={module.id} value={module.id}>
                {module.name}
              </option>
            ))}
          </select>
          <button
            type="button"
            className="primary-button"
            disabled={busy || !activeModule}
            onClick={() =>
              run(async () => {
                if (!activeModule) return;
                const started = await startLearningVerification(activeModule.id);
                setVerification(started);
                setAnswerDraft("");
                setShadows({});
              })
            }
          >
            开始验收
          </button>
        </div>

        {verification ? (
          <div className="learning-verification-items">
            {verification.items.map((item) => {
              const shadow = shadows[item.id];
              const isAnswered = item.answered_at !== null;
              return (
                <div
                  key={item.id}
                  className={`learning-item${isAnswered ? "" : " learning-item-active"}`}
                >
                  <div className="learning-item-head">
                    <span className="learning-item-level">
                      Level {item.level} · {LEVEL_NAMES[item.level] ?? ""}
                    </span>
                    {item.grade ? gradeChip(item.grade) : null}
                  </div>
                  <p className="learning-item-prompt">{item.prompt}</p>
                  {isAnswered ? (
                    <div className="learning-item-result">
                      <p className="learning-item-answer">{item.answer}</p>
                      {item.feedback ? (
                        <p className="learning-item-feedback">{item.feedback}</p>
                      ) : null}
                      {shadowSummary ? (
                        <div className="learning-shadow-row">
                          {shadow ? (
                            <span className="learning-shadow-note">
                              影子判分：{shadow.llm_grade ?? "失败"}
                              {shadow.agreement === true ? " · 与规则一致" : " · 与规则不一致"}
                              {shadow.error_message ? ` · ${shadow.error_message}` : ""}
                            </span>
                          ) : (
                            <button
                              type="button"
                              className="ghost-button"
                              disabled={busy}
                              onClick={() =>
                                run(async () => {
                                  const view = await runLearningShadowGrading(
                                    verification.id,
                                    item.id,
                                  );
                                  setShadows((current) => ({
                                    ...current,
                                    [item.id]: view,
                                  }));
                                  setShadowSummary(await getLearningShadowSummary());
                                })
                              }
                            >
                              影子判分对比
                            </button>
                          )}
                        </div>
                      ) : null}
                    </div>
                  ) : item.id === activeItem?.id ? (
                    <div className="learning-answer-form">
                      <textarea
                        className="learning-input learning-textarea"
                        placeholder="用自己的话回答。判分依据是上面的核心概念，不看措辞看理解。"
                        value={answerDraft}
                        onChange={(event) => setAnswerDraft(event.target.value)}
                        rows={4}
                      />
                      <button
                        type="button"
                        className="primary-button"
                        disabled={busy || answerDraft.trim().length === 0}
                        onClick={() =>
                          run(async () => {
                            if (!activeItem) return;
                            const result = await answerLearningItem(
                              verification.id,
                              activeItem.id,
                              answerDraft.trim(),
                            );
                            setVerification((current) =>
                              current
                                ? {
                                    ...current,
                                    status: result.verification_status,
                                    completed_at: null,
                                    items: current.items.map((candidate) =>
                                      candidate.id === result.item.id ? result.item : candidate,
                                    ),
                                  }
                                : current,
                            );
                            setAnswerDraft("");
                            await refreshCore();
                          })
                        }
                      >
                        提交回答
                      </button>
                    </div>
                  ) : null}
                </div>
              );
            })}
          </div>
        ) : (
          <p className="learning-hint">
            验收以「能否解释和应用」为标准：四级提问覆盖基础、原理、应用与面试追问，黄/红题目会自动进入复习队列。
          </p>
        )}
      </section>

      <section className="panel learning-panel">
        <div className="section-heading">
          <div>
            <div className="eyebrow">SPACED REPETITION · FSRS</div>
            <h3>今日复习队列</h3>
          </div>
          <span className="learning-verification-status">{queue.length} 张到期</span>
        </div>
        {queue.length === 0 ? (
          <p className="learning-hint">没有到期的复习卡。错题会按 FSRS 记忆模型安排复习时间。</p>
        ) : (
          <ul className="learning-queue">
            {queue.map((card) => (
              <li key={card.id} className="learning-queue-card">
                <p className="learning-item-prompt">{card.question}</p>
                {card.answer_hints.length > 0 ? (
                  <p className="learning-concepts">要点：{card.answer_hints.join(" · ")}</p>
                ) : null}
                <div className="learning-rating-row">
                  {RATING_OPTIONS.map((option) => (
                    <button
                      key={option.rating}
                      type="button"
                      className="ghost-button"
                      disabled={busy}
                      onClick={() =>
                        run(async () => {
                          await reviewLearningCard(card.id, option.rating);
                          await refreshCore();
                        })
                      }
                    >
                      {option.label}
                    </button>
                  ))}
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      {shadowSummary ? (
        <section className="panel learning-panel">
          <div className="section-heading">
            <div>
              <div className="eyebrow">SHADOW · NOT AUTHORITATIVE</div>
              <h3>影子判分一致性</h3>
            </div>
          </div>
          <p className="learning-hint">
            本地模型判分与 rule_v1 并行运行、永不接管。累计 {shadowSummary.total} 次：
            一致 {shadowSummary.agreed} · 分歧 {shadowSummary.disagreed} · 失败 {shadowSummary.failed}
            {shadowSummary.agreement_rate !== null
              ? ` · 一致率 ${(shadowSummary.agreement_rate * 100).toFixed(1)}%`
              : ""}
          </p>
        </section>
      ) : null}
    </div>
  );
}
