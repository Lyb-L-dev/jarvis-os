"use client";

import {
  archiveConversation,
  cancelChatStream,
  createConversationKnowledgeCapture,
  createConversation,
  createGrowthTask,
  getConversation,
  listConversations,
  previewAgentRouting,
  rememberMessage,
  renameConversation,
  streamChatMessage,
  streamRegenerateMessage,
  type AgentRouting,
  type ChatMessage,
  type ConversationDetail,
  type ConversationSummary,
  type ModelMode,
} from "@/lib/api";
import {
  Archive,
  BookOpenCheck,
  BrainCircuit,
  Check,
  ChevronRight,
  History,
  Layers3,
  LockKeyhole,
  Menu,
  MessageSquarePlus,
  Mic,
  Search,
  Send,
  ShieldCheck,
  Sparkles,
  Square,
  X,
} from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";

import {
  AgentSelector,
  type AgentId as DisplayAgentId,
} from "@/components/agents/AgentSelector";
import { AIStatus, type AIState } from "@/components/ai/AIStatus";
import { JarvisOrb } from "@/components/ai/JarvisOrb";
import { Message } from "@/components/chat/Message";

const modeOptions: Array<{
  value: ModelMode;
  label: string;
  detail: string;
}> = [
  { value: "standard", label: "标准", detail: "MiMo 主力 · 本地兜底" },
  { value: "deep", label: "深度", detail: "DeepSeek · 本地兜底" },
  { value: "local", label: "本地", detail: "Qwen3 4B" },
  { value: "auto", label: "自动", detail: "按任务智能选择" },
];

