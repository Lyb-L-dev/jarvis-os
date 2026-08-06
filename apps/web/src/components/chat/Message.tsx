"use client";

import {
  Brain,
  Clock3,
  Database,
  RefreshCw,
  Route,
  Sparkles,
} from "lucide-react";
import { motion } from "motion/react";

import { JarvisMark } from "@/components/jarvis-mark";
import type { ChatMessage } from "@/lib/api";
import { providerBadge as providerLabel } from "@/lib/utils";

const fallbackLabels: Record<string, string> = {
  mimo_not_configured: "MiMo 未配置，已使用本地模型",
  deepseek_not_configured: "DeepSeek 未配置，已使用本地模型",
};

type MessageProps = {
  converting: boolean;
  message: ChatMessage;
  onConvertTask: (message: ChatMessage) => void;
  onRegenerate: (message: ChatMessage) => void;
  onRemember: (message: ChatMessage) => void;
  remembering: boolean;
  retryable: boolean;
  sending: boolean;
};

export function Message({
  converting,
  message,
  onConvertTask,
  onRegenerate,
  onRemember,
  remembering,
  retryable,
  sending,
}: MessageProps) {
  const pending =
    message.id.startsWith("pending-") ||
    message.id.startsWith("regenerating-");
  const sources = message.metadata.knowledge_sources ?? [];

  if (message.role === "user") {
    return (
      <motion.article
        animate={{ opacity: 1, y: 0 }}
        className="workspace-message workspace-message-user"
        initial={{ opacity: 0, y: 8 }}
        transition={{ damping: 28, stiffness: 260, type: "spring" }}
      >
        <div className="workspace-user-copy">
          <span>YOU</span>
          <p>{message.content}</p>
        </div>
        <div className="workspace-user-avatar">你</div>
        {!pending ? (
          <div className="workspace-user-actions">
            <button
              disabled={remembering}
              onClick={() => onRemember(message)}
              type="button"
            >
              <Brain aria-hidden="true" />
              {remembering ? "保存中" : "记住"}
            </button>
            <button
              disabled={converting}
              onClick={() => onConvertTask(message)}
              type="button"
            >
              <Route aria-hidden="true" />
              {converting ? "创建中" : "转为任务"}
            </button>
          </div>
        ) : null}
      </motion.article>
    );
  }

  return (
    <motion.article
      animate={{ opacity: 1, y: 0 }}
      className="workspace-message workspace-message-jarvis"
      initial={{ opacity: 0, y: 10 }}
      transition={{ damping: 28, stiffness: 250, type: "spring" }}
    >
      <div className="workspace-jarvis-header">
        <div className="workspace-jarvis-avatar">
          <JarvisMark showText={false} title="Jarvis" />
        </div>
        <div>
          <strong>Jarvis</strong>
          <span>{providerLabel(message.provider)}</span>
        </div>
        {message.latency_ms ? (
          <time>
            <Clock3 aria-hidden="true" />
            {(message.latency_ms / 1000).toFixed(1)}s
          </time>
        ) : null}
      </div>

      <div
        className={`workspace-response ${
          message.status === "error" ? "is-error" : ""
        } ${message.status === "cancelled" ? "is-cancelled" : ""}`}
      >
        {message.metadata.streaming && !message.content ? (
          <div className="workspace-thinking" aria-label="Jarvis is thinking">
            <Sparkles aria-hidden="true" />
            <span>Jarvis is thinking</span>
            <i />
            <i />
            <i />
          </div>
        ) : (
          <div className="workspace-response-copy">{message.content}</div>
        )}
      </div>

      {message.status === "cancelled" ? (
        <div className="workspace-cancelled">已停止生成，当前内容已自动保存。</div>
      ) : null}

      {message.metadata.fallback_reason ? (
        <div className="workspace-fallback">
          {fallbackLabels[String(message.metadata.fallback_reason)] ||
            String(message.metadata.fallback_reason)}
        </div>
      ) : null}

      <div className="workspace-result-context">
        <div>
          <Database aria-hidden="true" />
          <span>执行上下文</span>
          <strong>
            {sources.length > 0
              ? `${sources.length} 篇本地知识 · ${providerLabel(message.provider)}`
              : `${providerLabel(message.provider)} · 未引用外部知识`}
          </strong>
        </div>
        <div>
          <Sparkles aria-hidden="true" />
          <span>行动状态</span>
          <strong>未自动执行高风险操作</strong>
        </div>
      </div>

      {sources.length > 0 ? (
        <div className="workspace-knowledge">
          <span>KNOWLEDGE REFERENCES</span>
          <div>
            {sources.map((source, index) => (
              <a href={source.obsidian_uri} key={source.document_id}>
                [K{index + 1}] {source.title}
              </a>
            ))}
          </div>
        </div>
      ) : null}

      {!pending ? (
        <div className="workspace-message-actions">
          <button
            disabled={remembering}
            onClick={() => onRemember(message)}
            type="button"
          >
            <Brain aria-hidden="true" />
            {remembering ? "保存中…" : "更新记忆"}
          </button>
          <button
            disabled={converting}
            onClick={() => onConvertTask(message)}
            type="button"
          >
            <Route aria-hidden="true" />
            {converting ? "创建中…" : "创建行动"}
          </button>
          {retryable && !sending ? (
            <button onClick={() => onRegenerate(message)} type="button">
              <RefreshCw aria-hidden="true" />
              重新回答
            </button>
          ) : null}
        </div>
      ) : null}
    </motion.article>
  );
}
