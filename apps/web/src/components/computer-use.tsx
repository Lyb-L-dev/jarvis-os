"use client";

import {
  AlertTriangle,
  ArrowRight,
  Check,
  Eye,
  FolderLock,
  LockKeyhole,
  Monitor,
  PenLine,
  Play,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Wand2,
  X,
} from "lucide-react";
import { FormEvent, useCallback, useEffect, useState } from "react";

import {
  ComputerPlanResult,
  ComputerUseStatus,
  createToolExecution,
  generateComputerPlan,
  getComputerUseStatus,
} from "@/lib/api";

const stageIcons = [
  <Eye key="1" />,
  <Wand2 key="2" />,
  <PenLine key="3" />,
  <ShieldCheck key="4" />,
];

const permanentLabels: Record<string, string> = {
  investment_trade: "投资交易",
  payment: "支付",
  delete_data: "删除数据",
  credential_operation: "凭据操作",
};

function errorText(error: unknown) {
  return error instanceof Error ? error.message : "Jarvis 暂时无法读取受控操作状态";
}

export function ComputerUse() {
  const [status, setStatus] = useState<ComputerUseStatus | null>(null);
  const [instruction, setInstruction] = useState("");
  const [plan, setPlan] = useState<ComputerPlanResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [runningStep, setRunningStep] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async (signal?: AbortSignal) => {
    try {
      const data = await getComputerUseStatus(signal);
      setStatus(data);
      setError(null);
    } catch (loadError) {
      if (!(loadError instanceof DOMException && loadError.name === "AbortError")) {
        setError(errorText(loadError));
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

  async function handlePlan(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const result = await generateComputerPlan(instruction);
      setPlan(result);
      setMessage(result.note);
    } catch (planError) {
      setError(errorText(planError));
    } finally {
      setBusy(false);
    }
  }

  async function runStep(step: ComputerPlanResult["steps"][number]) {
    if (step.requires_approval || step.blocked_by_stage) {
      setMessage("该步骤需要审批或提升阶段，请前往审批中心处理。");
      return;
    }
    setRunningStep(step.tool_id);
    setError(null);
    setMessage(null);
    try {
      const parameters =
        step.tool_id === "computer.file.read"
          ? { relative_path: step.target }
          : { include_windows: true };
      const execution = await createToolExecution({
        agent_id: "jarvis_core",
        idempotency_key: crypto.randomUUID(),
        parameters,
        tool_id: step.tool_id,
      });
      setMessage(
        execution.status === "succeeded"
          ? `只读执行完成：${step.tool_id}（${execution.output_summary?.chars ?? ""} 字符）。`
          : `已创建执行记录，状态：${execution.status}。`,
      );
    } catch (runError) {
      setError(errorText(runError));
    } finally {
      setRunningStep(null);
    }
  }

  return (
    <section className="computer-shell">
      <div className="computer-banner">
        <ShieldCheck />
        <div>
          <strong>受控电脑操作按风险逐级开放，永远不自动执行交易、支付、凭据和不可恢复删除。</strong>
          <p>当前阶段 {status?.stage ?? "—"}：只读工具可用；修改类动作必须先预览、再批准、再单独执行。</p>
        </div>
        <button aria-label="刷新受控操作状态" disabled={busy} onClick={() => void refresh()} type="button">
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

      <div className="computer-grid">
        <div className="computer-stage-panel">
          <div className="personality-panel-heading">
            <div><small>RISK LADDER</small><h2>风险逐级开放</h2></div>
            <ArrowRight />
          </div>
          <div className="computer-stage-list">
            {status?.ladder.map((item, index) => (
              <div className={`computer-stage-row ${item.enabled ? "is-enabled" : ""} ${item.stage === status.stage ? "is-current" : ""}`} key={item.stage}>
                <span className="computer-stage-icon">{stageIcons[index]}</span>
                <div className="computer-stage-main">
                  <div className="computer-stage-head">
                    <strong>阶段 {item.stage} · {item.label}</strong>
                    <em className={item.enabled ? "ok" : ""}>
                      {item.stage === status.stage ? "当前" : item.enabled ? "已开放" : "未开放"}
                    </em>
                  </div>
                  <p>{item.allowed.join(" · ")}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="computer-boundary-panel">
          <div className="personality-panel-heading">
            <div><small>PERMANENT BLOCKS</small><h2>永不自动执行</h2></div>
            <LockKeyhole />
          </div>
          <div className="computer-permanent-list">
            {status?.permanent_blocks.map((block) => (
              <div className="computer-permanent-row" key={block}>
                <LockKeyhole />
                <strong>{permanentLabels[block] ?? block}</strong>
                <span>没有 Agent 执行入口</span>
              </div>
            ))}
          </div>
          <div className="computer-sandbox">
            <FolderLock />
            <div>
              <small>TOOL SANDBOX</small>
              <strong>{status?.sandbox_root ?? "—"}</strong>
              <p>所有文件读写只允许发生在这个目录内。</p>
            </div>
          </div>
        </div>
      </div>

      <div className="computer-plan-panel">
        <div className="personality-panel-heading">
          <div><small>OPERATION PLAN</small><h2>生成操作计划</h2></div>
          <Wand2 />
        </div>
        <form className="computer-plan-form" onSubmit={(event) => void handlePlan(event)}>
          <textarea
            onChange={(event) => setInstruction(event.target.value)}
            placeholder="例如：查看当前屏幕窗口；或：读取 notes.md 的内容；或：把内容写入 notes.md"
            rows={3}
            value={instruction}
          />
          <button disabled={busy || !instruction.trim()} type="submit">
            <Sparkles />生成计划
          </button>
        </form>

        {plan ? (
          <div className="computer-steps">
            {plan.steps.map((step) => (
              <div className="computer-step" key={`${step.tool_id}-${step.target}`}>
                <span className={`observatory-risk is-${step.risk_level.toLowerCase()}`}>{step.risk_level}</span>
                <div className="computer-step-main">
                  <div className="computer-step-head">
                    <strong>{step.tool_id}</strong>
                    <span>{step.requires_approval ? "需要审批" : step.blocked_by_stage ? "阶段未开放" : "只读自动执行"}</span>
                  </div>
                  <p>{step.preview_hint}</p>
                  <small>目标：{step.target}</small>
                </div>
                <button
                  disabled={busy || runningStep !== null}
                  onClick={() => void runStep(step)}
                  type="button"
                >
                  {step.requires_approval || step.blocked_by_stage ? <ShieldCheck /> : <Play />}
                  {runningStep === step.tool_id ? "执行中…" : step.requires_approval ? "去审批" : step.blocked_by_stage ? "已阻断" : "执行"}
                </button>
              </div>
            ))}
          </div>
        ) : (
          <div className="observatory-empty compact">
            <Monitor />
            <span>输入一句指令，Jarvis 会给出结构化的只读/预览步骤。</span>
          </div>
        )}
      </div>
    </section>
  );
}
