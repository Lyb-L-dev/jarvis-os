"use client";

import type { KeyboardEvent, RefObject } from "react";
import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { AnimatePresence } from "motion/react";
import {
  Check,
  ChevronsLeftRight,
  History,
  Maximize2,
  Minimize2,
  PanelLeftClose,
  Pin,
  Plus,
  X,
} from "lucide-react";

import type { AIState } from "@/components/ai/AIStatus";
import { ChatComposerRegion } from "@/components/chat/chat-composer-region";
import { ChatMessageFlow } from "@/components/chat/chat-message-flow";
import { ChatSessionDrawer } from "@/components/chat/chat-session-drawer";
import { ChatWorkspaceHeader } from "@/components/chat/chat-workspace-header";
import { DialogWorkspacePanel } from "@/components/chat/dialog-workspace-panel";
import { MemoryCandidatePanel } from "@/components/chat/memory-candidate-panel";
import {
  WORKSPACE_PANELS,
  detectWorkspacePanels,
  panelsForSide,
  type WorkspacePanelId,
  type WorkspaceSide,
} from "@/components/chat/twin-workspace-config";
import {
  TwinWorkspacePanelContent,
  WorkspacePanelIcon,
} from "@/components/chat/twin-workspace-panels";
import { useTwinWorkspaceState } from "@/components/chat/use-twin-workspace-state";
import type { useChatStream } from "@/components/chat/use-chat-stream";
import type { useConversationList } from "@/components/chat/use-conversation-list";
import type { useVoiceLoop } from "@/components/chat/use-voice-loop";

import styles from "./twin-workspace.module.css";

type ConversationController = ReturnType<typeof useConversationList>;
type StreamController = ReturnType<typeof useChatStream>;
type VoiceController = ReturnType<typeof useVoiceLoop>;

const MOBILE_WORKSPACE_QUERY = "(max-width: 760px)";
const EMPTY_DECK_ICON: Record<WorkspaceSide, WorkspacePanelId> = {
  left: "career",
  right: "growth",
};

function subscribeToMobileWorkspace(callback: () => void) {
  const query = window.matchMedia(MOBILE_WORKSPACE_QUERY);
  query.addEventListener("change", callback);
  return () => query.removeEventListener("change", callback);
}

function getMobileWorkspaceSnapshot() {
  return window.matchMedia(MOBILE_WORKSPACE_QUERY).matches;
}

function getMobileWorkspaceServerSnapshot() {
  return false;
}

type TwinChatWorkspaceProps = {
  error: string | null;
  setError: (value: string | null) => void;
  input: string;
  setInput: (value: string) => void;
  list: ConversationController;
  stream: StreamController;
  voice: VoiceController;
  workspaceState: AIState;
  messageEndRef: RefObject<HTMLDivElement | null>;
  onStartNewConversation: () => void;
};

