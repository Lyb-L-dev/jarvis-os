"use client";

import { useCallback, useMemo, useState } from "react";

import { InvestmentAssetForm } from "@/components/investment/investment-asset-form";
import { InvestmentCurrencySummary } from "@/components/investment/investment-currency-summary";
import { InvestmentHeader } from "@/components/investment/investment-header";
import { InvestmentNews } from "@/components/investment/investment-news";
import { InvestmentPositions } from "@/components/investment/investment-positions";
import { InvestmentReviews } from "@/components/investment/investment-reviews";
import { InvestmentStats } from "@/components/investment/investment-stats";
import { InvestmentTelemetry } from "@/components/investment/investment-telemetry";
import { InvestmentTheses } from "@/components/investment/investment-theses";
import { InvestmentTransactions } from "@/components/investment/investment-transactions";
import { InvestmentTransactionForm } from "@/components/investment/investment-transaction-form";
import type { InvestmentTab } from "@/components/investment/investment-utils";
import { useInvestmentAssetForm } from "@/components/investment/use-investment-asset-form";
import { useInvestmentData } from "@/components/investment/use-investment-data";
import { useInvestmentReviews } from "@/components/investment/use-investment-reviews";
import { useInvestmentThesisForm } from "@/components/investment/use-investment-thesis-form";
import { useInvestmentTransactionForm } from "@/components/investment/use-investment-transaction-form";

import {
  deleteInvestmentAsset,
  linkAssetNews,
  unlinkAssetNews,
  type InvestmentAsset,
  type RelatedInvestmentNews,
} from "@/lib/api";

