import { useState } from "react";

import {
  generateInvestmentReview,
  updateInvestmentReview,
  type InvestmentReview,
} from "@/lib/api";

import type { InvestmentFeedback } from "@/components/investment/investment-utils";

export function useInvestmentReviews({
  load,
  feedback,
}: {
  load: () => Promise<void>;
  feedback: InvestmentFeedback;
}) {
  const { busy, setBusy, setError, setNotice, clearFeedback } = feedback;

  const [reviewAssetId, setReviewAssetId] = useState("");
  const [reviewType, setReviewType] = useState<
    InvestmentReview["review_type"]
  >("weekly");

  async function createReview() {
    if (!reviewAssetId || busy) return;
    clearFeedback();
    setBusy(true);
    try {
      await generateInvestmentReview({
        asset_id: reviewAssetId,
        review_type: reviewType,
      });
      setNotice("事实复盘草稿已生成，请检查并确认你的判断。");
      await load();
    } catch (reviewError) {
      setError(
        reviewError instanceof Error ? reviewError.message : "生成复盘失败",
      );
    } finally {
      setBusy(false);
    }
  }

  async function confirmReview(review: InvestmentReview) {
    const note =
      window.prompt("补充你的复盘结论（可留空）：", review.user_note ?? "") ??
      review.user_note ??
      "";
    const assessment =
      window.prompt(
        "请输入判断：unchanged / strengthened / weakened / invalidated / uncertain",
        review.thesis_assessment,
      ) ?? review.thesis_assessment;
    const allowed = [
      "unchanged",
      "strengthened",
      "weakened",
      "invalidated",
      "uncertain",
    ] as const;
    if (!allowed.includes(assessment as (typeof allowed)[number])) {
      setError("复盘判断值不正确，请重新确认。");
      return;
    }
    clearFeedback();
    setBusy(true);
    try {
      await updateInvestmentReview(review.id, {
        user_note: note || null,
        thesis_assessment: assessment as InvestmentReview["thesis_assessment"],
        status: "confirmed",
      });
      setNotice("复盘已确认并保存。");
      await load();
    } catch (reviewError) {
      setError(
        reviewError instanceof Error ? reviewError.message : "确认复盘失败",
      );
    } finally {
      setBusy(false);
    }
  }

  return {
    reviewAssetId,
    setReviewAssetId,
    reviewType,
    setReviewType,
    createReview,
    confirmReview,
  };
}
