"use client";

import { useEffect, useRef, useState } from "react";
import { AnimatePresence } from "motion/react";
import {
  ChevronRight,
  History,
  MessageSquareText,
  Plus,
  Sparkles,
} from "lucide-react";

import type { AIState } from "@/components/ai/AIStatus";
import { ChatComposerRegion } from "@/components/chat/chat-composer-region";
import { ChatMessageFlow } from "@/components/chat/chat-message-flow";
import { ChatSessionDrawer } from "@/components/chat/chat-session-drawer";
import { ChatWorkspaceHeader } from "@/components/chat/chat-workspace-header";
import { ChatWorkspaceInspector } from "@/components/chat/chat-workspace-inspector";
import { DialogWorkspacePanel } from "@/components/chat/dialog-workspace-panel";
import { MemoryCandidatePanel } from "@/components/chat/memory-candidate-panel";
import { TwinChatWorkspace } from "@/components/chat/twin-chat-workspace";
import { useChatStream } from "@/components/chat/use-chat-stream";
import { useConversationList } from "@/components/chat/use-conversation-list";
import { useVoiceLoop } from "@/components/chat/use-voice-loop";
import styles from "@/components/v3-convergence.module.css";
import { recordDesktopReliability } from "@/lib/desktop-reliability";

function formatTimelineDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "最近";
  return new Intl.DateTimeFormat("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function todayLabel() {
  return new Intl.DateTimeFormat("zh-CN", {
    dateStyle: "full",
  }).format(new Date());
}

