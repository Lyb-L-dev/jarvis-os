import dynamic from "next/dynamic";

import { CostCenter } from "@/components/cost-center";

const CostCharts = dynamic(
  () => import("@/components/charts/CostCharts").then((m) => m.CostCharts),
  { loading: () => null },
);

export default function CostPage() {
  return (
    <main className="dashboard cost-page">
      <header className="topbar cost-topbar">
        <div>
          <div className="eyebrow">RESOURCE PLANE · SPRINT 33</div>
          <h1>
            Cost <span>Center</span>
          </h1>
          <p className="page-description">
            查看 MiMo、DeepSeek 与本地模型的 Token 和调用次数；DeepSeek 费用单独统计，
            且只在你确认后才会发生。所有费用均为本地估算，不代表供应商账单。
          </p>
        </div>
        <div className="observatory-live-badge">
          <i /> ESTIMATE ONLY
        </div>
      </header>
      <CostCenter />
      <CostCharts />
    </main>
  );
}
