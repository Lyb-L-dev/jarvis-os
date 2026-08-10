import { ChevronRight, Sparkles } from "lucide-react";
import type { RefObject } from "react";

import { JarvisOrb } from "@/components/ai/JarvisOrb";
import { Message } from "@/components/chat/Message";

import type { AIState } from "@/components/ai/AIStatus";
import type {
  ChatMessage,
  ConversationDetail,
} from "@/lib/api";

export function ChatMessageFlow({
  loading,
  detail,
  workspaceState,
  onSelectSuggestion,
  onRemember,
  onConvert,
  onRegenerate,
  rememberingId,
  convertingId,
  sending,
  retryableAssistantId,
  messageEndRef,
}: {
  loading: boolean;
  detail: ConversationDetail | null;
  workspaceState: AIState;
  onSelectSuggestion: (suggestion: string) => void;
  onRemember: (message: ChatMessage) => void;
  onConvert: (message: ChatMessage) => void;
  onRegenerate: (message: ChatMessage) => void;
  rememberingId: string | null;
  convertingId: string | null;
  sending: boolean;
  retryableAssistantId: string | null;
  messageEndRef: RefObject<HTMLDivElement | null>;
}) {
  return (
    <div className="message-stage workspace-message-stage">
      {loading && !detail ? (
        <div className="workspace-loading">
          <JarvisOrb state="thinking" />
          <span>Jarvis is recalling your conversation…</span>
        </div>
      ) : null}

      {!loading && (!detail || detail.messages.length === 0) ? (
        <div className="workspace-welcome">
          <div className="workspace-welcome-core">
            <JarvisOrb state={workspaceState} />
          </div>
          <h2>从一个想法开始。</h2>
          <span>Jarvis 已就绪</span>
          <p>
            这里不是普通聊天窗口。Jarvis 会保留上下文、标注真实模型，
            并把有价值的结果转化为记忆、知识或下一步行动。
          </p>
          <div className="workspace-prompts">
            {[
              "帮我规划今天 4 小时最值得推进的事情",
              "研究一个 Agent 开发问题并给出行动方案",
              "结合我的长期目标，整理本周优先级",
            ].map((suggestion) => (
              <button
                key={suggestion}
                onClick={() => onSelectSuggestion(suggestion)}
                type="button"
              >
                <Sparkles aria-hidden="true" />
                <span>{suggestion}</span>
                <ChevronRight aria-hidden="true" />
              </button>
            ))}
          </div>
        </div>
      ) : null}

      <div className="workspace-message-flow">
        {detail?.messages.map((message) => (
          <Message
            converting={convertingId === message.id}
            key={message.id}
            message={message}
            onConvertTask={(item) => void onConvert(item)}
            onRegenerate={(item) => void onRegenerate(item)}
            onRemember={(item) => void onRemember(item)}
            remembering={rememberingId === message.id}
            retryable={
              message.role === "assistant" &&
              message.id === retryableAssistantId
            }
            sending={sending}
          />
        ))}
        <div ref={messageEndRef} />
      </div>
    </div>
  );
}
