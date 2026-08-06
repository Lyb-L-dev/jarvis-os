import { ComputerUse } from "@/components/computer-use";

export default function ComputerUsePage() {
  return (
    <main className="dashboard computer-page">
      <header className="topbar computer-topbar">
        <div>
          <div className="eyebrow">ACTION PLANE · SPRINT 37</div>
          <h1>
            Computer <span>Use</span>
          </h1>
          <p className="page-description">
            只读查看 → 操作计划与预览 → 确认后修改 → 外部账号逐项授权，逐级开放。
            永远不开放自动交易、支付、凭据和不可恢复删除。
          </p>
        </div>
        <div className="observatory-live-badge">
          <i /> STAGED ACCESS
        </div>
      </header>
      <ComputerUse />
    </main>
  );
}