export function TwinChatWorkspace({
  error,
  setError,
  input,
  setInput,
  list,
  stream,
  voice,
  workspaceState,
  messageEndRef,
  onStartNewConversation,
}: TwinChatWorkspaceProps) {
  const workspace = useTwinWorkspaceState(list.activeId);
  const [menuSide, setMenuSide] = useState<WorkspaceSide | null>(null);
  const isMobile = useSyncExternalStore(
    subscribeToMobileWorkspace,
    getMobileWorkspaceSnapshot,
    getMobileWorkspaceServerSnapshot,
  );
  const lastMobileTriggerRef = useRef<HTMLButtonElement | null>(null);
  const processedUserMessageRef = useRef<string | null>(null);
  const activatePanelFromIntent = workspace.activatePanel;
  const closeMobileWorkspacePanel = workspace.closeMobilePanel;
  const workspaceHydrated = workspace.hydrated;
  const workspaceMobileOpenSide = workspace.mobileOpenSide;

  useEffect(() => {
    if (!workspaceHydrated) return;
    const latestUserMessage = [...(list.detail?.messages ?? [])]
      .reverse()
      .find((message) => message.role === "user");
    if (
      !latestUserMessage ||
      processedUserMessageRef.current === latestUserMessage.id
    ) {
      return;
    }
    processedUserMessageRef.current = latestUserMessage.id;
    detectWorkspacePanels(latestUserMessage.content).forEach((panelId) =>
      activatePanelFromIntent(panelId, "intent"),
    );
  }, [
    activatePanelFromIntent,
    list.detail?.messages,
    workspaceHydrated,
  ]);

  useEffect(() => {
    if (!isMobile || !workspaceMobileOpenSide) return;
    function handleEscape(event: globalThis.KeyboardEvent) {
      if (event.key !== "Escape") return;
      closeMobileWorkspacePanel();
      window.requestAnimationFrame(() => lastMobileTriggerRef.current?.focus());
    }
    window.addEventListener("keydown", handleEscape);
    return () => window.removeEventListener("keydown", handleEscape);
  }, [closeMobileWorkspacePanel, isMobile, workspaceMobileOpenSide]);

  function openMobilePanel(
    panelId: WorkspacePanelId,
    trigger: HTMLButtonElement,
  ) {
    const side = WORKSPACE_PANELS[panelId].side;
    lastMobileTriggerRef.current = trigger;
    workspace.activatePanel(panelId);
    workspace.openSide(side);
    window.requestAnimationFrame(() => {
      document
        .querySelector<HTMLElement>(
          `[data-workspace-deck][data-side="${side}"]`,
        )
        ?.focus();
    });
  }

  function openEmptyMobileSide(side: WorkspaceSide, trigger: HTMLButtonElement) {
    lastMobileTriggerRef.current = trigger;
    workspace.openSide(side);
    window.requestAnimationFrame(() => {
      document
        .querySelector<HTMLElement>(
          `[data-workspace-deck][data-side="${side}"]`,
        )
        ?.focus();
    });
  }

  function closeMobilePanel() {
    workspace.closeMobilePanel();
    window.requestAnimationFrame(() => lastMobileTriggerRef.current?.focus());
  }

  function revealPanelsForPrompt(prompt: string) {
    detectWorkspacePanels(prompt).forEach((panelId) =>
      workspace.activatePanel(panelId, "intent"),
    );
  }

  function submitComposer() {
    const prompt = input.trim();
    if (!prompt) return;
    revealPanelsForPrompt(prompt);
    void stream.submitMessage();
  }

  function submitPanelPrompt(prompt: string) {
    revealPanelsForPrompt(prompt);
    void stream.submitMessage(prompt);
  }

  function handleComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submitComposer();
    }
  }

  return (
    <main
      className={styles.twinWorkspace}
      data-focus={workspace.focusSide ?? "both"}
      data-mobile-open={workspace.mobileOpenSide ?? "none"}
    >
      <template
        data-design-contract="jarvis-chat-twin-v3-4b"
        data-thesis="Conversation is the operating system; contextual evidence and executable outcomes assemble around it only when the task calls for them."
        data-own-world="Jarvis OS stays dark, technical, restrained, and evidence-led, extending the established application shell and chat primitives."
        data-story="Start with uninterrupted dialogue, reveal relevant context on the left, reveal actions and results on the right, then let the user focus, stack, pin, or dismiss panels."
        data-first-viewport="The central real chat owns the first viewport; empty wings invite task-driven activation without turning the page into a module dashboard."
        data-form="User-approved hybrid of prototype A balanced wings, B focus rails, and C stacked cards."
        data-finish="unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, and DESIGN.md"
        data-provenance="Selected from /chat?variant=A/B/C on 2026-08-10; no concept-seed run was used or claimed."
      />
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
            onNew={onStartNewConversation}
            onClose={() => list.setShowSessions(false)}
          />
        ) : null}
      </AnimatePresence>

      <WorkspaceDeck
        activeIds={workspace.left}
        disabled={stream.sending}
        focusSide={workspace.focusSide}
        isMobile={isMobile}
        menuOpen={menuSide === "left"}
        mobileOpenSide={workspace.mobileOpenSide}
        pinned={workspace.pinned}
        side="left"
        onActivate={workspace.activatePanel}
        onClose={workspace.closePanel}
        onCloseMobile={closeMobilePanel}
        onFocus={workspace.openSide}
        onMenuChange={(open) => setMenuSide(open ? "left" : null)}
        onShowBoth={workspace.showBothSides}
        onSync={submitPanelPrompt}
        onTogglePin={workspace.togglePin}
      />

      <WorkspaceRail
        activeIds={workspace.left}
        side="left"
        onActivate={(panelId) => {
          workspace.activatePanel(panelId);
          workspace.openSide("left");
        }}
      />

      <section className={styles.conversationCore} aria-label="Jarvis 中央对话">
        <div className={styles.workspaceCommandBar}>
          <span>
            <i data-state={workspaceState} />
            双翼工作台
          </span>
          <div>
            {workspace.focusSide ? (
              <button onClick={workspace.showBothSides} type="button">
                <ChevronsLeftRight aria-hidden="true" />
                双侧展开
              </button>
            ) : null}
            <button onClick={() => list.setShowSessions(true)} type="button">
              <History aria-hidden="true" />
              对话记录
            </button>
            <button
              disabled={stream.sending}
              onClick={onStartNewConversation}
              type="button"
            >
              <Plus aria-hidden="true" />
              新对话
            </button>
          </div>
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
          label="CURRENT CONVERSATION"
        />

        <div className={styles.conversationNotices}>
          <DialogWorkspacePanel />
          <MemoryCandidatePanel />
        </div>

        <section className={styles.conversationTranscript}>
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
            onToggleVoice={() => {
              if (stream.sending) void stream.stopGeneration();
              voice.toggle();
            }}
            input={input}
            setInput={setInput}
            sending={stream.sending}
            onSend={submitComposer}
            onStop={() => void stream.stopGeneration()}
            mode={list.mode}
            setMode={list.setMode}
            sensitive={stream.sensitive}
            setSensitive={stream.setSensitive}
            useKnowledge={stream.useKnowledge}
            setUseKnowledge={stream.setUseKnowledge}
            onComposerKeyDown={handleComposerKeyDown}
          />
        </section>
      </section>

      <WorkspaceRail
        activeIds={workspace.right}
        side="right"
        onActivate={(panelId) => {
          workspace.activatePanel(panelId);
          workspace.openSide("right");
        }}
      />

      <WorkspaceDeck
        activeIds={workspace.right}
        disabled={stream.sending}
        focusSide={workspace.focusSide}
        isMobile={isMobile}
        menuOpen={menuSide === "right"}
        mobileOpenSide={workspace.mobileOpenSide}
        pinned={workspace.pinned}
        side="right"
        onActivate={workspace.activatePanel}
        onClose={workspace.closePanel}
        onCloseMobile={closeMobilePanel}
        onFocus={workspace.openSide}
        onMenuChange={(open) => setMenuSide(open ? "right" : null)}
        onShowBoth={workspace.showBothSides}
        onSync={submitPanelPrompt}
        onTogglePin={workspace.togglePin}
      />

      <MobilePanelSwitcher
        leftIds={workspace.left}
        rightIds={workspace.right}
        onActivate={openMobilePanel}
        onOpenEmptySide={openEmptyMobileSide}
      />
    </main>
  );
}

