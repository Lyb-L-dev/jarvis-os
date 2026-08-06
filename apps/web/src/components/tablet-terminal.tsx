"use client";

import {
  cancelChatStream,
  createConversation,
  getConversation,
  getTabletBootstrap,
  listCompanionDevices,
  listConversations,
  streamChatMessage,
  type TabletBootstrapResponse,
  type ChatMessage,
  type CompanionDevice,
  type ConversationDetail,
  type ConversationSummary,
  type ModelMode,
  type ReadinessResponse,
} from "@/lib/api";
import { JarvisMark } from "@/components/jarvis-mark";
import {
  providerBadge,
  type SpeechRecognitionConstructor,
  type SpeechRecognitionLike,
} from "@/lib/utils";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

type WakeLockSentinel = {
  release: () => Promise<void>;
  addEventListener: (name: "release", handler: () => void) => void;
};

const tabletModes: Array<{
  value: ModelMode;
  label: string;
  detail: string;
}> = [
  { value: "standard", label: "标准", detail: "MiMo 主力" },
  { value: "local", label: "本地", detail: "Qwen · 隐私" },
  { value: "deep", label: "深度", detail: "DeepSeek · 需确认" },
];

function providerLabel(provider?: string | null) {
  if (provider === "ollama") return "LOCAL QWEN";
  return providerBadge(provider);
}

function temporaryMessage(
  conversationId: string,
  role: "user" | "assistant",
  content: string,
): ChatMessage {
  return {
    id: `tablet-${role}-${Date.now()}`,
    conversation_id: conversationId,
    role,
    content,
    status: "completed",
    metadata: role === "assistant" ? { streaming: true } : {},
    created_at: new Date().toISOString(),
  };
}

