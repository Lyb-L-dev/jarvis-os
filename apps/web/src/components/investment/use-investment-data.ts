import { useCallback, useEffect, useState } from "react";

import {
  getInvestmentOverview,
  listAssetNews,
  listInvestmentAssets,
  listInvestmentReviews,
  listInvestmentTheses,
  listInvestmentTransactions,
  type InvestmentAsset,
  type InvestmentOverview,
  type InvestmentReview,
  type InvestmentThesis,
  type InvestmentTransaction,
  type RelatedInvestmentNews,
} from "@/lib/api";

import type { InvestmentTab } from "@/components/investment/investment-utils";

export function useInvestmentData(tab: InvestmentTab) {
  const [overview, setOverview] = useState<InvestmentOverview | null>(null);
  const [assets, setAssets] = useState<InvestmentAsset[]>([]);
  const [transactions, setTransactions] = useState<InvestmentTransaction[]>([]);
  const [theses, setTheses] = useState<InvestmentThesis[]>([]);
  const [reviews, setReviews] = useState<InvestmentReview[]>([]);
  const [news, setNews] = useState<RelatedInvestmentNews[]>([]);
  const [newsAssetId, setNewsAssetId] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    try {
      const [nextOverview, nextAssets, nextTransactions, nextTheses, nextReviews] =
        await Promise.all([
          getInvestmentOverview(signal),
          listInvestmentAssets(signal),
          listInvestmentTransactions(signal),
          listInvestmentTheses(signal),
          listInvestmentReviews(signal),
        ]);
      setOverview(nextOverview);
      setAssets(nextAssets);
      setTransactions(nextTransactions);
      setTheses(nextTheses);
      setReviews(nextReviews);
      const preferred = nextAssets[0]?.id ?? "";
      setNewsAssetId((current) =>
        nextAssets.some((asset) => asset.id === current) ? current : preferred,
      );
      setError(null);
    } catch (loadError) {
      if (loadError instanceof DOMException && loadError.name === "AbortError") {
        return;
      }
      setError(
        loadError instanceof Error ? loadError.message : "读取投资数据失败",
      );
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, []);

  const loadNews = useCallback(async (assetId: string) => {
    if (!assetId) {
      setNews([]);
      return;
    }
    try {
      setNews(await listAssetNews(assetId, true));
    } catch (newsError) {
      setError(
        newsError instanceof Error ? newsError.message : "读取关联情报失败",
      );
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => {
      void load(controller.signal);
    }, 0);
    return () => {
      window.clearTimeout(timeout);
      controller.abort();
    };
  }, [load]);

  useEffect(() => {
    if (tab !== "news") return;
    const controller = new AbortController();
    void listAssetNews(newsAssetId, true, controller.signal)
      .then(setNews)
      .catch((newsError) => {
        if (
          newsError instanceof DOMException &&
          newsError.name === "AbortError"
        ) {
          return;
        }
        setError(
          newsError instanceof Error ? newsError.message : "读取关联情报失败",
        );
      });
    return () => controller.abort();
  }, [newsAssetId, tab]);

  return {
    overview,
    assets,
    transactions,
    theses,
    reviews,
    news,
    newsAssetId,
    setNewsAssetId,
    loading,
    error,
    setError,
    load,
    loadNews,
  };
}
