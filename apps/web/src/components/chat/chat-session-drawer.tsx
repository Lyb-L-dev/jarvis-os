import { History, MessageSquarePlus, Search, X } from "lucide-react";
import { motion } from "motion/react";

import type { ConversationSummary } from "@/lib/api";

import { formatConversationTime } from "@/components/chat/chat-utils";

export function ChatSessionDrawer({
  conversations,
  activeId,
  loading,
  searchQuery,
  setSearchQuery,
  searching,
  onOpen,
  onNew,
  onClose,
}: {
  conversations: ConversationSummary[];
  activeId: string | null;
  loading: boolean;
  searchQuery: string;
  setSearchQuery: (value: string) => void;
  searching: boolean;
  onOpen: (conversation: ConversationSummary) => void;
  onNew: () => void;
  onClose: () => void;
}) {
  return (
    <>
      <motion.button
        animate={{ opacity: 1 }}
        aria-label="关闭对话记录"
        className="workspace-session-backdrop"
        initial={{ opacity: 0 }}
        onClick={onClose}
        type="button"
      />
      <motion.aside
        animate={{ opacity: 1, x: 0 }}
        aria-label="对话记录"
        aria-modal="true"
        className="workspace-session-drawer"
        initial={{ opacity: 0, x: -24 }}
        role="dialog"
        transition={{ damping: 30, stiffness: 280, type: "spring" }}
      >
        <div className="workspace-session-header">
          <div>
            <span>CONVERSATION MEMORY</span>
            <h2>对话记录</h2>
          </div>
          <button aria-label="关闭" onClick={onClose} type="button">
            <X aria-hidden="true" />
          </button>
        </div>

        <button
          className="workspace-new-session"
          onClick={onNew}
          type="button"
        >
          <MessageSquarePlus aria-hidden="true" />
          开始新任务
        </button>

        <div className="workspace-session-search">
          <Search aria-hidden="true" />
          <input
            aria-label="搜索对话"
            onChange={(event) => setSearchQuery(event.target.value)}
            placeholder="搜索标题、问题或回答"
            type="search"
            value={searchQuery}
          />
          {searching ? <i aria-label="正在搜索" /> : null}
        </div>

        <div className="workspace-session-list">
          {conversations.length === 0 && !loading ? (
            <div className="workspace-session-empty">
              <History aria-hidden="true" />
              <strong>
                {searchQuery ? "没有找到相关对话" : "对话记忆已经准备好"}
              </strong>
              <p>
                {searchQuery
                  ? "尝试使用问题、回答或标题中的关键词。"
                  : "发送第一条消息后，Jarvis 会在这里自动保存。"}
              </p>
            </div>
          ) : null}
          {conversations.map((conversation) => (
            <button
              className={conversation.id === activeId ? "is-active" : ""}
              key={conversation.id}
              onClick={() => onOpen(conversation)}
              type="button"
            >
              <div>
                <strong>{conversation.title}</strong>
                <time>
                  {formatConversationTime(conversation.last_message_at)}
                </time>
              </div>
              <p>{conversation.last_message_preview || "等待第一条消息"}</p>
              <span>
                {conversation.message_count} 条消息
                {conversation.has_summary ? " · 已生成摘要" : ""}
              </span>
            </button>
          ))}
        </div>
      </motion.aside>
    </>
  );
}
