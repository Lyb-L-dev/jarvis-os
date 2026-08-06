"use client";

import {
  getEvaluationCases,
  getEvaluationOverview,
  getEvaluationRuns,
  runEvaluation,
  updateEvaluationFeedback,
  type EvaluationCase,
  type EvaluationOverview,
  type EvaluationProvider,
  type EvaluationRun,
} from "@/lib/api";
import { useEffect, useMemo, useState } from "react";
import { MemoryShadowLab } from "@/components/memory-shadow-lab";

const providerLabels: Record<EvaluationProvider, string> = {
  mimo: "MiMo",
  deepseek: "DeepSeek",
  ollama: "本地 Qwen",
};

const providerRoles: Record<EvaluationProvider, string> = {
  mimo: "日常主模型",
  deepseek: "复杂问题辅助 · 付费",
  ollama: "隐私与离线",
};

const categoryLabels: Record<string, string> = {
  daily: "日常规划",
  knowledge: "知识库",
  intelligence: "情报",
  investment: "投资安全",
  safety: "诚实性",
  english: "英语学习",
};

function metric(value: number | null | undefined, suffix = "") {
  return value == null ? "尚无数据" : `${value}${suffix}`;
}

function runTime(value: string) {
  return new Date(value).toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

export function EvaluationCenter() {
  const [overview, setOverview] = useState<EvaluationOverview | null>(null);
  const [cases, setCases] = useState<EvaluationCase[]>([]);
  const [runs, setRuns] = useState<EvaluationRun[]>([]);
  const [provider, setProvider] = useState<EvaluationProvider>("mimo");
  const [paidConfirmed, setPaidConfirmed] = useState(false);
  const [runningCase, setRunningCase] = useState<string | null>(null);
  const [busyFeedback, setBusyFeedback] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    const [nextOverview, nextCases, nextRuns] = await Promise.all([
      getEvaluationOverview(),
      getEvaluationCases(),
      getEvaluationRuns(30),
    ]);
    setOverview(nextOverview);
    setCases(nextCases);
    setRuns(nextRuns);
    const selected = nextOverview.providers.find(
      (item) => item.provider === provider,
    );
    if (!selected?.configured) {
      const fallback = nextOverview.providers.find((item) => item.configured);
      if (fallback) setProvider(fallback.provider);
    }
  }

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      getEvaluationOverview(),
      getEvaluationCases(),
      getEvaluationRuns(30),
    ])
      .then(([nextOverview, nextCases, nextRuns]) => {
        if (cancelled) return;
        setOverview(nextOverview);
        setCases(nextCases);
        setRuns(nextRuns);
        const preferred = nextOverview.providers.find(
          (item) => item.provider === "mimo" && item.configured,
        );
        const fallback = nextOverview.providers.find((item) => item.configured);
        const initial = preferred || fallback;
        if (initial) setProvider(initial.provider);
      })
      .catch((reason: unknown) => {
        if (!cancelled) {
          setError(reason instanceof Error ? reason.message : "读取评测数据失败");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const selectedProvider = useMemo(
    () => overview?.providers.find((item) => item.provider === provider),
    [overview, provider],
  );

  async function startCase(caseId: string) {
    setError(null);
    setRunningCase(caseId);
    try {
      await runEvaluation({
        case_id: caseId,
        provider,
        paid_call_confirmed: provider === "deepseek" && paidConfirmed,
      });
      await refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "运行测试失败");
    } finally {
      setRunningCase(null);
    }
  }

  async function saveFeedback(
    runId: string,
    rating: "helpful" | "not_helpful",
  ) {
    setBusyFeedback(runId);
    try {
      const updated = await updateEvaluationFeedback(runId, rating);
      setRuns((current) =>
        current.map((run) => (run.id === updated.id ? updated : run)),
      );
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "保存反馈失败");
    } finally {
      setBusyFeedback(null);
    }
  }

  if (loading) {
    return <section className="panel evaluation-loading">正在准备个人测试集…</section>;
  }

  return (
    <div className="evaluation-layout">
      {error ? <div className="evaluation-error">{error}</div> : null}

      <section className="evaluation-provider-grid">
        {overview?.providers.map((item) => (
          <button
            className={`evaluation-provider-card ${
              provider === item.provider ? "evaluation-provider-selected" : ""
            }`}
            disabled={!item.configured || runningCase !== null}
            key={item.provider}
            onClick={() => {
              setProvider(item.provider);
              setPaidConfirmed(false);
            }}
            type="button"
          >
            <div>
              <span>{providerRoles[item.provider]}</span>
              <strong>{providerLabels[item.provider]}</strong>
              <small>{item.model}</small>
            </div>
            <span
              className={`evaluation-provider-state ${
                item.configured ? "evaluation-provider-ready" : ""
              }`}
            >
              {item.configured ? "可测试" : "未配置"}
            </span>
            <dl>
              <div>
                <dt>真实调用</dt>
                <dd>{item.chat_call_count}</dd>
              </div>
              <div>
                <dt>成功率</dt>
                <dd>{metric(item.chat_success_rate, "%")}</dd>
              </div>
              <div>
                <dt>平均测试分</dt>
                <dd>{metric(item.average_evaluation_score, " 分")}</dd>
              </div>
              <div>
                <dt>首字速度</dt>
                <dd>
                  {item.average_first_token_ms == null
                    ? "尚无数据"
                    : `${(item.average_first_token_ms / 1000).toFixed(1)} 秒`}
                </dd>
              </div>
            </dl>
          </button>
        ))}
      </section>

      <section className="panel evaluation-privacy-panel">
        <div>
          <span className="evaluation-lock">本机安全记录</span>
          <strong>不会把你的私人对话当作测试数据</strong>
        </div>
        <p>{overview?.privacy_note}</p>
      </section>

      <MemoryShadowLab />

      <section className="panel evaluation-cases-panel">
        <div className="section-heading">
          <div>
            <div className="eyebrow">PERSONAL BENCHMARK</div>
            <h3>选择一项真实能力测试</h3>
          </div>
          <span className="settings-safe-label">
            当前：{providerLabels[provider]}
          </span>
        </div>

        {provider === "deepseek" ? (
          <label className="evaluation-paid-confirmation">
            <input
              checked={paidConfirmed}
              onChange={(event) => setPaidConfirmed(event.target.checked)}
              type="checkbox"
            />
            我确认本次测试会调用 DeepSeek 并产生钱包费用
          </label>
        ) : null}

        <div className="evaluation-case-grid">
          {cases.map((item) => (
            <article className="evaluation-case-card" key={item.id}>
              <span>{categoryLabels[item.category] || item.category}</span>
              <h4>{item.title}</h4>
              <p>{item.description}</p>
              <button
                className="primary-button"
                disabled={
                  runningCase !== null ||
                  !selectedProvider?.configured ||
                  (provider === "deepseek" && !paidConfirmed)
                }
                onClick={() => startCase(item.id)}
                type="button"
              >
                {runningCase === item.id ? "正在认真测试…" : "运行这项测试"}
              </button>
            </article>
          ))}
        </div>
      </section>

      <section className="panel evaluation-results-panel">
        <div className="section-heading">
          <div>
            <div className="eyebrow">RECENT RESULTS</div>
            <h3>最近测试结果</h3>
          </div>
        </div>
        {runs.length === 0 ? (
          <div className="call-history-empty">
            还没有测试结果。建议先用 MiMo 跑一项，再用本地 Qwen 对比。
          </div>
        ) : (
          <div className="evaluation-results">
            {runs.map((run) => {
              const testCase = cases.find((item) => item.id === run.case_id);
              return (
                <article className="evaluation-result-card" key={run.id}>
                  <div className="evaluation-result-head">
                    <div>
                      <span>{providerLabels[run.provider]}</span>
                      <strong>{testCase?.title || run.case_id}</strong>
                      <small>
                        {runTime(run.created_at)} ·{" "}
                        {run.latency_ms == null
                          ? "耗时未知"
                          : `${(run.latency_ms / 1000).toFixed(1)} 秒`}
                      </small>
                    </div>
                    <div
                      className={`evaluation-score ${
                        (run.score || 0) >= 80 ? "evaluation-score-good" : ""
                      }`}
                    >
                      {run.status === "failed"
                        ? "失败"
                        : `${run.score ?? "—"} 分`}
                    </div>
                  </div>
                  {run.response_text ? (
                    <p className="evaluation-answer">{run.response_text}</p>
                  ) : (
                    <p className="evaluation-answer">
                      模型未完成回答：{run.error_type || "未知错误"}
                    </p>
                  )}
                  <div className="evaluation-checks">
                    {run.checks.map((check) => (
                      <span
                        className={check.passed ? "evaluation-check-pass" : ""}
                        key={check.label}
                      >
                        {check.passed ? "✓" : "×"} {check.label}
                      </span>
                    ))}
                  </div>
                  <div className="call-actions">
                    <span>你认为这次结果：</span>
                    <button
                      className={
                        run.feedback_rating === "helpful"
                          ? "call-feedback-active"
                          : ""
                      }
                      disabled={busyFeedback === run.id}
                      onClick={() => saveFeedback(run.id, "helpful")}
                      type="button"
                    >
                      符合预期
                    </button>
                    <button
                      className={
                        run.feedback_rating === "not_helpful"
                          ? "call-feedback-active call-feedback-negative"
                          : ""
                      }
                      disabled={busyFeedback === run.id}
                      onClick={() => saveFeedback(run.id, "not_helpful")}
                      type="button"
                    >
                      不符合
                    </button>
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}