function formatClock(date: Date) {
  return date.toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

function greeting(date: Date) {
  const hour = date.getHours();
  if (hour < 6) return "夜深了";
  if (hour < 11) return "早上好";
  if (hour < 14) return "中午好";
  if (hour < 18) return "下午好";
  return "晚上好";
}

export function TabletTerminal() {
  const [clock, setClock] = useState<Date | null>(null);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [detail, setDetail] = useState<ConversationDetail | null>(null);
  const [mode, setMode] = useState<ModelMode>("standard");
  const [input, setInput] = useState("");
  const [sensitive, setSensitive] = useState(false);
  const [useKnowledge, setUseKnowledge] = useState(true);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [listening, setListening] = useState(false);
  const [dictationLanguage, setDictationLanguage] = useState<"zh-CN" | "en-US">(
    "zh-CN",
  );
  const [speechRiskAccepted, setSpeechRiskAccepted] = useState(false);
  const [wakeLockActive, setWakeLockActive] = useState(false);
  const [readiness, setReadiness] = useState<ReadinessResponse | null>(null);
  const [bootstrap, setBootstrap] = useState<TabletBootstrapResponse | null>(
    null,
  );
  const [devices, setDevices] = useState<CompanionDevice[]>([]);
  const [deviceMode, setDeviceMode] = useState("TABLET PREVIEW");
  const [error, setError] = useState<string | null>(null);
  const streamControllerRef = useRef<AbortController | null>(null);
  const streamRequestIdRef = useRef<string | null>(null);
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const wakeLockRef = useRef<WakeLockSentinel | null>(null);
  const messageEndRef = useRef<HTMLDivElement>(null);

  const refreshStatus = useCallback(async () => {
    const results = await Promise.allSettled([
      getTabletBootstrap(),
      listCompanionDevices(),
    ]);
    if (results[0].status === "fulfilled") {
      const data = results[0].value;
      setBootstrap(data);
      setReadiness({
        status: data.core === "ready" ? "ready" : "degraded",
        dependencies: [],
      });
    }
    if (results[1].status === "fulfilled") setDevices(results[1].value);
  }, []);

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
          setDetail(conversation);
          setMode(conversation.model_mode);
        }
        await refreshStatus();
      } catch (reason) {
        if (!cancelled) {
          setError(reason instanceof Error ? reason.message : "无法连接 Jarvis");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    const tickClock = () => setClock(new Date());
    tickClock();
    const clockTimer = window.setInterval(tickClock, 1000);
    const statusTimer = window.setInterval(() => void refreshStatus(), 15_000);
    const deviceTimer = window.setTimeout(
      () =>
        setDeviceMode(
          /Android/i.test(window.navigator.userAgent)
            ? "USB TABLET TERMINAL"
            : "DESKTOP TABLET PREVIEW",
        ),
      0,
    );
    return () => {
      cancelled = true;
      window.clearInterval(clockTimer);
      window.clearInterval(statusTimer);
      window.clearTimeout(deviceTimer);
      recognitionRef.current?.stop();
      void wakeLockRef.current?.release();
    };
  }, [refreshStatus]);

  useEffect(() => {
    messageEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [detail?.messages, sending]);

  const activeMode =
    tabletModes.find((option) => option.value === mode) ?? tabletModes[0];
  const onlineDevice = devices.find((device) => device.online);
  const configuredModels = bootstrap?.configured_models ?? 0;
  const totalModels = bootstrap?.total_models ?? 0;
  const coreState = error
    ? "alert"
    : listening
      ? "listening"
      : sending
        ? "thinking"
        : loading
          ? "booting"
          : "idle";
  const connectionReady = readiness?.status === "ready";

  const recentConversations = useMemo(
    () => conversations.slice(0, 8),
    [conversations],
  );

  async function createTabletConversation() {
    const conversation = await createConversation({ model_mode: mode });
    setConversations((current) => [conversation, ...current]);
    const nextDetail = { ...conversation, messages: [] };
    setDetail(nextDetail);
    setInput("");
    return nextDetail;
  }

  async function openConversation(conversationId: string) {
    if (sending || conversationId === detail?.id) return;
    setError(null);
    setLoading(true);
    try {
      const conversation = await getConversation(conversationId);
      setDetail(conversation);
      setMode(conversation.model_mode);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "无法打开对话");
    } finally {
      setLoading(false);
    }
  }

  async function submitMessage() {
    const content = input.trim();
    if (!content || sending) return;
    const paidCallConfirmed =
      mode === "deep" && !sensitive
        ? window.confirm(
            "本次将调用按量付费的 DeepSeek。只有确认后才会继续。",
          )
        : false;
    if (mode === "deep" && !sensitive && !paidCallConfirmed) return;

    setSending(true);
    setError(null);
    setInput("");
    let conversation = detail;
    try {
      if (!conversation) {
        conversation = await createTabletConversation();
      }
      const conversationId = conversation.id;
      const optimisticUser = temporaryMessage(conversationId, "user", content);
      const optimisticAssistant = temporaryMessage(
        conversationId,
        "assistant",
        "",
      );
      setDetail({
        ...conversation,
        messages: [
          ...conversation.messages,
          optimisticUser,
          optimisticAssistant,
        ],
      });

      const controller = new AbortController();
      const requestId = globalThis.crypto.randomUUID();
      streamControllerRef.current = controller;
      streamRequestIdRef.current = requestId;
      let streamedContent = "";
      await streamChatMessage(
        conversationId,
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
            setDetail((current) =>
              current
                ? {
                    ...current,
                    messages: current.messages.map((message) => {
                      if (message.id === optimisticUser.id) {
                        return meta.user_message;
                      }
                      if (message.id === optimisticAssistant.id) {
                        return {
                          ...message,
                          provider: meta.routing.provider_used,
                          model: meta.routing.model_used,
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
          onError: setError,
          onDone: (response) => {
            setDetail((current) => ({
              ...response.conversation,
              messages: (current?.messages ?? []).map((message) => {
                if (
                  message.id === optimisticUser.id ||
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
    } catch (reason) {
      const stopped = streamControllerRef.current?.signal.aborted ?? false;
      if (!stopped) {
        setInput(content);
        setError(reason instanceof Error ? reason.message : "消息发送失败");
      }
      if (conversation) {
        const conversationId = conversation.id;
        window.setTimeout(() => {
          void getConversation(conversationId).then(setDetail).catch(() => {});
        }, 250);
      }
    } finally {
      streamControllerRef.current = null;
      streamRequestIdRef.current = null;
      setSending(false);
    }
  }

  async function stopGeneration() {
    const requestId = streamRequestIdRef.current;
    streamControllerRef.current?.abort();
    if (requestId) {
      try {
        await cancelChatStream(requestId);
      } catch {
        // The local abort already stops this tablet stream.
      }
    }
  }

  function handleComposerKeyDown(
    event: React.KeyboardEvent<HTMLTextAreaElement>,
  ) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void submitMessage();
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
        "平板浏览器的语音转写可能调用浏览器或系统的在线语音服务。请勿口述密码、API Key 等敏感内容。是否继续？",
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
      setError("当前平板浏览器不支持语音转写，请使用 Chrome 或继续键盘输入。");
      return;
    }
    const instance = new Recognition();
    const originalInput = input.trim();
    recognitionRef.current = instance;
    instance.lang = dictationLanguage;
    instance.continuous = true;
    instance.interimResults = true;
    instance.onresult = (event) => {
      let transcript = "";
      for (let index = 0; index < event.results.length; index += 1) {
        transcript += event.results[index][0].transcript;
      }
      setInput(`${originalInput}${originalInput ? " " : ""}${transcript}`);
    };
    instance.onerror = (event) => {
      setError(
        event.error === "not-allowed"
          ? "请允许 Chrome 使用平板麦克风。"
          : "这次没有听清，可以直接修改已转写文字。",
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

  async function enterFullscreen() {
    try {
      if (!document.fullscreenElement) {
        await document.documentElement.requestFullscreen();
      }
      const orientation = screen.orientation as ScreenOrientation & {
        lock?: (orientation: "landscape") => Promise<void>;
      };
      await orientation.lock?.("landscape").catch(() => undefined);
    } catch {
      setError("浏览器未允许全屏；仍可继续使用平板终端。");
    }
  }

  async function toggleWakeLock() {
    if (wakeLockRef.current) {
      await wakeLockRef.current.release();
      wakeLockRef.current = null;
      setWakeLockActive(false);
      return;
    }
    const wakeNavigator = navigator as Navigator & {
      wakeLock?: { request: (type: "screen") => Promise<WakeLockSentinel> };
    };
    if (!wakeNavigator.wakeLock) {
      setError("当前浏览器不支持屏幕常亮，请在平板系统中临时延长休眠时间。");
      return;
    }
    try {
      const sentinel = await wakeNavigator.wakeLock.request("screen");
      wakeLockRef.current = sentinel;
      setWakeLockActive(true);
      sentinel.addEventListener("release", () => {
        wakeLockRef.current = null;
        setWakeLockActive(false);
      });
    } catch {
      setError("平板没有授予屏幕常亮权限。");
    }
  }

  return (
    <main className={`tablet-terminal tablet-core-${coreState}`}>
      <div className="tablet-grid-backdrop" aria-hidden="true" />
      <header className="tablet-topbar">
        <div className="tablet-brand">
          <JarvisMark className="jarvis-mark" showText={false} title="Jarvis OS" />
          <div>
            <strong>JARVIS</strong>
            <span>REMOTE COGNITIVE TERMINAL</span>
          </div>
        </div>
        <div className="tablet-connection">
          <i className={connectionReady ? "is-online" : ""} />
          <div>
            <strong>{connectionReady ? "CORE LINK ACTIVE" : "LINK DEGRADED"}</strong>
            <span>{deviceMode} · 127.0.0.1</span>
          </div>
        </div>
        <div className="tablet-clock">
          <span>
            {clock
              ? clock.toLocaleDateString("zh-CN", {
                  month: "2-digit",
                  day: "2-digit",
                  weekday: "short",
                })
              : ""}
          </span>
          <strong>{clock ? formatClock(clock) : ""}</strong>
        </div>
        <div className="tablet-display-controls">
          <button onClick={() => void enterFullscreen()} type="button">
            全屏
          </button>
          <button
            className={wakeLockActive ? "is-active" : ""}
            onClick={() => void toggleWakeLock()}
            type="button"
          >
            {wakeLockActive ? "常亮中" : "屏幕常亮"}
          </button>
        </div>
      </header>

      <section className="tablet-body">
        <aside className="tablet-left-rail">
          <div className="tablet-rail-heading">
            <span>SESSION ROUTE</span>
            <strong>对话控制</strong>
          </div>
          <button
            className="tablet-new-session"
            disabled={sending}
            onClick={() => void createTabletConversation()}
            type="button"
          >
            <span>＋</span> 新建对话
          </button>
          <label className="tablet-conversation-select">
            <span>最近会话</span>
            <select
              disabled={sending}
              onChange={(event) => void openConversation(event.target.value)}
              value={detail?.id ?? ""}
            >
              <option disabled value="">
                选择会话
              </option>
              {recentConversations.map((conversation) => (
                <option key={conversation.id} value={conversation.id}>
                  {conversation.title}
                </option>
              ))}
            </select>
          </label>
          <div className="tablet-mode-grid">
            {tabletModes.map((option) => (
              <button
                className={mode === option.value ? "is-selected" : ""}
                disabled={sending}
                key={option.value}
                onClick={() => setMode(option.value)}
                type="button"
              >
                <strong>{option.label}</strong>
                <span>{option.detail}</span>
              </button>
            ))}
          </div>
          <label className="tablet-switch">
            <span>
              <strong>知识增强</strong>
              <small>按 Obsidian 权限检索</small>
            </span>
            <input
              checked={useKnowledge}
              onChange={(event) => setUseKnowledge(event.target.checked)}
              type="checkbox"
            />
          </label>
          <label className="tablet-switch">
            <span>
              <strong>隐私模式</strong>
              <small>强制本地 Qwen</small>
            </span>
            <input
              checked={sensitive}
              onChange={(event) => setSensitive(event.target.checked)}
              type="checkbox"
            />
          </label>
          <div className="tablet-route-readout">
            <span>ACTIVE ROUTE</span>
            <strong>{sensitive ? "LOCAL QWEN" : activeMode.detail}</strong>
            <small>所有会话自动保存在电脑</small>
          </div>
        </aside>

        <section className="tablet-conversation">
          <header className="tablet-conversation-header">
            <div>
              <span>ACTIVE CONVERSATION</span>
              <h1>{detail?.title || "新的对话"}</h1>
            </div>
            <div className={`tablet-state-badge state-${coreState}`}>
              <i />
              {coreState === "thinking"
                ? "ANALYSING"
                : coreState === "listening"
                  ? "LISTENING"
                  : coreState === "alert"
                    ? "ATTENTION"
                    : coreState === "booting"
                      ? "BOOTING"
                      : "STANDBY"}
            </div>
          </header>

          <div className="tablet-messages">
            {!loading && (!detail || detail.messages.length === 0) ? (
              <div className="tablet-welcome">
                <div className="tablet-welcome-mark">
                  <JarvisMark className="jarvis-mark" showText={false} />
                </div>
                <span>PERSONAL AI OPERATING SYSTEM</span>
                <h2>
                  {clock ? `${greeting(clock)}，` : ""}
                  {bootstrap?.profile_name || "先生"}。
                </h2>
                <p>平板终端已经连接。推理、记忆和数据仍由电脑上的 Jarvis 处理。</p>
                <div>
                  {[
                    "汇总我今天最重要的三件事",
                    "打开一段新的学习讨论",
                    "检查今天还有哪些提醒",
                  ].map((suggestion) => (
                    <button
                      key={suggestion}
                      onClick={() => setInput(suggestion)}
                      type="button"
                    >
                      {suggestion}
                    </button>
                  ))}
                </div>
                {bootstrap ? (
                  <div className="tablet-bootstrap-strip">
                    <span>今日任务 {bootstrap.today_tasks.length}</span>
                    <span>未读提醒 {bootstrap.unread_notifications}</span>
                    <span>未读情报 {bootstrap.unread_intelligence}</span>
                    <span>记忆 {bootstrap.memory_active}</span>
                  </div>
                ) : null}
              </div>
            ) : null}
            {detail?.messages.map((message) => (
              <article
                className={`tablet-message tablet-message-${message.role}`}
                key={message.id}
              >
                <div className="tablet-message-avatar">
                  {message.role === "assistant" ? (
                    <JarvisMark className="jarvis-mark" showText={false} />
                  ) : (
                    "刘"
                  )}
                </div>
                <div>
                  <header>
                    <strong>{message.role === "assistant" ? "JARVIS" : "YOU"}</strong>
                    {message.role === "assistant" ? (
                      <span>{providerLabel(message.provider)}</span>
                    ) : null}
                  </header>
                  <p
                    className={
                      message.metadata.streaming && !message.content
                        ? "tablet-message-thinking"
                        : ""
                    }
                  >
                    {message.content ||
                      (message.metadata.streaming ? "正在组织回答…" : "—")}
                  </p>
                </div>
              </article>
            ))}
            <div ref={messageEndRef} />
          </div>

          {error ? (
            <div className="tablet-error">
              <span>ATTENTION</span>
              {error}
              <button onClick={() => setError(null)} type="button">
                ×
              </button>
            </div>
          ) : null}

          <footer className="tablet-composer">
            <div className="tablet-dictation-language">
              <button
                className={dictationLanguage === "zh-CN" ? "is-selected" : ""}
                onClick={() => setDictationLanguage("zh-CN")}
                type="button"
              >
                中
              </button>
              <button
                className={dictationLanguage === "en-US" ? "is-selected" : ""}
                onClick={() => setDictationLanguage("en-US")}
                type="button"
              >
                EN
              </button>
            </div>
            <button
              aria-label={listening ? "停止语音输入" : "开始语音输入"}
              className={`tablet-mic ${listening ? "is-listening" : ""}`}
              onClick={toggleDictation}
              type="button"
            >
              <span />
            </button>
            <textarea
              disabled={sending}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={handleComposerKeyDown}
              placeholder={
                listening ? "正在聆听…" : "向 Jarvis 下达指令或开始对话"
              }
              rows={2}
              value={input}
            />
            {sending ? (
              <button
                className="tablet-send tablet-stop"
                onClick={() => void stopGeneration()}
                type="button"
              >
                <span>■</span>
                停止
              </button>
            ) : (
              <button
                className="tablet-send"
                disabled={!input.trim()}
                onClick={() => void submitMessage()}
                type="button"
              >
                <span>↑</span>
                发送
              </button>
            )}
          </footer>
        </section>

        <aside className="tablet-right-rail">
          <div className="tablet-core-visual" aria-label={`Jarvis ${coreState}`}>
            <span className="tablet-core-ring ring-one" />
            <span className="tablet-core-ring ring-two" />
            <span className="tablet-core-ring ring-three" />
            <div className="tablet-core-energy">
              <JarvisMark className="jarvis-mark" showText={false} />
            </div>
          </div>
          <div className="tablet-core-caption">
            <span>J-CORE STATUS</span>
            <strong>
              {coreState === "thinking"
                ? "正在思考"
                : coreState === "listening"
                  ? "正在聆听"
                  : coreState === "alert"
                    ? "需要检查"
                    : "核心在线"}
            </strong>
          </div>
          <div className="tablet-system-readouts">
            <div>
              <span>CORE</span>
              <strong>{connectionReady ? "ONLINE" : "DEGRADED"}</strong>
              <i className={connectionReady ? "ok" : "warn"} />
            </div>
            <div>
              <span>MODELS</span>
              <strong>
                {configuredModels}/{totalModels} READY
              </strong>
              <i className={configuredModels ? "ok" : "warn"} />
            </div>
            <div>
              <span>VOICE</span>
              <strong>
                {onlineDevice?.voice_status?.bilingual_neural_ready
                  ? "BILINGUAL"
                  : "FALLBACK"}
              </strong>
              <i
                className={
                  onlineDevice?.voice_status?.bilingual_neural_ready
                    ? "ok"
                    : "warn"
                }
              />
            </div>
            <div>
              <span>MEMORY</span>
              <strong>PC HOSTED</strong>
              <i className="ok" />
            </div>
          </div>
          <div className="tablet-security-note">
            <span>SECURE LINK</span>
            <strong>USB · LOOPBACK ONLY</strong>
            <p>平板不保存模型与数据库，断开 USB 隧道后无法访问。</p>
          </div>
        </aside>
      </section>
    </main>
  );
}
