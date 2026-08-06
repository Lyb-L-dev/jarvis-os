import { useState, type FormEvent } from "react";

import {
  createEnglishSession,
  type EnglishCorrectionMode,
  type EnglishLevel,
  type EnglishProcessingMode,
  type EnglishSessionType,
} from "@/lib/api";

import {
  runAction,
  type EnglishFeedback,
} from "@/components/english/english-utils";
import type { EnglishCollections } from "@/components/english/use-english-collections";

export function useEnglishSetup({
  collections,
  setShowSetup,
  setDraft,
  feedback,
}: {
  collections: EnglishCollections;
  setShowSetup: (show: boolean) => void;
  setDraft: (draft: string) => void;
  feedback: EnglishFeedback;
}) {
  const [sessionType, setSessionType] = useState<EnglishSessionType>("free");
  const [topic, setTopic] = useState("");
  const [correctionMode, setCorrectionMode] =
    useState<EnglishCorrectionMode>("gentle");
  const [level, setLevel] = useState<EnglishLevel>("B1");
  const [processingMode, setProcessingMode] =
    useState<EnglishProcessingMode>("standard");

  async function startSession(event: FormEvent) {
    event.preventDefault();
    if (sessionType === "topic" && !topic.trim()) {
      feedback.setError("主题练习需要先填写一个主题。");
      return;
    }
    await runAction(
      feedback,
      "start-session",
      async () => {
        const session = await createEnglishSession({
          session_type: sessionType,
          topic: topic.trim() || undefined,
          correction_mode: correctionMode,
          level,
          processing_mode: processingMode,
        });
        collections.selectedSessionId.current = session.id;
        collections.setSelectedSession(session);
        collections.setSessions((current) => [session, ...current]);
        setShowSetup(false);
        setDraft("");
        await collections.refreshCollections();
      },
      "新练习已开始。先用英语说一句吧。",
    );
  }

  return {
    sessionType,
    setSessionType,
    topic,
    setTopic,
    correctionMode,
    setCorrectionMode,
    level,
    setLevel,
    processingMode,
    setProcessingMode,
    startSession,
  };
}
