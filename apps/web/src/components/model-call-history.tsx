"use client";

import {
  getModelCalls,
  getModelCallTrace,
  updateModelCallFeedback,
  type ModelCallLog,
  type ModelExecutionTrace,
} from "@/lib/api";
import { useEffect, useState } from "react";

const fallbackLabels: Record<string, string> = {
  mimo_not_configured: "MiMo 未配置",
  deepseek_not_configured: "DeepSeek 未配置",
};

function callTime(value: string) {
  return new Date(value).toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function providerName(value: string) {
  if (value === "ollama") return "Ollama";
  if (value === "deepseek") return "DeepSeek";
  if (value === "mimo") return "MiMo";
  return value;
}

export function ModelCallHistory() {
  const [calls, setCalls] = useState<ModelCallLog[]>([]);
  const [traces, setTraces] = useState<Record<string, ModelExecutionTrace>>({});
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getModelCalls(12)
      .then((items) => {
        if (!cancelled) setCalls(items);
      })
      .catch((reason: unknown) => {
        if (!cancelled) {
          setError(reason instanceof Error ? reason.message : "读取调用记录失败");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) {
    return <div className="call-history-empty">正在读取调用记录…</div>;
  }
  if (error) {
    return <div className="call-history-empty call-history-error">{error}</div>;
  }
  if (calls.length === 0) {
    return <div className="call-history-empty">还没有模型调用记录。</div>;
  }

  async function toggleTrace(callId: string) {
    if (expandedId === callId) {
      setExpandedId(null);
      return;
    }
    setExpandedId(callId);
    if (traces[callId]) return;
    setBusyId(callId);
    try {
      const trace = await getModelCallTrace(callId);
      setTraces((current) => ({ ...current, [callId]: trace }));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "读取执行过程失败");
    } finally {
      setBusyId(null);
    }
  }

  async function saveFeedback(
    callId: string,
    rating: "helpful" | "not_helpful",
  ) {
    setBusyId(callId);
    try {
      const updated = await updateModelCallFeedback(callId, { rating });
      setCalls((current) =>
        current.map((call) => (call.id === updated.id ? updated : call)),
      );
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "保存反馈失败");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="call-history">
      {calls.map((call) => {
        const trace = traces[call.id];
        const expanded = expandedId === call.id;
        return (
          <article className="call-card" key={call.id}>
            <div className="call-row">
              <span
                className={`call-state ${
                  call.success ? "call-state-success" : "call-state-error"
                }`}
              />
              <div className="call-route">
                <strong>{providerName(call.requested_provider)}</strong>
                {call.requested_provider !== call.provider_used ? (
                  <>
                    <span>→</span>
                    <strong>{providerName(call.provider_used)}</strong>
                  </>
                ) : null}
                <small>{call.model_used}</small>
              </div>
              <div className="call-reason">
                <span>
                  {call.fallback_reason
                    ? fallbackLabels[call.fallback_reason] ||
                      call.fallback_reason
                    : call.success
                      ? "按计划执行"
                      : call.error_type || "调用失败"}
                </span>
                {call.provider_used === "deepseek" && call.user_confirmed ? (
                  <small>已确认付费</small>
                ) : null}
              </div>
              <div className="call-metrics">
                <span>总耗时 {(call.latency_ms / 1000).toFixed(1)}s</span>
                <span>
                  首字{" "}
                  {call.first_token_ms == null
                    ? "—"
                    : `${(call.first_token_ms / 1000).toFixed(1)}s`}
                </span>
                <span>
                  {call.tokens_per_second == null
                    ? `${call.total_tokens ?? "—"} tokens`
                    : `${call.tokens_per_second.toFixed(1)} tokens/s`}
                </span>
                <time>{callTime(call.created_at)}</time>
              </div>
            </div>

            <div className="call-actions">
              <button
                className={
                  call.feedback_rating === "helpful"
                    ? "call-feedback-active"
                    : ""
                }
                disabled={busyId === call.id}
                onClick={() => saveFeedback(call.id, "helpful")}
                type="button"
              >
                有帮助
              </button>
              <button
                className={
                  call.feedback_rating === "not_helpful"
                    ? "call-feedback-active call-feedback-negative"
                    : ""
                }
                disabled={busyId === call.id}
                onClick={() => saveFeedback(call.id, "not_helpful")}
                type="button"
              >
                没解决
              </button>
              <button
                disabled={busyId === call.id}
                onClick={() => toggleTrace(call.id)}
                type="button"
              >
                {expanded ? "收起过程" : "查看过程"}
              </button>
            </div>

            {expanded ? (
              <div className="call-trace">
                {trace ? (
                  <>
                    <p>{trace.privacy_note}</p>
                    <div className="call-trace-steps">
                      {trace.steps.map((step, index) => (
                        <div className="call-trace-step" key={step.key}>
                          <span>{index + 1}</span>
                          <div>
                            <strong>{step.label}</strong>
                            <small>
                              {step.status === "completed"
                                ? "已完成"
                                : step.status === "failed"
                                  ? "失败"
                                  : "未执行"}
                              {step.duration_ms != null
                                ? ` · ${(step.duration_ms / 1000).toFixed(1)} 秒`
                                : ""}
                            </small>
                          </div>
                        </div>
                      ))}
                    </div>
                  </>
                ) : (
                  <p>正在读取安全执行记录…</p>
                )}
              </div>
            ) : null}
          </article>
        );
      })}
    </div>
  );
}
