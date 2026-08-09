"use client";

import {
  AlertTriangle,
  CalendarDays,
  Check,
  ChevronRight,
  CircleDot,
  FilePenLine,
  Fingerprint,
  History,
  LockKeyhole,
  Mail,
  Network,
  Play,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  X,
} from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import {
  ApprovalCenterItem,
  ApprovalCenterResponse,
  createToolExecution,
  decideDraftReview,
  decideToolApproval,
  executeApprovedTool,
  getApprovalCenter,
  getN8nProviderStatus,
  listToolCatalog,
  N8nProviderStatus,
  ToolCatalogItem,
  updateToolProposal,
} from "@/lib/api";

type ViewMode = "pending" | "approved" | "history";

const statusLabel: Record<string, string> = {
  approved: "已批准 · 待执行",
  consumed: "已完成",
  expired: "已过期",
  pending: "等待你的决定",
  rejected: "已拒绝",
};

const actionLabels: Record<string, string> = {
  credential_operation: "凭据操作",
  delete_data: "删除数据",
  investment_trade: "投资交易",
  payment: "支付",
};

function approvalKindLabel(item: ApprovalCenterItem) {
  if (item.source === "tool") return item.tool_id ?? "工具操作";
  if (item.source === "model") return `${item.provider ?? "模型"} 单次授权`;
  return item.preview.draft_kind === "orchestration_plan"
    ? "编排计划审阅"
    : "成长任务草稿审阅";
}

function approvalKindHeading(item: ApprovalCenterItem) {
  if (item.source === "tool") return "TOOL APPROVAL";
  if (item.source === "model") return "MODEL CONSENT";
  return "DRAFT REVIEW";
}

function approvalReason(item: ApprovalCenterItem) {
  if (item.source === "tool") {
    return "这是可能改变本地或外部状态的 R2 操作，批准后仍需单独执行。";
  }
  if (item.source === "model") {
    return "这是付费或云端模型的单次授权，不会扩展到其他运行或数据类别。";
  }
  return "这是 R1 产品草稿审阅，只决定计划或草稿是否继续，不授予模型权限，也不会执行外部操作。";
}

function approvalStatusLabel(item: ApprovalCenterItem) {
  if (item.source === "draft" && item.status === "approved") return "已通过审阅";
  return statusLabel[item.status] ?? item.status;
}

function draftDecisionSuccess(
  item: ApprovalCenterItem,
  decision: "approve" | "reject",
) {
  if (decision === "reject") return "草稿已拒绝，编排不会继续。";
  if (item.preview.draft_kind === "orchestration_plan") {
    return "编排计划已通过并启动；它只会生成待审阅的成长任务草稿。";
  }
  return "成长任务草稿已通过审阅；这不会创建正式任务或执行外部操作。";
}

function formatTime(value?: string | null) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("zh-CN", {
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    month: "2-digit",
  }).format(new Date(value));
}

function compactHash(value?: unknown) {
  if (typeof value !== "string" || value.length < 12) return String(value ?? "—");
  return `${value.slice(0, 8)}…${value.slice(-6)}`;
}

function errorText(error: unknown) {
  return error instanceof Error ? error.message : "Jarvis 暂时无法完成这个操作";
}

