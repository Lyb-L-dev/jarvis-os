"use client";

import {
  completeEnglishSession,
  confirmEnglishMistake,
  createEnglishSession,
  deleteEnglishMistake,
  deleteEnglishSession,
  disputeEnglishMistake,
  editEnglishTranscript,
  getEnglishOverview,
  getEnglishSession,
  listDueEnglishReviews,
  listEnglishMistakes,
  listEnglishSessions,
  listUpcomingEnglishReviews,
  masterEnglishMistake,
  rejectEnglishMistake,
  sendEnglishMessage,
  submitEnglishReview,
  updateEnglishMistake,
  type EnglishCorrectionMode,
  type EnglishLevel,
  type EnglishMessage,
  type EnglishMistake,
  type EnglishMistakeStatus,
  type EnglishOverview,
  type EnglishProcessingMode,
  type EnglishReview,
  type EnglishReviewResult,
  type EnglishSession,
  type EnglishSessionDetail,
  type EnglishSessionType,
} from "@/lib/api";
import {
  FormEvent,
  KeyboardEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { SpecialistHeader } from "@/components/agents/SpecialistHeader";

type EnglishTab = "practice" | "mistakes" | "review";

type SpeechResultEvent = {
  results: ArrayLike<{
    0: { transcript: string };
    isFinal: boolean;
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

const emptyOverview: EnglishOverview = {
  active_session_id: null,
  total_sessions: 0,
  completed_sessions: 0,
  pending_mistakes: 0,
  learning_mistakes: 0,
  mastered_mistakes: 0,
  due_reviews: 0,
};

const sessionTypes: Array<{
  value: EnglishSessionType;
  label: string;
  description: string;
}> = [
  { value: "free", label: "自由对话", description: "从日常话题自然开聊" },
  { value: "topic", label: "主题练习", description: "围绕指定主题深入表达" },
  { value: "interview", label: "面试模拟", description: "训练求职问答与追问" },
  { value: "technical", label: "技术英语", description: "练习专业概念与工作沟通" },
];

const correctionModes: Array<{
  value: EnglishCorrectionMode;
  label: string;
  description: string;
}> = [
  { value: "instant", label: "即时纠错", description: "每轮指出所有明确错误" },
  { value: "gentle", label: "温和纠错", description: "每轮只提醒最关键的一处" },
  { value: "summary", label: "结束总结", description: "对话中不打断，结束后统一分析" },
];

const statusLabels: Record<EnglishMistakeStatus, string> = {
  pending: "待确认",
  learning: "学习中",
  mastered: "已掌握",
  disputed: "解释待修正",
  rejected: "已忽略",
};

const reviewButtons: Array<{
  value: EnglishReviewResult;
  label: string;
  className?: string;
}> = [
  { value: "again", label: "没记住" },
  { value: "hard", label: "有点难" },
  { value: "good", label: "记住了", className: "review-good" },
  { value: "easy", label: "很轻松" },
  { value: "mastered", label: "已经掌握" },
];

function sessionTitle(session: EnglishSession) {
  const type = sessionTypes.find((item) => item.value === session.session_type);
  return session.topic || type?.label || "英语练习";
}

function correctionModeLabel(mode: EnglishCorrectionMode) {
  return correctionModes.find((item) => item.value === mode)?.label ?? mode;
}

function providerLabel(message: EnglishMessage) {
  if (message.provider_used === "mimo") return "MiMo";
  if (message.provider_used === "ollama") {
    return message.fallback_reason ? "本地 Qwen · 自动降级" : "本地 Qwen";
  }
  if (message.provider_used === "rule_based") return "本地规则兜底";
  return null;
}

function formatDateTime(value?: string | null) {
  if (!value) return "尚未安排";
  return new Date(value).toLocaleString("zh-CN", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function mergeMistakes(
  current: EnglishMistake[],
  incoming: EnglishMistake[],
) {
  const byId = new Map(current.map((item) => [item.id, item]));
  for (const item of incoming) byId.set(item.id, item);
  return Array.from(byId.values()).sort(
    (a, b) =>
      b.occurrence_count - a.occurrence_count ||
      new Date(b.last_seen_at).getTime() - new Date(a.last_seen_at).getTime(),
  );
}

export function EnglishCoach() {
  const [tab, setTab] = useState<EnglishTab>("practice");
  const [overview, setOverview] = useState(emptyOverview);
  const [sessions, setSessions] = useState<EnglishSession[]>([]);
  const [selectedSession, setSelectedSession] =
    useState<EnglishSessionDetail | null>(null);
  const selectedSessionId = useRef<string | null>(null);
  const [mistakes, setMistakes] = useState<EnglishMistake[]>([]);
  const [dueReviews, setDueReviews] = useState<EnglishReview[]>([]);
  const [upcomingReviews, setUpcomingReviews] = useState<EnglishReview[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [showSetup, setShowSetup] = useState(false);

  const [sessionType, setSessionType] = useState<EnglishSessionType>("free");
  const [topic, setTopic] = useState("");
  const [correctionMode, setCorrectionMode] =
    useState<EnglishCorrectionMode>("gentle");
  const [level, setLevel] = useState<EnglishLevel>("B1");
  const [processingMode, setProcessingMode] =
    useState<EnglishProcessingMode>("standard");

  const [draft, setDraft] = useState("");
  const [draftInputMode, setDraftInputMode] = useState<
    "text" | "voice_transcript"
  >("text");
  const [listening, setListening] = useState(false);
  const recognition = useRef<SpeechRecognitionLike | null>(null);
  const messagesEnd = useRef<HTMLDivElement | null>(null);

  const [mistakeQuery, setMistakeQuery] = useState("");
  const [mistakeStatus, setMistakeStatus] = useState<
    EnglishMistakeStatus | "all"
  >("all");
  const [editingMistakeId, setEditingMistakeId] = useState<string | null>(null);
  const [editCorrection, setEditCorrection] = useState("");
  const [editExplanation, setEditExplanation] = useState("");
  const [editingMessageId, setEditingMessageId] = useState<string | null>(null);
  const [editingTranscript, setEditingTranscript] = useState("");

  const [reviewAnswers, setReviewAnswers] = useState<Record<string, string>>({});
  const [revealedReviews, setRevealedReviews] = useState<Set<string>>(new Set());

  const refreshCollections = useCallback(async (signal?: AbortSignal) => {
    try {
      const [
        nextOverview,
        nextSessions,
        nextMistakes,
        nextDue,
        nextUpcoming,
      ] = await Promise.all([
        getEnglishOverview(signal),
        listEnglishSessions(signal),
        listEnglishMistakes({ signal }),
        listDueEnglishReviews(signal),
        listUpcomingEnglishReviews(signal),
      ]);
      setOverview(nextOverview);
      setSessions(nextSessions);
      setMistakes(nextMistakes);
      setDueReviews(nextDue);
      setUpcomingReviews(nextUpcoming);

      const wantedId =
        selectedSessionId.current || nextOverview.active_session_id || null;
      if (wantedId) {
        try {
          const detail = await getEnglishSession(wantedId, signal);
          selectedSessionId.current = detail.id;
          setSelectedSession(detail);
          setShowSetup(false);
        } catch (sessionError) {
          if (
            sessionError instanceof DOMException &&
            sessionError.name === "AbortError"
          ) {
            return;
          }
          selectedSessionId.current = null;
          setSelectedSession(null);
          setShowSetup(nextSessions.length === 0);
        }
      } else {
        setShowSetup(nextSessions.length === 0);
      }
      setError(null);
    } catch (loadError) {
      if (
        loadError instanceof DOMException &&
        loadError.name === "AbortError"
      ) {
        return;
      }
      setError(
        loadError instanceof Error ? loadError.message : "读取英语训练数据失败",
      );
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      void refreshCollections(controller.signal);
    }, 0);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
      recognition.current?.stop();
    };
  }, [refreshCollections]);

  useEffect(() => {
    messagesEnd.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [selectedSession?.messages.length, busy]);

  const mistakeMap = useMemo(
    () => new Map(mistakes.map((mistake) => [mistake.id, mistake])),
    [mistakes],
  );

  const filteredMistakes = useMemo(() => {
    const query = mistakeQuery.trim().toLocaleLowerCase();
    return mistakes.filter((mistake) => {
      if (mistakeStatus !== "all" && mistake.status !== mistakeStatus) {
        return false;
      }
      if (!query) return true;
      return [
        mistake.original_text,
        mistake.corrected_text,
        mistake.explanation,
        mistake.category,
      ].some((value) => value.toLocaleLowerCase().includes(query));
    });
  }, [mistakeQuery, mistakeStatus, mistakes]);

  async function runAction(
    key: string,
    action: () => Promise<void>,
    success?: string,
  ) {
    setBusy(key);
    setError(null);
    setNotice(null);
    try {
      await action();
      if (success) setNotice(success);
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : "操作失败");
    } finally {
      setBusy(null);
    }
  }

  async function openSession(sessionId: string) {
    await runAction("open-session", async () => {
      const detail = await getEnglishSession(sessionId);
      selectedSessionId.current = detail.id;
      setSelectedSession(detail);
      setShowSetup(false);
      setTab("practice");
    });
  }

  async function startSession(event: FormEvent) {
    event.preventDefault();
    if (sessionType === "topic" && !topic.trim()) {
      setError("主题练习需要先填写一个主题。");
      return;
    }
    await runAction(
      "start-session",
      async () => {
        const session = await createEnglishSession({
          session_type: sessionType,
          topic: topic.trim() || undefined,
          correction_mode: correctionMode,
          level,
          processing_mode: processingMode,
        });
        selectedSessionId.current = session.id;
        setSelectedSession(session);
        setSessions((current) => [session, ...current]);
        setShowSetup(false);
        setDraft("");
        await refreshCollections();
      },
      "新练习已开始。先用英语说一句吧。",
    );
  }

  async function removeSession(session: EnglishSession) {
    if (!window.confirm(`删除“${sessionTitle(session)}”这次会话？错题记录会保留。`)) {
      return;
    }
    await runAction(
      `delete-session-${session.id}`,
      async () => {
        await deleteEnglishSession(session.id);
        if (selectedSessionId.current === session.id) {
          selectedSessionId.current = null;
          setSelectedSession(null);
        }
        await refreshCollections();
      },
      "会话已删除，已经确认的错题仍然保留。",
    );
  }

  async function submitMessage() {
    const content = draft.trim();
    const session = selectedSession;
    if (!content || !session || session.status !== "active") return;
    await runAction("send-message", async () => {
      const response = await sendEnglishMessage(session.id, {
        content,
        input_mode: draftInputMode,
      });
      setSelectedSession((current) =>
        current
          ? {
              ...current,
              message_count: current.message_count + 2,
              mistake_count:
                current.mistake_count + response.mistakes.length,
              messages: [
                ...current.messages,
                response.user_message,
                response.assistant_message,
              ],
            }
          : current,
      );
      setMistakes((current) => mergeMistakes(current, response.mistakes));
      setOverview((current) => ({
        ...current,
        pending_mistakes:
          current.pending_mistakes +
          response.mistakes.filter((item) => item.status === "pending").length,
      }));
      setDraft("");
      setDraftInputMode("text");
    });
  }

  function handleComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void submitMessage();
    }
  }

  function toggleSpeech() {
    if (listening) {
      recognition.current?.stop();
      return;
    }
    const speechWindow = window as typeof window & {
      SpeechRecognition?: SpeechRecognitionConstructor;
      webkitSpeechRecognition?: SpeechRecognitionConstructor;
    };
    const Recognition =
      speechWindow.SpeechRecognition || speechWindow.webkitSpeechRecognition;
    if (!Recognition) {
      setError("当前浏览器不支持语音转写。可以继续直接输入文字。");
      return;
    }
    setError(null);
    const instance = new Recognition();
    recognition.current = instance;
    instance.lang = "en-US";
    instance.continuous = true;
    instance.interimResults = true;
    instance.onresult = (event) => {
      let transcript = "";
      for (let index = 0; index < event.results.length; index += 1) {
        transcript += event.results[index][0].transcript;
      }
      setDraft(transcript.trimStart());
      setDraftInputMode("voice_transcript");
    };
    instance.onerror = (event) => {
      setError(
        event.error === "not-allowed"
          ? "麦克风权限未开启。允许浏览器使用麦克风后可再次尝试。"
          : "这次没有听清，转写内容仍可手动修改。",
      );
    };
    instance.onend = () => {
      setListening(false);
      recognition.current = null;
    };
    setListening(true);
    instance.start();
  }

  async function finishSession() {
    if (!selectedSession) return;
    await runAction(
      "complete-session",
      async () => {
        const result = await completeEnglishSession(selectedSession.id);
        setSelectedSession((current) =>
          current
            ? {
                ...current,
                ...result.session,
              }
            : current,
        );
        setMistakes((current) => mergeMistakes(current, result.mistakes));
        await refreshCollections();
      },
      "本次练习已完成，纠错结果正在错题本等待你确认。",
    );
  }

  async function saveTranscript(messageId: string) {
    const value = editingTranscript.trim();
    if (!value) return;
    await runAction(
      `edit-message-${messageId}`,
      async () => {
        const updated = await editEnglishTranscript(messageId, value);
        setSelectedSession((current) =>
          current
            ? {
                ...current,
                messages: current.messages.map((message) =>
                  message.id === updated.id ? updated : message,
                ),
              }
            : current,
        );
        setEditingMessageId(null);
      },
      "转写已修改。已经生成的纠错不会自动覆盖，请在错题本中一并核对。",
    );
  }

  async function refreshAfterMistakeAction(message?: string) {
    await refreshCollections();
    if (message) setNotice(message);
  }

  async function confirmMistake(mistake: EnglishMistake) {
    await runAction(
      `confirm-${mistake.id}`,
      async () => {
        await confirmEnglishMistake(mistake.id);
        await refreshAfterMistakeAction(
          "已加入复习；明晚 19:00 会通过桌面和语音提醒你。",
        );
      },
    );
  }

  async function changeMistakeStatus(
    mistake: EnglishMistake,
    action: "reject" | "master" | "dispute",
  ) {
    await runAction(`${action}-${mistake.id}`, async () => {
      if (action === "reject") await rejectEnglishMistake(mistake.id);
      if (action === "master") await masterEnglishMistake(mistake.id);
      if (action === "dispute") await disputeEnglishMistake(mistake.id);
      await refreshAfterMistakeAction(
        action === "master"
          ? "已标记掌握，复习频率已降低到 30 天后。"
          : action === "dispute"
            ? "已暂停这道题的提醒。修改解释后可重新确认。"
            : "这条纠错已忽略，不会进入复习。",
      );
    });
  }

  function beginMistakeEdit(mistake: EnglishMistake) {
    setEditingMistakeId(mistake.id);
    setEditCorrection(mistake.corrected_text);
    setEditExplanation(mistake.explanation);
  }

  async function saveMistake(mistake: EnglishMistake) {
    if (!editCorrection.trim() || !editExplanation.trim()) return;
    await runAction(
      `edit-mistake-${mistake.id}`,
      async () => {
        await updateEnglishMistake(mistake.id, {
          corrected_text: editCorrection.trim(),
          explanation: editExplanation.trim(),
        });
        setEditingMistakeId(null);
        await refreshAfterMistakeAction("纠错内容已更新，请再次确认后进入复习。");
      },
    );
  }

  async function removeMistake(mistake: EnglishMistake) {
    if (!window.confirm("永久移除这条错题和它尚未触发的复习提醒？")) return;
    await runAction(
      `delete-mistake-${mistake.id}`,
      async () => {
        await deleteEnglishMistake(mistake.id);
        await refreshAfterMistakeAction("错题及未触发的复习提醒已移除。");
      },
    );
  }

  function revealReview(reviewId: string) {
    setRevealedReviews((current) => new Set(current).add(reviewId));
  }

  async function rateReview(
    review: EnglishReview,
    result: EnglishReviewResult,
  ) {
    await runAction(`review-${review.id}`, async () => {
      await submitEnglishReview(review.id, {
        submitted_answer: reviewAnswers[review.id]?.trim() || undefined,
        result,
      });
      setReviewAnswers((current) => {
        const next = { ...current };
        delete next[review.id];
        return next;
      });
      setRevealedReviews((current) => {
        const next = new Set(current);
        next.delete(review.id);
        return next;
      });
      await refreshAfterMistakeAction(
        result === "incorrect_explanation"
          ? "这道题已暂停。请在错题本修正解释后重新确认。"
          : "复习结果已保存，下次时间已自动安排。",
      );
    });
  }

  if (loading) {
    return (
      <main className="english-page">
        <div className="english-loading">
          <span />
          正在准备 English Coach…
        </div>
      </main>
    );
  }

  return (
    <main className="english-page specialist-page specialist-english">
      <SpecialistHeader
        accent="训练室"
        activeAgent="english"
        description="真实对话、人工确认纠错、间隔复习，形成一条完整学习闭环。"
        eyebrow="ENGLISH COACH"
        status={selectedSession?.status === "active" ? "SESSION ACTIVE" : "READY TO PRACTICE"}
        title="英语"
        actions={
          <button
            className="primary-button"
            onClick={() => {
              setShowSetup(true);
              setTab("practice");
            }}
            type="button"
          >
            ＋ 新练习
          </button>
        }
      />

      <div className="specialist-section-label">
        <div>
          <span>TODAY&apos;S PROGRESS</span>
          <strong>学习轨迹</strong>
        </div>
        <p>每一次确认都会进入你的长期语言记忆</p>
      </div>

      <section
        className="english-stats specialist-metrics"
        aria-label="英语训练概况"
      >
        <article>
          <span>完成会话</span>
          <strong>{overview.completed_sessions}</strong>
          <small>累计 {overview.total_sessions} 次</small>
        </article>
        <article className={overview.pending_mistakes ? "stat-attention" : ""}>
          <span>待你确认</span>
          <strong>{overview.pending_mistakes}</strong>
          <small>模型不会直接写入复习</small>
        </article>
        <article>
          <span>学习中</span>
          <strong>{overview.learning_mistakes}</strong>
          <small>按遗忘曲线安排</small>
        </article>
        <article className={overview.due_reviews ? "stat-due" : ""}>
          <span>今日到期</span>
          <strong>{overview.due_reviews}</strong>
          <small>桌面＋语音提醒</small>
        </article>
      </section>

      <nav
        className="english-tabs specialist-tabs"
        aria-label="英语训练分区"
      >
        <button
          className={tab === "practice" ? "english-tab-active" : ""}
          onClick={() => setTab("practice")}
          type="button"
        >
          对话训练
        </button>
        <button
          className={tab === "mistakes" ? "english-tab-active" : ""}
          onClick={() => setTab("mistakes")}
          type="button"
        >
          错题本
          {overview.pending_mistakes > 0 && (
            <span>{overview.pending_mistakes}</span>
          )}
        </button>
        <button
          className={tab === "review" ? "english-tab-active" : ""}
          onClick={() => setTab("review")}
          type="button"
        >
          今日复习
          {overview.due_reviews > 0 && <span>{overview.due_reviews}</span>}
        </button>
      </nav>

      {error && (
        <div className="english-feedback english-error" role="alert">
          <span>!</span>
          {error}
          <button onClick={() => setError(null)} type="button">
            ×
          </button>
        </div>
      )}
      {notice && (
        <div className="english-feedback" role="status">
          <span>✓</span>
          {notice}
          <button onClick={() => setNotice(null)} type="button">
            ×
          </button>
        </div>
      )}

      {tab === "practice" && (
        <section className="english-practice-layout">
          <aside className="english-session-rail">
            <div className="english-section-head">
              <div>
                <span>HISTORY</span>
                <h2>练习记录</h2>
              </div>
              <button
                aria-label="开始新练习"
                onClick={() => setShowSetup(true)}
                type="button"
              >
                ＋
              </button>
            </div>
            <div className="english-session-list">
              {sessions.map((session) => (
                <div
                  className={`english-session-item ${
                    selectedSession?.id === session.id && !showSetup
                      ? "session-selected"
                      : ""
                  }`}
                  key={session.id}
                >
                  <button
                    className="session-open"
                    onClick={() => void openSession(session.id)}
                    type="button"
                  >
                    <span>
                      {session.status === "active" ? "进行中" : "已完成"} ·{" "}
                      {session.level}
                    </span>
                    <strong>{sessionTitle(session)}</strong>
                    <small>
                      {correctionModeLabel(session.correction_mode)} ·{" "}
                      {Math.floor(session.message_count / 2)} 轮
                    </small>
                  </button>
                  <button
                    aria-label="删除会话"
                    className="session-delete"
                    disabled={busy === `delete-session-${session.id}`}
                    onClick={() => void removeSession(session)}
                    type="button"
                  >
                    ×
                  </button>
                </div>
              ))}
              {sessions.length === 0 && (
                <div className="english-inline-empty">
                  还没有练习记录
                  <small>从右侧选择一个场景开始</small>
                </div>
              )}
            </div>
          </aside>

          <div className="english-workspace">
            {showSetup || !selectedSession ? (
              <form className="english-setup" onSubmit={startSession}>
                <div className="english-setup-heading">
                  <span>NEW SESSION</span>
                  <h2>这次想怎么练？</h2>
                  <p>先选场景和纠错节奏，随时可以结束并生成学习总结。</p>
                </div>

                <fieldset>
                  <legend>练习场景</legend>
                  <div className="english-option-grid">
                    {sessionTypes.map((item) => (
                      <label
                        className={
                          sessionType === item.value ? "option-selected" : ""
                        }
                        key={item.value}
                      >
                        <input
                          checked={sessionType === item.value}
                          name="session-type"
                          onChange={() => setSessionType(item.value)}
                          type="radio"
                        />
                        <strong>{item.label}</strong>
                        <small>{item.description}</small>
                      </label>
                    ))}
                  </div>
                </fieldset>

                <label className="english-field english-field-wide">
                  <span>
                    {sessionType === "topic"
                      ? "练习主题（必填）"
                      : "主题或方向（可选）"}
                  </span>
                  <input
                    onChange={(event) => setTopic(event.target.value)}
                    placeholder={
                      sessionType === "interview"
                        ? "例如：前端开发岗位"
                        : sessionType === "technical"
                          ? "例如：解释一个 API 设计"
                          : "例如：My weekend plan"
                    }
                    value={topic}
                  />
                </label>

                <fieldset>
                  <legend>纠错节奏</legend>
                  <div className="english-correction-options">
                    {correctionModes.map((item) => (
                      <label
                        className={
                          correctionMode === item.value
                            ? "option-selected"
                            : ""
                        }
                        key={item.value}
                      >
                        <input
                          checked={correctionMode === item.value}
                          name="correction-mode"
                          onChange={() => setCorrectionMode(item.value)}
                          type="radio"
                        />
                        <strong>{item.label}</strong>
                        <small>{item.description}</small>
                      </label>
                    ))}
                  </div>
                </fieldset>

                <div className="english-setup-row">
                  <label className="english-field">
                    <span>当前水平</span>
                    <select
                      onChange={(event) =>
                        setLevel(event.target.value as EnglishLevel)
                      }
                      value={level}
                    >
                      {["A1", "A2", "B1", "B2", "C1", "C2"].map((item) => (
                        <option key={item} value={item}>
                          {item}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="english-field">
                    <span>模型路线</span>
                    <select
                      onChange={(event) =>
                        setProcessingMode(
                          event.target.value as EnglishProcessingMode,
                        )
                      }
                      value={processingMode}
                    >
                      <option value="standard">MiMo 优先 · 自动本地降级</option>
                      <option value="local">只用本地 Qwen</option>
                    </select>
                  </label>
                </div>

                <div className="english-cost-note">
                  <span>¥0</span>
                  English Coach 不会自动调用 DeepSeek，整个页面没有付费升级入口。
                </div>
                <button
                  className="primary-button english-start-button"
                  disabled={busy === "start-session"}
                  type="submit"
                >
                  {busy === "start-session" ? "正在创建…" : "开始英语对话"}
                </button>
              </form>
            ) : (
              <div className="english-conversation">
                <header className="english-conversation-head">
                  <div>
                    <span>
                      {sessionTypes.find(
                        (item) => item.value === selectedSession.session_type,
                      )?.label || "英语对话"}{" "}
                      · {selectedSession.level}
                    </span>
                    <h2>{sessionTitle(selectedSession)}</h2>
                    <p>
                      {correctionModeLabel(selectedSession.correction_mode)} ·{" "}
                      {selectedSession.processing_mode === "standard"
                        ? "MiMo 优先 / 本地兜底"
                        : "只用本地 Qwen"}
                    </p>
                  </div>
                  {selectedSession.status === "active" ? (
                    <button
                      className="english-finish-button"
                      disabled={busy === "complete-session"}
                      onClick={() => void finishSession()}
                      type="button"
                    >
                      {busy === "complete-session" ? "正在总结…" : "结束并总结"}
                    </button>
                  ) : (
                    <span className="english-complete-badge">已完成</span>
                  )}
                </header>

                <div className="english-message-list">
                  {selectedSession.messages.length === 0 && (
                    <div className="english-welcome">
                      <div>Aa</div>
                      <h3>Ready when you are.</h3>
                      <p>
                        用英语说说你现在在做什么。可以打字，也可以点击麦克风说话。
                      </p>
                    </div>
                  )}
                  {selectedSession.messages.map((message) => {
                    const corrections = message.correction_ids
                      .map((id) => mistakeMap.get(id))
                      .filter((item): item is EnglishMistake => Boolean(item));
                    return (
                      <div
                        className={`english-message english-message-${message.role}`}
                        key={message.id}
                      >
                        <div className="english-message-label">
                          <span>
                            {message.role === "user" ? "YOU" : "JARVIS COACH"}
                          </span>
                          {providerLabel(message) && (
                            <small>{providerLabel(message)}</small>
                          )}
                        </div>
                        {editingMessageId === message.id ? (
                          <div className="english-transcript-editor">
                            <textarea
                              onChange={(event) =>
                                setEditingTranscript(event.target.value)
                              }
                              value={editingTranscript}
                            />
                            <div>
                              <button
                                onClick={() => setEditingMessageId(null)}
                                type="button"
                              >
                                取消
                              </button>
                              <button
                                disabled={busy === `edit-message-${message.id}`}
                                onClick={() => void saveTranscript(message.id)}
                                type="button"
                              >
                                保存转写
                              </button>
                            </div>
                          </div>
                        ) : (
                          <p>{message.content}</p>
                        )}
                        {message.role === "user" && (
                          <button
                            className="english-edit-transcript"
                            onClick={() => {
                              setEditingMessageId(message.id);
                              setEditingTranscript(message.content);
                            }}
                            type="button"
                          >
                            {message.input_mode === "voice_transcript"
                              ? "修正语音转写"
                              : "编辑原句"}
                            {message.transcript_edited && " · 已修改"}
                          </button>
                        )}
                        {corrections.map((mistake) => (
                          <article
                            className="english-inline-correction"
                            key={mistake.id}
                          >
                            <div>
                              <span>{mistake.category}</span>
                              <small>{statusLabels[mistake.status]}</small>
                            </div>
                            <del>{mistake.original_text}</del>
                            <strong>{mistake.corrected_text}</strong>
                            <p>{mistake.explanation}</p>
                            {mistake.status === "pending" && (
                              <div className="english-inline-actions">
                                <button
                                  disabled={busy === `reject-${mistake.id}`}
                                  onClick={() =>
                                    void changeMistakeStatus(mistake, "reject")
                                  }
                                  type="button"
                                >
                                  解释不对
                                </button>
                                <button
                                  disabled={busy === `confirm-${mistake.id}`}
                                  onClick={() => void confirmMistake(mistake)}
                                  type="button"
                                >
                                  确认并加入复习
                                </button>
                              </div>
                            )}
                          </article>
                        ))}
                      </div>
                    );
                  })}
                  {busy === "send-message" && (
                    <div className="english-message english-message-assistant">
                      <div className="english-message-label">
                        <span>JARVIS COACH</span>
                        <small>正在组织回答</small>
                      </div>
                      <div className="english-thinking">
                        <i />
                        <i />
                        <i />
                      </div>
                    </div>
                  )}
                  {selectedSession.summary && (
                    <article className="english-session-summary">
                      <span>SESSION SUMMARY</span>
                      <h3>本次学习小结</h3>
                      <p>{selectedSession.summary}</p>
                      <button
                        onClick={() => setTab("mistakes")}
                        type="button"
                      >
                        打开错题本核对纠错 →
                      </button>
                    </article>
                  )}
                  <div ref={messagesEnd} />
                </div>

                {selectedSession.status === "active" && (
                  <div className="english-composer">
                    <div className="english-composer-status">
                      <span>
                        {draftInputMode === "voice_transcript"
                          ? "语音转写 · 发送前可自由修改"
                          : "English only · Enter 发送，Shift + Enter 换行"}
                      </span>
                      <small>
                        {selectedSession.correction_mode === "summary"
                          ? "本轮不会打断纠错"
                          : correctionModeLabel(selectedSession.correction_mode)}
                      </small>
                    </div>
                    <div className="english-composer-row">
                      <button
                        aria-label={listening ? "停止录音" : "开始语音输入"}
                        className={`english-mic-button ${
                          listening ? "mic-listening" : ""
                        }`}
                        onClick={toggleSpeech}
                        type="button"
                      >
                        {listening ? "■" : "●"}
                      </button>
                      <textarea
                        onChange={(event) => {
                          setDraft(event.target.value);
                          if (draftInputMode !== "voice_transcript") {
                            setDraftInputMode("text");
                          }
                        }}
                        onKeyDown={handleComposerKeyDown}
                        placeholder="Write or speak in English…"
                        value={draft}
                      />
                      <button
                        className="english-send-button"
                        disabled={!draft.trim() || busy === "send-message"}
                        onClick={() => void submitMessage()}
                        type="button"
                      >
                        发送
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </section>
      )}

      {tab === "mistakes" && (
        <section className="english-mistakes-view">
          <div className="english-view-toolbar">
            <div>
              <span>MISTAKE BOOK</span>
              <h2>错题本</h2>
              <p>同类错误会自动合并并累计次数，只有你确认后才会进入复习。</p>
            </div>
            <div className="english-mistake-filters">
              <input
                onChange={(event) => setMistakeQuery(event.target.value)}
                placeholder="搜索原句、改写或解释…"
                value={mistakeQuery}
              />
              <select
                onChange={(event) =>
                  setMistakeStatus(
                    event.target.value as EnglishMistakeStatus | "all",
                  )
                }
                value={mistakeStatus}
              >
                <option value="all">全部状态</option>
                <option value="pending">待确认</option>
                <option value="learning">学习中</option>
                <option value="mastered">已掌握</option>
                <option value="disputed">解释待修正</option>
                <option value="rejected">已忽略</option>
              </select>
            </div>
          </div>

          <div className="english-mistake-list">
            {filteredMistakes.map((mistake) => (
              <article
                className={`english-mistake-card mistake-${mistake.status}`}
                key={mistake.id}
              >
                <header>
                  <div>
                    <span className="mistake-category">{mistake.category}</span>
                    <span className={`mistake-status status-${mistake.status}`}>
                      {statusLabels[mistake.status]}
                    </span>
                    <small>{mistake.cefr}</small>
                  </div>
                  <strong>出现 {mistake.occurrence_count} 次</strong>
                </header>

                {editingMistakeId === mistake.id ? (
                  <div className="english-mistake-editor">
                    <label>
                      <span>正确表达</span>
                      <textarea
                        onChange={(event) =>
                          setEditCorrection(event.target.value)
                        }
                        value={editCorrection}
                      />
                    </label>
                    <label>
                      <span>解释</span>
                      <textarea
                        onChange={(event) =>
                          setEditExplanation(event.target.value)
                        }
                        value={editExplanation}
                      />
                    </label>
                    <div>
                      <button
                        onClick={() => setEditingMistakeId(null)}
                        type="button"
                      >
                        取消
                      </button>
                      <button
                        disabled={busy === `edit-mistake-${mistake.id}`}
                        onClick={() => void saveMistake(mistake)}
                        type="button"
                      >
                        保存修改
                      </button>
                    </div>
                  </div>
                ) : (
                  <>
                    <div className="english-correction-pair">
                      <div>
                        <span>你的原句</span>
                        <p>{mistake.original_text}</p>
                      </div>
                      <div>
                        <span>更自然的表达</span>
                        <p>{mistake.corrected_text}</p>
                      </div>
                    </div>
                    <p className="english-mistake-explanation">
                      {mistake.explanation}
                    </p>
                    <div className="english-mistake-meta">
                      <span>最近出现：{formatDateTime(mistake.last_seen_at)}</span>
                      <span>
                        下次复习：{formatDateTime(mistake.next_review_at)}
                      </span>
                    </div>
                  </>
                )}

                <footer>
                  <button
                    onClick={() => beginMistakeEdit(mistake)}
                    type="button"
                  >
                    修改纠错
                  </button>
                  {mistake.status === "pending" && (
                    <>
                      <button
                        onClick={() =>
                          void changeMistakeStatus(mistake, "reject")
                        }
                        type="button"
                      >
                        忽略
                      </button>
                      <button
                        className="mistake-primary-action"
                        onClick={() => void confirmMistake(mistake)}
                        type="button"
                      >
                        确认并加入复习
                      </button>
                    </>
                  )}
                  {mistake.status === "disputed" && (
                    <button
                      className="mistake-primary-action"
                      onClick={() => void confirmMistake(mistake)}
                      type="button"
                    >
                      修正后重新确认
                    </button>
                  )}
                  {mistake.status === "learning" && (
                    <>
                      <button
                        onClick={() =>
                          void changeMistakeStatus(mistake, "dispute")
                        }
                        type="button"
                      >
                        解释有误
                      </button>
                      <button
                        className="mistake-primary-action"
                        onClick={() =>
                          void changeMistakeStatus(mistake, "master")
                        }
                        type="button"
                      >
                        标记掌握
                      </button>
                    </>
                  )}
                  {mistake.status === "rejected" && (
                    <button
                      className="mistake-primary-action"
                      onClick={() => void confirmMistake(mistake)}
                      type="button"
                    >
                      恢复并加入复习
                    </button>
                  )}
                  <button
                    className="mistake-delete-action"
                    onClick={() => void removeMistake(mistake)}
                    type="button"
                  >
                    删除
                  </button>
                </footer>
              </article>
            ))}
            {filteredMistakes.length === 0 && (
              <div className="english-large-empty">
                <div>Aa</div>
                <strong>
                  {mistakes.length ? "没有符合条件的错题" : "错题本还是空的"}
                </strong>
                <p>开始英语对话后，关键纠错会先来到这里等你确认。</p>
                <button
                  className="primary-button"
                  onClick={() => {
                    setTab("practice");
                    setShowSetup(true);
                  }}
                  type="button"
                >
                  开始一次练习
                </button>
              </div>
            )}
          </div>
        </section>
      )}

      {tab === "review" && (
        <section className="english-review-view">
          <div className="english-view-toolbar">
            <div>
              <span>SPACED REVIEW</span>
              <h2>今日复习</h2>
              <p>高频、最近重复的错误优先。先自己改写，再核对答案。</p>
            </div>
            <div className="english-reminder-badge">
              <i />
              已接入桌面与语音提醒
            </div>
          </div>

          {dueReviews.length > 0 ? (
            <div className="english-review-list">
              {dueReviews.map((review, index) => {
                const revealed = revealedReviews.has(review.id);
                return (
                  <article className="english-review-card" key={review.id}>
                    <header>
                      <span>REVIEW {String(index + 1).padStart(2, "0")}</span>
                      <div>
                        <small>{review.mistake.category}</small>
                        <strong>出现 {review.mistake.occurrence_count} 次</strong>
                      </div>
                    </header>
                    <h3>{review.prompt}</h3>
                    <textarea
                      disabled={revealed}
                      onChange={(event) =>
                        setReviewAnswers((current) => ({
                          ...current,
                          [review.id]: event.target.value,
                        }))
                      }
                      placeholder="在这里写出你认为正确的句子…"
                      value={reviewAnswers[review.id] || ""}
                    />
                    {!revealed ? (
                      <button
                        className="primary-button review-reveal-button"
                        onClick={() => revealReview(review.id)}
                        type="button"
                      >
                        核对答案
                      </button>
                    ) : (
                      <div className="english-review-answer">
                        <span>参考表达</span>
                        <strong>{review.expected_answer}</strong>
                        <p>{review.mistake.explanation}</p>
                        <small>你记得怎么样？</small>
                        <div className="english-review-ratings">
                          {reviewButtons.map((item) => (
                            <button
                              className={item.className || ""}
                              disabled={busy === `review-${review.id}`}
                              key={item.value}
                              onClick={() =>
                                void rateReview(review, item.value)
                              }
                              type="button"
                            >
                              {item.label}
                            </button>
                          ))}
                        </div>
                        <button
                          className="review-dispute-button"
                          disabled={busy === `review-${review.id}`}
                          onClick={() =>
                            void rateReview(review, "incorrect_explanation")
                          }
                          type="button"
                        >
                          这条解释不正确，暂停复习
                        </button>
                      </div>
                    )}
                  </article>
                );
              })}
            </div>
          ) : (
            <div className="english-large-empty review-empty">
              <div>✓</div>
              <strong>今天的到期复习已清空</strong>
              <p>
                {upcomingReviews.length
                  ? `下一次安排在 ${formatDateTime(upcomingReviews[0].scheduled_for)}。`
                  : "确认一条错题后，首次复习会自动安排在明晚 19:00。"}
              </p>
              <button
                onClick={() => setTab("mistakes")}
                type="button"
              >
                去错题本看看
              </button>
            </div>
          )}

          {upcomingReviews.length > 0 && (
            <div className="english-upcoming">
              <div>
                <span>UPCOMING</span>
                <h3>接下来的复习</h3>
              </div>
              <div className="english-upcoming-list">
                {upcomingReviews.slice(0, 8).map((review) => (
                  <article key={review.id}>
                    <time>{formatDateTime(review.scheduled_for)}</time>
                    <p>{review.mistake.original_text}</p>
                    <span>
                      {review.mistake.status === "mastered"
                        ? "低频巩固"
                        : `间隔 ${review.mistake.interval_days} 天`}
                    </span>
                  </article>
                ))}
              </div>
            </div>
          )}
        </section>
      )}
    </main>
  );
}
