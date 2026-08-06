"use client";

import {
  AlertTriangle,
  CheckCircle2,
  Cpu,
  DollarSign,
  FileText,
  Gauge,
  HardDrive,
  Receipt,
  RefreshCw,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  CostCallItem,
  CostOverview,
  getCostOverview,
  listCostCalls,
} from "@/lib/api";
import { formatNumber, providerPlainLabels } from "@/lib/utils";
import { AnimatedNumber } from "@/components/common/AnimatedNumber";
import { GlassPanel } from "@/components/common/GlassPanel";
import { StatCard } from "@/components/common/StatCard";

const providerLabels: Record<string, string> = providerPlainLabels;

function formatCost(value: number) {
  return value.toLocaleString("zh-CN", {
    maximumFractionDigits: 4,
    minimumFractionDigits: 2,
  });
}

function formatTime(value: string) {
  return new Intl.DateTimeFormat("zh-CN", {
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    month: "2-digit",
  }).format(new Date(value));
}

function errorText(error: unknown) {
  return error instanceof Error ? error.message : "Jarvis 暂时无法读取费用统计";
}

export function CostCenter() {
  const [overview, setOverview] = useState<CostOverview | null>(null);
  const [calls, setCalls] = useState<CostCallItem[]>([]);
  const [days, setDays] = useState(30);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(
    async (signal?: AbortSignal) => {
      setRefreshing(true);
      try {
        const [overviewData, callsData] = await Promise.all([
          getCostOverview(days, signal),
          listCostCalls(50, signal),
        ]);
        setOverview(overviewData);
        setCalls(callsData);
        setError(null);
      } catch (refreshError) {
        if (!(refreshError instanceof DOMException && refreshError.name === "AbortError")) {
          setError(errorText(refreshError));
        }
      } finally {
        setRefreshing(false);
      }
    },
    [days],
  );

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

  const maxDailyTokens = useMemo(
    () => Math.max(...(overview?.daily.map((point) => point.total_tokens) ?? [1]), 1),
    [overview],
  );
  const maxDailyCost = useMemo(
    () =>
      Math.max(
        ...(overview?.daily.map((point) => point.deepseek_estimated_cost) ?? [0]),
        0.01,
      ),
    [overview],
  );

  const metricCards: Array<{
    key: string;
    label: string;
    value?: number;
    text?: string;
    format?: (value: number) => string;
    hint: string;
    icon: typeof Gauge;
    tone: string;
    trend?: number[];
  }> = [
    {
      key: "calls",
      label: "TOTAL CALLS",
      value: overview?.total_calls ?? 0,
      format: formatNumber,
      hint: `${overview?.total_successful_calls ?? 0} 次成功`,
      icon: Gauge,
      tone: "calls",
    },
    {
      key: "tokens",
      label: "TOTAL TOKENS",
      value: overview?.total_tokens ?? 0,
      format: formatNumber,
      hint: "输入 + 输出",
      icon: FileText,
      tone: "tokens",
      trend: overview?.daily.map((point) => point.total_tokens),
    },
    {
      key: "all",
      label: "DEEPSEEK 估算",
      value: overview?.deepseek_estimated_total ?? 0,
      format: (value) => `¥${formatCost(value)}`,
      hint: "全部成功调用",
      icon: Receipt,
      tone: "all",
    },
    {
      key: "confirmed",
      label: "已确认付费",
      value: overview?.deepseek_confirmed_estimated_total ?? 0,
      format: (value) => `¥${formatCost(value)}`,
      hint: "仅你确认过的调用",
      icon: ShieldCheck,
      tone: "confirmed",
    },
    {
      key: "local",
      label: "LOCAL ENGINE",
      text: overview?.local.status === "ready" ? "在线" : "离线",
      hint:
        overview?.local.status === "ready"
          ? `${overview.local.loaded_models.length} 个模型已加载`
          : overview?.local.detail ?? "Ollama 不可用",
      icon: Cpu,
      tone: "local",
    },
  ];

  return (
    <section className="cost-shell">
      <GlassPanel className="cost-disclaimer">
        <Receipt />
        <div>
          <strong>{overview?.disclaimer ?? "本地估算费用仅供参考，不代表任何供应商账单。"}</strong>
          <p>
            DeepSeek 按本地单价估算（输入 ¥{overview?.price_rules[1]?.input_per_million ?? 4}/M，
            输出 ¥{overview?.price_rules[1]?.output_per_million ?? 16}/M）；
            MiMo 走 Token Plan 套餐内，Ollama 为本地模型。
          </p>
        </div>
        <button aria-label="刷新费用统计" disabled={refreshing} onClick={() => void refresh()} type="button">
          <RefreshCw className={refreshing ? "is-spinning" : ""} />
        </button>
      </GlassPanel>

      {error && (
        <div className="observatory-notice is-error">
          <AlertTriangle />
          <span>{error}</span>
        </div>
      )}

      <div className="observatory-tabs cost-range-tabs">
        {([7, 30, 90] as const).map((value) => (
          <button
            className={days === value ? "is-active" : ""}
            key={value}
            onClick={() => setDays(value)}
            type="button"
          >
            近 {value} 天
          </button>
        ))}
      </div>

      <div className="observatory-metrics cost-metrics">
        {metricCards.map((card) => {
          const Icon = card.icon;
          return (
            <StatCard
              className={`is-${card.tone}`}
              hint={card.hint}
              icon={<Icon />}
              key={card.key}
              label={card.label}
              trend={card.trend}
              value={
                card.text ??
                (card.value != null ? (
                  <AnimatedNumber format={card.format} value={card.value} />
                ) : "—")
              }
            />
          );
        })}
      </div>

      <div className="cost-grid">
        <div className="cost-providers-panel">
          <div className="cost-panel-heading">
            <div><small>PROVIDER BREAKDOWN</small><h2>按供应商统计</h2></div>
            <span>{overview?.currency ?? "CNY"}</span>
          </div>
          {overview?.providers.map((provider) => (
            <div className={`cost-provider-row is-${provider.provider}`} key={provider.provider}>
              <div className="cost-provider-name">
                <strong>{providerLabels[provider.provider] ?? provider.provider}</strong>
                <small>{provider.cost_note}</small>
              </div>
              <div className="cost-provider-stats">
                <span><small>调用</small><strong>{provider.calls}</strong></span>
                <span><small>Token</small><strong>{formatNumber(provider.total_tokens)}</strong></span>
                {provider.provider === "deepseek" ? (
                  <>
                    <span><small>已确认</small><strong>{provider.confirmed_calls}</strong></span>
                    <span className="cost-value"><small>估算费用</small><strong>¥{formatCost(provider.estimated_cost)}</strong></span>
                  </>
                ) : (
                  <>
                    <span><small>平均耗时</small><strong>{provider.avg_latency_ms != null ? `${(provider.avg_latency_ms / 1000).toFixed(1)}s` : "—"}</strong></span>
                    <span className="cost-value"><small>费用</small><strong>¥0</strong></span>
                  </>
                )}
              </div>
            </div>
          ))}
        </div>

        <div className="cost-local-panel">
          <div className="cost-panel-heading">
            <div><small>LOCAL RUNTIME</small><h2>本地模型资源</h2></div>
            <span className={`cost-local-state is-${overview?.local.status ?? "offline"}`}>
              <i />{overview?.local.status === "ready" ? "运行正常" : "离线"}
            </span>
          </div>
          <div className="cost-local-facts">
            <span><small>进程 CPU</small><strong>{overview?.local.process_cpu_percent != null ? `${overview.local.process_cpu_percent}%` : "—"}</strong></span>
            <span><small>进程内存</small><strong>{overview?.local.process_memory_mb != null ? `${overview.local.process_memory_mb} MB` : "—"}</strong></span>
            <span><small>输出速度</small><strong>{overview?.providers.find((item) => item.provider === "ollama")?.avg_tokens_per_second != null ? `${overview.providers.find((item) => item.provider === "ollama")?.avg_tokens_per_second} tok/s` : "—"}</strong></span>
            <span><small>已加载</small><strong>{overview?.local.loaded_models.length ?? 0}</strong></span>
          </div>
          <div className="cost-loaded-models">
            {overview?.local.loaded_models.length ? overview.local.loaded_models.map((model) => (
              <div className="cost-model-row" key={model.name}>
                <HardDrive />
                <div><strong>{model.name}</strong><p>{model.processor}</p></div>
                <span>{model.size_vram_bytes ? `${(model.size_vram_bytes / 1048576).toFixed(0)} MB VRAM` : `${(model.size_bytes / 1048576).toFixed(0)} MB`}</span>
              </div>
            )) : (
              <div className="cost-empty"><Sparkles /><span>当前没有已加载的本地模型（需要时按需加载）</span></div>
            )}
          </div>
        </div>
      </div>

      <div className="cost-daily-panel">
        <div className="cost-panel-heading">
          <div><small>DAILY USAGE</small><h2>每日用量（近 {overview?.days ?? days} 天）</h2></div>
          <DollarSign />
        </div>
        <div className="cost-daily-chart">
          {overview?.daily.map((point) => (
            <div className="cost-day" key={point.date}>
              <div className="cost-day-bars">
                <span className="cost-bar-tokens" style={{ width: `${Math.max((point.total_tokens / maxDailyTokens) * 100, 2)}%` }} />
                <span className="cost-bar-cost" style={{ width: `${Math.max((point.deepseek_estimated_cost / maxDailyCost) * 100, 1)}%` }} />
              </div>
              <small>{point.date.slice(5)}</small>
              <em>¥{formatCost(point.deepseek_estimated_cost)}</em>
            </div>
          ))}
        </div>
        <div className="cost-chart-legend">
          <span><i className="is-tokens" />Token 用量</span>
          <span><i className="is-cost" />DeepSeek 估算费用</span>
        </div>
      </div>

      <div className="cost-calls-panel">
        <div className="cost-panel-heading">
          <div><small>RECENT ACTIVITY</small><h2>最近模型调用</h2></div>
          <CheckCircle2 />
        </div>
        <table className="observatory-table cost-table">
          <thead>
            <tr>
              <th>来源</th>
              <th>模型</th>
              <th>Token</th>
              <th>耗时</th>
              <th>确认</th>
              <th>估算</th>
              <th>时间</th>
            </tr>
          </thead>
          <tbody>
            {calls.length ? calls.map((call) => (
              <tr key={`${call.source}-${call.id}`}>
                <td>
                  <span className={`observatory-source is-${call.source}`}>
                    {call.source === "chat" ? "对话" : "工作流"}
                  </span>
                  {!call.success ? <span className="cost-failed-mark">失败</span> : null}
                </td>
                <td>
                  <strong>{providerLabels[call.provider_used] ?? call.provider_used}</strong>
                  <small>{call.model_used}</small>
                </td>
                <td>{formatNumber(call.total_tokens ?? 0)}</td>
                <td>{call.latency_ms != null ? `${(call.latency_ms / 1000).toFixed(1)}s` : "—"}</td>
                <td>{call.user_confirmed ? <span className="cost-confirmed-badge">已确认付费</span> : "—"}</td>
                <td className="cost-value">{call.estimated_cost > 0 ? `¥${formatCost(call.estimated_cost)}` : "—"}</td>
                <td>{formatTime(call.created_at)}</td>
              </tr>
            )) : (
              <tr><td className="observatory-table-empty" colSpan={7}>还没有模型调用记录</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
