"use client";

import {
  AlertTriangle,
  BellRing,
  BookOpen,
  Check,
  CheckCircle2,
  CircleDot,
  Clock,
  Flame,
  Lightbulb,
  ListTodo,
  Moon,
  RefreshCw,
  Sparkles,
  Target,
  X,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import {
  acceptProactiveSuggestion,
  dismissProactiveSuggestion,
  getProactiveOverview,
  listProactiveSuggestions,
  ProactiveOverview,
  ProactiveSuggestionItem,
  runProactiveScan,
} from "@/lib/api";

type ViewMode = "suggested" | "accepted" | "dismissed";

const typeLabels: Record<string, string> = {
  act: "行动",
  prepare: "准备",
  review: "复盘",
  learn: "学习",
};

const typeIcons: Record<string, ReactNode> = {
  act: <Flame />,
  prepare: <ListTodo />,
  review: <Target />,
  learn: <BookOpen />,
};

const sourceLabels: Record<string, string> = {
  task: "任务",
  weekly_review: "周复盘",
  intelligence: "情报",
  habit: "习惯",
  schedule: "日程",
};

const statusLabels: Record<string, string> = {
  suggested: "待处理",
  accepted: "已接受",
  dismissed: "已忽略",
};

function formatTime(value: string) {
  return new Intl.DateTimeFormat("zh-CN", {
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    month: "2-digit",
  }).format(new Date(value));
}

function errorText(error: unknown) {
  return error instanceof Error ? error.message : "Jarvis 暂时无法读取主动建议";
}

export function ProactiveEngine() {
  const [overview, setOverview] = useState<ProactiveOverview | null>(null);
  const [suggestions, setSuggestions] = useState<ProactiveSuggestionItem[]>([]);
  const [view, setView] = useState<ViewMode>("suggested");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async (signal?: AbortSignal) => {
    setBusy(true);
    try {
      const [overviewData, suggestionsData] = await Promise.all([
        getProactiveOverview(signal),
        listProactiveSuggestions({ signal }),
      ]);
      setOverview(overviewData);
      setSuggestions(suggestionsData);
      setError(null);
    } catch (refreshError) {
      if (!(refreshError instanceof DOMException && refreshError.name === "AbortError")) {
        setError(errorText(refreshError));
      }
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => void refresh(controller.signal), 0);
    const poll = window.setInterval(
      () => void refresh(controller.signal),
      15_000,
    );
    return () => {
      window.clearTimeout(timer);
      window.clearInterval(poll);
      controller.abort();
    };
  }, [refresh]);

  const visible = useMemo(
    () => suggestions.filter((item) => item.status === view),
    [suggestions, view],
  );

  async function scan() {
    setBusy(true);
    setMessage(null);
    setError(null);
    try {
      const result = await runProactiveScan();
      setMessage(
        result.quiet_active
          ? "当前处于静默时段，没有生成新建议（建议在静默结束后自动恢复）。"
          : `已生成 ${result.created} 条新建议${result.skipped.length ? `，跳过：${result.skipped.join("、")}` : ""}。`,
      );
      await refresh();
    } catch (scanError) {
      setError(errorText(scanError));
    } finally {
      setBusy(false);
    }
  }

  async function decide(item: ProactiveSuggestionItem, action: "accept" | "dismiss") {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      await (action === "accept"
        ? acceptProactiveSuggestion(item.id)
        : dismissProactiveSuggestion(item.id));
      setMessage(action === "accept" ? "已接受这条建议。" : "已忽略这条建议。");
      await refresh();
    } catch (actionError) {
      setError(errorText(actionError));
    } finally {
      setBusy(false);
    }
  }

  const metricCards = [
    {
      key: "pending",
      label: "PENDING",
      value: overview?.pending_count ?? 0,
      hint: "待你处理",
      icon: CircleDot,
      tone: "pending",
    },
    {
      key: "today",
      label: "TODAY",
      value: `${overview?.today_created ?? 0} / ${overview?.daily_cap ?? 10}`,
      hint: "今日生成 / 上限",
      icon: Sparkles,
      tone: "today",
    },
    {
      key: "quiet",
      label: "QUIET HOURS",
      value: overview?.quiet_active ? "静默中" : "可提醒",
      hint: overview?.quiet_window ?? "—",
      icon: Moon,
      tone: "quiet",
    },
    {
      key: "cooldown",
      label: "COOLDOWN",
      value: `${overview?.cooldown_hours ?? 24}h`,
      hint: "同类建议去重窗口",
      icon: Clock,
      tone: "cooldown",
    },
    {
      key: "enabled",
      label: "ENGINE",
      value: overview?.enabled ? "运行中" : "已停用",
      hint: "本地规则 · 不调用模型",
      icon: BellRing,
      tone: "enabled",
    },
  ];

  return (
    <section className="proactive-shell">
      <div className="proactive-banner">
        <Lightbulb />
        <div>
          <strong>{overview?.model_note ?? "主动建议由本地规则生成，只产生建议与草稿，不执行动作。"}</strong>
          <p>
            基于目标、任务、情报与习惯信号；遵守静默时段、每日上限和去重冷却，后台不调用任何模型。
          </p>
        </div>
        <button aria-label="立即扫描建议" disabled={busy} onClick={() => void scan()} type="button">
          <RefreshCw className={busy ? "is-spinning" : ""} />
        </button>
      </div>

      {(message || error) && (
        <div className={`personality-notice ${error ? "is-error" : "is-success"}`}>
          {error ? <AlertTriangle /> : <Check />}
          <span>{error ?? message}</span>
          <button onClick={() => { setMessage(null); setError(null); }} type="button"><X /></button>
        </div>
      )}

      <div className="observatory-metrics proactive-metrics">
        {metricCards.map((card) => {
          const Icon = card.icon;
          return (
            <article className={`is-${card.tone}`} key={card.key}>
              <span><Icon /></span>
              <div>
                <small>{card.label}</small>
                <strong>{card.value}</strong>
                <p>{card.hint}</p>
              </div>
            </article>
          );
        })}
      </div>

      <div className="observatory-tabs proactive-tabs">
        {([
          ["suggested", "待处理", overview?.pending_count ?? 0],
          ["accepted", "已接受", suggestions.filter((item) => item.status === "accepted").length],
          ["dismissed", "已忽略", suggestions.filter((item) => item.status === "dismissed").length],
        ] as const).map(([key, label, count]) => (
          <button className={view === key ? "is-active" : ""} key={key} onClick={() => setView(key)} type="button">
            {label}<span>{count}</span>
          </button>
        ))}
      </div>

      <div className="proactive-list">
        {visible.length ? visible.map((item) => {
          const Icon = typeIcons[item.suggestion_type] ?? <Sparkles />;
          return (
            <article className="proactive-card" key={item.id}>
              <div className={`proactive-card-icon is-${item.suggestion_type}`}>
                {Icon}
              </div>
              <div className="proactive-card-body">
                <div className="proactive-card-head">
                  <span className={`proactive-type is-${item.suggestion_type}`}>
                    {typeLabels[item.suggestion_type] ?? item.suggestion_type}
                  </span>
                  <span className="proactive-source">
                    {sourceLabels[item.source_type] ?? item.source_type}
                  </span>
                  <span className={`proactive-priority p${item.priority}`}>
                    {"●".repeat(item.priority)}{"○".repeat(5 - item.priority)}
                  </span>
                  <time>{formatTime(item.suggested_at)}</time>
                </div>
                <h3>{item.title}</h3>
                <p>{item.rationale}</p>
              </div>
              {view === "suggested" ? (
                <div className="proactive-card-actions">
                  <button disabled={busy} onClick={() => void decide(item, "dismiss")} type="button">
                    <X />忽略
                  </button>
                  <button disabled={busy} onClick={() => void decide(item, "accept")} type="button">
                    <Check />接受
                  </button>
                </div>
              ) : (
                <div className="proactive-card-done">
                  <CheckCircle2 />
                  <span>{statusLabels[item.status]}</span>
                </div>
              )}
            </article>
          );
        }) : (
          <div className="observatory-empty">
            <Sparkles />
            <strong>{view === "suggested" ? "当前没有待处理建议" : "这里暂时是空的"}</strong>
            <p>Jarvis 会根据你的任务、情报和习惯在合适的时间主动提出建议。</p>
          </div>
        )}
      </div>
    </section>
  );
}
