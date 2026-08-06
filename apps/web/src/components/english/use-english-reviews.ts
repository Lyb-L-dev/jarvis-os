import { useState } from "react";

import {
  submitEnglishReview,
  type EnglishReview,
  type EnglishReviewResult,
} from "@/lib/api";

import {
  refreshAfterMistakeAction,
  runAction,
  type EnglishFeedback,
} from "@/components/english/english-utils";
import type { EnglishCollections } from "@/components/english/use-english-collections";

export function useEnglishReviews({
  collections,
  feedback,
}: {
  collections: EnglishCollections;
  feedback: EnglishFeedback;
}) {
  const [reviewAnswers, setReviewAnswers] = useState<Record<string, string>>({});
  const [revealedReviews, setRevealedReviews] = useState<Set<string>>(
    new Set(),
  );

  function revealReview(reviewId: string) {
    setRevealedReviews((current) => new Set(current).add(reviewId));
  }

  async function rateReview(
    review: EnglishReview,
    result: EnglishReviewResult,
  ) {
    await runAction(feedback, `review-${review.id}`, async () => {
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
        feedback,
        () => collections.refreshCollections(),
        result === "incorrect_explanation"
          ? "这道题已暂停。请在错题本修正解释后重新确认。"
          : "复习结果已保存，下次时间已自动安排。",
      );
    });
  }

  return {
    reviewAnswers,
    setReviewAnswers,
    revealedReviews,
    revealReview,
    rateReview,
  };
}
