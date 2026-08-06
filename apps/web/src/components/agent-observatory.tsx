"use client";

import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  ChevronRight,
  CircleDot,
  Eye,
  LockKeyhole,
  PauseCircle,
  RefreshCw,
  ShieldCheck,
  Wrench,
  XCircle,
} from "lucide-react";
import { motion } from "motion/react";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  getObservatoryOverview,
  getObservatoryRun,
  listObservatoryApprovals,
  listObservatoryErrors,
  listObservatoryRuns,
  listObservatoryToolExecutions,
  ObservatoryApproval,
  ObservatoryError,
  ObservatoryOverview,
  ObservatoryRunDetail,
  ObservatoryRunSummary,
  ObservatoryRunStep,
  ObservatoryToolExecution,
} from "@/lib/api";
import { EmptyState } from "@/components/common/EmptyState";
import { StatusDot, type StatusTone } from "@/components/common/StatusDot";

type ViewMode = "runs" | "tools" | "approvals" | "errors";

const runStatusLabels: Record<string, string> = {
  created: "已创建",
  running: "运行中",
  waiting_for_input: "等待补充信息",
  waiting_for_model_approval: "等待模型确认",
  waiting_for_draft_review: "等待草稿审核",
  completed: "已完成",
  failed: "失败",
  cancelled: "已取消",
  rejected: "已拒绝",
};

const runStatusTone: Record<string, StatusTone> = {
  created: "neutral",
  running: "listen",
  waiting_for_input: "warning",
  waiting_for_model_approval: "warning",
  waiting_for_draft_review: "warning",
  completed: "success",
  failed: "danger",
  cancelled: "neutral",
  rejected: "danger",
};

const stepKindLabels: Record<string, string> = {
  approval: "审批",
  model: "模型",
  planning: "规划",
  research: "研究",
  retrieval: "读取",
  tool: "工具",
};

const stepStatusLabels: Record<string, string> = {
  running: "执行中",
  completed: "完成",
  failed: "失败",
  waiting_for_approval: "等待审批",
  waiting_for_user: "等待用户",
};

const toolStatusLabels: Record<string, string> = {
  created: "已创建",
  pending_approval: "等待审批",
  executing: "执行中",
  succeeded: "已完成",
  failed: "失败",
  rejected: "已拒绝",
  expired: "已过期",
};

const approvalStatusLabels: Record<string, string> = {
  pending: "待决定",
  approved: "已批准",
  rejected: "已拒绝",
  expired: "已过期",
  consumed: "已使用",
};

function formatTime(value?: string | null) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("zh-CN", {
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    month: "2-digit",
  }).format(new Date(value));
}

