import { useState } from "react";

import {
  createInvestmentTransaction,
  deleteInvestmentTransaction,
  updateInvestmentTransaction,
  type InvestmentTransaction,
  type InvestmentTransactionType,
} from "@/lib/api";

import {
  dateLabel,
  today,
  transactionLabels,
  type InvestmentFeedback,
} from "@/components/investment/investment-utils";

export function useInvestmentTransactionForm({
  load,
  feedback,
}: {
  load: () => Promise<void>;
  feedback: InvestmentFeedback;
}) {
  const { busy, setBusy, setError, setNotice, clearFeedback } = feedback;

  const [showTransactionForm, setShowTransactionForm] = useState(false);
  const [editingTransactionId, setEditingTransactionId] = useState<
    string | null
  >(null);
  const [txAssetId, setTxAssetId] = useState("");
  const [txType, setTxType] = useState<InvestmentTransactionType>("buy");
  const [txDate, setTxDate] = useState(today());
  const [txQuantity, setTxQuantity] = useState("");
  const [txPrice, setTxPrice] = useState("");
  const [txCash, setTxCash] = useState("");
  const [txFees, setTxFees] = useState("0");
  const [txReason, setTxReason] = useState("");
  const [txNotes, setTxNotes] = useState("");

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

  return {
    showTransactionForm,
    setShowTransactionForm,
    editingTransactionId,
    txAssetId,
    setTxAssetId,
    txType,
    setTxType,
    txDate,
    setTxDate,
    txQuantity,
    setTxQuantity,
    txPrice,
    setTxPrice,
    txCash,
    setTxCash,
    txFees,
    setTxFees,
    txReason,
    setTxReason,
    txNotes,
    setTxNotes,
    resetTransactionForm,
    editTransaction,
    saveTransaction,
    removeTransaction,
  };
}
