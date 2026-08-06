import { ApprovalCenter } from "@/components/approval-center";

export default function ApprovalsPage() {
  return (
    <main className="dashboard approval-page">
      <header className="topbar approval-topbar">
        <div>
          <div className="eyebrow">HUMAN CONTROL PLANE</div>
          <h1>
            审批 <span>中心</span>
          </h1>
          <p className="page-description">
            所有会改变文件、日历、邮件或外部账号的动作，都必须先在这里看清、确认，
            再单独执行。
          </p>
        </div>
        <div className="approval-live-badge">
          <i /> HUMAN IN CONTROL
        </div>
      </header>
      <ApprovalCenter />
    </main>
  );
}
