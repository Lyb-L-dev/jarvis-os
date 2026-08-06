"use client";

import {
  getMemoryShadowCases,
  getMemoryShadowRuns,
  getMemoryShadowStatus,
  reviewMemoryShadowCandidate,
  runMemoryShadowCase,
  type MemoryShadowCandidate,
  type MemoryShadowCase,
  type MemoryShadowEngine,
  type MemoryShadowRun,
  type MemoryShadowStatus,
} from "@/lib/api";
import { useEffect, useState } from "react";

const engineLabels: Record<MemoryShadowEngine, string> = {
  rule: "现有规则",
  qwen: "本地 Qwen",
  mem0: "Mem0 影子",
};

function percent(value: number | null | undefined) {
  return value == null ? "尚无结果" : `${Math.round(value * 100)}%`;
}

export function MemoryShadowLab() {
  const [status, setStatus] = useState<MemoryShadowStatus | null>(null);
  const [cases, setCases] = useState<MemoryShadowCase[]>([]);
  const [runs, setRuns] = useState<MemoryShadowRun[]>([]);
  const [runningCase, setRunningCase] = useState<string | null>(null);
  const [reviewing, setReviewing] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    const [nextStatus, nextCases, nextRuns] = await Promise.all([
      getMemoryShadowStatus(),
      getMemoryShadowCases(),
      getMemoryShadowRuns(12),
    ]);
    setStatus(nextStatus);
    setCases(nextCases);
    setRuns(nextRuns);
  }

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      getMemoryShadowStatus(),
      getMemoryShadowCases(),
      getMemoryShadowRuns(12),
    ])
      .then(([nextStatus, nextCases, nextRuns]) => {
        if (cancelled) return;
        setStatus(nextStatus);
        setCases(nextCases);
        setRuns(nextRuns);
      })
      .catch((reason: unknown) => {
        if (!cancelled) {
          setError(reason instanceof Error ? reason.message : "读取记忆实验室失败");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function startCase(caseId: string) {
    setError(null);
    setRunningCase(caseId);
    try {
      await runMemoryShadowCase(caseId);
      await refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "影子评测失败");
    } finally {
      setRunningCase(null);
    }
  }

  async function saveReview(
    candidate: MemoryShadowCandidate,
    verdict: "correct" | "partial" | "incorrect",
  ) {
    setReviewing(candidate.id);
    setError(null);
    try {
      const updated = await reviewMemoryShadowCandidate(candidate.id, verdict);
      setRuns((current) =>
        current.map((run) => ({
          ...run,
          candidates: run.candidates.map((item) =>
            item.id === updated.id ? updated : item,
          ),
        })),
      );
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "保存人工判断失败");
    } finally {
      setReviewing(null);
    }
  }

  if (loading) {
    return <section className="panel memory-shadow-loading">正在隔离启动记忆实验室…</section>;
  }

  return (
    <section className="panel memory-shadow-lab">
      <div className="memory-shadow-head">
        <div>
          <div className="eyebrow">SPRINT 28 · MEMORY SHADOW LAB</div>
          <h3>规则、Qwen 与 Mem0 的盲测台</h3>
          <p>
            三套引擎读取同一组固定场景，只生成影子候选。这里没有“写入正式记忆”按钮。
          </p>
        </div>
        <span
          className={`memory-shadow-state ${status?.configured ? "memory-shadow-state-ready" : ""}`}
        >
          {status?.configured ? "本地隔离已就绪" : "影子引擎未就绪"}
        </span>
      </div>

      {error ? <div className="evaluation-error">{error}</div> : null}

      <div className="memory-shadow-boundaries">
        <span>云模型 {status?.cloud_models_used ? "已使用" : "未使用"}</span>
        <span>遥测 {status?.telemetry_enabled ? "已开启" : "已关闭"}</span>
        <span>
          正式记忆写入 {status?.authoritative_memory_writes ? "已开启" : "不存在"}
        </span>
        <span>
          聊天自动运行 {status?.chat_auto_shadow_enabled ? "已开启" : "已关闭"}
        </span>
      </div>

      <div className="memory-shadow-engine-grid">
        {status?.engines.map((engine) => (
          <article key={engine.engine}>
            <span>{engineLabels[engine.engine]}</span>
            <strong>{percent(engine.average_f1)}</strong>
            <small>
              已测 {engine.evaluated_cases}/{engine.total_cases} · 安全违规 {engine.safety_violations}
            </small>
          </article>
        ))}
        <article className={status?.advancement_ready ? "memory-shadow-gate-ready" : ""}>
          <span>升级门槛 {Math.round((status?.accuracy_threshold || 0.8) * 100)}%</span>
          <strong>{status?.advancement_ready ? "已达到" : "保持影子"}</strong>
          <small>{status?.advancement_reason}</small>
        </article>
      </div>

      <div className="memory-shadow-case-list">
        {cases.map((item) => (
          <article key={item.id}>
            <div>
              <span>{item.category}</span>
              <strong>{item.title}</strong>
              <p>{item.input_preview}</p>
              <small>{item.description}</small>
            </div>
            <button
              className="primary-button"
              disabled={!status?.configured || runningCase !== null}
              onClick={() => startCase(item.id)}
              type="button"
            >
              {runningCase === item.id ? "三引擎正在盲测…" : "运行三引擎对比"}
            </button>
          </article>
        ))}
      </div>

      <div className="memory-shadow-results">
        <div className="section-heading">
          <div>
            <div className="eyebrow">SHADOW RESULTS</div>
            <h3>最近影子候选</h3>
          </div>
        </div>
        {runs.length === 0 ? (
          <div className="call-history-empty">尚无结果。运行一个固定场景开始比较。</div>
        ) : (
          runs.map((run) => {
            const testCase = cases.find((item) => item.id === run.case_id);
            return (
              <article className="memory-shadow-run" key={run.id}>
                <div className="memory-shadow-run-head">
                  <div>
                    <span>{testCase?.category || "memory"}</span>
                    <strong>{testCase?.title || run.case_id}</strong>
                  </div>
                  <b>{run.aggregate_score == null ? "失败" : `${run.aggregate_score} 分`}</b>
                </div>
                <div className="memory-shadow-metrics">
                  {run.engines.map((engine) => {
                    const metric = run.engine_results[engine];
                    return (
                      <div key={engine}>
                        <span>{engineLabels[engine]}</span>
                        <strong>
                          {metric?.status === "completed"
                            ? percent(metric.f1)
                            : "未完成"}
                        </strong>
                        <small>
                          {metric?.status === "completed"
                            ? `${metric.candidate_count || 0} 条 · ${((metric.latency_ms || 0) / 1000).toFixed(1)} 秒`
                            : metric?.error_message || "没有结果"}
                        </small>
                      </div>
                    );
                  })}
                </div>
                {run.candidates.length === 0 ? (
                  <p className="memory-shadow-no-candidate">三套引擎都没有生成候选。</p>
                ) : (
                  <div className="memory-shadow-candidates">
                    {run.candidates.map((candidate) => (
                      <div key={candidate.id}>
                        <div>
                          <span>{engineLabels[candidate.engine]}</span>
                          <small>{candidate.memory_type}</small>
                        </div>
                        <p>{candidate.content}</p>
                        <div className="memory-shadow-review">
                          <span>
                            {candidate.blocked_reason
                              ? "敏感候选已拦截"
                              : candidate.expected_match
                                ? "自动匹配预期"
                                : "需要人工判断"}
                          </span>
                          {(["correct", "partial", "incorrect"] as const).map(
                            (verdict) => (
                              <button
                                className={
                                  candidate.review_verdict === verdict
                                    ? "memory-shadow-review-active"
                                    : ""
                                }
                                disabled={reviewing === candidate.id}
                                key={verdict}
                                onClick={() => saveReview(candidate, verdict)}
                                type="button"
                              >
                                {verdict === "correct"
                                  ? "正确"
                                  : verdict === "partial"
                                    ? "部分正确"
                                    : "错误"}
                              </button>
                            ),
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </article>
            );
          })
        )}
      </div>
    </section>
  );
}