type WorkspaceDeckProps = {
  side: WorkspaceSide;
  activeIds: WorkspacePanelId[];
  pinned: WorkspacePanelId[];
  disabled: boolean;
  focusSide: WorkspaceSide | null;
  isMobile: boolean;
  menuOpen: boolean;
  mobileOpenSide: WorkspaceSide | null;
  onActivate: (panelId: WorkspacePanelId, source?: "manual" | "intent") => void;
  onClose: (panelId: WorkspacePanelId) => void;
  onCloseMobile: () => void;
  onFocus: (side: WorkspaceSide) => void;
  onMenuChange: (open: boolean) => void;
  onShowBoth: () => void;
  onSync: (prompt: string) => void;
  onTogglePin: (panelId: WorkspacePanelId) => void;
};

function WorkspaceDeck({
  side,
  activeIds,
  pinned,
  disabled,
  focusSide,
  isMobile,
  menuOpen,
  mobileOpenSide,
  onActivate,
  onClose,
  onCloseMobile,
  onFocus,
  onMenuChange,
  onShowBoth,
  onSync,
  onTogglePin,
}: WorkspaceDeckProps) {
  const activeId = activeIds[0] ?? null;
  const sideTitle = side === "left" ? "资料与上下文" : "行动与结果";

  return (
    <aside
      aria-hidden={isMobile && mobileOpenSide !== side ? true : undefined}
      className={styles.workspaceDeck}
      data-side={side}
      data-workspace-deck
      inert={isMobile && mobileOpenSide !== side}
      tabIndex={-1}
    >
      <header className={styles.deckHeader}>
        <div>
          <strong>{sideTitle}</strong>
          <span>{activeIds.length}/3</span>
        </div>
        <div className={styles.deckControls}>
          <button
            aria-label={focusSide === side ? "恢复双侧展开" : `聚焦${sideTitle}`}
            onClick={() => (focusSide === side ? onShowBoth() : onFocus(side))}
            type="button"
          >
            {focusSide === side ? <Minimize2 /> : <Maximize2 />}
          </button>
          <button
            aria-expanded={menuOpen}
            aria-label={`打开${sideTitle}面板选择器`}
            onClick={() => onMenuChange(!menuOpen)}
            type="button"
          >
            <Plus />
          </button>
          <button
            aria-label="在手机上收起功能面板"
            className={styles.mobileDeckClose}
            onClick={onCloseMobile}
            type="button"
          >
            <PanelLeftClose />
          </button>
        </div>
      </header>

      {menuOpen ? (
        <div className={styles.panelMenu}>
          {panelsForSide(side).map((panel) => {
            const isOpen = activeIds.includes(panel.id);
            return (
              <button
                key={panel.id}
                onClick={() => {
                  onActivate(panel.id);
                  onMenuChange(false);
                }}
                type="button"
              >
                <span data-tone={panel.tone}>
                  <WorkspacePanelIcon panelId={panel.id} />
                </span>
                <span>
                  <strong>{panel.title}</strong>
                  <small>{isOpen ? "已在工作区" : panel.description}</small>
                </span>
                {isOpen ? <Check aria-hidden="true" /> : null}
              </button>
            );
          })}
        </div>
      ) : null}

      {activeId ? (
        <div className={styles.deckStage}>
          <div className={styles.deckBackStack} aria-label="后台面板">
            {activeIds.slice(1).map((panelId, index) => {
              const panel = WORKSPACE_PANELS[panelId];
              return (
                <button
                  data-depth={index + 1}
                  data-tone={panel.tone}
                  key={panel.id}
                  onClick={() => onActivate(panel.id)}
                  type="button"
                >
                  <WorkspacePanelIcon panelId={panel.id} />
                  <span>{panel.shortTitle}</span>
                  {pinned.includes(panel.id) ? <Pin aria-hidden="true" /> : null}
                </button>
              );
            })}
          </div>

          <WorkspacePanelCard
            disabled={disabled}
            panelId={activeId}
            pinned={pinned.includes(activeId)}
            onClose={() => onClose(activeId)}
            onSync={onSync}
            onTogglePin={() => onTogglePin(activeId)}
          />
        </div>
      ) : (
        <div className={styles.emptyDeck}>
          <WorkspacePanelIcon panelId={EMPTY_DECK_ICON[side]} />
          <strong>这一侧暂时没有面板</strong>
          <p>在对话中提到相关目标，或使用上方加号重新打开。</p>
          <button onClick={() => onMenuChange(true)} type="button">
            选择面板
          </button>
        </div>
      )}
    </aside>
  );
}

