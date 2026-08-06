import type {
  AgentRouting,
  ChatMessage,
  ConversationDetail,
  ModelMode,
} from "@/lib/api";
import { getConversation } from "@/lib/api";

import type { AgentId as DisplayAgentId } from "@/components/agents/AgentSelector";

export const modeOptions: Array<{
  value: ModelMode;
  label: string;
  detail: string;
}> = [
  { value: "standard", label: "标准", detail: "MiMo 主力 · 本地兜底" },
  { value: "deep", label: "深度", detail: "DeepSeek · 本地兜底" },
  { value: "local", label: "本地", detail: "Qwen3 4B" },
  { value: "auto", label: "自动", detail: "按任务智能选择" },
];

export function formatConversationTime(value: string) {
  const date = new Date(value);
  const today = new Date();
  if (date.toDateString() === today.toDateString()) {
    return date.toLocaleTimeString("zh-CN", {
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    });
  }
  return date.toLocaleDateString("zh-CN", { month: "numeric", day: "numeric" });
}

export function temporaryUserMessage(
  conversationId: string,
  content: string,
): ChatMessage {
  return {
    id: `pending-user-${Date.now()}`,
    conversation_id: conversationId,
    role: "user",
    content,
    status: "completed",
    metadata: {},
    created_at: new Date().toISOString(),
  };
}

export function temporaryAssistantMessage(conversationId: string): ChatMessage {
  return {
    id: `pending-assistant-${Date.now()}`,
    conversation_id: conversationId,
    role: "assistant",
    content: "",
    status: "completed",
    metadata: { streaming: true },
    created_at: new Date().toISOString(),
  };
}

export function temporaryRegenerationId(messageId: string) {
  return `regenerating-${messageId}-${Date.now()}`;
}

export function displayAgentId(routing: AgentRouting | null): DisplayAgentId {
  if (!routing) return "general";
  if (routing.agent_id === "english_coach") return "english";
  if (routing.agent_id === "growth") return "growth";
  if (routing.agent_id === "research") return "research";
  return "general";
}

export function savedAgentRouting(
  conversation: ConversationDetail,
): AgentRouting | null {
  const candidate = [...conversation.messages]
    .reverse()
    .find((message) => message.role === "assistant")?.metadata.agent_routing;
  if (
    candidate &&
    typeof candidate === "object" &&
    "agent_id" in candidate &&
    "routing_reason" in candidate
  ) {
    return candidate as AgentRouting;
  }
  return null;
}

export function deepSeekConfirmationText(
  routing: AgentRouting | null,
  action: "生成回答" | "重新回答",
) {
  const disclosure = routing?.model.deepseek_disclosure;
  if (!disclosure) {
    return `${action}将调用按量付费的 DeepSeek。确定继续吗？\n\n确认仅覆盖本次任务。`;
  }
  return [
    `${action}建议调用按量付费的 DeepSeek。`,
    "",
    `作用：${disclosure.purpose}`,
    `负责步骤：${disclosure.covered_steps.join("、")}`,
    `数据类别：${disclosure.data_categories.join("、")}`,
    `替代方案：${disclosure.alternatives.join("；")}`,
    "",
    "确定后，授权仅覆盖本次任务中列出的步骤。",
  ].join("\n");
}

export function newStreamRequestId() {
  return globalThis.crypto.randomUUID();
}

export async function refreshConversationUntil(
  conversationId: string,
  isReady: (conversation: ConversationDetail) => boolean,
) {
  let latest = await getConversation(conversationId);
  for (let attempt = 0; attempt < 4 && !isReady(latest); attempt += 1) {
    await new Promise((resolve) => window.setTimeout(resolve, 200));
    latest = await getConversation(conversationId);
  }
  return latest;
}