export function InvestmentCenter() {
  const [tab, setTab] = useState<InvestmentTab>("positions");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const {
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
  } = useInvestmentData(tab);

  const clearFeedback = useCallback(() => {
    setError(null);
    setNotice(null);
  }, [setError, setNotice]);

  const feedback = useMemo(
    () => ({ busy, setBusy, setError, setNotice, clearFeedback }),
    [busy, setError, setNotice, clearFeedback],
  );

  const positions = useMemo(() => overview?.positions ?? [], [overview]);
  const positionByAsset = useMemo(
    () => new Map(positions.map((position) => [position.asset.id, position])),
    [positions],
  );
  const unpositionedAssets = assets.filter(
    (asset) => !positionByAsset.has(asset.id),
  );

  const assetForm = useInvestmentAssetForm({
    load,
    positionByAsset,
    feedback,
  });
  const transactionForm = useInvestmentTransactionForm({ load, feedback });
  const thesisForm = useInvestmentThesisForm({ load, feedback });
  const reviewControls = useInvestmentReviews({ load, feedback });

  async function removeAsset(asset: InvestmentAsset) {
    if (
      !window.confirm(
        `确定移除 ${asset.name}（${asset.symbol}）吗？\n\n相关持仓、交易、理由和复盘会被软删除，情报关联也会解除。`,
      )
    ) {
      return;
    }
    clearFeedback();
    setBusy(true);
    try {
      await deleteInvestmentAsset(asset.id);
      setNotice("资产及其关联记录已移除。");
      await load();
    } catch (removeError) {
      setError(
        removeError instanceof Error ? removeError.message : "删除资产失败",
      );
    } finally {
      setBusy(false);
    }
  }

  async function toggleNews(item: RelatedInvestmentNews) {
    if (!newsAssetId || busy) return;
    clearFeedback();
    setBusy(true);
    try {
      if (item.linked) {
        await unlinkAssetNews(newsAssetId, item.id);
        setNotice("已解除情报与资产的关联。");
      } else {
        const note =
          window.prompt(
            "可选：说明这条情报为什么与该资产有关。",
            item.relationship_note ?? "",
          ) ?? "";
        await linkAssetNews(newsAssetId, item.id, note);
        setNotice("情报已与资产关联，后续复盘会引用它。");
      }
      await Promise.all([load(), loadNews(newsAssetId)]);
    } catch (linkError) {
      setError(
        linkError instanceof Error ? linkError.message : "更新情报关联失败",
      );
    } finally {
      setBusy(false);
    }
  }

  if (loading && !overview) {
    return (
      <main className="investment-page">
        <div className="investment-loading">
          <span />
          正在核对持仓与交易记录…
        </div>
      </main>
    );
  }

  return (
    <main className="investment-page">
      <InvestmentHeader
        onNewTransaction={() => {
          transactionForm.resetTransactionForm();
          transactionForm.setShowTransactionForm((current) => !current);
          setTab("transactions");
        }}
        onNewAsset={() => {
          assetForm.resetAssetForm();
          assetForm.setShowAssetForm((current) => !current);
          setTab("positions");
        }}
      />

      <InvestmentTelemetry tab={tab} overview={overview} />

      <section className="investment-boundary">
        <span>安全边界</span>
        <p>{overview?.disclaimer}</p>
        <strong>最新价格全部由你手动录入</strong>
      </section>

      {assetForm.showAssetForm ? (
        <InvestmentAssetForm
          form={assetForm}
          positionByAsset={positionByAsset}
          busy={busy}
        />
      ) : null}

      {transactionForm.showTransactionForm ? (
        <InvestmentTransactionForm
          form={transactionForm}
          assets={assets}
          busy={busy}
        />
      ) : null}

      {error ? <div className="investment-feedback error">{error}</div> : null}
      {notice ? <div className="investment-feedback">{notice}</div> : null}

      <InvestmentStats overview={overview} />
      <InvestmentCurrencySummary
        totals={overview?.totals_by_currency ?? []}
      />

      <nav className="investment-tabs" aria-label="投资模块">
        {(
          [
            ["positions", "持仓"],
            ["transactions", "交易"],
            ["theses", "投资理由"],
            ["news", "关联情报"],
            ["reviews", "复盘"],
          ] as Array<[InvestmentTab, string]>
        ).map(([value, label]) => (
          <button
            className={tab === value ? "active" : ""}
            key={value}
            onClick={() => setTab(value)}
            type="button"
          >
            {label}
          </button>
        ))}
      </nav>

      {tab === "positions" ? (
        <InvestmentPositions
          positions={positions}
          unpositionedAssets={unpositionedAssets}
          busy={busy}
          onEditPosition={(position) => {
            assetForm.editPosition(position);
            setTab("positions");
            window.scrollTo({ top: 0, behavior: "smooth" });
          }}
          onRemoveAsset={(asset) => void removeAsset(asset)}
          onRecordFirstBuy={(asset) => {
            transactionForm.setTxAssetId(asset.id);
            transactionForm.setShowTransactionForm(true);
            setTab("transactions");
          }}
          onAddFirstAsset={() => assetForm.setShowAssetForm(true)}
        />
      ) : null}

      {tab === "transactions" ? (
        <InvestmentTransactions
          transactions={transactions}
          busy={busy}
          onNew={() => transactionForm.setShowTransactionForm(true)}
          onEdit={(transaction) => {
            transactionForm.editTransaction(transaction);
            setTab("transactions");
            window.scrollTo({ top: 0, behavior: "smooth" });
          }}
          onRemove={(transaction) =>
            void transactionForm.removeTransaction(transaction)
          }
        />
      ) : null}

      {tab === "theses" ? (
        <InvestmentTheses
          theses={theses}
          assets={assets}
          busy={busy}
          form={thesisForm}
        />
      ) : null}

      {tab === "news" ? (
        <InvestmentNews
          assets={assets}
          news={news}
          newsAssetId={newsAssetId}
          busy={busy}
          onAssetChange={setNewsAssetId}
          onToggle={(item) => void toggleNews(item)}
        />
      ) : null}

      {tab === "reviews" ? (
        <InvestmentReviews
          reviews={reviews}
          assets={assets}
          busy={busy}
          reviewAssetId={reviewControls.reviewAssetId}
          reviewType={reviewControls.reviewType}
          onAssetChange={reviewControls.setReviewAssetId}
          onTypeChange={reviewControls.setReviewType}
          onCreate={() => void reviewControls.createReview()}
          onConfirm={(review) => void reviewControls.confirmReview(review)}
        />
      ) : null}
    </main>
  );
}