function WorkspacePanelCard({
  panelId,
  pinned,
  disabled,
  onClose,
  onSync,
  onTogglePin,
}: {
  panelId: WorkspacePanelId;
  pinned: boolean;
  disabled: boolean;
  onClose: () => void;
  onSync: (prompt: string) => void;
  onTogglePin: () => void;
}) {
  const panel = WORKSPACE_PANELS[panelId];
  return (
    <section className={styles.workspacePanelCard} data-tone={panel.tone}>
      <header className={styles.panelCardHeader}>
        <span className={styles.panelCardIcon}>
          <WorkspacePanelIcon panelId={panelId} />
        </span>
        <div>
          <h2>{panel.title}</h2>
          <p>{panel.description}</p>
        </div>
        <div className={styles.panelCardControls}>
          <button
            aria-label={pinned ? `取消固定${panel.title}` : `固定${panel.title}`}
            aria-pressed={pinned}
            className={pinned ? styles.panelPinned : ""}
            onClick={onTogglePin}
            type="button"
          >
            <Pin />
          </button>
          <button aria-label={`关闭${panel.title}`} onClick={onClose} type="button">
            <X />
          </button>
        </div>
      </header>
      <TwinWorkspacePanelContent
        disabled={disabled}
        onSync={onSync}
        panelId={panelId}
      />
    </section>
  );
}

