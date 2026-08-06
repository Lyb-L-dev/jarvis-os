"use client";

import {
  ArrowUpRight,
  BrainCircuit,
  CalendarClock,
  MessageSquareText,
  Radar,
  RefreshCw,
  Route,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { motion } from "motion/react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { providerTitle as providerLabel } from "@/lib/utils";

import {
  JarvisOrb,
  type AIState,
} from "@/components/ai/JarvisOrb";
import { GrowthCard } from "@/components/dashboard/GrowthCard";
import { IntelligenceCard } from "@/components/dashboard/IntelligenceCard";
import {
  getEnglishOverview,
  getGrowthOverview,
  getIntelligenceOverview,
  getInvestmentOverview,
  getMemoryStats,
  getModelStatus,
  getProfile,
  getReadiness,
  getTodayIntelligenceBrief,
  getTodayPlan,
  type DailyBrief,
  type DailyPlan,
  type EnglishOverview,
  type GrowthOverview,
  type IntelligenceOverview,
  type InvestmentOverview,
  type MemoryStats,
  type ModelStatusResponse,
  type ProfileResponse,
  type ReadinessResponse,
} from "@/lib/api";
import { AnimatedNumber } from "@/components/common/AnimatedNumber";
import { Badge } from "@/components/common/Badge";
import { Skeleton } from "@/components/common/Skeleton";
import { Reveal } from "@/components/motion/Reveal";

type DashboardSnapshot = {
  profile: ProfileResponse | null;
  readiness: ReadinessResponse | null;
  models: ModelStatusResponse | null;
  growth: GrowthOverview | null;
  plan: DailyPlan | null;
  english: EnglishOverview | null;
  intelligence: IntelligenceOverview | null;
  brief: DailyBrief | null;
  investment: InvestmentOverview | null;
  memory: MemoryStats | null;
};

const emptySnapshot: DashboardSnapshot = {
  profile: null,
  readiness: null,
  models: null,
  growth: null,
  plan: null,
  english: null,
  intelligence: null,
  brief: null,
  investment: null,
  memory: null,
};

function settledValue<T>(result: PromiseSettledResult<T>): T | null {
  return result.status === "fulfilled" ? result.value : null;
}

function fetchDashboardSnapshot(signal?: AbortSignal) {
  return Promise.allSettled([
    getProfile(signal),
    getReadiness(signal),
    getModelStatus(signal),
    getGrowthOverview(signal),
    getTodayPlan(signal),
    getEnglishOverview(signal),
    getIntelligenceOverview(signal),
    getTodayIntelligenceBrief(signal),
    getInvestmentOverview(signal),
    getMemoryStats(signal),
  ] as const);
}

type DashboardResults = Awaited<ReturnType<typeof fetchDashboardSnapshot>>;

function formatClock(date: Date) {
  return date.toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    hour12: false,
    minute: "2-digit",
  });
}

function formatDate(date: Date) {
  return date.toLocaleDateString("zh-CN", {
    day: "numeric",
    month: "long",
    weekday: "long",
  });
}

function greeting(date: Date) {
  const hour = date.getHours();
  if (hour < 6) return "夜深了";
  if (hour < 11) return "早上好";
  if (hour < 14) return "中午好";
  if (hour < 18) return "下午好";
  return "晚上好";
}

