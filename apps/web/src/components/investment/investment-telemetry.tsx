import { CommandTelemetry } from "@/components/command-telemetry";

import type {
  InvestmentOverview,
} from "@/lib/api";

import type { InvestmentTab } from "@/components/investment/investment-utils";

export function InvestmentTelemetry({
  tab,
  overview,
}: {
  tab: InvestmentTab;
  overview: InvestmentOverview | null;
}) {
  return (
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
  );
}
