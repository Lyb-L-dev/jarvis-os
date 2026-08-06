import dynamic from "next/dynamic";

import { AgentObservatory } from "@/components/agent-observatory";

const ObservatoryCharts = dynamic(
  () =>
    import("@/components/charts/ObservatoryCharts").then(
      (m) => m.ObservatoryCharts,
    ),
  { loading: () => null },
);

export default function ObservatoryPage() {
  return (
    <main className="dashboard observatory-page">
      <header className="topbar observatory-topbar">
        <div>
          <div className="eyebrow">RUNNING PLANE · SPRINT 32</div>
          <h1>
            Agent <span>Observatory</span>
          </h1>
          <p className="page-description">
            查看每个 Agent 任务运行到哪一步、为什么暂停或失败，以及关联的审批与工具调用。
            这里只展示运行状态，不展示隐藏推理和私人正文。
          </p>
        </div>
        <div className="observatory-live-badge">
          <i /> LIVE OBSERVATION
        </div>
      </header>
      <AgentObservatory />
      <ObservatoryCharts />
    </main>
  );
}