export function Dashboard() {
  const [snapshot, setSnapshot] = useState<DashboardSnapshot>(emptySnapshot);
  const [clock, setClock] = useState<Date | null>(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [systemError, setSystemError] = useState<string | null>(null);

  const applySnapshot = useCallback((results: DashboardResults) => {
    const readiness = settledValue(results[1]);
    setSnapshot({
      profile: settledValue(results[0]),
      readiness,
      models: settledValue(results[2]),
      growth: settledValue(results[3]),
      plan: settledValue(results[4]),
      english: settledValue(results[5]),
      intelligence: settledValue(results[6]),
      brief: settledValue(results[7]),
      investment: settledValue(results[8]),
      memory: settledValue(results[9]),
    });
    setSystemError(
      results[1].status === "rejected"
        ? "Jarvis Core 暂时无法连接"
        : readiness?.status === "degraded"
          ? "部分系统连接需要检查"
          : null,
    );
    setLoading(false);
    setSyncing(false);
  }, []);

  const loadSnapshot = useCallback(async () => {
    applySnapshot(await fetchDashboardSnapshot());
  }, [applySnapshot]);

  const handleManualSync = useCallback(() => {
    setSyncing(true);
    void loadSnapshot();
  }, [loadSnapshot]);

  useEffect(() => {
    const controller = new AbortController();
    void fetchDashboardSnapshot(controller.signal).then((results) => {
      if (!controller.signal.aborted) applySnapshot(results);
    });
    const tickClock = () => setClock(new Date());
    tickClock();
    const timer = window.setInterval(tickClock, 30_000);
    return () => {
      controller.abort();
      window.clearInterval(timer);
    };
  }, [applySnapshot]);

  const aiState: AIState = loading || syncing
    ? "thinking"
    : systemError
      ? "error"
      : "idle";

  const userName = snapshot.profile?.name || "指挥官";
  const configuredModels =
    snapshot.models?.providers.filter((provider) => provider.configured).length ??
    0;
  const totalModels = snapshot.models?.providers.length ?? 3;
  const primaryProvider = providerLabel(snapshot.models?.default_provider);
  const dependencies = snapshot.readiness?.dependencies ?? [];
  const readyDependencies = dependencies.filter(
    (dependency) => dependency.status === "ready",
  ).length;
  const focusTasks = snapshot.plan?.tasks.slice(0, 3) ?? [];
  const intelligenceItems = snapshot.brief?.items.slice(0, 3) ?? [];

  const directive = (() => {
    if (snapshot.intelligence?.today_brief_ready) {
      return `今日情报已经就绪，共 ${snapshot.intelligence.today_brief_count} 条。Jarvis 已优先整理与你的目标和关注方向相关的变化。`;
    }
    if (focusTasks.length > 0) {
      return `今天有 ${focusTasks.length} 项重点任务。先推进“${focusTasks[0].title}”，再处理新的情报与提醒。`;
    }
    return "系统处于待命状态。你可以从一次对话开始，让 Jarvis 帮你确定今天最值得推进的一件事。";
  })();

  const quickActions = [
    {
      href: "/chat",
      icon: MessageSquareText,
      label: "Talk",
      description: "开始对话",
    },
    {
      href: "/intelligence",
      icon: Radar,
      label: "Research",
      description: "研究情报",
    },
    {
      href: "/growth",
      icon: Route,
      label: "Plan",
      description: "规划行动",
    },
  ];

  return (
    <motion.main
      animate={{ opacity: 1, y: 0 }}
      className="dashboard command-center-v2"
      initial={{ opacity: 0, y: 10 }}
      transition={{ damping: 30, stiffness: 240, type: "spring" }}
    >
      <div className="cc-page-ambient" aria-hidden="true" />

      <Reveal>
      <header className="cc-header">
        <div className="cc-greeting">
          <span>JARVIS · PERSONAL AI OPERATING SYSTEM</span>
          <h1>
            {clock ? `${greeting(clock)}，` : ""}
            <strong>{userName}</strong>
          </h1>
          <p>你的私人 AI 助手正在运行。</p>
        </div>

        <div className="cc-runtime">
          <div className={`cc-runtime-state ${systemError ? "is-warn" : ""}`}>
            <i />
            <div>
              <strong>{systemError ? "Partial connection" : "All systems calm"}</strong>
              <small>
                {readyDependencies}/{dependencies.length || 4} 核心服务在线
              </small>
            </div>
          </div>
          <div className="cc-time">
            <span>{clock ? formatDate(clock) : ""}</span>
            <strong>{clock ? formatClock(clock) : ""}</strong>
          </div>
          <button
            aria-label="同步 Jarvis 数据"
            disabled={syncing}
            onClick={handleManualSync}
            type="button"
          >
            <motion.span
              animate={syncing ? { rotate: 360 } : { rotate: 0 }}
              transition={{
                duration: 1,
                ease: "linear",
                repeat: syncing ? Number.POSITIVE_INFINITY : 0,
              }}
            >
              <RefreshCw aria-hidden="true" />
            </motion.span>
          </button>
        </div>
      </header>
      </Reveal>

      <Reveal delay={0.08}>
      <section className="cc-core-deck">
        <div className="cc-core-grid">
          <aside className="cc-core-brief">
            <div className="cc-eyebrow">
              <Sparkles aria-hidden="true" />
              <span>JARVIS NOTICES</span>
            </div>
            <h2>当前建议</h2>
            <p>{loading ? "Jarvis 正在同步你的个人上下文…" : directive}</p>
            <Link href={focusTasks.length > 0 ? "/growth" : "/chat"}>
              {focusTasks.length > 0 ? "进入今日计划" : "请 Jarvis 帮我规划"}
              <ArrowUpRight aria-hidden="true" />
            </Link>
          </aside>

          <div className="cc-core-center">
            <span className="cc-core-kicker">JARVIS CORE</span>
            <JarvisOrb state={aiState} />
          </div>

          <aside className="cc-core-vitals">
            <div className="cc-eyebrow">
              <BrainCircuit aria-hidden="true" />
              <span>LIVE CONTEXT</span>
            </div>
            <h2>正在理解你</h2>
            <div className="cc-vital-list">
              <div>
                <span>Primary intelligence</span>
                <strong>{primaryProvider}</strong>
                <small>
                  {configuredModels}/{totalModels} 模型已配置
                </small>
              </div>
              <div>
                <span>Today&apos;s awareness</span>
                <strong>
                  {loading ? (
                    <Skeleton className="cc-vital-skeleton" />
                  ) : (
                    <AnimatedNumber value={snapshot.intelligence?.unread_items ?? 0} />
                  )}
                </strong>
                <small>条未读情报</small>
              </div>
              <div>
                <span>Memory context</span>
                <strong>
                  {loading ? (
                    <Skeleton className="cc-vital-skeleton" />
                  ) : (
                    <AnimatedNumber value={snapshot.memory?.active ?? 0} />
                  )}
                </strong>
                <small>条有效长期记忆</small>
              </div>
            </div>
            <div className="cc-private-note">
              <ShieldCheck aria-hidden="true" />
              <Badge tone="energy">本地优先 · 私人数据边界已启用</Badge>
            </div>
          </aside>
        </div>

        <nav className="cc-quick-actions" aria-label="快捷行动">
          {quickActions.map((action) => {
            const Icon = action.icon;
            return (
              <Link href={action.href} key={action.href}>
                <span>
                  <Icon aria-hidden="true" strokeWidth={1.6} />
                </span>
                <div>
                  <strong>{action.label}</strong>
                  <small>{action.description}</small>
                </div>
                <ArrowUpRight aria-hidden="true" />
              </Link>
            );
          })}
        </nav>
      </section>
      </Reveal>

      <Reveal delay={0.16}>
      <section className="cc-lower-grid">
        <section className="cc-intelligence-section">
          <div className="cc-section-heading">
            <div>
              <span>TODAY&apos;S INTELLIGENCE</span>
              <h2>值得你关注的变化</h2>
            </div>
            <Link href="/intelligence">
              查看完整情报
              <ArrowUpRight aria-hidden="true" />
            </Link>
          </div>

          {intelligenceItems.length > 0 ? (
            <div className="cc-intelligence-grid">
              <IntelligenceCard featured item={intelligenceItems[0]} />
              <div className="cc-intelligence-secondary">
                {intelligenceItems.slice(1).map((item) => (
                  <IntelligenceCard item={item} key={item.id} />
                ))}
              </div>
            </div>
          ) : (
            <div className="cc-intelligence-empty">
              <Radar aria-hidden="true" />
              <div>
                <strong>Your intelligence system is ready.</strong>
                <p>生成第一份每日情报，让 Jarvis 开始为你筛选重要变化。</p>
              </div>
              <Link href="/intelligence">
                Start your first mission
                <ArrowUpRight aria-hidden="true" />
              </Link>
            </div>
          )}
        </section>

        <GrowthCard
          activeMemories={snapshot.memory?.active ?? 0}
          activePositions={snapshot.investment?.active_positions ?? 0}
          completedTasks={snapshot.growth?.today_completed ?? 0}
          dueReviews={snapshot.english?.due_reviews ?? 0}
          taskCount={snapshot.growth?.today_tasks ?? 0}
          weekMinutes={snapshot.growth?.week_actual_minutes ?? 0}
        />
      </section>
      </Reveal>

      <footer className="cc-footer-note">
        <CalendarClock aria-hidden="true" />
        <span>
          Jarvis 会根据你的任务、情报、记忆和反馈持续更新这里，但不会自动执行高风险操作。
        </span>
      </footer>
    </motion.main>
  );
}
