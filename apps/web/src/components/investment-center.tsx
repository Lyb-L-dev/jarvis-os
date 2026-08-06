"use client";

import {
  createInitialPosition,
  createInvestmentAsset,
  createInvestmentThesis,
  createInvestmentTransaction,
  deleteInvestmentAsset,
  deleteInvestmentTransaction,
  generateInvestmentReview,
  getInvestmentOverview,
  linkAssetNews,
  listAssetNews,
  listInvestmentAssets,
  listInvestmentReviews,
  listInvestmentTheses,
  listInvestmentTransactions,
  unlinkAssetNews,
  updateInvestmentAsset,
  updateInvestmentReview,
  updateInvestmentThesis,
  updateInvestmentTransaction,
  updatePortfolioPosition,
  type InvestmentAsset,
  type InvestmentAssetType,
  type InvestmentOverview,
  type InvestmentReview,
  type InvestmentRisk,
  type InvestmentThesis,
  type InvestmentTransaction,
  type InvestmentTransactionType,
  type MoneyValue,
  type PortfolioPosition,
  type RelatedInvestmentNews,
} from "@/lib/api";
import { useCallback, useEffect, useMemo, useState } from "react";

import { CommandTelemetry } from "@/components/command-telemetry";

type Tab = "positions" | "transactions" | "theses" | "news" | "reviews";

const today = () => new Date().toISOString().slice(0, 10);

const assetTypeOptions: Array<{ value: InvestmentAssetType; label: string }> = [
  { value: "stock", label: "股票" },
  { value: "etf", label: "ETF" },
  { value: "fund", label: "基金" },
  { value: "bond", label: "债券" },
  { value: "crypto", label: "数字资产" },
  { value: "cash", label: "现金" },
  { value: "other", label: "其他" },
];

const riskLabels: Record<InvestmentRisk, string> = {
  low: "低",
  medium: "中",
  high: "高",
  very_high: "很高",
};

const transactionLabels: Record<InvestmentTransactionType, string> = {
  opening: "初始持仓",
  buy: "买入记录",
  sell: "卖出记录",
  dividend: "分红",
};

const assessmentLabels: Record<InvestmentReview["thesis_assessment"], string> = {
  unchanged: "假设未变",
  strengthened: "假设增强",
  weakened: "假设减弱",
  invalidated: "假设失效",
  uncertain: "等待判断",
};

function numeric(value: MoneyValue | null | undefined) {
  return value === null || value === undefined ? null : Number(value);
}

function amount(value: MoneyValue | null | undefined, currency?: string) {
  const number = numeric(value);
  if (number === null || Number.isNaN(number)) return "—";
  return `${number.toLocaleString("zh-CN", {
    maximumFractionDigits: 4,
    minimumFractionDigits: 0,
  })}${currency ? ` ${currency}` : ""}`;
}

function compactNumber(value: MoneyValue | null | undefined) {
  const number = numeric(value);
  if (number === null || Number.isNaN(number)) return "—";
  return number.toLocaleString("zh-CN", { maximumFractionDigits: 6 });
}

function splitLines(value: string) {
  return value
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}

function dateLabel(value?: string | null) {
  if (!value) return "未记录";
  return new Date(`${value}T00:00:00`).toLocaleDateString("zh-CN");
}

