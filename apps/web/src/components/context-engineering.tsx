"use client";

import {
  Activity,
  AlertTriangle,
  BarChart3,
  BookOpen,
  Brain,
  FileText,
  Gauge,
  History,
  Layers,
  RefreshCw,
  Scissors,
  ShieldCheck,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  ContextAssemblyItem,
  ContextOverview,
  getContextOverview,
  listContextAssemblies,
} from "@/lib/api";
import { formatNumber, providerPlainLabels } from "@/lib/utils";

const sectionLabels: Record<string, string> = {
  system: "系统",
  memory: "记忆",
  knowledge: "知识",
  history: "历史",
};

const providerLabels: Record<string, string> = providerPlainLabels;

const agentLabels: Record<string, string> = {
  jarvis_core: "Jarvis Core",
  english_coach: "English Coach",
  research: "Research",
  growth: "Growth",
  local_document: "Local Doc",
  investment_intelligence: "Investment",
  default: "默认预算",
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
  return error instanceof Error ? error.message : "Jarvis 暂时无法读取上下文预算";
}

export function ContextEngineering() {
  const [overview, setOverview] = useState<ContextOverview | null>(null);
  const [assemblies, setAssemblies] = useState<ContextAssemblyItem[]>([]);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async (signal?: AbortSignal) => {
    setRefreshing(true);
    try {
      const [overviewData, assembliesData] = await Promise.all([
        getContextOverview(signal),
        listContextAssemblies(50, signal),
      ]);
      setOverview(overviewData);
      setAssemblies(assembliesData);
      setError(null);
    } catch (refreshError) {
      if (!(refreshError instanceof DOMException && refreshError.name === "AbortError")) {
        setError(errorText(refreshError));
      }
    } finally {
      setRefreshing(false);
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

  const maxBudget = useMemo(
    () =>
      Math.max(
        ...(overview?.budgets.map((budget) => budget.budget_chars) ?? [6000]),
        1,
      ),
    [overview],
  );

  const metricCards = [
    {
      key: "today",
      label: "TODAY",
      value: overview?.assemblies_today ?? 0,
      hint: "今日上下文装配",
      icon: Activity,
      tone: "today",
    },
    {
      key: "saved",
      label: "TRIMMED TODAY",
      value: `${formatNumber(overview?.total_trimmed_today ?? 0)}`,
      hint: "今日节省字符",
      icon: Scissors,
      tone: "saved",
    },
    {
      key: "avg",
      label: "AVG CONTEXT",
      value: formatNumber(overview?.avg_total_chars ?? 0),
      hint: "平均上下文（字符）",
      icon: Layers,
      tone: "avg",
    },
    {
      key: "tokens",
      label: "AVG TOKENS",
      value: formatNumber(overview?.avg_estimated_tokens ?? 0),
      hint: `估算约 ${overview?.estimate_chars_per_token ?? 3} 字符/Token`,
      icon: Gauge,
      tone: "tokens",
    },
    {
      key: "total",
      label: "TOTAL",
      value: overview?.assemblies_total ?? 0,
      hint: "全部装配记录",
      icon: History,
      tone: "total",
    },
  ];

  return (
    <section className="context-shell">
      <div className="context-disclaimer">
        <ShieldCheck />
        <div>
          <strong>{overview?.disclaimer ?? "上下文预算按字符估算，用于控制发送给模型的上下文规模。"}</strong>
          <p>
            每个 Agent 有独立预算，按“系统 / 记忆 / 知识 / 历史”分区；超出的历史消息与记忆会在发送前截断，
            不展示隐藏推理与私人正文，只记录统计。
          </p>
        </div>
        <button aria-label="刷新上下文统计" disabled={refreshing} onClick={() => void refresh()} type="button">
          <RefreshCw className={refreshing ? "is-spinning" : ""} />
        </button>
      </div>

      {error && (
        <div className="observatory-notice is-error">
          <AlertTriangle />
          <span>{error}</span>
        </div>
      )}

      <div className="observatory-metrics context-metrics">
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

      <div className="context-grid">
        <div className="context-budgets-panel">
          <div className="cost-panel-heading">
            <div><small>AGENT BUDGETS</small><h2>按 Agent 的上下文预算</h2></div>
            <BarChart3 />
          </div>
          <div className="context-budget-list">
            {overview?.budgets.map((budget) => (
              <div className="context-budget-row" key={budget.agent_id}>
                <div className="context-budget-head">
                  <strong>{agentLabels[budget.agent_id] ?? budget.agent_id}</strong>
                  <span>{formatNumber(budget.budget_chars)} 字符</span>
                </div>
                <div className="context-budget-bar">
                  <span style={{ width: `${(budget.budget_chars / maxBudget) * 100}%` }} />
                </div>
                <div className="context-budget-sections">
                  {Object.entries(budget.sections).map(([key, chars]) => (
                    <span className={`is-${key}`} key={key}>
                      {sectionLabels[key] ?? key} {formatNumber(chars)}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="context-explainer-panel">
          <div className="cost-panel-heading">
            <div><small>HOW IT WORKS</small><h2>装配规则</h2></div>
            <Layers />
          </div>
          <div className="context-rule-list">
            <div><span className="is-system"><FileText /></span><div><strong>系统提示</strong><p>固定占用约 10% 预算，超长自动截断。</p></div></div>
            <div><span className="is-memory"><Brain /></span><div><strong>长期记忆</strong><p>只加载与当前问题相关的已确认记忆，并限制在预算内。</p></div></div>
            <div><span className="is-knowledge"><BookOpen /></span><div><strong>Obsidian 知识</strong><p>按相关性检索，只取命中文档片段，不发送整篇。</p></div></div>
            <div><span className="is-history"><History /></span><div><strong>对话历史</strong><p>超过 20 条自动压缩为摘要，最近消息按预算保留最新部分。</p></div></div>
          </div>
          <p className="context-privacy-note">
            装配记录只保存分区字符数与数量，不保存对话正文、记忆内容或知识文档。
          </p>
        </div>
      </div>

      <div className="context-assemblies-panel">
        <div className="cost-panel-heading">
          <div><small>RECENT ASSEMBLIES</small><h2>最近上下文装配</h2></div>
          <Activity />
        </div>
        <table className="observatory-table context-table">
          <thead>
            <tr>
              <th>Agent</th>
              <th>模型</th>
              <th>预算占用</th>
              <th>估算 Token</th>
              <th>节省</th>
              <th>分区</th>
              <th>时间</th>
            </tr>
          </thead>
          <tbody>
            {assemblies.length ? assemblies.map((item) => {
              const ratio = Math.min((item.total_chars / Math.max(item.budget_chars, 1)) * 100, 100);
              return (
                <tr key={item.id}>
                  <td><strong>{agentLabels[item.agent_id] ?? item.agent_id}</strong></td>
                  <td>{providerLabels[item.provider_used] ?? item.provider_used}</td>
                  <td>
                    <div className="context-usage-cell">
                      <span className="context-usage-bar"><i style={{ width: `${ratio}%` }} /></span>
                      <small>{formatNumber(item.total_chars)} / {formatNumber(item.budget_chars)}</small>
                    </div>
                  </td>
                  <td>{formatNumber(item.estimated_tokens)}</td>
                  <td>{item.trimmed_chars > 0 ? `-${formatNumber(item.trimmed_chars)}` : "—"}</td>
                  <td>
                    <div className="context-section-chips">
                      {item.sections.map((section) => (
                        <span className={`is-${section.key}`} key={section.key}>
                          {sectionLabels[section.key] ?? section.key} {formatNumber(section.chars)}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td>{formatTime(item.created_at)}</td>
                </tr>
              );
            }) : (
              <tr><td className="observatory-table-empty" colSpan={7}>还没有上下文装配记录——发送一条对话后会自动生成</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
