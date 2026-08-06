import { useState } from "react";

import {
  createInvestmentThesis,
  updateInvestmentThesis,
  type InvestmentRisk,
  type InvestmentThesis,
} from "@/lib/api";

import {
  splitLines,
  type InvestmentFeedback,
} from "@/components/investment/investment-utils";

export function useInvestmentThesisForm({
  load,
  feedback,
}: {
  load: () => Promise<void>;
  feedback: InvestmentFeedback;
}) {
  const { busy, setBusy, setError, setNotice, clearFeedback } = feedback;

  const [showThesisForm, setShowThesisForm] = useState(false);
  const [thesisAssetId, setThesisAssetId] = useState("");
  const [thesisTitle, setThesisTitle] = useState("");
  const [originalReason, setOriginalReason] = useState("");
  const [currentView, setCurrentView] = useState("");
  const [assumptions, setAssumptions] = useState("");
  const [watchEvents, setWatchEvents] = useState("");
  const [invalidations, setInvalidations] = useState("");
  const [thesisRisk, setThesisRisk] = useState<InvestmentRisk>("medium");
  const [thesisCloud, setThesisCloud] = useState(false);

  function resetThesisForm() {
    setThesisTitle("");
    setOriginalReason("");
    setCurrentView("");
    setAssumptions("");
    setWatchEvents("");
    setInvalidations("");
    setThesisRisk("medium");
    setThesisCloud(false);
  }

  async function saveThesis() {
    if (!thesisAssetId || !thesisTitle.trim() || !originalReason.trim() || busy) {
      return;
    }
    clearFeedback();
    setBusy(true);
    try {
      await createInvestmentThesis({
        asset_id: thesisAssetId,
        title: thesisTitle.trim(),
        original_reason: originalReason.trim(),
        current_view: currentView.trim() || undefined,
        key_assumptions: splitLines(assumptions),
        watch_events: splitLines(watchEvents),
        invalidation_conditions: splitLines(invalidations),
        risk_level: thesisRisk,
        cloud_allowed: thesisCloud,
      });
      setNotice("新的投资理由已保存，上一版本仍会保留用于复盘。");
      resetThesisForm();
      setShowThesisForm(false);
      await load();
    } catch (saveError) {
      setError(
        saveError instanceof Error ? saveError.message : "保存投资理由失败",
      );
    } finally {
      setBusy(false);
    }
  }

  async function changeThesis(
    thesis: InvestmentThesis,
    action: "cloud" | "invalidated" | "closed",
  ) {
    clearFeedback();
    setBusy(true);
    try {
      if (action === "cloud") {
        if (
          !thesis.cloud_allowed &&
          !window.confirm(
            "开启后，相关分析可能把这份投资理由发送给 MiMo 或 DeepSeek。确定允许吗？",
          )
        ) {
          return;
        }
        await updateInvestmentThesis(thesis.id, {
          cloud_allowed: !thesis.cloud_allowed,
        });
      } else {
        await updateInvestmentThesis(thesis.id, { status: action });
      }
      setNotice("投资理由状态已更新。");
      await load();
    } catch (changeError) {
      setError(
        changeError instanceof Error ? changeError.message : "更新理由失败",
      );
    } finally {
      setBusy(false);
    }
  }

  return {
    showThesisForm,
    setShowThesisForm,
    thesisAssetId,
    setThesisAssetId,
    thesisTitle,
    setThesisTitle,
    originalReason,
    setOriginalReason,
    currentView,
    setCurrentView,
    assumptions,
    setAssumptions,
    watchEvents,
    setWatchEvents,
    invalidations,
    setInvalidations,
    thesisRisk,
    setThesisRisk,
    thesisCloud,
    setThesisCloud,
    resetThesisForm,
    saveThesis,
    changeThesis,
  };
}