export function InvestmentCenter() {
  const [tab, setTab] = useState<Tab>("positions");
  const [overview, setOverview] = useState<InvestmentOverview | null>(null);
  const [assets, setAssets] = useState<InvestmentAsset[]>([]);
  const [transactions, setTransactions] = useState<InvestmentTransaction[]>([]);
  const [theses, setTheses] = useState<InvestmentThesis[]>([]);
  const [reviews, setReviews] = useState<InvestmentReview[]>([]);
  const [news, setNews] = useState<RelatedInvestmentNews[]>([]);
  const [newsAssetId, setNewsAssetId] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const [showAssetForm, setShowAssetForm] = useState(false);
  const [editingAssetId, setEditingAssetId] = useState<string | null>(null);
  const [assetName, setAssetName] = useState("");
  const [assetSymbol, setAssetSymbol] = useState("");
  const [assetMarket, setAssetMarket] = useState("");
  const [assetType, setAssetType] = useState<InvestmentAssetType>("stock");
  const [assetCurrency, setAssetCurrency] = useState("CNY");
  const [assetPrice, setAssetPrice] = useState("");
  const [assetPriceDate, setAssetPriceDate] = useState("");
  const [assetNotes, setAssetNotes] = useState("");
  const [initialQuantity, setInitialQuantity] = useState("");
  const [initialCost, setInitialCost] = useState("");
  const [initialFees, setInitialFees] = useState("0");
  const [initialDate, setInitialDate] = useState("");
  const [initialReason, setInitialReason] = useState("");
  const [positionRisk, setPositionRisk] = useState<InvestmentRisk>("medium");
  const [targetAllocation, setTargetAllocation] = useState("");

  const [showTransactionForm, setShowTransactionForm] = useState(false);
  const [editingTransactionId, setEditingTransactionId] = useState<string | null>(
    null,
  );
  const [txAssetId, setTxAssetId] = useState("");
  const [txType, setTxType] = useState<InvestmentTransactionType>("buy");
  const [txDate, setTxDate] = useState("");
  const [txQuantity, setTxQuantity] = useState("");
  const [txPrice, setTxPrice] = useState("");
  const [txCash, setTxCash] = useState("");
  const [txFees, setTxFees] = useState("0");
  const [txReason, setTxReason] = useState("");
  const [txNotes, setTxNotes] = useState("");

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

  const [reviewAssetId, setReviewAssetId] = useState("");
  const [reviewType, setReviewType] =
    useState<InvestmentReview["review_type"]>("weekly");

  const positions = useMemo(() => overview?.positions ?? [], [overview]);
  const positionByAsset = useMemo(
    () => new Map(positions.map((position) => [position.asset.id, position])),
    [positions],
  );
  const unpositionedAssets = assets.filter(
    (asset) => !positionByAsset.has(asset.id),
  );

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
      setTxAssetId((current) =>
        nextAssets.some((asset) => asset.id === current) ? current : preferred,
      );
      setThesisAssetId((current) =>
        nextAssets.some((asset) => asset.id === current) ? current : preferred,
      );
      setReviewAssetId((current) =>
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

  useEffect(() => {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => {
      setAssetPriceDate(today());
      setInitialDate(today());
      setTxDate(today());
      void load(controller.signal);
    }, 0);
    return () => {
      window.clearTimeout(timeout);
      controller.abort();
    };
  }, [load]);

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

  function clearFeedback() {
    setError(null);
    setNotice(null);
  }

  function resetAssetForm() {
    setEditingAssetId(null);
    setAssetName("");
    setAssetSymbol("");
    setAssetMarket("");
    setAssetType("stock");
    setAssetCurrency("CNY");
    setAssetPrice("");
    setAssetPriceDate(today());
    setAssetNotes("");
    setInitialQuantity("");
    setInitialCost("");
    setInitialFees("0");
    setInitialDate(today());
    setInitialReason("");
    setPositionRisk("medium");
    setTargetAllocation("");
  }

  function editPosition(position: PortfolioPosition) {
    setEditingAssetId(position.asset.id);
    setAssetName(position.asset.name);
    setAssetSymbol(position.asset.symbol);
    setAssetMarket(position.asset.market);
    setAssetType(position.asset.asset_type);
    setAssetCurrency(position.asset.currency);
    setAssetPrice(
      position.asset.latest_price === null ||
        position.asset.latest_price === undefined
        ? ""
        : String(position.asset.latest_price),
    );
    setAssetPriceDate(position.asset.latest_price_date ?? today());
    setAssetNotes(position.asset.notes ?? "");
    setPositionRisk(position.risk_level);
    setTargetAllocation(
      position.target_allocation === null ||
        position.target_allocation === undefined
        ? ""
        : String(position.target_allocation),
    );
    setShowAssetForm(true);
    setTab("positions");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function saveAsset() {
    if (!assetName.trim() || !assetSymbol.trim() || !assetMarket.trim() || busy) {
      return;
    }
    clearFeedback();
    setBusy(true);
    try {
      if (editingAssetId) {
        const position = positionByAsset.get(editingAssetId);
        await updateInvestmentAsset(editingAssetId, {
          name: assetName.trim(),
          symbol: assetSymbol.trim(),
          market: assetMarket.trim(),
          asset_type: assetType,
          currency: assetCurrency.trim(),
          latest_price: assetPrice ? Number(assetPrice) : null,
          latest_price_date: assetPrice ? assetPriceDate : null,
          notes: assetNotes.trim() || null,
        });
        if (position) {
          await updatePortfolioPosition(position.id, {
            risk_level: positionRisk,
            target_allocation: targetAllocation
              ? Number(targetAllocation)
              : null,
          });
        }
        setNotice("资产、手动价格和持仓设置已更新。");
      } else {
        const asset = await createInvestmentAsset({
          name: assetName.trim(),
          symbol: assetSymbol.trim(),
          market: assetMarket.trim(),
          asset_type: assetType,
          currency: assetCurrency.trim(),
          latest_price: assetPrice ? Number(assetPrice) : undefined,
          latest_price_date: assetPrice ? assetPriceDate : undefined,
          notes: assetNotes.trim() || undefined,
        });
        if (initialQuantity && Number(initialQuantity) > 0) {
          if (!initialCost || !initialReason.trim()) {
            throw new Error("录入初始持仓时，需要填写平均成本和原始投资理由。");
          }
          await createInitialPosition({
            asset_id: asset.id,
            quantity: Number(initialQuantity),
            average_cost: Number(initialCost),
            fees: Number(initialFees || 0),
            transaction_date: initialDate,
            reason: initialReason.trim(),
            target_allocation: targetAllocation
              ? Number(targetAllocation)
              : undefined,
            risk_level: positionRisk,
          });
        }
        setNotice(
          initialQuantity
            ? "资产和初始持仓已建立。接下来可以补充完整投资理由。"
            : "资产已保存，尚未建立持仓。",
        );
      }
      resetAssetForm();
      setShowAssetForm(false);
      await load();
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "保存资产失败");
    } finally {
      setBusy(false);
    }
  }

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

  function resetTransactionForm() {
    setEditingTransactionId(null);
    setTxType("buy");
    setTxDate(today());
    setTxQuantity("");
    setTxPrice("");
    setTxCash("");
    setTxFees("0");
    setTxReason("");
    setTxNotes("");
  }

  function editTransaction(transaction: InvestmentTransaction) {
    setEditingTransactionId(transaction.id);
    setTxAssetId(transaction.asset.id);
    setTxType(transaction.transaction_type);
    setTxDate(transaction.transaction_date);
    setTxQuantity(
      transaction.quantity === null || transaction.quantity === undefined
        ? ""
        : String(transaction.quantity),
    );
    setTxPrice(
      transaction.unit_price === null || transaction.unit_price === undefined
        ? ""
        : String(transaction.unit_price),
    );
    setTxCash(
      transaction.cash_amount === null || transaction.cash_amount === undefined
        ? ""
        : String(transaction.cash_amount),
    );
    setTxFees(String(transaction.fees));
    setTxReason(transaction.reason ?? "");
    setTxNotes(transaction.notes ?? "");
    setShowTransactionForm(true);
    setTab("transactions");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function saveTransaction() {
    if (!txAssetId || busy) return;
    const isDividend = txType === "dividend";
    if (
      (isDividend && !txCash) ||
      (!isDividend && (!txQuantity || !txPrice))
    ) {
      setError(isDividend ? "请填写分红金额。" : "请填写数量和成交单价。");
      return;
    }
    clearFeedback();
    setBusy(true);
    try {
      const payload = {
        transaction_type: txType,
        transaction_date: txDate,
        quantity: isDividend ? null : Number(txQuantity),
        unit_price: isDividend ? null : Number(txPrice),
        cash_amount: isDividend ? Number(txCash) : null,
        fees: Number(txFees || 0),
        reason: txReason.trim() || null,
        notes: txNotes.trim() || null,
      };
      if (editingTransactionId) {
        await updateInvestmentTransaction(editingTransactionId, payload);
        setNotice("历史交易已更新，之后的持仓和成本已重新计算。");
      } else {
        await createInvestmentTransaction({
          asset_id: txAssetId,
          transaction_type: txType,
          transaction_date: txDate,
          quantity: isDividend ? undefined : Number(txQuantity),
          unit_price: isDividend ? undefined : Number(txPrice),
          cash_amount: isDividend ? Number(txCash) : undefined,
          fees: Number(txFees || 0),
          reason: txReason.trim() || undefined,
          notes: txNotes.trim() || undefined,
        });
        setNotice("交易已记录，持仓成本已重新计算。");
      }
      resetTransactionForm();
      setShowTransactionForm(false);
      await load();
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "保存交易失败");
    } finally {
      setBusy(false);
    }
  }

  async function removeTransaction(transaction: InvestmentTransaction) {
    if (
      !window.confirm(
        `确定删除 ${dateLabel(transaction.transaction_date)} 的${transactionLabels[transaction.transaction_type]}吗？\n\n系统会重新计算之后的所有持仓成本。`,
      )
    ) {
      return;
    }
    clearFeedback();
    setBusy(true);
    try {
      await deleteInvestmentTransaction(transaction.id);
      setNotice("交易已删除，持仓历史已重新计算。");
      await load();
    } catch (removeError) {
      setError(
        removeError instanceof Error ? removeError.message : "删除交易失败",
      );
    } finally {
      setBusy(false);
    }
  }

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
      <header className="investment-topbar">
        <div>
          <div className="eyebrow">MANUAL · LOCAL · AUDITABLE</div>
          <h1>
            Jarvis <span>投资助手</span>
          </h1>
          <p>手动记录真实交易，保留原始理由，让每次复盘都能回到事实。</p>
        </div>
        <div className="investment-header-actions">
          <button
            className="ghost-button"
            onClick={() => {
              resetTransactionForm();
              setShowTransactionForm((current) => !current);
              setTab("transactions");
            }}
            type="button"
          >
            记录交易
          </button>
          <button
            className="primary-button"
            onClick={() => {
              resetAssetForm();
              setShowAssetForm((current) => !current);
              setTab("positions");
            }}
            type="button"
          >
            + 添加资产
          </button>
        </div>
      </header>

      <CommandTelemetry
        label="投资助手实时状态"
        items={[
          {
            label: "ACTIVE VIEW",
            value:
              tab === "positions"
                ? "持仓"
                : tab === "transactions"
                  ? "交易"
                  : tab === "theses"
                    ? "投资理由"
                    : tab === "news"
                      ? "关联情报"
                      : "事实复盘",
            detail: "手动记录模式",
          },
          {
            label: "POSITIONS",
            value: overview?.active_positions ?? 0,
            detail: `${overview?.asset_count ?? 0} 个资产档案`,
            tone: "green",
          },
          {
            label: "TRANSACTIONS",
            value: overview?.transaction_count ?? 0,
            detail: "完整历史流水",
            tone: "cyan",
          },
          {
            label: "SAFETY LINE",
            value: "人工决策",
            detail: "不预测 · 不自动交易",
            tone: "amber",
          },
        ]}
      />

      <section className="investment-boundary">
        <span>安全边界</span>
        <p>{overview?.disclaimer}</p>
        <strong>最新价格全部由你手动录入</strong>
      </section>

      {showAssetForm ? (
        <section className="panel investment-form-panel">
          <div className="investment-form-head">
            <div>
              <div className="eyebrow">ASSET & POSITION</div>
              <h2>{editingAssetId ? "更新资产与持仓设置" : "建立资产档案"}</h2>
            </div>
            <button
              className="quiet-button"
              onClick={() => setShowAssetForm(false)}
              type="button"
            >
              收起
            </button>
          </div>
          <div className="investment-form-grid asset-form-grid">
            <label>
              资产名称
              <input
                onChange={(event) => setAssetName(event.target.value)}
                placeholder="例如：沪深300 ETF"
                value={assetName}
              />
            </label>
            <label>
              资产代码
              <input
                onChange={(event) => setAssetSymbol(event.target.value)}
                placeholder="510300"
                value={assetSymbol}
              />
            </label>
            <label>
              市场
              <input
                onChange={(event) => setAssetMarket(event.target.value)}
                placeholder="SSE / NASDAQ"
                value={assetMarket}
              />
            </label>
            <label>
              类型
              <select
                onChange={(event) =>
                  setAssetType(event.target.value as InvestmentAssetType)
                }
                value={assetType}
              >
                {assetTypeOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              币种
              <input
                disabled={Boolean(editingAssetId && positionByAsset.get(editingAssetId))}
                maxLength={8}
                onChange={(event) =>
                  setAssetCurrency(event.target.value.toUpperCase())
                }
                value={assetCurrency}
              />
            </label>
            <label>
              手动最新价格
              <input
                min="0"
                onChange={(event) => setAssetPrice(event.target.value)}
                placeholder="未填写就不计算市值"
                step="any"
                type="number"
                value={assetPrice}
              />
            </label>
            <label>
              价格日期
              <input
                disabled={!assetPrice}
                onChange={(event) => setAssetPriceDate(event.target.value)}
                type="date"
                value={assetPriceDate}
              />
            </label>
            <label>
              风险等级
              <select
                onChange={(event) =>
                  setPositionRisk(event.target.value as InvestmentRisk)
                }
                value={positionRisk}
              >
                {Object.entries(riskLabels).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              目标仓位 %
              <input
                max="100"
                min="0"
                onChange={(event) => setTargetAllocation(event.target.value)}
                step="0.1"
                type="number"
                value={targetAllocation}
              />
            </label>
            <label className="investment-wide-field">
              备注
              <textarea
                onChange={(event) => setAssetNotes(event.target.value)}
                placeholder="账户名称等身份信息不要写入这里。"
                rows={2}
                value={assetNotes}
              />
            </label>
          </div>
          {!editingAssetId ? (
            <div className="initial-position-box">
              <div>
                <strong>可选：同时录入初始持仓</strong>
                <span>系统会生成一笔“初始持仓”交易，之后所有成本都从它重算。</span>
              </div>
              <div className="investment-form-grid">
                <label>
                  持仓数量
                  <input
                    min="0"
                    onChange={(event) => setInitialQuantity(event.target.value)}
                    step="any"
                    type="number"
                    value={initialQuantity}
                  />
                </label>
                <label>
                  平均成本
                  <input
                    min="0"
                    onChange={(event) => setInitialCost(event.target.value)}
                    step="any"
                    type="number"
                    value={initialCost}
                  />
                </label>
                <label>
                  手续费
                  <input
                    min="0"
                    onChange={(event) => setInitialFees(event.target.value)}
                    step="any"
                    type="number"
                    value={initialFees}
                  />
                </label>
                <label>
                  建仓日期
                  <input
                    onChange={(event) => setInitialDate(event.target.value)}
                    type="date"
                    value={initialDate}
                  />
                </label>
                <label className="investment-wide-field">
                  当时的原始理由
                  <textarea
                    onChange={(event) => setInitialReason(event.target.value)}
                    placeholder="写下当时真实的事实、判断和目标，避免事后改写记忆。"
                    rows={2}
                    value={initialReason}
                  />
                </label>
              </div>
            </div>
          ) : null}
          <div className="investment-form-actions">
            <button
              className="primary-button"
              disabled={
                busy ||
                !assetName.trim() ||
                !assetSymbol.trim() ||
                !assetMarket.trim()
              }
              onClick={() => void saveAsset()}
              type="button"
            >
              {busy ? "保存中…" : editingAssetId ? "保存修改" : "保存资产"}
            </button>
            <button
              className="quiet-button"
              onClick={() => {
                resetAssetForm();
                setShowAssetForm(false);
              }}
              type="button"
            >
              取消
            </button>
          </div>
        </section>
      ) : null}

      {showTransactionForm ? (
        <section className="panel investment-form-panel">
          <div className="investment-form-head">
            <div>
              <div className="eyebrow">TRANSACTION LEDGER</div>
              <h2>{editingTransactionId ? "修改历史交易" : "记录一笔交易"}</h2>
            </div>
            <span>保存后自动重算之后的全部成本</span>
          </div>
          <div className="investment-form-grid transaction-form-grid">
            <label>
              资产
              <select
                disabled={Boolean(editingTransactionId)}
                onChange={(event) => setTxAssetId(event.target.value)}
                value={txAssetId}
              >
                <option value="">选择资产</option>
                {assets.map((asset) => (
                  <option key={asset.id} value={asset.id}>
                    {asset.name} · {asset.symbol}
                  </option>
                ))}
              </select>
            </label>
            <label>
              类型
              <select
                disabled={txType === "opening"}
                onChange={(event) =>
                  setTxType(event.target.value as InvestmentTransactionType)
                }
                value={txType}
              >
                <option value="buy">买入记录</option>
                <option value="sell">卖出记录</option>
                <option value="dividend">分红</option>
                {txType === "opening" ? (
                  <option value="opening">初始持仓</option>
                ) : null}
              </select>
            </label>
            <label>
              日期
              <input
                onChange={(event) => setTxDate(event.target.value)}
                type="date"
                value={txDate}
              />
            </label>
            {txType === "dividend" ? (
              <label>
                分红金额
                <input
                  min="0"
                  onChange={(event) => setTxCash(event.target.value)}
                  step="any"
                  type="number"
                  value={txCash}
                />
              </label>
            ) : (
              <>
                <label>
                  数量
                  <input
                    min="0"
                    onChange={(event) => setTxQuantity(event.target.value)}
                    step="any"
                    type="number"
                    value={txQuantity}
                  />
                </label>
                <label>
                  成交单价
                  <input
                    min="0"
                    onChange={(event) => setTxPrice(event.target.value)}
                    step="any"
                    type="number"
                    value={txPrice}
                  />
                </label>
              </>
            )}
            <label>
              手续费
              <input
                min="0"
                onChange={(event) => setTxFees(event.target.value)}
                step="any"
                type="number"
                value={txFees}
              />
            </label>
            <label className="investment-wide-field">
              这笔交易当时的理由
              <textarea
                onChange={(event) => setTxReason(event.target.value)}
                placeholder="只记录事实和当时的真实判断。"
                rows={2}
                value={txReason}
              />
            </label>
            <label className="investment-wide-field">
              补充备注
              <textarea
                onChange={(event) => setTxNotes(event.target.value)}
                rows={2}
                value={txNotes}
              />
            </label>
          </div>
          <div className="investment-form-actions">
            <button
              className="primary-button"
              disabled={busy || !txAssetId}
              onClick={() => void saveTransaction()}
              type="button"
            >
              {busy ? "重算中…" : editingTransactionId ? "保存并重算" : "记录交易"}
            </button>
            <button
              className="quiet-button"
              onClick={() => {
                resetTransactionForm();
                setShowTransactionForm(false);
              }}
              type="button"
            >
              取消
            </button>
          </div>
        </section>
      ) : null}

      {error ? <div className="investment-feedback error">{error}</div> : null}
      {notice ? <div className="investment-feedback">{notice}</div> : null}

      <section className="investment-stats">
        <article>
          <span>当前持仓</span>
          <strong>{overview?.active_positions ?? 0}</strong>
          <small>{overview?.asset_count ?? 0} 个资产档案</small>
        </article>
        <article>
          <span>交易记录</span>
          <strong>{overview?.transaction_count ?? 0}</strong>
          <small>可修改并从头重算</small>
        </article>
        <article>
          <span>当前投资理由</span>
          <strong>{overview?.current_theses ?? 0}</strong>
          <small>保留历史版本</small>
        </article>
        <article>
          <span>关联情报</span>
          <strong>{overview?.linked_news ?? 0}</strong>
          <small>只用于研究与复盘</small>
        </article>
      </section>

      {overview?.totals_by_currency.length ? (
        <section className="currency-summary">
          {overview.totals_by_currency.map((total) => (
            <article key={total.currency}>
              <header>
                <strong>{total.currency}</strong>
                <span>
                  {total.priced_positions}/{total.total_positions} 个持仓有价格
                </span>
              </header>
              <div>
                <span>
                  成本 <b>{amount(total.cost_basis)}</b>
                </span>
                <span>
                  手动市值 <b>{amount(total.market_value)}</b>
                </span>
                <span
                  className={
                    numeric(total.unrealized_pnl) &&
                    Number(total.unrealized_pnl) < 0
                      ? "negative"
                      : "positive"
                  }
                >
                  浮动 <b>{amount(total.unrealized_pnl)}</b>
                </span>
                <span>
                  已实现 <b>{amount(total.realized_pnl)}</b>
                </span>
                <span>
                  分红 <b>{amount(total.dividend_income)}</b>
                </span>
              </div>
              {total.market_value === null || total.market_value === undefined ? (
                <p>部分持仓缺少手动价格，因此不展示合计市值和浮动收益。</p>
              ) : null}
            </article>
          ))}
        </section>
      ) : null}

      <nav className="investment-tabs" aria-label="投资模块">
        {(
          [
            ["positions", "持仓"],
            ["transactions", "交易"],
            ["theses", "投资理由"],
            ["news", "关联情报"],
            ["reviews", "复盘"],
          ] as Array<[Tab, string]>
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
        <section className="investment-section">
          <div className="investment-section-head">
            <div>
              <div className="eyebrow">POSITIONS</div>
              <h2>持仓与手动估值</h2>
            </div>
            <span>不同币种不会被直接相加</span>
          </div>
          {positions.length === 0 && unpositionedAssets.length === 0 ? (
            <div className="investment-empty">
              <div>◇</div>
              <strong>还没有资产和持仓</strong>
              <p>先添加一个资产，可选择同时录入初始数量、平均成本和原始理由。</p>
              <button
                className="primary-button"
                onClick={() => setShowAssetForm(true)}
                type="button"
              >
                添加第一个资产
              </button>
            </div>
          ) : (
            <div className="position-grid">
              {positions.map((position) => {
                const pnl = numeric(position.unrealized_pnl);
                return (
                  <article className="position-card" key={position.id}>
                    <header>
                      <div>
                        <span>{position.asset.symbol}</span>
                        <h3>{position.asset.name}</h3>
                        <small>
                          {position.asset.market} · {position.asset.currency}
                        </small>
                      </div>
                      <i className={`risk-${position.risk_level}`}>
                        {riskLabels[position.risk_level]}风险
                      </i>
                    </header>
                    <div className="position-main-value">
                      <span>手动市值</span>
                      <strong>
                        {amount(position.market_value, position.asset.currency)}
                      </strong>
                      {position.latest_price_missing ? (
                        <small>未录入最新价格，不计算浮动收益</small>
                      ) : (
                        <small>
                          价格 {amount(position.asset.latest_price)} ·{" "}
                          {dateLabel(position.asset.latest_price_date)}
                        </small>
                      )}
                    </div>
                    <div className="position-metrics">
                      <span>
                        数量 <b>{compactNumber(position.quantity)}</b>
                      </span>
                      <span>
                        平均成本 <b>{amount(position.average_cost)}</b>
                      </span>
                      <span>
                        成本合计 <b>{amount(position.cost_basis)}</b>
                      </span>
                      <span className={pnl !== null && pnl < 0 ? "negative" : "positive"}>
                        浮动{" "}
                        <b>
                          {amount(position.unrealized_pnl)}
                          {position.unrealized_pnl_percent !== null &&
                          position.unrealized_pnl_percent !== undefined
                            ? ` / ${Number(position.unrealized_pnl_percent).toFixed(2)}%`
                            : ""}
                        </b>
                      </span>
                      <span>
                        已实现 <b>{amount(position.realized_pnl)}</b>
                      </span>
                      <span>
                        分红 <b>{amount(position.dividend_income)}</b>
                      </span>
                    </div>
                    <footer>
                      <span>
                        目标仓位{" "}
                        {position.target_allocation !== null &&
                        position.target_allocation !== undefined
                          ? `${Number(position.target_allocation)}%`
                          : "未设置"}
                      </span>
                      <span>{position.related_news_count} 条关联情报</span>
                      <div>
                        <button onClick={() => editPosition(position)} type="button">
                          编辑 / 更新价格
                        </button>
                        <button
                          className="danger-text-button"
                          disabled={busy}
                          onClick={() => void removeAsset(position.asset)}
                          type="button"
                        >
                          移除
                        </button>
                      </div>
                    </footer>
                  </article>
                );
              })}
              {unpositionedAssets.map((asset) => (
                <article className="position-card asset-only-card" key={asset.id}>
                  <header>
                    <div>
                      <span>{asset.symbol}</span>
                      <h3>{asset.name}</h3>
                      <small>
                        {asset.market} · 尚未建仓
                      </small>
                    </div>
                  </header>
                  <p>资产档案已经保存，但还没有初始持仓或交易记录。</p>
                  <footer>
                    <button
                      onClick={() => {
                        setTxAssetId(asset.id);
                        setShowTransactionForm(true);
                        setTab("transactions");
                      }}
                      type="button"
                    >
                      记录第一笔买入
                    </button>
                    <button
                      className="danger-text-button"
                      onClick={() => void removeAsset(asset)}
                      type="button"
                    >
                      移除
                    </button>
                  </footer>
                </article>
              ))}
            </div>
          )}
        </section>
      ) : null}

      {tab === "transactions" ? (
        <section className="investment-section">
          <div className="investment-section-head">
            <div>
              <div className="eyebrow">LEDGER</div>
              <h2>交易流水</h2>
            </div>
            <button
              className="primary-button"
              onClick={() => setShowTransactionForm(true)}
              type="button"
            >
              + 记录交易
            </button>
          </div>
          {transactions.length === 0 ? (
            <div className="investment-empty compact">
              <strong>暂无交易记录</strong>
              <p>建立初始持仓后，所有成本变化都会在这里保留。</p>
            </div>
          ) : (
            <div className="transaction-table-wrap">
              <table className="transaction-table">
                <thead>
                  <tr>
                    <th>日期 / 类型</th>
                    <th>资产</th>
                    <th>数量</th>
                    <th>单价 / 金额</th>
                    <th>手续费</th>
                    <th>交易后数量</th>
                    <th>交易后均价</th>
                    <th>已实现</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {transactions.map((transaction) => (
                    <tr key={transaction.id}>
                      <td>
                        <strong>
                          {transactionLabels[transaction.transaction_type]}
                        </strong>
                        <span>{dateLabel(transaction.transaction_date)}</span>
                      </td>
                      <td>
                        <b>{transaction.asset.symbol}</b>
                        <span>{transaction.asset.name}</span>
                      </td>
                      <td>{compactNumber(transaction.quantity)}</td>
                      <td>
                        {transaction.transaction_type === "dividend"
                          ? amount(transaction.cash_amount, transaction.currency)
                          : amount(transaction.unit_price, transaction.currency)}
                      </td>
                      <td>{amount(transaction.fees)}</td>
                      <td>{compactNumber(transaction.quantity_after)}</td>
                      <td>{amount(transaction.average_cost_after)}</td>
                      <td
                        className={
                          numeric(transaction.realized_pnl) &&
                          Number(transaction.realized_pnl) < 0
                            ? "negative"
                            : "positive"
                        }
                      >
                        {amount(transaction.realized_pnl)}
                      </td>
                      <td>
                        <button
                          onClick={() => editTransaction(transaction)}
                          type="button"
                        >
                          编辑
                        </button>
                        <button
                          className="danger-text-button"
                          disabled={busy}
                          onClick={() => void removeTransaction(transaction)}
                          type="button"
                        >
                          删除
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      ) : null}

      {tab === "theses" ? (
        <section className="investment-section">
          <div className="investment-section-head">
            <div>
              <div className="eyebrow">INVESTMENT THESES</div>
              <h2>投资理由与失效条件</h2>
            </div>
            <button
              className="primary-button"
              onClick={() => setShowThesisForm((current) => !current)}
              type="button"
            >
              + 记录新理由
            </button>
          </div>
          {showThesisForm ? (
            <div className="panel investment-form-panel thesis-form">
              <div className="investment-form-grid">
                <label>
                  资产
                  <select
                    onChange={(event) => setThesisAssetId(event.target.value)}
                    value={thesisAssetId}
                  >
                    <option value="">选择资产</option>
                    {assets.map((asset) => (
                      <option key={asset.id} value={asset.id}>
                        {asset.name} · {asset.symbol}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  标题
                  <input
                    onChange={(event) => setThesisTitle(event.target.value)}
                    placeholder="例如：2026 年初始投资假设"
                    value={thesisTitle}
                  />
                </label>
                <label>
                  风险等级
                  <select
                    onChange={(event) =>
                      setThesisRisk(event.target.value as InvestmentRisk)
                    }
                    value={thesisRisk}
                  >
                    {Object.entries(riskLabels).map(([value, label]) => (
                      <option key={value} value={value}>
                        {label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="investment-wide-field">
                  原始投资理由
                  <textarea
                    onChange={(event) => setOriginalReason(event.target.value)}
                    placeholder="保存后不会被后续版本覆盖。"
                    rows={4}
                    value={originalReason}
                  />
                </label>
                <label className="investment-wide-field">
                  当前看法
                  <textarea
                    onChange={(event) => setCurrentView(event.target.value)}
                    rows={3}
                    value={currentView}
                  />
                </label>
                <label>
                  关键假设（每行一条）
                  <textarea
                    onChange={(event) => setAssumptions(event.target.value)}
                    rows={4}
                    value={assumptions}
                  />
                </label>
                <label>
                  关注事件（每行一条）
                  <textarea
                    onChange={(event) => setWatchEvents(event.target.value)}
                    rows={4}
                    value={watchEvents}
                  />
                </label>
                <label>
                  失效条件（每行一条）
                  <textarea
                    onChange={(event) => setInvalidations(event.target.value)}
                    rows={4}
                    value={invalidations}
                  />
                </label>
              </div>
              <label className="investment-cloud-control">
                <input
                  checked={thesisCloud}
                  onChange={(event) => setThesisCloud(event.target.checked)}
                  type="checkbox"
                />
                允许相关分析把这份理由发送给云端模型
              </label>
              <div className="investment-form-actions">
                <button
                  className="primary-button"
                  disabled={
                    busy ||
                    !thesisAssetId ||
                    !thesisTitle.trim() ||
                    !originalReason.trim()
                  }
                  onClick={() => void saveThesis()}
                  type="button"
                >
                  保存新版本
                </button>
                <button
                  className="quiet-button"
                  onClick={() => setShowThesisForm(false)}
                  type="button"
                >
                  取消
                </button>
              </div>
            </div>
          ) : null}
          {theses.length === 0 ? (
            <div className="investment-empty compact">
              <strong>还没有完整投资理由</strong>
              <p>建议记录事实依据、关键假设、关注事件和明确的失效条件。</p>
            </div>
          ) : (
            <div className="thesis-list">
              {theses.map((thesis) => (
                <article
                  className={`thesis-card ${thesis.is_current ? "current" : ""}`}
                  key={thesis.id}
                >
                  <header>
                    <div>
                      <span>
                        {thesis.asset.symbol} ·{" "}
                        {thesis.is_current ? "当前版本" : "历史版本"}
                      </span>
                      <h3>{thesis.title}</h3>
                    </div>
                    <div>
                      <i>{riskLabels[thesis.risk_level]}风险</i>
                      <i>{thesis.cloud_allowed ? "云端可用" : "仅本机"}</i>
                    </div>
                  </header>
                  <section>
                    <strong>原始投资理由</strong>
                    <p>{thesis.original_reason}</p>
                  </section>
                  {thesis.current_view ? (
                    <section>
                      <strong>当前看法</strong>
                      <p>{thesis.current_view}</p>
                    </section>
                  ) : null}
                  <div className="thesis-columns">
                    <div>
                      <strong>关键假设</strong>
                      <ul>
                        {thesis.key_assumptions.length ? (
                          thesis.key_assumptions.map((item) => (
                            <li key={item}>{item}</li>
                          ))
                        ) : (
                          <li>未记录</li>
                        )}
                      </ul>
                    </div>
                    <div>
                      <strong>关注事件</strong>
                      <ul>
                        {thesis.watch_events.length ? (
                          thesis.watch_events.map((item) => (
                            <li key={item}>{item}</li>
                          ))
                        ) : (
                          <li>未记录</li>
                        )}
                      </ul>
                    </div>
                    <div>
                      <strong>失效条件</strong>
                      <ul>
                        {thesis.invalidation_conditions.length ? (
                          thesis.invalidation_conditions.map((item) => (
                            <li key={item}>{item}</li>
                          ))
                        ) : (
                          <li>未记录</li>
                        )}
                      </ul>
                    </div>
                  </div>
                  <footer>
                    <span>
                      {new Date(thesis.created_at).toLocaleDateString("zh-CN")} ·{" "}
                      {thesis.status}
                    </span>
                    <div>
                      <button
                        disabled={busy}
                        onClick={() => void changeThesis(thesis, "cloud")}
                        type="button"
                      >
                        {thesis.cloud_allowed ? "改为仅本机" : "允许云端"}
                      </button>
                      {thesis.is_current ? (
                        <>
                          <button
                            disabled={busy}
                            onClick={() =>
                              void changeThesis(thesis, "invalidated")
                            }
                            type="button"
                          >
                            标记失效
                          </button>
                          <button
                            disabled={busy}
                            onClick={() => void changeThesis(thesis, "closed")}
                            type="button"
                          >
                            关闭
                          </button>
                        </>
                      ) : null}
                    </div>
                  </footer>
                </article>
              ))}
            </div>
          )}
        </section>
      ) : null}

      {tab === "news" ? (
        <section className="investment-section">
          <div className="investment-section-head news-section-head">
            <div>
              <div className="eyebrow">INTELLIGENCE LINK</div>
              <h2>资产与情报关联</h2>
            </div>
            <label>
              查看资产
              <select
                onChange={(event) => setNewsAssetId(event.target.value)}
                value={newsAssetId}
              >
                {assets.map((asset) => (
                  <option key={asset.id} value={asset.id}>
                    {asset.name} · {asset.symbol}
                  </option>
                ))}
              </select>
            </label>
          </div>
          {!assets.length ? (
            <div className="investment-empty compact">
              <strong>请先添加资产</strong>
              <p>有了资产后，才能把相关情报纳入投资复盘。</p>
            </div>
          ) : news.length === 0 ? (
            <div className="investment-empty compact">
              <strong>还没有可关联的投资情报</strong>
              <p>情报中心出现投资类内容后，会在这里显示候选项。</p>
            </div>
          ) : (
            <div className="investment-news-list">
              {news.map((item) => (
                <article className={item.linked ? "linked" : ""} key={item.id}>
                  <div>
                    <span>
                      {item.source_name} ·{" "}
                      {item.published_at
                        ? new Date(item.published_at).toLocaleDateString("zh-CN")
                        : "日期未知"}
                    </span>
                    <h3>{item.title}</h3>
                    <p>{item.summary}</p>
                    {item.relationship_note ? (
                      <small>关联说明：{item.relationship_note}</small>
                    ) : null}
                  </div>
                  <div>
                    <a href={item.url} rel="noreferrer" target="_blank">
                      查看来源
                    </a>
                    <button
                      className={item.linked ? "linked-button" : ""}
                      disabled={busy}
                      onClick={() => void toggleNews(item)}
                      type="button"
                    >
                      {item.linked ? "✓ 已关联" : "+ 关联资产"}
                    </button>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>
      ) : null}

      {tab === "reviews" ? (
        <section className="investment-section">
          <div className="investment-section-head review-section-head">
            <div>
              <div className="eyebrow">FACT-BASED REVIEW</div>
              <h2>周度与月度复盘</h2>
            </div>
            <div>
              <select
                onChange={(event) => setReviewAssetId(event.target.value)}
                value={reviewAssetId}
              >
                {assets.map((asset) => (
                  <option key={asset.id} value={asset.id}>
                    {asset.name} · {asset.symbol}
                  </option>
                ))}
              </select>
              <select
                onChange={(event) =>
                  setReviewType(
                    event.target.value as InvestmentReview["review_type"],
                  )
                }
                value={reviewType}
              >
                <option value="weekly">本周复盘</option>
                <option value="monthly">本月复盘</option>
                <option value="manual">今日复盘</option>
              </select>
              <button
                className="primary-button"
                disabled={busy || !reviewAssetId}
                onClick={() => void createReview()}
                type="button"
              >
                生成事实草稿
              </button>
            </div>
          </div>
          {reviews.length === 0 ? (
            <div className="investment-empty compact">
              <strong>暂无投资复盘</strong>
              <p>系统只根据你的交易、手动价格、原始理由和关联情报生成事实草稿。</p>
            </div>
          ) : (
            <div className="review-list">
              {reviews.map((review) => (
                <article className="review-card" key={review.id}>
                  <header>
                    <div>
                      <span>
                        {review.asset.symbol} · {review.review_type}
                      </span>
                      <h3>
                        {dateLabel(review.period_start)} —{" "}
                        {dateLabel(review.period_end)}
                      </h3>
                    </div>
                    <i className={review.status === "confirmed" ? "confirmed" : ""}>
                      {review.status === "confirmed" ? "已确认" : "事实草稿"}
                    </i>
                  </header>
                  <p>{review.summary}</p>
                  <div className="review-columns">
                    <section>
                      <strong>风险与失效条件</strong>
                      <ul>
                        {review.risks.length ? (
                          review.risks.map((item) => <li key={item}>{item}</li>)
                        ) : (
                          <li>本期未自动识别</li>
                        )}
                      </ul>
                    </section>
                    <section>
                      <strong>待确认问题</strong>
                      <ul>
                        {review.questions.length ? (
                          review.questions.map((item) => (
                            <li key={item}>{item}</li>
                          ))
                        ) : (
                          <li>暂无</li>
                        )}
                      </ul>
                    </section>
                  </div>
                  {review.user_note ? (
                    <blockquote>{review.user_note}</blockquote>
                  ) : null}
                  <footer>
                    <span>
                      {assessmentLabels[review.thesis_assessment]} ·{" "}
                      {review.generated_by === "rules" ? "规则整理" : review.generated_by}
                    </span>
                    {review.status === "draft" ? (
                      <button
                        className="primary-button"
                        disabled={busy}
                        onClick={() => void confirmReview(review)}
                        type="button"
                      >
                        检查并确认
                      </button>
                    ) : null}
                  </footer>
                  <small>{review.disclaimer}</small>
                </article>
              ))}
            </div>
          )}
        </section>
      ) : null}
    </main>
  );
}
