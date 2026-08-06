import Link from "next/link";
import { notFound } from "next/navigation";

const modules: Record<string, { eyebrow: string; title: string; description: string }> = {
  chat: {
    eyebrow: "AGENT CONVERSATION",
    title: "对话",
    description: "General Jarvis 与多模型路由将在 Sprint 2 接入。",
  },
  growth: {
    eyebrow: "GROWTH MANAGER",
    title: "成长",
    description: "目标、里程碑、任务和周复盘将在 Sprint 3 接入。",
  },
  english: {
    eyebrow: "ENGLISH COACH",
    title: "英语",
    description: "英语对话、纠错和复习系统将在 Sprint 5 接入。",
  },
  intelligence: {
    eyebrow: "INFORMATION INTELLIGENCE",
    title: "情报",
    description: "RSS、信息筛选与每日情报将在 Sprint 6 接入。",
  },
  investment: {
    eyebrow: "INVESTMENT ASSISTANT",
    title: "投资",
    description: "手动持仓、交易和投资复盘将在 Sprint 7 接入。",
  },
  memory: {
    eyebrow: "MEMORY CENTER",
    title: "记忆",
    description: "长期记忆管理中心将在 Sprint 3 接入。",
  },
};

export default async function ModulePage({
  params,
}: {
  params: Promise<{ module: string }>;
}) {
  const { module } = await params;
  const item = modules[module];

  if (!item) {
    notFound();
  }

  return (
    <main className="dashboard settings-page">
      <header className="topbar">
        <div>
          <div className="eyebrow">{item.eyebrow}</div>
          <h1>
            Jarvis <span>{item.title}</span>
          </h1>
        </div>
      </header>

      <section className="panel module-placeholder">
        <div className="placeholder-mark">J</div>
        <h2>{item.title}模块已预留</h2>
        <p>{item.description}</p>
        <Link className="primary-button placeholder-link" href="/">
          返回总览
        </Link>
      </section>
    </main>
  );
}
