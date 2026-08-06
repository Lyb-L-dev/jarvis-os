import { useState } from "react";

import {
  createInitialPosition,
  createInvestmentAsset,
  updateInvestmentAsset,
  updatePortfolioPosition,
  type InvestmentAssetType,
  type InvestmentRisk,
  type PortfolioPosition,
} from "@/lib/api";

import {
  today,
  type InvestmentFeedback,
} from "@/components/investment/investment-utils";

export function useInvestmentAssetForm({
  load,
  positionByAsset,
  feedback,
}: {
  load: () => Promise<void>;
  positionByAsset: Map<string, PortfolioPosition>;
  feedback: InvestmentFeedback;
}) {
  const { busy, setBusy, setError, setNotice, clearFeedback } = feedback;

  const [showAssetForm, setShowAssetForm] = useState(false);
  const [editingAssetId, setEditingAssetId] = useState<string | null>(null);
  const [assetName, setAssetName] = useState("");
  const [assetSymbol, setAssetSymbol] = useState("");
  const [assetMarket, setAssetMarket] = useState("");
  const [assetType, setAssetType] = useState<InvestmentAssetType>("stock");
  const [assetCurrency, setAssetCurrency] = useState("CNY");
  const [assetPrice, setAssetPrice] = useState("");
  const [assetPriceDate, setAssetPriceDate] = useState(today());
  const [assetNotes, setAssetNotes] = useState("");
  const [initialQuantity, setInitialQuantity] = useState("");
  const [initialCost, setInitialCost] = useState("");
  const [initialFees, setInitialFees] = useState("0");
  const [initialDate, setInitialDate] = useState(today());
  const [initialReason, setInitialReason] = useState("");
  const [positionRisk, setPositionRisk] = useState<InvestmentRisk>("medium");
  const [targetAllocation, setTargetAllocation] = useState("");

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

  return {
    showAssetForm,
    setShowAssetForm,
    editingAssetId,
    setEditingAssetId,
    assetName,
    setAssetName,
    assetSymbol,
    setAssetSymbol,
    assetMarket,
    setAssetMarket,
    assetType,
    setAssetType,
    assetCurrency,
    setAssetCurrency,
    assetPrice,
    setAssetPrice,
    assetPriceDate,
    setAssetPriceDate,
    assetNotes,
    setAssetNotes,
    initialQuantity,
    setInitialQuantity,
    initialCost,
    setInitialCost,
    initialFees,
    setInitialFees,
    initialDate,
    setInitialDate,
    initialReason,
    setInitialReason,
    positionRisk,
    setPositionRisk,
    targetAllocation,
    setTargetAllocation,
    resetAssetForm,
    editPosition,
    saveAsset,
  };
}
