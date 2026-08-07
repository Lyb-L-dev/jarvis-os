"use client";

import { useEffect, useRef, useState } from "react";
import { AnimatePresence } from "motion/react";

import type { AIState } from "@/components/ai/AIStatus";
import { ChatComposerRegion } from "@/components/chat/chat-composer-region";
import { ChatMessageFlow } from "@/components/chat/chat-message-flow";
import { ChatSessionDrawer } from "@/components/chat/chat-session-drawer";
import { ChatWorkspaceHeader } from "@/components/chat/chat-workspace-header";
import { ChatWorkspaceInspector } from "@/components/chat/chat-workspace-inspector";
import { DialogWorkspacePanel } from "@/components/chat/dialog-workspace-panel";
import { useChatStream } from "@/components/chat/use-chat-stream";
import { useConversationList } from "@/components/chat/use-conversation-list";
import { useDictation } from "@/components/chat/use-dictation";

export function ChatWorkspace() {
  const [error, setError] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const messageEndRef = useRef<HTMLDivElement>(null);

  const list = useConversationList({ setError });
  const dictation = useDictation({ input, setInput, setError });
  const stream = useChatStream({
    list,
    makeConversation: list.makeConversation,
    stopDictation: dictation.stopDictation,
    input,
    setInput,
    setError,
  });

  const workspaceState: AIState = dictation.listening
    ? "listening"
    : stream.sending
      ? stream.streamHasContent
        ? "speaking"
        : "thinking"
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

  return (
    <main className="chat-page workspace-page">
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
        />

        <DialogWorkspacePanel />

        <div className="workspace-body">
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
              listening={dictation.listening}
              onToggleDictation={dictation.toggleDictation}
              input={input}
              setInput={setInput}
              sending={stream.sending}
              onSend={() => void stream.submitMessage()}
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