function formatDuration(value?: number | null) {
  if (!value || value < 0) return "—";
  const seconds = Math.round(value / 1000);
  if (seconds < 60) return `${seconds} 秒`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} 分 ${seconds % 60} 秒`;
  return `${Math.floor(minutes / 60)} 时 ${minutes % 60} 分`;
}

function errorText(error: unknown) {
  return error instanceof Error ? error.message : "Jarvis 暂时无法读取运行状态";
}

function statusClass(value: string) {
  return value.toLowerCase().replaceAll("_", "-");
}

function StepRow({ step, last }: { step: ObservatoryRunStep; last: boolean }) {
  const failed = step.status === "failed";
  const waiting = step.status.startsWith("waiting");
  return (
    <div className="observatory-step-row">
      <div className="observatory-step-rail">
        <span className={`observatory-step-node is-${statusClass(step.status)}`}>
          {failed ? <XCircle /> : waiting ? <PauseCircle /> : <CheckCircle2 />}
        </span>
        {last ? null : <i className="observatory-step-line" />}
      </div>
      <div className="observatory-step-body">
        <div className="observatory-step-head">
          <span className="observatory-step-index">STEP {String(step.sequence).padStart(2, "0")}</span>
          <span className={`observatory-step-status is-${statusClass(step.status)}`}>
            {stepStatusLabels[step.status] ?? step.status}
          </span>
        </div>
        <strong>{step.step_key}</strong>
        <p>
          {stepKindLabels[step.kind] ?? step.kind}
          {step.error_code ? ` · 错误 ${step.error_code}` : ""}
          {step.duration_ms != null ? ` · ${formatDuration(step.duration_ms)}` : ""}
        </p>
        {step.output_refs.length > 0 ? (
          <small className="observatory-step-refs">
            {step.output_refs.map((ref) => `${ref.kind}:${ref.ref_id.slice(0, 8)}`).join(" · ")}
          </small>
        ) : null}
      </div>
    </div>
  );
}

function RunDetailPanel({
  detail,
  onClose,
}: {
  detail: ObservatoryRunDetail | null;
  onClose: () => void;
}) {
  if (!detail) {
    return (
      <div className="observatory-empty inspector">
        <Eye />
        <strong>选择一个运行任务</strong>
        <p>查看它执行到哪一步、为什么暂停或失败，以及关联的审批与工具调用。</p>
      </div>
    );
  }
  return (
    <motion.div
      animate={{ opacity: 1, y: 0 }}
      className="observatory-run-inspector"
      initial={false}
      key={detail.id}
    >
      <div className="observatory-inspector-head">
        <div>
          <span className={`observatory-run-status is-${statusClass(detail.status)}`}>
            {runStatusLabels[detail.status] ?? detail.status}
          </span>
          <small>
            {detail.agent_id.toUpperCase()} · {detail.workflow_version} ·{" "}
            {detail.runtime.toUpperCase()}
          </small>
        </div>
        <button aria-label="关闭详情" onClick={onClose} type="button">×</button>
      </div>
      <h2>{detail.request_type}</h2>
      <div className="observatory-inspector-facts">
        <span><small>当前步骤</small><strong>{detail.current_step ?? "—"}</strong></span>
        <span><small>暂停原因</small><strong>{detail.pending_label ?? "—"}</strong></span>
        <span><small>模型</small><strong>{detail.model_used ?? detail.provider_used ?? "—"}</strong></span>
        <span><small>Token</small><strong>{detail.total_tokens ?? "—"}</strong></span>
        <span><small>耗时</small><strong>{formatDuration(detail.duration_ms)}</strong></span>
        <span><small>创建</small><strong>{formatTime(detail.created_at)}</strong></span>
      </div>
      {detail.error_code ? (
        <div className="observatory-inspector-error">
          <AlertTriangle />
          <div><strong>运行失败</strong><p>{detail.error_code}</p></div>
        </div>
      ) : null}

      <div className="observatory-inspector-section">
        <div className="observatory-section-title">
          <Activity /><span>步骤时间线</span><small>{detail.steps.length} 步</small>
        </div>
        {detail.steps.length ? (
          <div className="observatory-timeline">
            {detail.steps.map((step, index) => (
              <StepRow key={`${step.sequence}-${step.step_key}`} last={index === detail.steps.length - 1} step={step} />
            ))}
          </div>
        ) : (
          <EmptyState compact title="还没有步骤记录" />
        )}
      </div>

      <div className="observatory-inspector-grid">
        <div className="observatory-inspector-section">
          <div className="observatory-section-title">
            <ShieldCheck /><span>审批</span><small>{detail.approvals.length} 条</small>
          </div>
          {detail.approvals.length ? detail.approvals.map((approval) => (
            <div className="observatory-linked-row" key={approval.kind}>
              <span className={`observatory-mini-status is-${statusClass(approval.status)}`}>
                {approvalStatusLabels[approval.status] ?? approval.status}
              </span>
              <div><strong>{approval.title}</strong><p>{approval.reason_code}{approval.provider ? ` · ${approval.provider}` : ""}</p></div>
              <small>{formatTime(approval.decided_at ?? approval.created_at)}</small>
            </div>
          )) : (
            <EmptyState compact title="没有审批记录" />
          )}
        </div>
        <div className="observatory-inspector-section">
          <div className="observatory-section-title">
            <Wrench /><span>工具调用</span><small>{detail.tool_executions.length} 次</small>
          </div>
          {detail.tool_executions.length ? detail.tool_executions.map((tool) => (
            <div className="observatory-linked-row" key={tool.id}>
              <span className={`observatory-mini-status is-${statusClass(tool.status)}`}>
                {toolStatusLabels[tool.status] ?? tool.status}
              </span>
              <div>
                <strong>{tool.tool_id}</strong>
                <p>R{tool.risk_level.replace("R", "")}{tool.error_code ? ` · ${tool.error_code}` : ""}</p>
              </div>
              <small>{formatTime(tool.completed_at ?? tool.started_at)}</small>
            </div>
          )) : (
            <EmptyState compact title="没有工具调用" />
          )}
        </div>
      </div>
    </motion.div>
  );
}

export function AgentObservatory() {
  const [view, setView] = useState<ViewMode>("runs");
  const [overview, setOverview] = useState<ObservatoryOverview | null>(null);
  const [runs, setRuns] = useState<ObservatoryRunSummary[]>([]);
  const [tools, setTools] = useState<ObservatoryToolExecution[]>([]);
  const [approvals, setApprovals] = useState<ObservatoryApproval[]>([]);
  const [errors, setErrors] = useState<ObservatoryError[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [detail, setDetail] = useState<ObservatoryRunDetail | null>(null);
  const [runStatusFilter, setRunStatusFilter] = useState("");
  const [agentFilter, setAgentFilter] = useState("");
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async (signal?: AbortSignal) => {
    setRefreshing(true);
    try {
      const [overviewData, runsData, toolsData, approvalsData, errorsData] =
        await Promise.all([
          getObservatoryOverview(signal),
          listObservatoryRuns({ signal }),
          listObservatoryToolExecutions({ signal }),
          listObservatoryApprovals({ signal }),
          listObservatoryErrors({ signal }),
        ]);
      setOverview(overviewData);
      setRuns(runsData);
      setTools(toolsData);
      setApprovals(approvalsData);
      setErrors(errorsData);
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

  useEffect(() => {
    if (!selectedRunId) {
      return;
    }
    const controller = new AbortController();
    void getObservatoryRun(selectedRunId, controller.signal)
      .then(setDetail)
      .catch((detailError) => {
        if (!(detailError instanceof DOMException && detailError.name === "AbortError")) {
          setError(errorText(detailError));
        }
      });
    return () => controller.abort();
  }, [selectedRunId]);

  const filteredRuns = useMemo(
    () =>
      runs.filter(
        (run) =>
          (!runStatusFilter || run.status === runStatusFilter) &&
          (!agentFilter || run.agent_id === agentFilter),
      ),
    [runs, runStatusFilter, agentFilter],
  );

  const agentIds = useMemo(
    () => [...new Set(runs.map((run) => run.agent_id))].sort(),
    [runs],
  );

  const metricCards = [
    {
      key: "active",
      label: "ACTIVE",
      value: overview?.runs.active ?? 0,
      hint: "运行中",
      icon: CircleDot,
      tone: "active",
    },
    {
      key: "paused",
      label: "PAUSED",
      value: overview?.runs.paused ?? 0,
      hint: "等待你决定",
      icon: PauseCircle,
      tone: "paused",
    },
    {
      key: "failed",
      label: "FAILED",
      value: (overview?.runs.failed ?? 0) + (overview?.tools.failed ?? 0),
      hint: `72h 内错误 ${overview?.errors_recent ?? 0}`,
      icon: XCircle,
      tone: "failed",
    },
    {
      key: "pending",
      label: "APPROVALS",
      value: overview?.approvals.pending ?? 0,
      hint: "待决定",
      icon: ShieldCheck,
      tone: "approval",
    },
    {
      key: "completed",
      label: "COMPLETED",
      value: overview?.runs.completed ?? 0,
      hint: "任务完成",
      icon: CheckCircle2,
      tone: "completed",
    },
  ];

  return (
    <section className="observatory-shell">
      <div className="observatory-privacy-banner">
        <LockKeyhole />
        <div>
          <strong>观测 ≠ 窥探</strong>
          <p>{overview?.privacy_note ?? "观测台只展示运行状态、步骤、审批与错误代码，不展示隐藏推理和私人正文。"}</p>
        </div>
        <button aria-label="刷新观测台" disabled={refreshing} onClick={() => void refresh()} type="button">
          <RefreshCw className={refreshing ? "is-spinning" : ""} />
        </button>
      </div>

      {error && (
        <div className="observatory-notice is-error">
          <AlertTriangle />
          <span>{error}</span>
        </div>
      )}

      <div className="observatory-metrics">
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

      {overview && overview.agents.length > 0 ? (
        <div className="observatory-agent-strip">
          {overview.agents.map((agent) => (
            <div key={agent.agent_id}>
              <small>{agent.agent_id.toUpperCase()}</small>
              <strong>{agent.total}</strong>
              <span className="ok">{agent.active + agent.paused} 活跃</span>
              <span className={agent.failed ? "bad" : ""}>{agent.failed} 失败</span>
            </div>
          ))}
        </div>
      ) : null}

      <div className="observatory-tabs">
        {([
          ["runs", "Agent 运行", overview?.runs.total ?? 0],
          ["tools", "工具调用", overview?.tools.total ?? 0],
          ["approvals", "审批记录", (overview?.approvals.pending ?? 0) + (overview?.approvals.approved ?? 0)],
          ["errors", "错误", (overview?.errors_recent ?? 0)],
        ] as const).map(([key, label, count]) => (
          <button className={view === key ? "is-active" : ""} key={key} onClick={() => setView(key)} type="button">
            {label}<span>{count}</span>
          </button>
        ))}
      </div>

      {view === "runs" ? (
        <div className="observatory-runs-layout">
          <div className="observatory-list-panel">
            <div className="observatory-filter-row">
              <select
                aria-label="按 Agent 过滤"
                onChange={(event) => setAgentFilter(event.target.value)}
                value={agentFilter}
              >
                <option value="">全部 Agent</option>
                {agentIds.map((id) => <option key={id} value={id}>{id}</option>)}
              </select>
              <select
                aria-label="按状态过滤"
                onChange={(event) => setRunStatusFilter(event.target.value)}
                value={runStatusFilter}
              >
                <option value="">全部状态</option>
                {Object.entries(runStatusLabels).map(([key, label]) => (
                  <option key={key} value={key}>{label}</option>
                ))}
              </select>
              <small>{filteredRuns.length} 条记录</small>
            </div>
            <div className="observatory-run-list">
              {filteredRuns.length ? filteredRuns.map((run) => (
                <button
                  className={`observatory-run-row ${selectedRunId === run.id ? "is-selected" : ""}`}
                  key={run.id}
                  onClick={() => setSelectedRunId(run.id)}
                  type="button"
                >
                  <span className={`observatory-run-status is-${statusClass(run.status)}`}>
                    <StatusDot
                      pulse={run.status === "running"}
                      tone={runStatusTone[run.status] ?? "neutral"}
                    />
                    {runStatusLabels[run.status] ?? run.status}
                  </span>
                  <div className="observatory-run-main">
                    <strong>{run.request_type}</strong>
                    <p>
                      {run.agent_id} · {run.current_step ?? "—"}
                      {run.pending_label ? ` · ${run.pending_label}` : ""}
                    </p>
                  </div>
                  <div className="observatory-run-meta">
                    <small>{run.steps_count} 步 · {formatDuration(run.duration_ms)}</small>
                    <small>{formatTime(run.created_at)}</small>
                  </div>
                  {run.error_code ? <span className="observatory-run-error">{run.error_code}</span> : null}
                  <ChevronRight />
                </button>
              )) : (
                <EmptyState
                  description="调整过滤条件，或等 Jarvis 开始新的工作流任务。"
                  title="没有匹配的运行记录"
                />
              )}
            </div>
          </div>
          <RunDetailPanel
            detail={detail}
            onClose={() => {
              setSelectedRunId(null);
              setDetail(null);
            }}
          />
        </div>
      ) : null}

      {view === "tools" ? (
        <div className="observatory-table-panel">
          <table className="observatory-table">
            <thead>
              <tr>
                <th>工具</th>
                <th>Agent</th>
                <th>风险</th>
                <th>状态</th>
                <th>审批</th>
                <th>错误</th>
                <th>时间</th>
              </tr>
            </thead>
            <tbody>
              {tools.length ? tools.map((tool) => (
                <tr key={tool.id}>
                  <td><strong>{tool.tool_id}</strong><small>v{tool.tool_version}</small></td>
                  <td>{tool.agent_id}</td>
                  <td><span className={`observatory-risk is-${statusClass(tool.risk_level)}`}>{tool.risk_level}</span></td>
                  <td><span className={`observatory-run-status is-${statusClass(tool.status)}`}>{toolStatusLabels[tool.status] ?? tool.status}</span></td>
                  <td>{tool.approval_status ? approvalStatusLabels[tool.approval_status] ?? tool.approval_status : "—"}</td>
                  <td>{tool.error_code ? <span className="observatory-run-error">{tool.error_code}</span> : "—"}</td>
                  <td>{formatTime(tool.completed_at ?? tool.started_at)}</td>
                </tr>
              )) : (
                <tr><td className="observatory-table-empty" colSpan={7}>还没有工具调用记录</td></tr>
              )}
            </tbody>
          </table>
        </div>
      ) : null}

      {view === "approvals" ? (
        <div className="observatory-table-panel">
          <table className="observatory-table">
            <thead>
              <tr>
                <th>类型</th>
                <th>动作</th>
                <th>Agent</th>
                <th>风险</th>
                <th>状态</th>
                <th>创建</th>
                <th>决定</th>
              </tr>
            </thead>
            <tbody>
              {approvals.length ? approvals.map((approval) => (
                <tr key={approval.id}>
                  <td><span className={`observatory-source is-${approval.source}`}>{approval.source === "tool" ? "工具" : "模型"}</span></td>
                  <td><strong>{approval.title}</strong><small>{approval.reason_code}</small></td>
                  <td>{approval.agent_id}</td>
                  <td><span className={`observatory-risk is-${statusClass(approval.risk_level)}`}>{approval.risk_level}</span></td>
                  <td><span className={`observatory-run-status is-${statusClass(approval.status)}`}>{approvalStatusLabels[approval.status] ?? approval.status}</span></td>
                  <td>{formatTime(approval.created_at)}</td>
                  <td>{formatTime(approval.decided_at)}</td>
                </tr>
              )) : (
                <tr><td className="observatory-table-empty" colSpan={7}>还没有审批记录</td></tr>
              )}
            </tbody>
          </table>
        </div>
      ) : null}

      {view === "errors" ? (
        <div className="observatory-errors-panel">
          {errors.length ? errors.map((item) => (
            <div className="observatory-error-row" key={`${item.source}-${item.id}`}>
              <span className={`observatory-source is-${item.source}`}>
                {item.source === "agent_run" ? "运行" : "工具"}
              </span>
              <div>
                <strong>{item.source === "agent_run" ? item.request_type ?? item.agent_id : item.tool_id}</strong>
                <p>{item.error_code}{item.error_message ? ` · ${item.error_message}` : ""}</p>
              </div>
              <small>{item.agent_id} · {formatTime(item.occurred_at)}</small>
            </div>
          )) : (
            <EmptyState
              description="所有 Agent 运行和工具调用都保持健康。"
              title="最近 72 小时没有错误"
            />
          )}
        </div>
      ) : null}
    </section>
  );
}