function WorkspaceRail({
  side,
  activeIds,
  onActivate,
}: {
  side: WorkspaceSide;
  activeIds: WorkspacePanelId[];
  onActivate: (panelId: WorkspacePanelId) => void;
}) {
  return (
    <aside className={styles.workspaceRail} data-side={side}>
      <span>{side === "left" ? "资料" : "行动"}</span>
      {activeIds.map((panelId) => {
        const panel = WORKSPACE_PANELS[panelId];
        return (
          <button
            aria-label={`打开${panel.title}`}
            data-tone={panel.tone}
            key={panel.id}
            onClick={() => onActivate(panel.id)}
            title={panel.title}
            type="button"
          >
            <WorkspacePanelIcon panelId={panel.id} />
            <small>{panel.shortTitle}</small>
          </button>
        );
      })}
    </aside>
  );
}

function MobilePanelSwitcher({
  leftIds,
  rightIds,
  onActivate,
  onOpenEmptySide,
}: {
  leftIds: WorkspacePanelId[];
  rightIds: WorkspacePanelId[];
  onActivate: (panelId: WorkspacePanelId, trigger: HTMLButtonElement) => void;
  onOpenEmptySide: (side: WorkspaceSide, trigger: HTMLButtonElement) => void;
}) {
  const activeIds = [...leftIds, ...rightIds];
  return (
    <nav className={styles.mobilePanelSwitcher} aria-label="功能面板切换">
      {activeIds.map((panelId) => {
        const panel = WORKSPACE_PANELS[panelId];
        return (
          <button
            aria-label={`打开${panel.title}`}
            data-tone={panel.tone}
            key={panelId}
            onClick={(event) => onActivate(panelId, event.currentTarget)}
            type="button"
          >
            <WorkspacePanelIcon panelId={panelId} />
            <span>{panel.shortTitle}</span>
          </button>
        );
      })}
      {activeIds.length === 0 ? (
        <>
          <button
            aria-label="打开资料面板选择器"
            onClick={(event) => onOpenEmptySide("left", event.currentTarget)}
            type="button"
          >
            <Plus aria-hidden="true" />
            <span>资料</span>
          </button>
          <button
            aria-label="打开行动面板选择器"
            onClick={(event) => onOpenEmptySide("right", event.currentTarget)}
            type="button"
          >
            <Plus aria-hidden="true" />
            <span>行动</span>
          </button>
        </>
      ) : null}
    </nav>
  );
}
