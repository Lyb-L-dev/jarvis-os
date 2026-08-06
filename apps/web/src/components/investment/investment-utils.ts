import type {
  InvestmentAssetType,
  InvestmentReview,
  InvestmentRisk,
  InvestmentTransactionType,
  MoneyValue,
} from "@/lib/api";
import { splitLines, today } from "@/lib/utils";

export { splitLines, today };

export type InvestmentTab =
  | "positions"
  | "transactions"
  | "theses"
  | "news"
  | "reviews";

export const assetTypeOptions: Array<{
  value: InvestmentAssetType;
  label: string;
}> = [
  { value: "stock", label: "股票" },
  { value: "etf", label: "ETF" },
  { value: "fund", label: "基金" },
  { value: "bond", label: "债券" },
  { value: "crypto", label: "数字资产" },
  { value: "cash", label: "现金" },
  { value: "other", label: "其他" },
];

export const riskLabels: Record<InvestmentRisk, string> = {
  low: "低",
  medium: "中",
  high: "高",
  very_high: "很高",
};

export const transactionLabels: Record<InvestmentTransactionType, string> = {
  opening: "初始持仓",
  buy: "买入记录",
  sell: "卖出记录",
  dividend: "分红",
};

export const assessmentLabels: Record<
  InvestmentReview["thesis_assessment"],
  string
> = {
  unchanged: "假设未变",
  strengthened: "假设增强",
  weakened: "假设减弱",
  invalidated: "假设失效",
  uncertain: "等待判断",
};

export type InvestmentFeedback = {
  busy: boolean;
  setBusy: (busy: boolean) => void;
  setError: (error: string | null) => void;
  setNotice: (notice: string | null) => void;
  clearFeedback: () => void;
};

export function numeric(value: MoneyValue | null | undefined) {
  return value === null || value === undefined ? null : Number(value);
}

export function amount(value: MoneyValue | null | undefined, currency?: string) {
  const number = numeric(value);
  if (number === null || Number.isNaN(number)) return "—";
  return `${number.toLocaleString("zh-CN", {
    maximumFractionDigits: 4,
    minimumFractionDigits: 0,
  })}${currency ? ` ${currency}` : ""}`;
}

export function compactNumber(value: MoneyValue | null | undefined) {
  const number = numeric(value);
  if (number === null || Number.isNaN(number)) return "—";
  return number.toLocaleString("zh-CN", { maximumFractionDigits: 6 });
}

export function dateLabel(value?: string | null) {
  if (!value) return "未记录";
  return new Date(`${value}T00:00:00`).toLocaleDateString("zh-CN");
}