export function ApprovalCenter() {
  const reducedMotion = useReducedMotion();
  const [data, setData] = useState<ApprovalCenterResponse | null>(null);
  const [catalog, setCatalog] = useState<ToolCatalogItem[]>([]);
  const [provider, setProvider] = useState<N8nProviderStatus | null>(null);
  const [automationResult, setAutomationResult] = useState<Record<string, unknown> | null>(null);
  const [view, setView] = useState<ViewMode>("pending");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [path, setPath] = useState("drafts/jarvis-note.md");
  const [content, setContent] = useState("# Jarvis 草稿\n\n这是一个等待确认的本地文件预览。");
  const [overwrite, setOverwrite] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async (signal?: AbortSignal) => {
    try {
      const [center, tools, n8n] = await Promise.all([
        getApprovalCenter(signal),
        listToolCatalog(signal),
        getN8nProviderStatus(signal),
      ]);
      setData(center);
      setCatalog(tools);
      setProvider(n8n);
      setError(null);
    } catch (refreshError) {
      if (!(refreshError instanceof DOMException && refreshError.name === "AbortError")) {
        setError(errorText(refreshError));
      }
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => void refresh(controller.signal), 0);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [refresh]);

  const visibleItems = useMemo(() => {
    const items = data?.items ?? [];
    if (view === "pending") return items.filter((item) => item.status === "pending");
    if (view === "approved") return items.filter((item) => item.status === "approved");
    return items.filter((item) => !["pending", "approved"].includes(item.status));
  }, [data, view]);

  const selected =
    visibleItems.find((item) => item.id === selectedId) ??
    visibleItems[0] ??
    null;
  const liveTools = catalog.filter((item) => item.available);
  const reservedTools = catalog.filter((item) => !item.available);

  async function withAction(key: string, action: () => Promise<unknown>, success: string) {
    setBusy(key);
    setError(null);
    setMessage(null);
    try {
      await action();
      setMessage(success);
      await refresh();
    } catch (actionError) {
      setError(errorText(actionError));
    } finally {
      setBusy(null);
    }
  }

  async function submitPreview(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await withAction(
      "create",
      () =>
        createToolExecution({
          agent_id: "local_document",
          idempotency_key: crypto.randomUUID(),
          parameters: { content, overwrite, relative_path: path },
          tool_id: "workspace.file.write",
        }),
      "预览已生成。文件尚未写入，等待你的明确批准。",
    );
    setView("pending");
  }

  async function editSelected() {
    if (!selected || selected.source !== "tool") return;
    await withAction(
      `edit-${selected.id}`,
      () =>
        updateToolProposal(selected.id, {
          content,
          overwrite,
          relative_path: path,
        }),
      "预览已更新，旧批准范围已失效。",
    );
  }

  async function decide(item: ApprovalCenterItem, decision: "approve" | "reject") {
    await withAction(
      `${decision}-${item.id}`,
      () => item.source === "draft"
        ? decideDraftReview(item, decision)
        : decideToolApproval(item.id, decision),
      item.source === "draft"
        ? draftDecisionSuccess(item, decision)
        : decision === "approve"
          ? "已批准，但尚未执行。请再检查一次后点击执行。"
          : "已拒绝，Jarvis 不会执行这个动作。",
    );
    setView(decision === "approve" ? "approved" : "history");
  }

  async function execute(item: ApprovalCenterItem) {
    if (!item.execution_id) return;
    await withAction(
      `execute-${item.id}`,
      () => executeApprovedTool(item.execution_id as string),
      "已执行并保存审计证明；相同请求重放不会再次写入。",
    );
    setView("history");
  }

  async function runAutomationTest(kind: "calendar" | "email") {
    const now = new Date();
    const endsAt = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000);
    const toolId = kind === "calendar" ? "calendar.events.read" : "email.draft.prepare";
    setBusy(`automation-${kind}`);
    setError(null);
    setMessage(null);
    setAutomationResult(null);
    try {
      const execution = await createToolExecution({
        agent_id: "jarvis_core",
        idempotency_key: crypto.randomUUID(),
        parameters: kind === "calendar"
          ? {
              account_alias: "jarvis_sandbox",
              ends_at: endsAt.toISOString(),
              max_results: 10,
              starts_at: now.toISOString(),
            }
          : {
              account_alias: "jarvis_sandbox",
              body: "This message remains inside Jarvis and has not been sent.",
              subject: "Jarvis Sprint 30 safety check",
              to: "test-account@jarvis.local",
            },
        tool_id: toolId,
      });
      setAutomationResult(execution.output_summary ?? {});
      setMessage(kind === "calendar"
        ? "只读日历测试完成，没有修改任何外部数据。"
        : "本地邮件草稿已生成，没有发送邮件。"
      );
      await refresh();
    } catch (actionError) {
      setError(errorText(actionError));
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="approval-shell">
      <div className="approval-metrics">
        <article>
          <span className="approval-metric-icon pending"><CircleDot /></span>
          <div><small>WAITING</small><strong>{data?.pending_count ?? 0}</strong><p>等待确认</p></div>
        </article>
        <article>
          <span className="approval-metric-icon approved"><ShieldCheck /></span>
          <div><small>APPROVED</small><strong>{data?.approved_count ?? 0}</strong><p>已批准或通过</p></div>
        </article>
        <article>
          <span className="approval-metric-icon history"><History /></span>
          <div><small>AUDIT TRAIL</small><strong>{data?.history_count ?? 0}</strong><p>全部审批记录</p></div>
        </article>
        <article className="approval-policy-card">
          <span className="approval-metric-icon blocked"><LockKeyhole /></span>
          <div><small>R3 BOUNDARY</small><strong>{data?.permanent_blocks.length ?? 4}</strong><p>永不自动执行</p></div>
        </article>
      </div>

      {(message || error) && (
        <motion.div
          animate={{ opacity: 1, y: 0 }}
          className={`approval-notice ${error ? "is-error" : "is-success"}`}
          initial={reducedMotion ? false : { opacity: 0, y: -8 }}
        >
          {error ? <AlertTriangle /> : <Check />}
          <span>{error ?? message}</span>
          <button onClick={() => { setError(null); setMessage(null); }} type="button"><X /></button>
        </motion.div>
      )}

      <div className="approval-grid">
        <div className="approval-queue-panel">
          <div className="approval-panel-heading">
            <div><small>DECISION QUEUE</small><h2>需要你决定</h2></div>
            <button aria-label="刷新审批中心" disabled={busy !== null} onClick={() => void refresh()} type="button">
              <RefreshCw className={busy ? "is-spinning" : ""} />
            </button>
          </div>
          <div className="approval-tabs">
            {([
              ["pending", "待确认", data?.pending_count ?? 0],
              ["approved", "已批准/通过", data?.approved_count ?? 0],
              ["history", "历史", Math.max(0, (data?.history_count ?? 0) - (data?.pending_count ?? 0) - (data?.approved_count ?? 0))],
            ] as const).map(([key, label, count]) => (
              <button className={view === key ? "is-active" : ""} key={key} onClick={() => setView(key)} type="button">
                {label}<span>{count}</span>
              </button>
            ))}
          </div>
          <div className="approval-queue">
            {visibleItems.length ? visibleItems.map((item) => (
              <button className={`approval-queue-item ${selected?.id === item.id ? "is-selected" : ""}`} key={item.id} onClick={() => setSelectedId(item.id)} type="button">
                <span className={`approval-risk risk-${item.risk_level.toLowerCase()}`}>{item.risk_level}</span>
                <div>
                  <strong>{item.title}</strong>
                  <small>{approvalKindLabel(item)}</small>
                  <p>{approvalStatusLabel(item)} · {formatTime(item.created_at)}</p>
                </div>
                <ChevronRight />
              </button>
            )) : (
              <div className="approval-empty">
                <ShieldCheck />
                <strong>{view === "pending" ? "当前没有待确认动作" : "这个区域暂时是空的"}</strong>
                <p>Jarvis 只会在需要你做决定时打扰你。</p>
              </div>
            )}
          </div>
        </div>

        <div className="approval-inspector">
          {selected ? (
            <motion.div animate={{ opacity: 1 }} initial={reducedMotion ? false : { opacity: 0 }} key={selected.id}>
              <div className="approval-inspector-head">
                <div><span className={`approval-risk risk-${selected.risk_level.toLowerCase()}`}>{selected.risk_level}</span><small>{approvalKindHeading(selected)}</small></div>
                <span className={`approval-status status-${selected.status}`}>{approvalStatusLabel(selected)}</span>
              </div>
              <h2>{selected.title}</h2>
              <p className="approval-reason">{approvalReason(selected)}</p>

              <div className="approval-preview-card">
                <div className="approval-preview-title"><FilePenLine /><span>{selected.source === "draft" ? "审阅内容" : "执行前预览"}</span><small>{selected.source === "draft" ? "DECISION PREVIEW" : "PREVIEW · NOT EXECUTED"}</small></div>
                {selected.source === "tool" ? (
                  <>
                    <div className="approval-preview-meta">
                      <span><small>动作</small>{String(selected.preview.operation ?? selected.tool_id)}</span>
                      <span><small>目标</small>{String(selected.preview.sandbox_relative_path ?? "受控空间")}</span>
                      <span><small>大小</small>{String(selected.preview.size_bytes ?? "—")} bytes</span>
                    </div>
                    <pre>{String(selected.preview.content_preview ?? JSON.stringify(selected.preview, null, 2))}</pre>
                    <div className="approval-fingerprint"><Fingerprint /><span>内容指纹</span><code>{compactHash(selected.preview.after_sha256)}</code></div>
                  </>
                ) : (
                  <pre>{JSON.stringify(selected.preview, null, 2)}</pre>
                )}
              </div>

              {selected.status === "pending" && selected.source === "tool" && (
                <div className="approval-decision-row">
                  <button className="approval-button reject" disabled={busy !== null} onClick={() => void decide(selected, "reject")} type="button"><X />拒绝</button>
                  <button className="approval-button edit" disabled={busy !== null} onClick={() => void editSelected()} type="button"><FilePenLine />用下方内容更新预览</button>
                  <button className="approval-button approve" disabled={busy !== null} onClick={() => void decide(selected, "approve")} type="button"><Check />批准范围</button>
                </div>
              )}
              {selected.status === "pending" && selected.source === "draft" && (
                <div className="approval-decision-row">
                  <button className="approval-button reject" disabled={busy !== null} onClick={() => void decide(selected, "reject")} type="button"><X />拒绝草稿</button>
                  <button className="approval-button approve" disabled={busy !== null} onClick={() => void decide(selected, "approve")} type="button"><Check />通过审阅</button>
                </div>
              )}
              {selected.status === "approved" && selected.source === "draft" && selected.preview.draft_kind === "orchestration_plan" && (
                <div className="approval-decision-row">
                  <button className="approval-button approve" disabled={busy !== null} onClick={() => void decide(selected, "approve")} type="button"><Play />启动或重试编排</button>
                </div>
              )}
              {selected.status === "approved" && selected.source === "tool" && (
                <div className="approval-execute-zone">
                  <AlertTriangle />
                  <div><strong>批准不等于执行</strong><p>点击执行后才会产生这一次副作用；批准仅能使用一次。</p></div>
                  <button disabled={busy !== null} onClick={() => void execute(selected)} type="button"><Play />执行已批准动作</button>
                </div>
              )}
              <div className="approval-audit-strip">
                <span><small>REQUESTED BY</small>{selected.agent_id}</span>
                <span><small>POLICY</small>{selected.reason_code}</span>
                <span><small>EXPIRES</small>{formatTime(selected.expires_at)}</span>
              </div>
            </motion.div>
          ) : (
            <div className="approval-empty inspector-empty"><Sparkles /><strong>安全边界正在运行</strong><p>选择一条记录，可以检查预览、风险和授权范围。</p></div>
          )}
        </div>
      </div>

      <div className="approval-lower-grid">
        <form className="approval-simulator" onSubmit={(event) => void submitPreview(event)}>
          <div className="approval-panel-heading">
            <div><small>SAFE TOOL LAB</small><h2>创建本地文件预览</h2></div>
            <span className="approval-risk risk-r2">R2</span>
          </div>
          <p>这里只生成预览，不写文件。批准后仍需在“待执行”中再确认一次。</p>
          <label>受控目录内的相对路径<input onChange={(event) => setPath(event.target.value)} required value={path} /></label>
          <label>文件内容<textarea onChange={(event) => setContent(event.target.value)} required rows={6} value={content} /></label>
          <label className="approval-check"><input checked={overwrite} onChange={(event) => setOverwrite(event.target.checked)} type="checkbox" /><span>目标存在时允许覆盖（仍需重新预览与批准）</span></label>
          <button className="approval-create-button" disabled={!data?.tool_gateway_enabled || busy !== null} type="submit"><Sparkles />只生成预览</button>
        </form>

        <div className="approval-boundary-panel">
          <div className="approval-panel-heading"><div><small>POLICY MATRIX</small><h2>不可越过的边界</h2></div><LockKeyhole /></div>
          <div className="approval-risk-scale">
            <div><span className="risk-r0">R0</span><strong>读取</strong><p>可自动执行，保留审计。</p></div>
            <div><span className="risk-r1">R1</span><strong>内部草稿</strong><p>可自动生成，不对外发送。</p></div>
            <div><span className="risk-r2">R2</span><strong>有副作用</strong><p>预览、批准、执行三步分离。</p></div>
            <div><span className="risk-r3">R3</span><strong>永久禁用</strong><p>没有 Agent 执行入口。</p></div>
          </div>
          <div className="approval-permanent-blocks">
            {(data?.permanent_blocks ?? ["investment_trade", "payment", "delete_data", "credential_operation"]).map((item) => (
              <span key={item}><LockKeyhole />{actionLabels[item] ?? item}</span>
            ))}
          </div>
          <div className="approval-tool-summary">
            <div><small>AVAILABLE NOW</small><strong>{liveTools.length}</strong><p>{liveTools.map((item) => item.display_name).join(" · ") || "正在读取"}</p></div>
            <div><small>RESERVED · DISCONNECTED</small><strong>{reservedTools.length}</strong><p>日历、邮件与外部账号尚未接入</p></div>
          </div>
        </div>
      </div>

      <section className="automation-provider-panel">
        <div className="automation-provider-heading">
          <div className="automation-provider-mark"><Network /></div>
          <div>
            <small>AUTOMATION PROVIDER · N8N</small>
            <h2>隔离自动化通道</h2>
            <p>只开放本机签名入口。当前没有真实外部账号，也不允许外部写入。</p>
          </div>
          <span className={`automation-provider-state is-${provider?.status ?? "offline"}`}>
            <i />{provider?.status === "ready" ? "运行正常" : provider?.status === "disabled" ? "未启用" : "已离线"}
          </span>
        </div>

        <div className="automation-provider-grid">
          <div className="automation-provider-facts">
            <span><small>NETWORK</small><strong>{provider?.isolated ? "独立网络" : "待核验"}</strong></span>
            <span><small>INGRESS</small><strong>{provider?.signed_webhooks ? "HMAC 签名" : "未就绪"}</strong></span>
            <span><small>REDIS</small><strong>{provider?.redis_used ? "已使用" : "未使用"}</strong></span>
            <span><small>EDITOR</small><strong>{provider?.editor_exposed ? "已暴露" : "未暴露"}</strong></span>
            <span><small>REAL ACCOUNTS</small><strong>{provider?.real_accounts_connected ? "已连接" : "未连接"}</strong></span>
            <span><small>EXTERNAL WRITE</small><strong>{provider?.external_writes_enabled ? "已开放" : "已关闭"}</strong></span>
          </div>

          <div className="automation-safe-tools">
            <button disabled={provider?.status !== "ready" || busy !== null} onClick={() => void runAutomationTest("calendar")} type="button">
              <CalendarDays /><span><small>R0 · READ ONLY</small><strong>读取沙盒日历</strong><em>不创建、不修改事件</em></span>
            </button>
            <button disabled={provider?.status !== "ready" || busy !== null} onClick={() => void runAutomationTest("email")} type="button">
              <Mail /><span><small>R1 · LOCAL DRAFT</small><strong>生成本地邮件草稿</strong><em>不会发送邮件</em></span>
            </button>
          </div>
        </div>

        <div className="automation-provider-result">
          <div>
            <small>ACTIVE WORKFLOWS</small>
            <p>{provider?.workflows.join(" · ") || provider?.detail || "等待 Provider 状态"}</p>
          </div>
          {automationResult && <pre>{JSON.stringify(automationResult, null, 2)}</pre>}
        </div>
      </section>
    </section>
  );
}
