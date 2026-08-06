import { useEffect, useRef, useState, type KeyboardEvent } from "react";

import {
  completeEnglishSession,
  editEnglishTranscript,
  sendEnglishMessage,
} from "@/lib/api";
import {
  type SpeechRecognitionConstructor,
  type SpeechRecognitionLike,
} from "@/lib/utils";

import {
  mergeMistakes,
  runAction,
  type EnglishFeedback,
} from "@/components/english/english-utils";
import type { EnglishCollections } from "@/components/english/use-english-collections";

export function useEnglishConversation({
  collections,
  feedback,
}: {
  collections: EnglishCollections;
  feedback: EnglishFeedback;
}) {
  const [draft, setDraft] = useState("");
  const [draftInputMode, setDraftInputMode] = useState<
    "text" | "voice_transcript"
  >("text");
  const [listening, setListening] = useState(false);
  const recognition = useRef<SpeechRecognitionLike | null>(null);
  const messagesEnd = useRef<HTMLDivElement | null>(null);
  const [editingMessageId, setEditingMessageId] = useState<string | null>(null);
  const [editingTranscript, setEditingTranscript] = useState("");

  useEffect(() => {
    messagesEnd.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [collections.selectedSession?.messages.length, feedback.busy]);

  useEffect(
    () => () => {
      recognition.current?.stop();
    },
    [],
  );

  async function submitMessage() {
    const content = draft.trim();
    const session = collections.selectedSession;
    if (!content || !session || session.status !== "active") return;
    await runAction(feedback, "send-message", async () => {
      const response = await sendEnglishMessage(session.id, {
        content,
        input_mode: draftInputMode,
      });
      collections.setSelectedSession((current) =>
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
      collections.setMistakes((current) =>
        mergeMistakes(current, response.mistakes),
      );
      collections.setOverview((current) => ({
        ...current,
        pending_mistakes:
          current.pending_mistakes +
          response.mistakes.filter((item) => item.status === "pending").length,
      }));
      setDraft("");
      setDraftInputMode("text");
    });
  }

  function handleComposerKeyDown(
    event: KeyboardEvent<HTMLTextAreaElement>,
  ) {
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
      feedback.setError("当前浏览器不支持语音转写。可以继续直接输入文字。");
      return;
    }
    feedback.setError(null);
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
      feedback.setError(
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
    const session = collections.selectedSession;
    if (!session) return;
    await runAction(
      feedback,
      "complete-session",
      async () => {
        const result = await completeEnglishSession(session.id);
        collections.setSelectedSession((current) =>
          current
            ? {
                ...current,
                ...result.session,
              }
            : current,
        );
        collections.setMistakes((current) =>
          mergeMistakes(current, result.mistakes),
        );
        await collections.refreshCollections();
      },
      "本次练习已完成，纠错结果正在错题本等待你确认。",
    );
  }

  async function saveTranscript(messageId: string) {
    const value = editingTranscript.trim();
    if (!value) return;
    await runAction(
      feedback,
      `edit-message-${messageId}`,
      async () => {
        const updated = await editEnglishTranscript(messageId, value);
        collections.setSelectedSession((current) =>
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

  return {
    draft,
    setDraft,
    draftInputMode,
    setDraftInputMode,
    listening,
    toggleSpeech,
    submitMessage,
    handleComposerKeyDown,
    finishSession,
    saveTranscript,
    editingMessageId,
    setEditingMessageId,
    editingTranscript,
    setEditingTranscript,
    messagesEnd,
  };
}
