import { ContextEngineering } from "@/components/context-engineering";

export default function ContextPage() {
  return (
    <main className="dashboard context-page">
      <header className="topbar context-topbar">
        <div>
          <div className="eyebrow">CONTEXT PLANE · SPRINT 34</div>
          <h1>
            Context <span>Engineering</span>
          </h1>
          <p className="page-description">
            每个 Agent 只加载当前任务需要的记忆与知识，超长历史先压缩再发送。
            降低 Token、延迟和隐私暴露，并为不同 Agent 执行独立上下文预算。
          </p>
        </div>
        <div className="observatory-live-badge">
          <i /> BUDGETED CONTEXT
        </div>
      </header>
      <ContextEngineering />
    </main>
  );
}
