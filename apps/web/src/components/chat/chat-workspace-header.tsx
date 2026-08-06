import { Archive, BookOpenCheck, Check, Menu } from "lucide-react";

import type { AgentRouting, ConversationDetail } from "@/lib/api";

import { AgentSelector } from "@/components/agents/AgentSelector";
import { displayAgentId } from "@/components/chat/chat-utils";

export function ChatWorkspaceHeader({
  detail,
  sending,
  renaming,
  setRenaming,
  titleDraft,
  setTitleDraft,
  renameSaving,
  onSaveTitle,
  onBeginRename,
  agentRouting,
  onOpenSessions,
  capturing,
  onCapture,
  onArchive,
}: {
  detail: ConversationDetail | null;
  sending: boolean;
  renaming: boolean;
  setRenaming: (value: boolean) => void;
  titleDraft: string;
  setTitleDraft: (value: string) => void;
  renameSaving: boolean;
  onSaveTitle: () => void;
  onBeginRename: () => void;
  agentRouting: AgentRouting | null;
  onOpenSessions: () => void;
  capturing: boolean;
  onCapture: () => void;
  onArchive: () => void;
}) {
  return (
    <header className="workspace-header">
      <div className="workspace-identity">
        <button
          aria-label="打开对话记录"
          className="workspace-sessions-button"
          onClick={onOpenSessions}
          type="button"
        >
          <Menu aria-hidden="true" />
          <span>对话记录</span>
        </button>
        <div>
          <span>AI WORKSPACE</span>
          {renaming && detail ? (
            <div className="workspace-title-editor">
              <input
                aria-label="对话标题"
                autoFocus
                disabled={renameSaving}
                maxLength={160}
                onChange={(event) => setTitleDraft(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") onSaveTitle();
                  if (event.key === "Escape") setRenaming(false);
                }}
                value={titleDraft}
              />
              <button
                disabled={!titleDraft.trim() || renameSaving}
                onClick={onSaveTitle}
                type="button"
              >
                保存
              </button>
              <button onClick={() => setRenaming(false)} type="button">
                取消
              </button>
            </div>
          ) : (
            <button
              className="workspace-title"
              disabled={!detail || sending}
              onClick={onBeginRename}
              type="button"
            >
              <strong>{detail?.title || "新的对话"}</strong>
              {detail ? <span>点击重命名</span> : null}
            </button>
          )}
        </div>
      </div>

      <AgentSelector
        activeAgent={displayAgentId(agentRouting)}
        modelHint={
          agentRouting
            ? `· 建议 ${agentRouting.model.recommended_provider}`
            : undefined
        }
        routeReason={agentRouting?.routing_reason}
        runtime={agentRouting?.runtime}
      />

      <div className="workspace-header-actions">
        {detail?.has_summary ? (
          <span className="workspace-summary-state">
            <Check aria-hidden="true" />
            摘要上下文
          </span>
        ) : null}
        {detail ? (
          <>
            <button
              disabled={sending || capturing || detail.message_count < 2}
              onClick={onCapture}
              title="将有价值的对话整理为待确认知识草稿"
              type="button"
            >
              <BookOpenCheck aria-hidden="true" />
              <span>{capturing ? "整理中…" : "沉淀知识"}</span>
            </button>
            <button
              disabled={sending}
              onClick={onArchive}
              title="归档当前对话"
              type="button"
            >
              <Archive aria-hidden="true" />
            </button>
          </>
        ) : null}
      </div>
    </header>
  );
}
