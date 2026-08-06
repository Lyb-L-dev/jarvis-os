"use client";

import {
  cancelGrowthWorkflow,
  listGrowthWorkflows,
  resumeGrowthWorkflow,
  startGrowthWorkflow,
  supplementGrowthWorkflow,
  updateGrowthWorkflowDraft,
  type GrowthModelPreference,
  type GrowthPlanDraft,
  type GrowthWorkflowRun,
} from "@/lib/api";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useMemo, useState } from "react";

type Props = {
  onApplied?: () => void | Promise<void>;
};

const activeStatuses = new Set([
  "created",
  "running",
  "waiting_for_input",
  "waiting_for_model_approval",
  "waiting_for_draft_review",
]);

const providerNames: Record<string, string> = {
  deepseek: "DeepSeek",
  mimo: "MiMo",
  ollama: "本地 Qwen",
};

const dataCategoryNames: Record<string, string> = {
  planning_request: "本次填写的目标、约束与时间",
  user_profile: "成长档案中的职业方向、技能和薄弱项",
  active_goals: "当前活跃目标的标题",
};

function statusText(status: GrowthWorkflowRun["status"]) {
  return {
    created: "正在创建",
    running: "正在规划",
    waiting_for_input: "等待补充信息",
    waiting_for_model_approval: "等待模型授权",
    waiting_for_draft_review: "等待审核草稿",
    completed: "已生成正式计划",
    rejected: "草稿已放弃",
    cancelled: "规划已取消",
    failed: "规划中断",
  }[status];
}

function providerName(provider?: string | null) {
  if (!provider) return "尚未选择";
  return providerNames[provider] ?? provider;
}

