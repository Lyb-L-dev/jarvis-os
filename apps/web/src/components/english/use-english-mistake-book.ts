import { useMemo, useState } from "react";

import {
  confirmEnglishMistake,
  deleteEnglishMistake,
  disputeEnglishMistake,
  masterEnglishMistake,
  rejectEnglishMistake,
  updateEnglishMistake,
  type EnglishMistake,
  type EnglishMistakeStatus,
} from "@/lib/api";

import {
  refreshAfterMistakeAction,
  runAction,
  type EnglishFeedback,
} from "@/components/english/english-utils";
import type { EnglishCollections } from "@/components/english/use-english-collections";

export function useEnglishMistakeBook({
  collections,
  feedback,
}: {
  collections: EnglishCollections;
  feedback: EnglishFeedback;
}) {
  const [mistakeQuery, setMistakeQuery] = useState("");
  const [mistakeStatus, setMistakeStatus] = useState<
    EnglishMistakeStatus | "all"
  >("all");
  const [editingMistakeId, setEditingMistakeId] = useState<string | null>(null);
  const [editCorrection, setEditCorrection] = useState("");
  const [editExplanation, setEditExplanation] = useState("");

  const mistakeMap = useMemo(
    () => new Map(collections.mistakes.map((mistake) => [mistake.id, mistake])),
    [collections.mistakes],
  );

  const filteredMistakes = useMemo(() => {
    const query = mistakeQuery.trim().toLocaleLowerCase();
    return collections.mistakes.filter((mistake) => {
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
  }, [mistakeQuery, mistakeStatus, collections.mistakes]);

  async function confirmMistake(mistake: EnglishMistake) {
    await runAction(
      feedback,
      `confirm-${mistake.id}`,
      async () => {
        await confirmEnglishMistake(mistake.id);
        await refreshAfterMistakeAction(
          feedback,
          () => collections.refreshCollections(),
          "已加入复习；明晚 19:00 会通过桌面和语音提醒你。",
        );
      },
    );
  }

  async function changeMistakeStatus(
    mistake: EnglishMistake,
    action: "reject" | "master" | "dispute",
  ) {
    await runAction(
      feedback,
      `${action}-${mistake.id}`,
      async () => {
        if (action === "reject") await rejectEnglishMistake(mistake.id);
        if (action === "master") await masterEnglishMistake(mistake.id);
        if (action === "dispute") await disputeEnglishMistake(mistake.id);
        await refreshAfterMistakeAction(
          feedback,
          () => collections.refreshCollections(),
          action === "master"
            ? "已标记掌握，复习频率已降低到 30 天后。"
            : action === "dispute"
              ? "已暂停这道题的提醒。修改解释后可重新确认。"
              : "这条纠错已忽略，不会进入复习。",
        );
      },
    );
  }

  function beginMistakeEdit(mistake: EnglishMistake) {
    setEditingMistakeId(mistake.id);
    setEditCorrection(mistake.corrected_text);
    setEditExplanation(mistake.explanation);
  }

  async function saveMistake(mistake: EnglishMistake) {
    if (!editCorrection.trim() || !editExplanation.trim()) return;
    await runAction(
      feedback,
      `edit-mistake-${mistake.id}`,
      async () => {
        await updateEnglishMistake(mistake.id, {
          corrected_text: editCorrection.trim(),
          explanation: editExplanation.trim(),
        });
        setEditingMistakeId(null);
        await refreshAfterMistakeAction(
          feedback,
          () => collections.refreshCollections(),
          "纠错内容已更新，请再次确认后进入复习。",
        );
      },
    );
  }

  async function removeMistake(mistake: EnglishMistake) {
    if (!window.confirm("永久移除这条错题和它尚未触发的复习提醒？")) return;
    await runAction(
      feedback,
      `delete-mistake-${mistake.id}`,
      async () => {
        await deleteEnglishMistake(mistake.id);
        await refreshAfterMistakeAction(
          feedback,
          () => collections.refreshCollections(),
          "错题及未触发的复习提醒已移除。",
        );
      },
    );
  }

  return {
    mistakeQuery,
    setMistakeQuery,
    mistakeStatus,
    setMistakeStatus,
    editingMistakeId,
    setEditingMistakeId,
    editCorrection,
    setEditCorrection,
    editExplanation,
    setEditExplanation,
    mistakeMap,
    filteredMistakes,
    confirmMistake,
    changeMistakeStatus,
    beginMistakeEdit,
    saveMistake,
    removeMistake,
  };
}
