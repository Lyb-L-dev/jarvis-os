import type {
  EnglishCorrectionMode,
  EnglishMistake,
  EnglishMistakeStatus,
  EnglishOverview,
  EnglishReviewResult,
  EnglishSession,
  EnglishSessionType,
} from "@/lib/api";
import {
  formatDateTime as formatDateTimeShared,
  providerDisplayNames,
} from "@/lib/utils";

export type EnglishTab = "practice" | "mistakes" | "review";

export type EnglishFeedback = {
  busy: string | null;
  setBusy: (busy: string | null) => void;
  setError: (error: string | null) => void;
  setNotice: (notice: string | null) => void;
};

export const emptyOverview: EnglishOverview = {
  active_session_id: null,
  total_sessions: 0,
  completed_sessions: 0,
  pending_mistakes: 0,
  learning_mistakes: 0,
  mastered_mistakes: 0,
  due_reviews: 0,
};

export const sessionTypes: Array<{
  value: EnglishSessionType;
  label: string;
  description: string;
}> = [
  { value: "free", label: "自由对话", description: "从日常话题自然开聊" },
  { value: "topic", label: "主题练习", description: "围绕指定主题深入表达" },
  { value: "interview", label: "面试模拟", description: "训练求职问答与追问" },
  { value: "technical", label: "技术英语", description: "练习专业概念与工作沟通" },
];

export const correctionModes: Array<{
  value: EnglishCorrectionMode;
  label: string;
  description: string;
}> = [
  { value: "instant", label: "即时纠错", description: "每轮指出所有明确错误" },
  { value: "gentle", label: "温和纠错", description: "每轮只提醒最关键的一处" },
  { value: "summary", label: "结束总结", description: "对话中不打断，结束后统一分析" },
];

export const statusLabels: Record<EnglishMistakeStatus, string> = {
  pending: "待确认",
  learning: "学习中",
  mastered: "已掌握",
  disputed: "解释待修正",
  rejected: "已忽略",
};

export const reviewButtons: Array<{
  value: EnglishReviewResult;
  label: string;
  className?: string;
}> = [
  { value: "again", label: "没记住" },
  { value: "hard", label: "有点难" },
  { value: "good", label: "记住了", className: "review-good" },
  { value: "easy", label: "很轻松" },
  { value: "mastered", label: "已经掌握" },
];

export function sessionTitle(session: EnglishSession) {
  const type = sessionTypes.find((item) => item.value === session.session_type);
  return session.topic || type?.label || "英语练习";
}

export function correctionModeLabel(mode: EnglishCorrectionMode) {
  return correctionModes.find((item) => item.value === mode)?.label ?? mode;
}

export function providerLabel(message: {
  provider_used?: string | null;
  fallback_reason?: string | null;
}) {
  if (message.provider_used === "mimo") return providerDisplayNames.mimo;
  if (message.provider_used === "ollama") {
    return message.fallback_reason
      ? `${providerDisplayNames.ollama} · 自动降级`
      : providerDisplayNames.ollama;
  }
  if (message.provider_used === "rule_based") return "本地规则兜底";
  return null;
}

export function formatDateTime(value?: string | null) {
  return formatDateTimeShared(value, "尚未安排");
}

export function mergeMistakes(
  current: EnglishMistake[],
  incoming: EnglishMistake[],
) {
  const byId = new Map(current.map((item) => [item.id, item]));
  for (const item of incoming) byId.set(item.id, item);
  return Array.from(byId.values()).sort(
    (a, b) =>
      b.occurrence_count - a.occurrence_count ||
      new Date(b.last_seen_at).getTime() - new Date(a.last_seen_at).getTime(),
  );
}

export async function runAction(
  feedback: EnglishFeedback,
  key: string,
  action: () => Promise<void>,
  success?: string,
) {
  feedback.setBusy(key);
  feedback.setError(null);
  feedback.setNotice(null);
  try {
    await action();
    if (success) feedback.setNotice(success);
  } catch (actionError) {
    feedback.setError(
      actionError instanceof Error ? actionError.message : "操作失败",
    );
  } finally {
    feedback.setBusy(null);
  }
}

export async function refreshAfterMistakeAction(
  feedback: EnglishFeedback,
  refreshCollections: () => Promise<void>,
  message?: string,
) {
  await refreshCollections();
  if (message) feedback.setNotice(message);
}