export function ChatWorkspace({
  layout = "timeline",
}: {
  layout?: "timeline" | "twin";
}) {
  const [error, setError] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const messageEndRef = useRef<HTMLDivElement>(null);
  const cancelVoiceRef = useRef<() => void>(() => undefined);
  const fileAnalysisPendingRef = useRef(false);

  const list = useConversationList({ setError });
  const openConversationByIdRef = useRef(list.openConversationById);

  useEffect(() => {
    openConversationByIdRef.current = list.openConversationById;
  }, [list.openConversationById]);

  const stream = useChatStream({
    list,
    makeConversation: list.makeConversation,
    stopDictation: () => cancelVoiceRef.current(),
    input,
    setInput,
    setError,
    onSubmitResult: ({ outcome, durationMs }) => {
      if (!fileAnalysisPendingRef.current) return;
      recordDesktopReliability({ kind: "file_analyze", outcome, durationMs });
      if (outcome === "succeeded") fileAnalysisPendingRef.current = false;
    },
  });
  const voice = useVoiceLoop({
    setInput,
    setError,
    onTranscript: stream.submitMessage,
  });
  const setConversationMode = list.setMode;
  const setSensitive = stream.setSensitive;
  const setUseKnowledge = stream.setUseKnowledge;

  useEffect(() => {
    type TauriCore = { invoke: <T>(command: string, args?: Record<string, unknown>) => Promise<T> };
    const core = (window as typeof window & { __TAURI__?: { core?: TauriCore } }).__TAURI__?.core;
    if (!core) return;
    void core.invoke("desktop_update_set_activity", { busy: stream.sending });
    return () => {
      void core.invoke("desktop_update_set_activity", { busy: false });
    };
  }, [stream.sending]);

  useEffect(() => {
    type DesktopOpenDetail = {
      conversationId?: string | null;
      draft?: string | null;
      localOnly?: boolean;
    };
    const consume = (detail?: DesktopOpenDetail | null) => {
      if (!detail) return;
      if (detail.draft) setInput(detail.draft);
      if (detail.localOnly) {
        fileAnalysisPendingRef.current = true;
        setConversationMode("local");
        setSensitive(true);
        setUseKnowledge(false);
      }
      if (detail.conversationId) void openConversationByIdRef.current(detail.conversationId);
      delete (window as typeof window & { __JARVIS_DESKTOP_OPEN__?: DesktopOpenDetail }).__JARVIS_DESKTOP_OPEN__;
    };
    const target = window as typeof window & { __JARVIS_DESKTOP_OPEN__?: DesktopOpenDetail };
    consume(target.__JARVIS_DESKTOP_OPEN__);
    const listener = (event: Event) => consume((event as CustomEvent<DesktopOpenDetail>).detail);
    window.addEventListener("jarvis:open-conversation", listener);
    return () => window.removeEventListener("jarvis:open-conversation", listener);
  }, [setConversationMode, setSensitive, setUseKnowledge]);

  useEffect(() => {
    cancelVoiceRef.current = voice.cancel;
  }, [voice.cancel]);

  const workspaceState: AIState = voice.state === "listening"
    ? "listening"
    : voice.state === "transcribing" ||
        voice.state === "responding" ||
        stream.sending
      ? stream.streamHasContent
        ? "speaking"
        : "thinking"
      : voice.state === "speaking"
        ? "speaking"
      : error
        ? "error"
        : "idle";

  useEffect(() => {
    messageEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [list.detail?.messages, stream.sending]);

  async function startNewConversation() {
    if (stream.sending) return;
    try {
      await list.makeConversation();
      setInput("");
      list.setShowSessions(false);
    } catch (createError) {
      setError(
        createError instanceof Error ? createError.message : "创建对话失败",
      );
    }
  }

  if (layout === "twin") {
    return (
      <TwinChatWorkspace
        error={error}
        setError={setError}
        input={input}
        setInput={setInput}
        list={list}
        stream={stream}
        voice={voice}
        workspaceState={workspaceState}
        messageEndRef={messageEndRef}
        onStartNewConversation={() => void startNewConversation()}
      />
    );
  }

  const recentConversations = list.conversations
    .filter((conversation) => conversation.id !== list.activeId)
    .slice(0, 2);

  return (
    <main className={`chat-page workspace-page ${styles.chatTimeline}`}>
      <AnimatePresence>
        {list.showSessions ? (
          <ChatSessionDrawer
            conversations={list.conversations}
            activeId={list.activeId}
            loading={list.loading}
            searchQuery={list.searchQuery}
            setSearchQuery={list.setSearchQuery}
            searching={list.searching}
            onOpen={(conversation) => {
              if (!stream.sending) void list.openConversation(conversation);
            }}
            onNew={() => void startNewConversation()}
            onClose={() => list.setShowSessions(false)}
          />
        ) : null}
      </AnimatePresence>

      <section className="chat-main ai-workspace">
        <header className={styles.timelineLead}>
          <div>
            <h1>今天</h1>
            <p>{todayLabel()}</p>
          </div>
          <div className={styles.timelineLeadActions}>
            <button onClick={() => list.setShowSessions(true)} type="button">
              <History aria-hidden="true" />
              对话记录
            </button>
            <button
              className={styles.timelinePrimaryAction}
              disabled={stream.sending}
              onClick={() => void startNewConversation()}
              type="button"
            >
              <Plus aria-hidden="true" />
              新对话
            </button>
          </div>
        </header>

        <div className={styles.timelineLayout}>
          <section className={styles.timelineFeed} aria-label="对话时间流">
            {recentConversations.map((conversation) => (
              <div className={styles.timelineRow} key={conversation.id}>
                <div className={styles.timeRail}>
                  <time>{formatTimelineDate(conversation.last_message_at)}</time>
                  <i />
                </div>
                <button
                  className={styles.timelineHistoryEvent}
                  disabled={stream.sending}
                  onClick={() => void list.openConversation(conversation)}
                  type="button"
                >
                  <span className={styles.eventMeta}>
                    <span><MessageSquareText aria-hidden="true" /> 对话</span>
                    <small>{conversation.model_mode} · {conversation.message_count} 条消息</small>
                  </span>
                  <strong>{conversation.title}</strong>
                  <p>{conversation.last_message_preview || "打开这段对话，继续之前的思路。"}</p>
                  <ChevronRight aria-hidden="true" />
                </button>
              </div>
            ))}

            <div className={styles.timelineRow}>
              <div className={styles.timeRail}>
                <time>{list.detail ? formatTimelineDate(list.detail.last_message_at) : "现在"}</time>
                <i className={styles.activeTimeDot} />
              </div>
              <article className={styles.activeEvent}>
                <div className={styles.eventMeta}>
                  <span><Sparkles aria-hidden="true" /> 当前对话</span>
                  <small>{list.agentRouting?.agent_name || "Jarvis Core"} · {stream.sending ? "回应中" : "就绪"}</small>
                </div>

                <ChatWorkspaceHeader
                  detail={list.detail}
                  sending={stream.sending}
                  renaming={list.renaming}
                  setRenaming={list.setRenaming}
                  titleDraft={list.titleDraft}
                  setTitleDraft={list.setTitleDraft}
                  renameSaving={list.renameSaving}
                  onSaveTitle={() => void list.saveTitle()}
                  onBeginRename={() => {
                    if (!stream.sending) list.beginRename();
                  }}
                  agentRouting={list.agentRouting}
                  onOpenSessions={() => list.setShowSessions(true)}
                  capturing={stream.capturing}
                  onCapture={() => void stream.captureConversationKnowledge()}
                  onArchive={() => {
                    if (!stream.sending) void list.archiveActiveConversation();
                  }}
                  showSessionsButton={false}
                  label={null}
                />

                <DialogWorkspacePanel />
                <MemoryCandidatePanel />

                <section className="workspace-transcript">
                  <ChatMessageFlow
                    loading={list.loading}
                    detail={list.detail}
                    workspaceState={workspaceState}
                    onSelectSuggestion={setInput}
                    onRemember={(message) => void stream.rememberChatMessage(message)}
                    onConvert={(message) => void stream.convertMessageToTask(message)}
                    onRegenerate={(message) => void stream.regenerateMessage(message)}
                    rememberingId={stream.rememberingId}
                    convertingId={stream.convertingId}
                    sending={stream.sending}
                    retryableAssistantId={stream.retryableAssistantId}
                    messageEndRef={messageEndRef}
                  />

                  <ChatComposerRegion
                    error={error}
                    setError={setError}
                    memoryNotice={stream.memoryNotice}
                    setMemoryNotice={stream.setMemoryNotice}
                    taskNotice={stream.taskNotice}
                    setTaskNotice={stream.setTaskNotice}
                    captureNotice={stream.captureNotice}
                    setCaptureNotice={stream.setCaptureNotice}
                    voiceState={voice.state}
                    voiceAvailable={voice.available}
                    voiceReason={voice.status?.reason ?? null}
                    onStartVoice={() => {
                      if (stream.sending) void stream.stopGeneration();
                      void voice.startListening();
                    }}
                    onStopVoice={voice.stopListening}
                    onCancelVoice={voice.cancel}
                    input={input}
                    setInput={setInput}
                    sending={stream.sending}
                    onSend={() => {
                      void voice.submitConfirmedVoice(input).then((handled) => {
                        if (!handled) void stream.submitMessage();
                      });
                    }}
                    onStop={() => void stream.stopGeneration()}
                    mode={list.mode}
                    setMode={list.setMode}
                    sensitive={stream.sensitive}
                    setSensitive={stream.setSensitive}
                    useKnowledge={stream.useKnowledge}
                    setUseKnowledge={stream.setUseKnowledge}
                    onComposerKeyDown={stream.handleComposerKeyDown}
                  />
                </section>
              </article>
            </div>
          </section>

          <ChatWorkspaceInspector
            workspaceState={workspaceState}
            activeMode={list.activeMode}
            detail={list.detail}
            useKnowledge={stream.useKnowledge}
            sensitive={stream.sensitive}
          />
        </div>
      </section>
    </main>
  );
}
