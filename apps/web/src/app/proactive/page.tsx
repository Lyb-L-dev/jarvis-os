import { ProactiveEngine } from "@/components/proactive-engine";

export default function ProactivePage() {
  return (
    <main className="dashboard proactive-page">
      <header className="topbar proactive-topbar">
        <div>
          <div className="eyebrow">INITIATIVE PLANE · SPRINT 36</div>
          <h1>
            Proactive <span>Engine</span>
          </h1>
          <p className="page-description">
            基于你的目标、任务、情报与习惯，在合适的时间给出主动建议。
            默认只生成建议与草稿，不执行动作，不静默调用付费模型。
          </p>
        </div>
        <div className="observatory-live-badge">
          <i /> SUGGEST ONLY
        </div>
      </header>
      <ProactiveEngine />
    </main>
  );
}