function formatConversationTime(value: string) {
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

type SpeechResultEvent = {
  results: ArrayLike<{
    0: { transcript: string };
  }>;
};

type SpeechRecognitionLike = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onresult: ((event: SpeechResultEvent) => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
};

type SpeechRecognitionConstructor = new () => SpeechRecognitionLike;

function temporaryUserMessage(
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

function temporaryAssistantMessage(conversationId: string): ChatMessage {
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

function temporaryRegenerationId(messageId: string) {
  return `regenerating-${messageId}-${Date.now()}`;
}

function displayAgentId(routing: AgentRouting | null): DisplayAgentId {
  if (!routing) return "general";
  if (routing.agent_id === "english_coach") return "english";
  if (routing.agent_id === "growth") return "growth";
  if (routing.agent_id === "research") return "research";
  return "general";
}

function savedAgentRouting(conversation: ConversationDetail): AgentRouting | null {
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

function deepSeekConfirmationText(
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

function newStreamRequestId() {
  return globalThis.crypto.randomUUID();
}

async function refreshConversationUntil(
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

export function ChatWorkspace() {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [detail, setDetail] = useState<ConversationDetail | null>(null);
  const [mode, setMode] = useState<ModelMode>("standard");
  const [agentRouting, setAgentRouting] = useState<AgentRouting | null>(null);
  const [sensitive, setSensitive] = useState(false);
  const [useKnowledge, setUseKnowledge] = useState(true);
  const [input, setInput] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [renaming, setRenaming] = useState(false);
  const [renameSaving, setRenameSaving] = useState(false);
  const [titleDraft, setTitleDraft] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [memoryNotice, setMemoryNotice] = useState<string | null>(null);
  const [taskNotice, setTaskNotice] = useState<string | null>(null);
  const [captureNotice, setCaptureNotice] = useState<string | null>(null);
  const [capturing, setCapturing] = useState(false);
  const [rememberingId, setRememberingId] = useState<string | null>(null);
  const [convertingId, setConvertingId] = useState<string | null>(null);
  const [showSessions, setShowSessions] = useState(false);
  const [listening, setListening] = useState(false);
  const [speechRiskAccepted, setSpeechRiskAccepted] = useState(false);
  const [streamHasContent, setStreamHasContent] = useState(false);
  const messageEndRef = useRef<HTMLDivElement>(null);
  const streamControllerRef = useRef<AbortController | null>(null);
  const streamRequestIdRef = useRef<string | null>(null);
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);

  const activeMode = useMemo(
    () => modeOptions.find((option) => option.value === mode) ?? modeOptions[0],
    [mode],
  );
  const retryableAssistantId = useMemo(
    () =>
      [...(detail?.messages ?? [])]
        .reverse()
        .find((message) => message.role === "assistant")?.id ?? null,
    [detail?.messages],
  );
  const workspaceState: AIState = listening
    ? "listening"
    : sending
      ? streamHasContent
        ? "speaking"
        : "thinking"
      : error
        ? "error"
        : "idle";

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
  }, []);

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
  }, [searchQuery]);

  useEffect(() => {
    messageEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [detail?.messages, sending]);

  useEffect(() => {
    if (!showSessions) return;
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setShowSessions(false);
    };
    window.addEventListener("keydown", handleEscape);
    return () => window.removeEventListener("keydown", handleEscape);
  }, [showSessions]);

  useEffect(
    () => () => {
      recognitionRef.current?.stop();
    },
    [],
  );

  async function openConversation(conversation: ConversationSummary) {
    if (sending || conversation.id === activeId) return;
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

  async function startNewConversation() {
    if (sending) return;
    try {
      await makeConversation();
      setInput("");
      setShowSessions(false);
    } catch (createError) {
      setError(
        createError instanceof Error ? createError.message : "创建对话失败",
      );
    }
  }

  async function archiveActiveConversation() {
    if (!activeId || sending) return;
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
    if (!detail || sending) return;
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

  async function submitMessage() {
    const content = input.trim();
    if (!content || sending) return;
    recognitionRef.current?.stop();
    let routePreview: AgentRouting | null = null;
    if (mode === "deep" && !sensitive) {
      try {
        routePreview = await previewAgentRouting({
          content,
          mode,
          sensitive,
          paid_call_confirmed: false,
        });
        setAgentRouting(routePreview);
      } catch {
        routePreview = null;
      }
    }
    const paidCallConfirmed =
      mode === "deep" && !sensitive
        ? window.confirm(deepSeekConfirmationText(routePreview, "生成回答"))
        : false;
    if (mode === "deep" && !sensitive && !paidCallConfirmed) return;

    setSending(true);
    setStreamHasContent(false);
    setError(null);
    setMemoryNotice(null);
    setInput("");

    let targetId = activeId;
    let currentDetail = detail;
    try {
      if (!targetId) {
        const created = await makeConversation();
        targetId = created.id;
        currentDetail = { ...created, messages: [] };
      }

      const optimistic = temporaryUserMessage(targetId, content);
      const optimisticAssistant = temporaryAssistantMessage(targetId);
      setDetail({
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
          mode,
          sensitive,
          request_id: requestId,
          paid_call_confirmed: paidCallConfirmed,
          use_knowledge: useKnowledge,
        },
        {
          onMeta: (meta) => {
            setAgentRouting(meta.agent_routing ?? null);
            setDetail((current) =>
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
            setDetail((current) =>
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
            setAgentRouting(response.agent_routing ?? null);
            if (response.memory_candidates_created > 0) {
              setMemoryNotice(
                "已提取一条候选记忆，请到记忆中心确认后再让 Jarvis 使用。",
              );
            }
            setDetail((current) => ({
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
            setConversations((current) => [
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
          setDetail(refreshed);
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
    if (!activeId || sending || capturing) return;
    setCapturing(true);
    setCaptureNotice(null);
    setError(null);
    try {
      const capture = await createConversationKnowledgeCapture(activeId);
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
    if (!activeId || sending || message.role !== "assistant") return;
    const messageIndex = detail?.messages.findIndex((item) => item.id === message.id) ?? -1;
    const sourceContent =
      messageIndex > 0
        ? [...(detail?.messages.slice(0, messageIndex) ?? [])]
            .reverse()
            .find((item) => item.role === "user")?.content ?? "重新生成回答"
        : "重新生成回答";
    let routePreview: AgentRouting | null = null;
    if (mode === "deep" && !sensitive) {
      try {
        routePreview = await previewAgentRouting({
          content: sourceContent,
          mode,
          sensitive,
          paid_call_confirmed: false,
        });
        setAgentRouting(routePreview);
      } catch {
        routePreview = null;
      }
    }
    const paidCallConfirmed =
      mode === "deep" && !sensitive
        ? window.confirm(deepSeekConfirmationText(routePreview, "重新回答"))
        : false;
    if (mode === "deep" && !sensitive && !paidCallConfirmed) return;

    setSending(true);
    setStreamHasContent(false);
    setError(null);
    const optimisticId = temporaryRegenerationId(message.id);
    setDetail((current) =>
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
        activeId,
        message.id,
        {
          mode,
          sensitive,
          request_id: requestId,
          paid_call_confirmed: paidCallConfirmed,
          use_knowledge: useKnowledge,
        },
        {
          onMeta: (meta) => {
            setAgentRouting(meta.agent_routing ?? null);
            setDetail((current) =>
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
            setDetail((current) =>
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
            setAgentRouting(response.agent_routing ?? null);
            setDetail((current) => ({
              ...response.conversation,
              messages: (current?.messages ?? []).map((item) =>
                item.id === optimisticId ? response.assistant_message : item,
              ),
            }));
            setConversations((current) => [
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
        setDetail(
          wasStopped
            ? await refreshConversationUntil(
                activeId,
                (conversation) =>
                  [...conversation.messages]
                    .reverse()
                    .find((item) => item.role === "assistant")?.id !== message.id,
              )
            : await getConversation(activeId),
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
    const suggestedTitle = message.content.trim().replaceAll("\n", " ").slice(0, 120);
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

  function toggleDictation() {
    if (listening) {
      recognitionRef.current?.stop();
      return;
    }
    if (
      !speechRiskAccepted &&
      !window.confirm(
        "浏览器语音转写可能调用浏览器或系统的在线语音服务。请勿口述密码、API Key 或其他敏感信息。是否继续？",
      )
    ) {
      return;
    }

    setSpeechRiskAccepted(true);
    const speechWindow = window as typeof window & {
      SpeechRecognition?: SpeechRecognitionConstructor;
      webkitSpeechRecognition?: SpeechRecognitionConstructor;
    };
    const Recognition =
      speechWindow.SpeechRecognition || speechWindow.webkitSpeechRecognition;
    if (!Recognition) {
      setError("当前浏览器不支持语音转写，请使用 Edge / Chrome 或继续键盘输入。");
      return;
    }

    const instance = new Recognition();
    const originalInput = input.trim();
    recognitionRef.current = instance;
    instance.lang = "zh-CN";
    instance.continuous = true;
    instance.interimResults = true;
    instance.onresult = (event) => {
      let transcript = "";
      for (let index = 0; index < event.results.length; index += 1) {
        transcript += event.results[index][0].transcript;
      }
      setInput(
        originalInput
          ? `${originalInput} ${transcript}`.trim()
          : transcript.trim(),
      );
    };
    instance.onerror = (event) => {
      setError(
        event.error === "not-allowed"
          ? "麦克风权限未开启，Jarvis 无法开始聆听。"
          : `语音转写中断：${event.error}`,
      );
    };
    instance.onend = () => {
      setListening(false);
      recognitionRef.current = null;
    };
    setError(null);
    setListening(true);
    instance.start();
  }

  function handleComposerKeyDown(
    event: React.KeyboardEvent<HTMLTextAreaElement>,
  ) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void submitMessage();
    }
  }

  return (
    <main className="chat-page workspace-page">
      <AnimatePresence>
        {showSessions ? (
          <>
            <motion.button
              animate={{ opacity: 1 }}
              aria-label="关闭对话记录"
              className="workspace-session-backdrop"
              initial={{ opacity: 0 }}
              onClick={() => setShowSessions(false)}
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
                <button
                  aria-label="关闭"
                  onClick={() => setShowSessions(false)}
                  type="button"
                >
                  <X aria-hidden="true" />
                </button>
              </div>

              <button
                className="workspace-new-session"
                onClick={() => void startNewConversation()}
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
                    className={
                      conversation.id === activeId ? "is-active" : ""
                    }
                    key={conversation.id}
                    onClick={() => void openConversation(conversation)}
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
        ) : null}
      </AnimatePresence>

      <section className="chat-main ai-workspace">
        <header className="workspace-header">
          <div className="workspace-identity">
            <button
              aria-label="打开对话记录"
              className="workspace-sessions-button"
              onClick={() => setShowSessions(true)}
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
                      if (event.key === "Enter") void saveTitle();
                      if (event.key === "Escape") setRenaming(false);
                    }}
                    value={titleDraft}
                  />
                  <button
                    disabled={!titleDraft.trim() || renameSaving}
                    onClick={() => void saveTitle()}
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
                  onClick={beginRename}
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
                  onClick={() => void captureConversationKnowledge()}
                  title="将有价值的对话整理为待确认知识草稿"
                  type="button"
                >
                  <BookOpenCheck aria-hidden="true" />
                  <span>{capturing ? "整理中…" : "沉淀知识"}</span>
                </button>
                <button
                  disabled={sending}
                  onClick={() => void archiveActiveConversation()}
                  title="归档当前对话"
                  type="button"
                >
                  <Archive aria-hidden="true" />
                </button>
              </>
            ) : null}
          </div>
        </header>

        <div className="workspace-body">
          <section className="workspace-transcript">
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
                  <span>GENERAL JARVIS · READY</span>
                  <h2>从一个想法开始。</h2>
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
                        onClick={() => setInput(suggestion)}
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
                    onConvertTask={(item) => void convertMessageToTask(item)}
                    onRegenerate={(item) => void regenerateMessage(item)}
                    onRemember={(item) => void rememberChatMessage(item)}
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

            <div className="workspace-composer-region">
              {error ? (
                <div className="workspace-notice workspace-notice-error">
                  <span>{error}</span>
                  <button
                    aria-label="关闭错误提示"
                    onClick={() => setError(null)}
                    type="button"
                  >
                    <X aria-hidden="true" />
                  </button>
                </div>
              ) : null}
              {memoryNotice ? (
                <div className="workspace-notice">
                  <BrainCircuit aria-hidden="true" />
                  <span>{memoryNotice}</span>
                  <Link href="/memory">检查记忆</Link>
                  <button
                    aria-label="关闭记忆提示"
                    onClick={() => setMemoryNotice(null)}
                    type="button"
                  >
                    <X aria-hidden="true" />
                  </button>
                </div>
              ) : null}
              {taskNotice ? (
                <div className="workspace-notice">
                  <Layers3 aria-hidden="true" />
                  <span>{taskNotice}</span>
                  <Link href="/growth">打开行动</Link>
                  <button
                    aria-label="关闭任务提示"
                    onClick={() => setTaskNotice(null)}
                    type="button"
                  >
                    <X aria-hidden="true" />
                  </button>
                </div>
              ) : null}
              {captureNotice ? (
                <div className="workspace-notice">
                  <BookOpenCheck aria-hidden="true" />
                  <span>{captureNotice}</span>
                  <Link href="/knowledge">检查知识草稿</Link>
                  <button
                    aria-label="关闭知识草稿提示"
                    onClick={() => setCaptureNotice(null)}
                    type="button"
                  >
                    <X aria-hidden="true" />
                  </button>
                </div>
              ) : null}

              <div className="workspace-composer">
                <div className="workspace-composer-input">
                  <button
                    aria-label={listening ? "停止语音输入" : "开始语音输入"}
                    className={listening ? "is-listening" : ""}
                    disabled={sending}
                    onClick={toggleDictation}
                    type="button"
                  >
                    <Mic aria-hidden="true" />
                  </button>
                  <textarea
                    aria-label="发送给 Jarvis"
                    disabled={sending}
                    onChange={(event) => setInput(event.target.value)}
                    onKeyDown={handleComposerKeyDown}
                    placeholder={
                      listening
                        ? "Jarvis 正在聆听…"
                        : "告诉 Jarvis 你想理解、规划或完成什么…"
                    }
                    rows={2}
                    value={input}
                  />
                  <button
                    aria-label={sending ? "停止生成" : "发送"}
                    className={`workspace-send ${sending ? "is-stopping" : ""}`}
                    disabled={!sending && !input.trim()}
                    onClick={() =>
                      sending ? void stopGeneration() : void submitMessage()
                    }
                    type="button"
                  >
                    {sending ? (
                      <Square aria-hidden="true" />
                    ) : (
                      <Send aria-hidden="true" />
                    )}
                  </button>
                </div>

                <div className="workspace-composer-controls">
                  <select
                    aria-label="模型模式"
                    disabled={sending}
                    onChange={(event) =>
                      setMode(event.target.value as ModelMode)
                    }
                    value={mode}
                  >
                    {modeOptions.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label} · {option.detail}
                      </option>
                    ))}
                  </select>
                  <label className={sensitive ? "is-active" : ""}>
                    <input
                      checked={sensitive}
                      disabled={sending}
                      onChange={(event) => setSensitive(event.target.checked)}
                      type="checkbox"
                    />
                    <LockKeyhole aria-hidden="true" />
                    隐私模式
                  </label>
                  <label
                    className={useKnowledge ? "is-active" : ""}
                    title="本地模式可使用所有已启用笔记；云端模型只使用明确允许的笔记"
                  >
                    <input
                      checked={useKnowledge}
                      disabled={sending}
                      onChange={(event) => setUseKnowledge(event.target.checked)}
                      type="checkbox"
                    />
                    <BookOpenCheck aria-hidden="true" />
                    知识增强
                  </label>
                  <span>
                    {sending
                      ? "结果正在生成，点击停止会自动保存已有内容"
                      : "Enter 发送 · Shift+Enter 换行"}
                  </span>
                </div>
              </div>
            </div>
          </section>

          <aside className="workspace-inspector">
            <div className="workspace-core-presence">
              <span>JARVIS PRESENCE</span>
              <AIStatus state={workspaceState} />
            </div>

            <div className="workspace-inspector-section">
              <span>SESSION CONTEXT</span>
              <div className="workspace-context-list">
                <div>
                  <BrainCircuit aria-hidden="true" />
                  <span>模型路由</span>
                  <strong>{activeMode.label}</strong>
                  <small>{activeMode.detail}</small>
                </div>
                <div>
                  <Layers3 aria-hidden="true" />
                  <span>对话上下文</span>
                  <strong>{detail?.message_count ?? 0} MSG</strong>
                  <small>
                    {detail?.has_summary ? "摘要上下文已启用" : "保留原始上下文"}
                  </small>
                </div>
                <div>
                  <BookOpenCheck aria-hidden="true" />
                  <span>知识边界</span>
                  <strong>{useKnowledge ? "增强开启" : "未启用"}</strong>
                  <small>按照笔记权限检索</small>
                </div>
                <div>
                  <LockKeyhole aria-hidden="true" />
                  <span>隐私边界</span>
                  <strong>{sensitive ? "仅本地" : "标准"}</strong>
                  <small>
                    {sensitive ? "内容不会发送云端" : "按模型路由处理"}
                  </small>
                </div>
              </div>
            </div>

            <div className="workspace-boundary-note">
              <ShieldCheck aria-hidden="true" />
              <div>
                <strong>Safe execution boundary</strong>
                <p>
                  Jarvis 会展示模型、知识来源和执行结果，但不会暴露私人推理正文，
                  也不会未经确认执行高风险操作。
                </p>
              </div>
            </div>
          </aside>
        </div>
      </section>
    </main>
  );
}
