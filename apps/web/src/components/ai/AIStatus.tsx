"use client";

import { motion } from "motion/react";

export type AIState =
  | "idle"
  | "thinking"
  | "listening"
  | "speaking"
  | "error";

export const AI_STATE_META: Record<
  AIState,
  { code: string; label: string; description: string }
> = {
  idle: {
    code: "ONLINE",
    label: "待命",
    description: "核心在线，随时可以开始",
  },
  thinking: {
    code: "THINKING",
    label: "思考中",
    description: "正在同步你的个人上下文",
  },
  listening: {
    code: "LISTENING",
    label: "正在聆听",
    description: "语音通道已开启",
  },
  speaking: {
    code: "SPEAKING",
    label: "正在回应",
    description: "Jarvis 正在与你交流",
  },
  error: {
    code: "INTERRUPTED",
    label: "连接中断",
    description: "Jarvis 正在尝试恢复连接",
  },
};

export function AIStatus({ state }: { state: AIState }) {
  const meta = AI_STATE_META[state];

  return (
    <div className={`ai-status ai-status-${state}`} role="status">
      <motion.span
        animate={
          state === "error"
            ? { opacity: [0.45, 1, 0.45], scale: [0.85, 1, 0.85] }
            : { opacity: [0.6, 1, 0.6], scale: [0.9, 1, 0.9] }
        }
        aria-hidden="true"
        transition={{
          duration: state === "thinking" ? 1.1 : 2.4,
          ease: "easeInOut",
          repeat: Number.POSITIVE_INFINITY,
        }}
      />
      <div>
        <strong>{meta.label}</strong>
        <small>{meta.description}</small>
      </div>
      <em>{meta.code}</em>
    </div>
  );
}