export function GrowthWorkflowPlanner({ onApplied }: Props) {
  const [run, setRun] = useState<GrowthWorkflowRun | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [objective, setObjective] = useState("");
  const [constraints, setConstraints] = useState("");
  const [targetDate, setTargetDate] = useState("");
  const [weeklyHours, setWeeklyHours] = useState("");
  const [modelPreference, setModelPreference] =
    useState<GrowthModelPreference>("auto");
  const [cloudAllowed, setCloudAllowed] = useState(true);
  const [draft, setDraft] = useState<GrowthPlanDraft | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    void listGrowthWorkflows(controller.signal)
      .then((runs) => {
        const current = runs.find((item) => activeStatuses.has(item.status));
        const latest = current ?? runs[0] ?? null;
        setRun(latest);
        setDraft(latest?.draft ? structuredClone(latest.draft) : null);
        setShowCreate(runs.length === 0);
      })
      .catch((loadError) => {
        if (loadError instanceof DOMException && loadError.name === "AbortError") {
          return;
        }
        setError(
          loadError instanceof Error
            ? loadError.message
            : "成长规划工作流暂时无法读取。",
        );
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, []);

  const planningStep = useMemo(() => {
    if (!run) return 0;
    if (run.status === "waiting_for_input") return 1;
    if (run.status === "waiting_for_model_approval") return 2;
    if (run.status === "waiting_for_draft_review") return 3;
    if (run.status === "completed") return 4;
    return 0;
  }, [run]);

  async function perform(
    key: string,
    action: () => Promise<GrowthWorkflowRun>,
    success?: string,
  ) {
    setBusy(key);
    setError(null);
    setNotice(null);
    try {
      const next = await action();
      setRun(next);
      setDraft(next.draft ? structuredClone(next.draft) : null);
      setShowCreate(false);
      if (success) setNotice(success);
      if (next.status === "completed") await onApplied?.();
    } catch (actionError) {
      setError(
        actionError instanceof Error ? actionError.message : "规划操作未完成。",
      );
    } finally {
      setBusy(null);
    }
  }

  function startPlanning() {
    const hours = weeklyHours ? Number(weeklyHours) : undefined;
    if (!objective.trim()) return;
    if (hours !== undefined && (!Number.isInteger(hours) || hours < 1 || hours > 80)) {
      setError("每周时间需要是 1～80 小时的整数，也可以先留空。 ");
      return;
    }
    void perform(
      "start",
      () =>
        startGrowthWorkflow({
          objective: objective.trim(),
          constraints: constraints.trim() || undefined,
          target_date: targetDate || undefined,
          weekly_hours: hours,
          model_preference: modelPreference,
          cloud_allowed: cloudAllowed,
        }),
      "规划上下文已建立。",
    );
  }

  function supplementPlanning() {
    if (!run) return;
    const hours = Number(weeklyHours);
    if (!Number.isInteger(hours) || hours < 1 || hours > 80) {
      setError("请填写每周 1～80 小时的可投入时间。 ");
      return;
    }
    void perform(
      "supplement",
      () =>
        supplementGrowthWorkflow(run.id, {
          weekly_hours: hours,
          constraints: constraints.trim() || run.request.constraints || undefined,
          target_date: targetDate || run.request.target_date || undefined,
        }),
      "补充信息已保存，工作流已继续。",
    );
  }

  function updateMilestone(
    index: number,
    field: "title" | "description",
    value: string,
  ) {
    if (!draft) return;
    setDraft({
      ...draft,
      milestones: draft.milestones.map((item, itemIndex) =>
        itemIndex === index ? { ...item, [field]: value } : item,
      ),
    });
  }

  function updateTask(
    index: number,
    field: "title" | "description" | "milestone_index" | "priority" | "estimated_minutes",
    value: string | number,
  ) {
    if (!draft) return;
    setDraft({
      ...draft,
      tasks: draft.tasks.map((item, itemIndex) =>
        itemIndex === index ? { ...item, [field]: value } : item,
      ),
    });
  }

  async function saveDraft() {
    if (!run || !draft) return null;
    const next = await updateGrowthWorkflowDraft(run.id, {
      title: draft.title,
      summary: draft.summary,
      milestones: draft.milestones,
      tasks: draft.tasks,
    });
    setRun(next);
    setDraft(next.draft ? structuredClone(next.draft) : null);
    return next;
  }

  async function approveDraft() {
    if (!run || !draft) return;
    const confirmed = window.confirm(
      "确认后，Jarvis 会把这份草稿创建为正式目标、里程碑和待办任务。是否继续？",
    );
    if (!confirmed) return;
    setBusy("approve-draft");
    setError(null);
    setNotice(null);
    try {
      const saved = await saveDraft();
      if (!saved) return;
      const next = await resumeGrowthWorkflow(saved.id, "approve_draft");
      setRun(next);
      setDraft(next.draft ? structuredClone(next.draft) : null);
      setNotice("正式成长计划已创建，目标与任务列表已同步。 ");
      await onApplied?.();
    } catch (actionError) {
      setError(
        actionError instanceof Error ? actionError.message : "正式计划未创建。",
      );
    } finally {
      setBusy(null);
    }
  }

  const dataCategories = Array.isArray(run?.pending_payload?.data_categories)
    ? (run.pending_payload.data_categories as string[])
    : [];

  return (
    <motion.section
      animate={{ opacity: 1, y: 0 }}
      className="panel growth-workflow"
      initial={{ opacity: 0, y: 8 }}
      transition={{ duration: 0.28 }}
    >
      <div className="growth-workflow-head">
        <div>
          <div className="eyebrow">LANGGRAPH · CHECKPOINTED</div>
          <h2>AI 成长规划器</h2>
          <p>规划可暂停、补充和恢复；模型只生成草稿，正式任务由你确认。</p>
        </div>
        {run ? (
          <div className={`growth-workflow-state workflow-${run.status}`}>
            <i />
            {statusText(run.status)}
          </div>
        ) : null}
      </div>

      {run ? (
        <div className="growth-workflow-steps" aria-label="成长规划进度">
          {["理解目标", "补全条件", "模型决策", "审核草稿", "正式计划"].map(
            (label, index) => (
              <div
                className={index <= planningStep ? "step-active" : ""}
                key={label}
              >
                <span>{String(index + 1).padStart(2, "0")}</span>
                <small>{label}</small>
              </div>
            ),
          )}
        </div>
      ) : null}

      {error ? <div className="growth-feedback growth-error">{error}</div> : null}
      {notice ? <div className="growth-feedback">{notice}</div> : null}
      {loading ? <div className="growth-workflow-loading">Jarvis 正在恢复规划进度…</div> : null}

      <AnimatePresence mode="wait">
        {!loading && (showCreate || !run) ? (
          <motion.div
            animate={{ opacity: 1 }}
            className="growth-workflow-create"
            exit={{ opacity: 0 }}
            initial={{ opacity: 0 }}
            key="create"
          >
            <label className="workflow-objective">
              你想实现什么目标？
              <textarea
                maxLength={4000}
                onChange={(event) => setObjective(event.target.value)}
                placeholder="例如：6 个月内具备 AI 应用工程师的项目能力"
                value={objective}
              />
            </label>
            <label>
              每周可投入时间
              <input
                max={80}
                min={1}
                onChange={(event) => setWeeklyHours(event.target.value)}
                placeholder="可以先留空"
                type="number"
                value={weeklyHours}
              />
            </label>
            <label>
              目标日期（可选）
              <input
                onChange={(event) => setTargetDate(event.target.value)}
                type="date"
                value={targetDate}
              />
            </label>
            <label className="workflow-constraints">
              现实约束（可选）
              <textarea
                maxLength={8000}
                onChange={(event) => setConstraints(event.target.value)}
                placeholder="例如：工作日只能晚上学习，希望以项目实践为主"
                value={constraints}
              />
            </label>
            <div className="workflow-model-choice">
              <strong>规划模型</strong>
              <div>
                {(
                  [
                    ["auto", "Jarvis 决策", "复杂规划优先建议 DeepSeek，但调用前仍需你确认"],
                    ["deep", "DeepSeek", "多步骤权衡更强，会消耗付费余额并再次请求授权"],
                    ["mimo", "MiMo", "使用你的 Token Plan，适合常规成长规划"],
                    ["local", "本地 Qwen", "资料不离开电脑，速度和规划质量可能较低"],
                  ] as Array<[GrowthModelPreference, string, string]>
                ).map(([value, title, detail]) => (
                  <button
                    className={modelPreference === value ? "model-active" : ""}
                    key={value}
                    onClick={() => setModelPreference(value)}
                    type="button"
                  >
                    <span>{title}</span>
                    <small>{detail}</small>
                  </button>
                ))}
              </div>
            </div>
            <label className="workflow-cloud-check">
              <input
                checked={cloudAllowed}
                onChange={(event) => setCloudAllowed(event.target.checked)}
                type="checkbox"
              />
              允许将本次规划资料发送给所选云模型
            </label>
            <button
              className="primary-button workflow-start"
              disabled={!objective.trim() || busy === "start"}
              onClick={startPlanning}
              type="button"
            >
              {busy === "start" ? "正在建立规划…" : "开始规划"}
            </button>
          </motion.div>
        ) : null}

        {!loading && run?.status === "waiting_for_input" ? (
          <motion.div
            animate={{ opacity: 1, y: 0 }}
            className="growth-workflow-decision"
            initial={{ opacity: 0, y: 6 }}
            key="input"
          >
            <span className="workflow-decision-code">INPUT REQUIRED</span>
            <h3>还需要一个现实条件</h3>
            <p>Jarvis 需要知道你每周实际能投入多少时间，才能控制任务密度。</p>
            <div className="workflow-supplement-row">
              <label>
                每周可投入小时
                <input
                  max={80}
                  min={1}
                  onChange={(event) => setWeeklyHours(event.target.value)}
                  type="number"
                  value={weeklyHours}
                />
              </label>
              <button
                className="primary-button"
                disabled={busy === "supplement" || !weeklyHours}
                onClick={supplementPlanning}
                type="button"
              >
                补充并继续
              </button>
            </div>
          </motion.div>
        ) : null}

        {!loading && run?.status === "waiting_for_model_approval" ? (
          <motion.div
            animate={{ opacity: 1, y: 0 }}
            className="growth-workflow-decision workflow-deepseek-gate"
            initial={{ opacity: 0, y: 6 }}
            key="approval"
          >
            <span className="workflow-decision-code">PAID MODEL GATE</span>
            <h3>是否授权 DeepSeek 完成本次成长规划？</h3>
            <p>
              DeepSeek 在多目标权衡、长期路线和任务依赖分析上更适合 Growth Agent。
              它只负责生成计划草稿，不会直接创建任务；这次调用会消耗你的 DeepSeek 余额。
            </p>
            <div className="workflow-disclosure">
              <div>
                <strong>将执行</strong>
                <span>生成路线 → 校验时间与里程碑 → 返回可编辑草稿</span>
              </div>
              <div>
                <strong>将发送</strong>
                <span>
                  {dataCategories.map((item) => dataCategoryNames[item] ?? item).join("；")}
                </span>
              </div>
              <div>
                <strong>不会执行</strong>
                <span>不会修改文件、日历或账号，不会创建正式成长任务</span>
              </div>
            </div>
            <div className="workflow-decision-actions">
              <button
                className="primary-button"
                disabled={busy !== null}
                onClick={() =>
                  void perform(
                    "deepseek",
                    () => resumeGrowthWorkflow(run.id, "approve_deepseek"),
                    "DeepSeek 已获本次单次授权。",
                  )
                }
                type="button"
              >
                {busy === "deepseek" ? "正在生成草稿…" : "授权本次 DeepSeek"}
              </button>
              <button
                disabled={busy !== null}
                onClick={() =>
                  void perform("mimo", () => resumeGrowthWorkflow(run.id, "use_mimo"))
                }
                type="button"
              >
                改用 MiMo
              </button>
              <button
                disabled={busy !== null}
                onClick={() =>
                  void perform("local", () => resumeGrowthWorkflow(run.id, "use_local"))
                }
                type="button"
              >
                改用本地 Qwen
              </button>
            </div>
          </motion.div>
        ) : null}

        {!loading && run?.status === "waiting_for_draft_review" && draft ? (
          <motion.div
            animate={{ opacity: 1, y: 0 }}
            className="growth-draft-review"
            initial={{ opacity: 0, y: 6 }}
            key="draft"
          >
            <div className="growth-draft-intro">
              <div>
                <span className="workflow-decision-code">DRAFT · REVIEW REQUIRED</span>
                <h3>计划仍未生效</h3>
                <p>由 {providerName(run.provider_used)} 生成。你可以直接修改，确认后才创建正式记录。</p>
              </div>
              <span>{draft.tasks.length} 项任务 · {draft.milestones.length} 个阶段</span>
            </div>
            <label className="growth-draft-title">
              计划标题
              <input
                maxLength={200}
                onChange={(event) => setDraft({ ...draft, title: event.target.value })}
                value={draft.title}
              />
            </label>
            <label className="growth-draft-summary">
              计划说明
              <textarea
                maxLength={4000}
                onChange={(event) => setDraft({ ...draft, summary: event.target.value })}
                value={draft.summary}
              />
            </label>
            <div className="growth-draft-columns">
              <div className="growth-draft-milestones">
                <strong>路线阶段</strong>
                {draft.milestones.map((item, index) => (
                  <article key={item.order_index}>
                    <span>{String(index + 1).padStart(2, "0")}</span>
                    <input
                      aria-label={`第 ${index + 1} 阶段名称`}
                      maxLength={200}
                      onChange={(event) => updateMilestone(index, "title", event.target.value)}
                      value={item.title}
                    />
                    <textarea
                      aria-label={`第 ${index + 1} 阶段说明`}
                      maxLength={2000}
                      onChange={(event) =>
                        updateMilestone(index, "description", event.target.value)
                      }
                      value={item.description}
                    />
                  </article>
                ))}
              </div>
              <div className="growth-draft-tasks">
                <strong>待创建任务</strong>
                {draft.tasks.map((item, index) => (
                  <article key={`${item.milestone_index}-${index}`}>
                    <input
                      aria-label={`第 ${index + 1} 个任务名称`}
                      maxLength={240}
                      onChange={(event) => updateTask(index, "title", event.target.value)}
                      value={item.title}
                    />
                    <div>
                      <select
                        aria-label={`第 ${index + 1} 个任务所属阶段`}
                        onChange={(event) =>
                          updateTask(index, "milestone_index", Number(event.target.value))
                        }
                        value={item.milestone_index}
                      >
                        {draft.milestones.map((milestone) => (
                          <option key={milestone.order_index} value={milestone.order_index}>
                            {milestone.title}
                          </option>
                        ))}
                      </select>
                      <label>
                        P
                        <input
                          max={5}
                          min={1}
                          onChange={(event) =>
                            updateTask(index, "priority", Number(event.target.value))
                          }
                          type="number"
                          value={item.priority}
                        />
                      </label>
                      <label>
                        分钟
                        <input
                          max={1440}
                          min={5}
                          onChange={(event) =>
                            updateTask(index, "estimated_minutes", Number(event.target.value))
                          }
                          type="number"
                          value={item.estimated_minutes}
                        />
                      </label>
                    </div>
                  </article>
                ))}
              </div>
            </div>
            <div className="growth-draft-actions">
              <button
                disabled={busy !== null}
                onClick={() =>
                  void perform(
                    "reject-draft",
                    () => resumeGrowthWorkflow(run.id, "reject_draft"),
                    "草稿已放弃，没有创建任何正式目标或任务。",
                  )
                }
                type="button"
              >
                放弃草稿
              </button>
              <button
                disabled={busy !== null}
                onClick={() =>
                  void (async () => {
                    setBusy("save-draft");
                    setError(null);
                    try {
                      await saveDraft();
                      setNotice("草稿修改已保存。 ");
                    } catch (saveError) {
                      setError(saveError instanceof Error ? saveError.message : "草稿未保存。 ");
                    } finally {
                      setBusy(null);
                    }
                  })()
                }
                type="button"
              >
                {busy === "save-draft" ? "保存中…" : "保存草稿"}
              </button>
              <button
                className="primary-button"
                disabled={busy !== null}
                onClick={() => void approveDraft()}
                type="button"
              >
                {busy === "approve-draft" ? "正在创建…" : "确认并创建正式计划"}
              </button>
            </div>
          </motion.div>
        ) : null}

        {!loading && run && ["completed", "rejected", "cancelled", "failed"].includes(run.status) ? (
          <motion.div
            animate={{ opacity: 1 }}
            className={`growth-workflow-outcome outcome-${run.status}`}
            initial={{ opacity: 0 }}
            key="outcome"
          >
            <div>
              <span>{run.status === "completed" ? "PLAN ONLINE" : "WORKFLOW CLOSED"}</span>
              <h3>{statusText(run.status)}</h3>
              <p>
                {run.status === "completed"
                  ? `已由 ${providerName(run.provider_used)} 完成，并创建 ${run.draft?.created_task_ids.length ?? 0} 项任务。`
                  : "没有创建新的正式目标或任务，你可以重新发起规划。"}
              </p>
            </div>
            <button className="primary-button" onClick={() => setShowCreate(true)} type="button">
              发起新规划
            </button>
          </motion.div>
        ) : null}
      </AnimatePresence>

      {run && activeStatuses.has(run.status) && run.status !== "waiting_for_draft_review" ? (
        <button
          className="growth-workflow-cancel"
          disabled={busy !== null}
          onClick={() =>
            void perform(
              "cancel",
              () => cancelGrowthWorkflow(run.id),
              "本次规划已取消。",
            )
          }
          type="button"
        >
          取消本次规划
        </button>
      ) : null}
    </motion.section>
  );
}
