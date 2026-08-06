import { useMemo, useRef, useState, type KeyboardEvent } from "react";

import {
  cancelChatStream,
  createConversationKnowledgeCapture,
  createGrowthTask,
  getConversation,
  previewAgentRouting,
  rememberMessage,
  streamChatMessage,
  streamRegenerateMessage,
  type ChatMessage,
  type ConversationDetail,
  type ConversationSummary,
} from "@/lib/api";

import {
  deepSeekConfirmationText,
  newStreamRequestId,
  refreshConversationUntil,
  temporaryAssistantMessage,
  temporaryRegenerationId,
  temporaryUserMessage,
} from "@/components/chat/chat-utils";
import type { ChatList } from "@/components/chat/use-conversation-list";

export function useChatStream({
  list,
  makeConversation,
  stopDictation,
  input,
  setInput,
  setError,
}: {
  list: ChatList;
  makeConversation: () => Promise<ConversationSummary>;
  stopDictation: () => void;
  input: string;
  setInput: (value: string) => void;
  setError: (error: string | null) => void;
}) {
  const [sending, setSending] = useState(false);
  const [sensitive, setSensitive] = useState(false);
  const [useKnowledge, setUseKnowledge] = useState(true);
  const [memoryNotice, setMemoryNotice] = useState<string | null>(null);
  const [taskNotice, setTaskNotice] = useState<string | null>(null);
  const [captureNotice, setCaptureNotice] = useState<string | null>(null);
  const [capturing, setCapturing] = useState(false);
  const [rememberingId, setRememberingId] = useState<string | null>(null);
  const [convertingId, setConvertingId] = useState<string | null>(null);
  const [streamHasContent, setStreamHasContent] = useState(false);
  const streamControllerRef = useRef<AbortController | null>(null);
  const streamRequestIdRef = useRef<string | null>(null);

  const retryableAssistantId = useMemo(
    () =>
      [...(list.detail?.messages ?? [])]
        .reverse()
        .find((message) => message.role === "assistant")?.id ?? null,
    [list.detail?.messages],
  );

  async function submitMessage() {
    const content = input.trim();
    if (!content || sending) return;
    stopDictation();
    let routePreview: import("@/lib/api").AgentRouting | null = null;
    if (list.mode === "deep" && !sensitive) {
      try {
        routePreview = await previewAgentRouting({
          content,
          mode: list.mode,
          sensitive,
          paid_call_confirmed: false,
        });
        list.setAgentRouting(routePreview);
      } catch {
        routePreview = null;
      }
    }
    const paidCallConfirmed =
      list.mode === "deep" && !sensitive
        ? window.confirm(deepSeekConfirmationText(routePreview, "生成回答"))
        : false;
    if (list.mode === "deep" && !sensitive && !paidCallConfirmed) return;

    setSending(true);
    setStreamHasContent(false);
    setError(null);
    setMemoryNotice(null);
    setInput("");

    let targetId = list.activeId;
    let currentDetail = list.detail;
    try {
      if (!targetId) {
        const created = await makeConversation();
        targetId = created.id;
        currentDetail = { ...created, messages: [] };
      }

      const optimistic = temporaryUserMessage(targetId, content);
      const optimisticAssistant = temporaryAssistantMessage(targetId);
      list.setDetail({
        ...(currentDetail as ConversationDetail),
        messages: [
          ...(currentDetail?.messages ?? []),
          optimistic,
          optimisticAssistant,
        ],
      });

      const controller = new AbortController();
      const requestId = newStreamRequestId();
      streamControllerRef.current = controller;
      streamRequestIdRef.current = requestId;
      let streamedContent = "";

      await streamChatMessage(
        targetId,
        {
          content,
          mode: list.mode,
          sensitive,
          request_id: requestId,
          paid_call_confirmed: paidCallConfirmed,
          use_knowledge: useKnowledge,
        },
        {
          onMeta: (meta) => {
            list.setAgentRouting(meta.agent_routing ?? null);
            list.setDetail((current) =>
              current
                ? {
                    ...current,
                    messages: current.messages.map((message) => {
                      if (message.id === optimistic.id) {
                        return meta.user_message;
                      }
                      if (message.id === optimisticAssistant.id) {
                        return {
                          ...message,
                          provider: meta.routing.provider_used,
                          model: meta.routing.model_used,
                          metadata: {
                            ...message.metadata,
                            requested_provider:
                              meta.routing.requested_provider,
                            fallback_reason: meta.routing.fallback_reason,
                            knowledge_sources: meta.knowledge_sources,
                          },
                        };
                      }
                      return message;
                    }),
                  }
                : current,
            );
          },
          onDelta: (delta) => {
            streamedContent += delta;
            setStreamHasContent(true);
            list.setDetail((current) =>
              current
                ? {
                    ...current,
                    messages: current.messages.map((message) =>
                      message.id === optimisticAssistant.id
                        ? { ...message, content: streamedContent }
                        : message,
                    ),
                  }
                : current,
            );
          },
          onError: (message) => setError(message),
          onDone: (response) => {
            list.setAgentRouting(response.agent_routing ?? null);
            if (response.memory_candidates_created > 0) {
              setMemoryNotice(
                "已提取一条候选记忆，请到记忆中心确认后再让 Jarvis 使用。",
              );
            }
            list.setDetail((current) => ({
              ...response.conversation,
              messages: (current?.messages ?? []).map((message) => {
                if (
                  message.id === optimistic.id ||
                  message.id === response.user_message.id
                ) {
                  return response.user_message;
                }
                if (message.id === optimisticAssistant.id) {
                  return response.assistant_message;
                }
                return message;
              }),
            }));
            list.setConversations((current) => [
              response.conversation,
              ...current.filter(
                (item) => item.id !== response.conversation.id,
              ),
            ]);
          },
        },
        controller.signal,
      );
    } catch (sendError) {
      const wasStopped = streamControllerRef.current?.signal.aborted ?? false;
      if (!wasStopped) {
        setInput(content);
        setError(
          sendError instanceof Error ? sendError.message : "消息发送失败",
        );
      }
      if (targetId) {
        try {
          const expectedMessageCount =
            (currentDetail?.messages.length ?? 0) + 2;
          const refreshed = wasStopped
            ? await refreshConversationUntil(
                targetId,
                (conversation) =>
                  conversation.messages.length >= expectedMessageCount,
              )
            : await getConversation(targetId);
          list.setDetail(refreshed);
        } catch {
          // Keep the optimistic view if refreshing also fails.
        }
      }
    } finally {
      streamControllerRef.current = null;
      streamRequestIdRef.current = null;
      setStreamHasContent(false);
      setSending(false);
    }
  }

  async function stopGeneration() {
    const requestId = streamRequestIdRef.current;
    if (!requestId) {
      streamControllerRef.current?.abort();
      return;
    }
    try {
      await cancelChatStream(requestId);
    } catch {
      streamControllerRef.current?.abort();
    }
  }

  async function captureConversationKnowledge() {
    if (!list.activeId || sending || capturing) return;
    setCapturing(true);
    setCaptureNotice(null);
    setError(null);
    try {
      const capture = await createConversationKnowledgeCapture(list.activeId);
      setCaptureNotice(
        capture.status === "archived"
          ? "这轮对话已经沉淀到知识库。"
          : "本地 Qwen 已生成知识草稿，请检查和确认后再写入 Obsidian。",
      );
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "无法生成对话知识草稿",
      );
    } finally {
      setCapturing(false);
    }
  }

  async function regenerateMessage(message: ChatMessage) {
    if (!list.activeId || sending || message.role !== "assistant") return;
    const messageIndex =
      list.detail?.messages.findIndex((item) => item.id === message.id) ?? -1;
    const sourceContent =
      messageIndex > 0
        ? [...(list.detail?.messages.slice(0, messageIndex) ?? [])]
            .reverse()
            .find((item) => item.role === "user")?.content ?? "重新生成回答"
        : "重新生成回答";
    let routePreview: import("@/lib/api").AgentRouting | null = null;
    if (list.mode === "deep" && !sensitive) {
      try {
        routePreview = await previewAgentRouting({
          content: sourceContent,
          mode: list.mode,
          sensitive,
          paid_call_confirmed: false,
        });
        list.setAgentRouting(routePreview);
      } catch {
        routePreview = null;
      }
    }
    const paidCallConfirmed =
      list.mode === "deep" && !sensitive
        ? window.confirm(deepSeekConfirmationText(routePreview, "重新回答"))
        : false;
    if (list.mode === "deep" && !sensitive && !paidCallConfirmed) return;

    setSending(true);
    setStreamHasContent(false);
    setError(null);
    const optimisticId = temporaryRegenerationId(message.id);
    list.setDetail((current) =>
      current
        ? {
            ...current,
            messages: current.messages.map((item) =>
              item.id === message.id
                ? {
                    ...item,
                    id: optimisticId,
                    content: "",
                    status: "completed",
                    metadata: {
                      ...item.metadata,
                      streaming: true,
                      regenerating_from: message.id,
                    },
                  }
                : item,
            ),
          }
        : current,
    );

    const controller = new AbortController();
    const requestId = newStreamRequestId();
    streamControllerRef.current = controller;
    streamRequestIdRef.current = requestId;
    let streamedContent = "";
    try {
      await streamRegenerateMessage(
        list.activeId,
        message.id,
        {
          mode: list.mode,
          sensitive,
          request_id: requestId,
          paid_call_confirmed: paidCallConfirmed,
          use_knowledge: useKnowledge,
        },
        {
          onMeta: (meta) => {
            list.setAgentRouting(meta.agent_routing ?? null);
            list.setDetail((current) =>
              current
                ? {
                    ...current,
                    messages: current.messages.map((item) =>
                      item.id === optimisticId
                        ? {
                            ...item,
                            provider: meta.routing.provider_used,
                            model: meta.routing.model_used,
                            metadata: {
                              ...item.metadata,
                              requested_provider:
                                meta.routing.requested_provider,
                              fallback_reason: meta.routing.fallback_reason,
                              knowledge_sources: meta.knowledge_sources,
                            },
                          }
                        : item,
                    ),
                  }
                : current,
            );
          },
          onDelta: (delta) => {
            streamedContent += delta;
            setStreamHasContent(true);
            list.setDetail((current) =>
              current
                ? {
                    ...current,
                    messages: current.messages.map((item) =>
                      item.id === optimisticId
                        ? { ...item, content: streamedContent }
                        : item,
                    ),
                  }
                : current,
            );
          },
          onError: (messageText) => setError(messageText),
          onDone: (response) => {
            list.setAgentRouting(response.agent_routing ?? null);
            list.setDetail((current) => ({
              ...response.conversation,
              messages: (current?.messages ?? []).map((item) =>
                item.id === optimisticId ? response.assistant_message : item,
              ),
            }));
            list.setConversations((current) => [
              response.conversation,
              ...current.filter(
                (item) => item.id !== response.conversation.id,
              ),
            ]);
          },
        },
        controller.signal,
      );
    } catch (regenerateError) {
      const wasStopped = controller.signal.aborted;
      if (!wasStopped) {
        setError(
          regenerateError instanceof Error
            ? regenerateError.message
            : "重新回答失败",
        );
      }
      try {
        list.setDetail(
          wasStopped
            ? await refreshConversationUntil(
                list.activeId,
                (conversation) =>
                  [...conversation.messages]
                    .reverse()
                    .find((item) => item.role === "assistant")?.id !== message.id,
              )
            : await getConversation(list.activeId),
        );
      } catch {
        // Keep the streamed view when refreshing also fails.
      }
    } finally {
      streamControllerRef.current = null;
      streamRequestIdRef.current = null;
      setStreamHasContent(false);
      setSending(false);
    }
  }

  async function rememberChatMessage(message: ChatMessage) {
    if (
      rememberingId ||
      message.id.startsWith("pending-") ||
      message.id.startsWith("regenerating-")
    ) {
      return;
    }
    setRememberingId(message.id);
    setError(null);
    try {
      const result = await rememberMessage(message.id);
      setMemoryNotice(
        result.created
          ? "这条内容已加入长期记忆。默认只在本机使用。"
          : "这条内容已存在，并已按你的操作确认。",
      );
    } catch (rememberError) {
      setError(
        rememberError instanceof Error
          ? rememberError.message
          : "保存记忆失败",
      );
    } finally {
      setRememberingId(null);
    }
  }

  async function convertMessageToTask(message: ChatMessage) {
    if (
      convertingId ||
      message.id.startsWith("pending-") ||
      message.id.startsWith("regenerating-")
    ) {
      return;
    }
    const suggestedTitle = message.content
      .trim()
      .replaceAll("\n", " ")
      .slice(0, 120);
    const title = window.prompt("任务名称", suggestedTitle);
    if (title === null || !title.trim()) return;
    const minutesText = window.prompt("预计投入多少分钟？", "60");
    if (minutesText === null) return;
    const minutes = Number(minutesText);
    if (!Number.isInteger(minutes) || minutes < 5 || minutes > 1440) {
      setError("预计时长需要是 5～1440 分钟的整数。");
      return;
    }
    setConvertingId(message.id);
    setError(null);
    try {
      await createGrowthTask({
        title: title.trim(),
        description: `来源：对话消息\n\n${message.content}`,
        area: "personal",
        priority: 3,
        estimated_minutes: minutes,
        source_type: "conversation",
      });
      setTaskNotice("这条消息已转换为成长任务。");
    } catch (convertError) {
      setError(
        convertError instanceof Error ? convertError.message : "创建任务失败",
      );
    } finally {
      setConvertingId(null);
    }
  }

  function handleComposerKeyDown(
    event: KeyboardEvent<HTMLTextAreaElement>,
  ) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void submitMessage();
    }
  }

  return {
    sending,
    setSending,
    sensitive,
    setSensitive,
    useKnowledge,
    setUseKnowledge,
    memoryNotice,
    setMemoryNotice,
    taskNotice,
    setTaskNotice,
    captureNotice,
    setCaptureNotice,
    capturing,
    convertingId,
    rememberingId,
    streamHasContent,
    retryableAssistantId,
    submitMessage,
    stopGeneration,
    regenerateMessage,
    captureConversationKnowledge,
    rememberChatMessage,
    convertMessageToTask,
    handleComposerKeyDown,
  };
}
