import { useEffect, useMemo, useState } from "react";

import {
  archiveConversation,
  createConversation,
  getConversation,
  listConversations,
  renameConversation,
  type AgentRouting,
  type ConversationDetail,
  type ConversationSummary,
  type ModelMode,
} from "@/lib/api";

import {
  modeOptions,
  savedAgentRouting,
} from "@/components/chat/chat-utils";

export function useConversationList({
  setError,
}: {
  setError: (error: string | null) => void;
}) {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [detail, setDetail] = useState<ConversationDetail | null>(null);
  const [mode, setMode] = useState<ModelMode>("standard");
  const [agentRouting, setAgentRouting] = useState<AgentRouting | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const [loading, setLoading] = useState(true);
  const [showSessions, setShowSessions] = useState(false);
  const [renaming, setRenaming] = useState(false);
  const [renameSaving, setRenameSaving] = useState(false);
  const [titleDraft, setTitleDraft] = useState("");

  const activeMode = useMemo(
    () => modeOptions.find((option) => option.value === mode) ?? modeOptions[0],
    [mode],
  );

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const items = await listConversations();
        if (cancelled) return;
        setConversations(items);
        if (items[0]) {
          const conversation = await getConversation(items[0].id);
          if (cancelled) return;
          setActiveId(items[0].id);
          setDetail(conversation);
          setAgentRouting(savedAgentRouting(conversation));
          setMode(conversation.model_mode);
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(
            loadError instanceof Error
              ? loadError.message
              : "无法载入对话记录",
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [setError]);

  useEffect(() => {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => {
      setSearching(true);
      listConversations(controller.signal, searchQuery)
        .then(setConversations)
        .catch((searchError: unknown) => {
          if (
            searchError instanceof DOMException &&
            searchError.name === "AbortError"
          ) {
            return;
          }
          setError(
            searchError instanceof Error
              ? searchError.message
              : "搜索对话失败",
          );
        })
        .finally(() => {
          if (!controller.signal.aborted) setSearching(false);
        });
    }, 250);
    return () => {
      window.clearTimeout(timeout);
      controller.abort();
    };
  }, [searchQuery, setError]);

  useEffect(() => {
    if (!showSessions) return;
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setShowSessions(false);
    };
    window.addEventListener("keydown", handleEscape);
    return () => window.removeEventListener("keydown", handleEscape);
  }, [showSessions]);

  async function openConversation(conversation: ConversationSummary) {
    if (conversation.id === activeId) return;
    setError(null);
    setLoading(true);
    try {
      const nextDetail = await getConversation(conversation.id);
      setActiveId(conversation.id);
      setDetail(nextDetail);
      setAgentRouting(savedAgentRouting(nextDetail));
      setMode(nextDetail.model_mode);
      setShowSessions(false);
    } catch (openError) {
      setError(
        openError instanceof Error ? openError.message : "无法打开这个对话",
      );
    } finally {
      setLoading(false);
    }
  }

  async function makeConversation() {
    setError(null);
    const conversation = await createConversation({ model_mode: mode });
    setConversations((current) => [conversation, ...current]);
    setActiveId(conversation.id);
    setDetail({ ...conversation, messages: [] });
    return conversation;
  }

  async function archiveActiveConversation() {
    if (!activeId) return;
    if (!window.confirm("归档这个对话？记录不会删除，后续可以恢复。")) {
      return;
    }
    setError(null);
    try {
      await archiveConversation(activeId);
      const remaining = conversations.filter((item) => item.id !== activeId);
      setConversations(remaining);
      if (remaining[0]) {
        const nextDetail = await getConversation(remaining[0].id);
        setActiveId(remaining[0].id);
        setDetail(nextDetail);
        setMode(nextDetail.model_mode);
      } else {
        setActiveId(null);
        setDetail(null);
      }
    } catch (archiveError) {
      setError(
        archiveError instanceof Error ? archiveError.message : "归档对话失败",
      );
    }
  }

  function beginRename() {
    if (!detail) return;
    setTitleDraft(detail.title);
    setRenaming(true);
  }

  async function saveTitle() {
    const title = titleDraft.trim();
    if (!detail || !title || renameSaving) return;
    setRenameSaving(true);
    setError(null);
    try {
      const updated = await renameConversation(detail.id, title);
      setDetail((current) =>
        current ? { ...current, ...updated, messages: current.messages } : current,
      );
      setConversations((current) =>
        current.map((conversation) =>
          conversation.id === updated.id ? updated : conversation,
        ),
      );
      setRenaming(false);
    } catch (renameError) {
      setError(
        renameError instanceof Error ? renameError.message : "重命名失败",
      );
    } finally {
      setRenameSaving(false);
    }
  }

  return {
    conversations,
    setConversations,
    activeId,
    detail,
    setDetail,
    mode,
    setMode,
    agentRouting,
    setAgentRouting,
    searchQuery,
    setSearchQuery,
    searching,
    loading,
    showSessions,
    setShowSessions,
    renaming,
    setRenaming,
    renameSaving,
    titleDraft,
    setTitleDraft,
    activeMode,
    openConversation,
    makeConversation,
    archiveActiveConversation,
    beginRename,
    saveTitle,
  };
}

export type ChatList = ReturnType<typeof useConversationList>;
