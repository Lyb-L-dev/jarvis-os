"use client";

import { useCallback, useEffect, useState } from "react";

import {
  getSemanticIndexStatus,
  rebuildSemanticIndex,
  type SemanticIndexStatus,
} from "@/lib/api";

function timeLabel(value?: string | null) {
  if (!value) return "尚未构建";
  return new Intl.DateTimeFormat("zh-CN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

const stateLabels: Record<string, string> = {
  disabled: "未启用",
  empty: "等待首次构建",
  rebuilding: "正在构建",
  ready: "语义检索就绪",
  degraded: "已安全降级",
};

export function SemanticIndexPanel({ compact = false }: { compact?: boolean }) {
  const [status, setStatus] = useState<SemanticIndexStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (signal?: AbortSignal) => {
    try {
      setStatus(await getSemanticIndexStatus(signal));
      setError(null);
    } catch (reason) {
      if (reason instanceof DOMException && reason.name === "AbortError") return;
      setError(reason instanceof Error ? reason.message : "无法读取语义索引状态。");
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => void load(controller.signal), 0);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [load]);

  async function rebuild() {
    setBusy(true);
    setError(null);
    try {
      setStatus(await rebuildSemanticIndex());
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "语义索引重建失败。");
      await load();
    } finally {
      setBusy(false);
    }
  }

  const coverage = status?.coverage_percent ?? 0;
  return (
    <section className={`panel semantic-index-panel ${compact ? "semantic-index-compact" : ""}`}>
      <div className="semantic-index-heading">
        <div>
          <div className="eyebrow">LOCAL SEMANTIC MEMORY</div>
          <h2>语义索引</h2>
          <p>
            本地 bge-m3 理解相近含义；原始内容仍保存在 PostgreSQL，失败时自动使用关键词。
          </p>
        </div>
        <span className={`semantic-index-state state-${status?.status ?? "empty"}`}>
          {stateLabels[status?.status ?? "empty"] ?? status?.status}
        </span>
      </div>

      <div className="semantic-index-metrics">
        <article>
          <span>索引覆盖</span>
          <strong>{coverage.toFixed(1)}%</strong>
          <small>
            记忆 {status?.memory_indexed_count ?? 0}/{status?.memory_eligible_count ?? 0}
          </small>
        </article>
        <article>
          <span>知识文档</span>
          <strong>
            {status?.knowledge_indexed_count ?? 0}/{status?.knowledge_eligible_count ?? 0}
          </strong>
          <small>{status?.chunk_count ?? 0} 个可重建片段</small>
        </article>
        <article>
          <span>本地模型</span>
          <strong>{status?.local_model_available ? "在线" : "不可用"}</strong>
          <small>{status?.embedding_model ?? "bge-m3:latest"} · 1024 维</small>
        </article>
        <article>
          <span>最近构建</span>
          <strong>{timeLabel(status?.last_completed_at)}</strong>
          <small>
            {status?.fallback_active ? "关键词回退保持可用" : status?.index_version}
          </small>
        </article>
      </div>

      <div className="semantic-index-footer">
        <span>只有当前权限允许的结果才会进入模型上下文。</span>
        <button
          className="primary-button"
          disabled={busy || !status?.enabled}
          onClick={() => void rebuild()}
          type="button"
        >
          {busy ? "本地构建中…" : "重建语义索引"}
        </button>
      </div>
      {error ? <div className="backup-notice error">{error}</div> : null}
      {status?.last_error ? (
        <div className="backup-notice warning">{status.last_error}</div>
      ) : null}
    </section>
  );
}
