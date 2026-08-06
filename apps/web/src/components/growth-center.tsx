"use client";

import {
  confirmTodayPlan,
  createGoal,
  createGrowthTask,
  createMilestone,
  deleteGoal,
  deleteGrowthTask,
  generateTodayPlan,
  generateWeeklyReview,
  getGrowthOverview,
  getTodayPlan,
  getWeeklyReview,
  listGoals,
  listGrowthTasks,
  logGrowthTaskTime,
  resetTodayPlan,
  transitionGrowthTask,
  updateGoal,
  updateGrowthTask,
  updateMilestone,
  updateWeeklyReview,
  type DailyPlan,
  type Goal,
  type GrowthArea,
  type GrowthOverview,
  type GrowthTask,
  type WeeklyReview,
} from "@/lib/api";
import { useCallback, useEffect, useMemo, useState } from "react";

import { SpecialistHeader } from "@/components/agents/SpecialistHeader";
import { GrowthWorkflowPlanner } from "@/components/growth-workflow-planner";

type GrowthTab = "today" | "goals" | "review";

const areaOptions: Array<{ value: GrowthArea; label: string }> = [
  { value: "technology", label: "技术" },
  { value: "career", label: "职业" },
  { value: "english", label: "英语" },
  { value: "investment", label: "投资" },
  { value: "personal", label: "个人" },
];

const taskStatusLabels: Record<GrowthTask["status"], string> = {
  todo: "待开始",
  in_progress: "进行中",
  paused: "已暂停",
  completed: "已完成",
  cancelled: "已取消",
};

function localDateString() {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function areaLabel(area: GrowthArea) {
  return areaOptions.find((item) => item.value === area)?.label ?? area;
}

function formatMinutes(minutes: number) {
  if (minutes < 60) return `${minutes} 分钟`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest ? `${hours} 小时 ${rest} 分钟` : `${hours} 小时`;
}

function formatDate(value?: string | null) {
  if (!value) return "未设置";
  return new Date(`${value.slice(0, 10)}T00:00:00`).toLocaleDateString("zh-CN", {
    month: "numeric",
    day: "numeric",
  });
}

export function GrowthCenter() {
  const [tab, setTab] = useState<GrowthTab>("today");
  const [overview, setOverview] = useState<GrowthOverview>({
    active_goals: 0,
    today_tasks: 0,
    today_completed: 0,
    week_completed: 0,
    week_actual_minutes: 0,
    today_capacity_minutes: 240,
  });
  const [goals, setGoals] = useState<Goal[]>([]);
  const [tasks, setTasks] = useState<GrowthTask[]>([]);
  const [plan, setPlan] = useState<DailyPlan | null>(null);
  const [review, setReview] = useState<WeeklyReview | null>(null);
  const [reviewNote, setReviewNote] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [showTaskForm, setShowTaskForm] = useState(false);
  const [showGoalForm, setShowGoalForm] = useState(false);
  const [milestoneGoalId, setMilestoneGoalId] = useState<string | null>(null);
  const [milestoneTitle, setMilestoneTitle] = useState("");

  const [taskTitle, setTaskTitle] = useState("");
  const [taskArea, setTaskArea] = useState<GrowthArea>("technology");
  const [taskGoalId, setTaskGoalId] = useState("");
  const [taskMilestoneId, setTaskMilestoneId] = useState("");
  const [taskPriority, setTaskPriority] = useState(3);
  const [taskMinutes, setTaskMinutes] = useState(60);
  const [taskForToday, setTaskForToday] = useState(true);
  const [taskReminderAt, setTaskReminderAt] = useState("");

  const [goalTitle, setGoalTitle] = useState("");
  const [goalDescription, setGoalDescription] = useState("");
  const [goalArea, setGoalArea] = useState<GrowthArea>("career");
  const [goalDate, setGoalDate] = useState("");

  const refresh = useCallback(async (signal?: AbortSignal) => {
    try {
      const [nextOverview, nextGoals, nextTasks, nextPlan, nextReview] =
        await Promise.all([
          getGrowthOverview(signal),
          listGoals(signal),
          listGrowthTasks(signal),
          getTodayPlan(signal),
          getWeeklyReview(signal),
        ]);
      setOverview(nextOverview);
      setGoals(nextGoals);
      setTasks(nextTasks);
      setPlan(nextPlan);
      setReview(nextReview);
      setReviewNote(nextReview?.user_note ?? "");
      setError(null);
    } catch (loadError) {
      if (
        loadError instanceof DOMException &&
        loadError.name === "AbortError"
      ) {
        return;
      }
      setError(
        loadError instanceof Error ? loadError.message : "读取成长数据失败",
      );
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => {
      void refresh(controller.signal);
    }, 0);
    return () => {
      window.clearTimeout(timeout);
      controller.abort();
    };
  }, [refresh]);

  const selectedGoal = useMemo(
    () => goals.find((goal) => goal.id === taskGoalId) ?? null,
    [goals, taskGoalId],
  );
  const today = localDateString();
  const todayTasks = useMemo(
    () =>
      tasks.filter(
        (task) =>
          task.planned_date === today &&
          task.status !== "cancelled",
      ),
    [tasks, today],
  );
  const backlogTasks = useMemo(
    () =>
      tasks
        .filter(
          (task) =>
            task.planned_date !== today &&
            !["completed", "cancelled"].includes(task.status),
        )
        .slice(0, 6),
    [tasks, today],
  );

  async function runAction(
    key: string,
    action: () => Promise<unknown>,
    success: string,
  ) {
    setBusy(key);
    setError(null);
    setNotice(null);
    try {
      await action();
      setNotice(success);
      await refresh();
    } catch (actionError) {
      setError(
        actionError instanceof Error ? actionError.message : "操作失败",
      );
    } finally {
      setBusy(null);
    }
  }

  async function addTask() {
    const title = taskTitle.trim();
    if (!title) return;
    await runAction(
      "create-task",
      () =>
        createGrowthTask({
          title,
          area: taskArea,
          goal_id: taskGoalId || undefined,
          milestone_id: taskMilestoneId || undefined,
          priority: taskPriority,
          planned_date: taskForToday ? today : undefined,
          reminder_at: taskReminderAt
            ? new Date(taskReminderAt).toISOString()
            : undefined,
          estimated_minutes: taskMinutes,
        }),
      "任务已创建。",
    );
    setTaskTitle("");
    setTaskMilestoneId("");
    setTaskReminderAt("");
    setShowTaskForm(false);
  }

  async function addGoal() {
    const title = goalTitle.trim();
    if (!title) return;
    await runAction(
      "create-goal",
      () =>
        createGoal({
          title,
          description: goalDescription.trim() || undefined,
          area: goalArea,
          target_date: goalDate || undefined,
        }),
      "长期目标已创建。",
    );
    setGoalTitle("");
    setGoalDescription("");
    setGoalDate("");
    setShowGoalForm(false);
  }

  async function addMilestone(goalId: string) {
    const title = milestoneTitle.trim();
    if (!title) return;
    await runAction(
      `milestone-${goalId}`,
      () =>
        createMilestone(goalId, {
          title,
          order_index:
            (goals.find((goal) => goal.id === goalId)?.milestones.length ?? 0) +
            1,
        }),
      "里程碑已添加。",
    );
    setMilestoneTitle("");
    setMilestoneGoalId(null);
  }

  function editTask(task: GrowthTask) {
    const title = window.prompt("修改任务名称", task.title);
    if (title === null || !title.trim()) return;
    const minutesText = window.prompt(
      "预计投入多少分钟？",
      String(task.estimated_minutes),
    );
    if (minutesText === null) return;
    const minutes = Number(minutesText);
    if (!Number.isInteger(minutes) || minutes < 5 || minutes > 1440) {
      setError("预计时长需要是 5～1440 分钟的整数。");
      return;
    }
    void runAction(
      task.id,
      () =>
        updateGrowthTask(task.id, {
          title: title.trim(),
          estimated_minutes: minutes,
        }),
      "任务已更新。",
    );
  }

  function completeTask(task: GrowthTask) {
    const minutesText = window.prompt(
      "这项任务实际投入了多少分钟？",
      String(task.actual_minutes || task.estimated_minutes),
    );
    if (minutesText === null) return;
    const minutes = Number(minutesText);
    if (!Number.isInteger(minutes) || minutes < 0 || minutes > 10080) {
      setError("实际投入时间格式不正确。");
      return;
    }
    const evidence = window.prompt(
      "可以填写完成证据（可留空）",
      task.completion_evidence ?? "",
    );
    if (evidence === null) return;
    void runAction(
      task.id,
      () =>
        transitionGrowthTask(task.id, "complete", {
          actual_minutes: minutes,
          completion_evidence: evidence.trim() || undefined,
        }),
      "任务已完成，实际投入已记录。",
    );
  }

  function pauseTask(task: GrowthTask) {
    const blocker = window.prompt(
      "暂停原因或当前阻塞是什么？",
      task.blocker_reason ?? "",
    );
    if (blocker === null) return;
    void runAction(
      task.id,
      () =>
        transitionGrowthTask(task.id, "pause", {
          blocker_reason: blocker.trim() || undefined,
        }),
      "任务已暂停，阻塞原因已记录。",
    );
  }

  function logTime(task: GrowthTask) {
    const minutesText = window.prompt("本次投入多少分钟？", "30");
    if (minutesText === null) return;
    const minutes = Number(minutesText);
    if (!Number.isInteger(minutes) || minutes < 1 || minutes > 1440) {
      setError("投入时间需要是 1～1440 分钟的整数。");
      return;
    }
    void runAction(
      task.id,
      () => logGrowthTaskTime(task.id, minutes),
      `已记录 ${minutes} 分钟投入。`,
    );
  }

  function removeTask(task: GrowthTask) {
    if (!window.confirm(`确定删除任务“${task.title}”吗？`)) return;
    void runAction(
      task.id,
      () => deleteGrowthTask(task.id),
      "任务已删除。",
    );
  }

  function renderTask(task: GrowthTask) {
    return (
      <article className={`growth-task growth-task-${task.status}`} key={task.id}>
        <button
          aria-label={
            task.status === "completed"
              ? `${task.title}已完成`
              : `完成${task.title}`
          }
          className="growth-task-check"
          disabled={
            task.status === "completed" ||
            task.status === "cancelled" ||
            busy === task.id
          }
          onClick={() => completeTask(task)}
          type="button"
        >
          {task.status === "completed" ? "✓" : ""}
        </button>
        <div className="growth-task-body">
          <div className="growth-task-title">
            <strong>{task.title}</strong>
            <span className={`growth-task-state state-${task.status}`}>
              {taskStatusLabels[task.status]}
            </span>
          </div>
          <div className="growth-task-meta">
            <span>{areaLabel(task.area)}</span>
            <span>优先级 P{task.priority}</span>
            <span>预计 {formatMinutes(task.estimated_minutes)}</span>
            <span>已投入 {formatMinutes(task.actual_minutes)}</span>
            {task.reminder_at ? (
              <span>
                提醒{" "}
                {new Date(task.reminder_at).toLocaleString("zh-CN", {
                  month: "numeric",
                  day: "numeric",
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </span>
            ) : null}
          </div>
          {task.blocker_reason ? (
            <p className="growth-blocker">阻塞：{task.blocker_reason}</p>
          ) : null}
          {task.completion_evidence ? (
            <p className="growth-evidence">证据：{task.completion_evidence}</p>
          ) : null}
        </div>
        <div className="growth-task-actions">
          {task.status === "todo" || task.status === "paused" ? (
            <button
              disabled={busy === task.id}
              onClick={() =>
                void runAction(
                  task.id,
                  () => transitionGrowthTask(task.id, "start"),
                  "任务已开始。",
                )
              }
              type="button"
            >
              开始
            </button>
          ) : null}
          {task.status === "in_progress" ? (
            <button onClick={() => pauseTask(task)} type="button">
              暂停
            </button>
          ) : null}
          {!["completed", "cancelled"].includes(task.status) ? (
            <button onClick={() => logTime(task)} type="button">
              记时
            </button>
          ) : null}
          <button onClick={() => editTask(task)} type="button">
            编辑
          </button>
          <button
            className="growth-delete-action"
            onClick={() => removeTask(task)}
            type="button"
          >
            删除
          </button>
        </div>
      </article>
    );
  }

  return (
    <main className="dashboard growth-page specialist-page specialist-growth">
      <SpecialistHeader
        accent="成长中心"
        activeAgent="growth"
        description="把长期目标变成今天可以开始、可以计时、可以复盘的真实行动。"
        eyebrow="GOAL · ACTION · REVIEW"
        status={overview.today_tasks ? "PLAN IN MOTION" : "READY TO PLAN"}
        title="Jarvis "
        actions={
          <button
            className="primary-button"
            onClick={() => setShowTaskForm((current) => !current)}
            type="button"
          >
            {showTaskForm ? "收起" : "+ 新建任务"}
          </button>
        }
      />

      <div className="specialist-section-label">
        <div>
          <span>YOUR TRAJECTORY</span>
          <strong>当前成长轨迹</strong>
        </div>
        <p>目标、行动与真实投入会在这里形成连续路径</p>
      </div>

      <section className="growth-stats specialist-metrics">
        <article>
          <span>活跃目标</span>
          <strong>{overview.active_goals}</strong>
        </article>
        <article>
          <span>今日完成</span>
          <strong>
            {overview.today_completed}
            <small> / {overview.today_tasks}</small>
          </strong>
        </article>
        <article>
          <span>本周完成</span>
          <strong>{overview.week_completed}</strong>
        </article>
        <article>
          <span>本周真实投入</span>
          <strong>{formatMinutes(overview.week_actual_minutes)}</strong>
        </article>
      </section>

      <GrowthWorkflowPlanner onApplied={refresh} />

      <nav className="growth-tabs specialist-tabs" aria-label="成长中心视图">
        {(
          [
            ["today", "今日行动"],
            ["goals", "长期目标"],
            ["review", "本周复盘"],
          ] as Array<[GrowthTab, string]>
        ).map(([value, label]) => (
          <button
            className={tab === value ? "growth-tab-active" : ""}
            key={value}
            onClick={() => setTab(value)}
            type="button"
          >
            {label}
          </button>
        ))}
      </nav>

      {showTaskForm ? (
        <section className="panel growth-form-panel">
          <div className="growth-form-heading">
            <div>
              <div className="eyebrow">NEW ACTION</div>
              <h2>新建可执行任务</h2>
            </div>
            <span>每项任务都可以追踪状态和实际投入</span>
          </div>
          <div className="growth-task-form">
            <label className="growth-form-wide">
              任务名称
              <input
                aria-label="任务名称"
                maxLength={240}
                onChange={(event) => setTaskTitle(event.target.value)}
                placeholder="例如：完成 Tool Calling 练习"
                value={taskTitle}
              />
            </label>
            <label>
              领域
              <select
                onChange={(event) =>
                  setTaskArea(event.target.value as GrowthArea)
                }
                value={taskArea}
              >
                {areaOptions.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              关联目标
              <select
                onChange={(event) => {
                  setTaskGoalId(event.target.value);
                  setTaskMilestoneId("");
                }}
                value={taskGoalId}
              >
                <option value="">不关联目标</option>
                {goals
                  .filter((goal) => goal.status === "active")
                  .map((goal) => (
                    <option key={goal.id} value={goal.id}>
                      {goal.title}
                    </option>
                  ))}
              </select>
            </label>
            <label>
              关联里程碑
              <select
                disabled={!selectedGoal}
                onChange={(event) => setTaskMilestoneId(event.target.value)}
                value={taskMilestoneId}
              >
                <option value="">不关联里程碑</option>
                {selectedGoal?.milestones.map((milestone) => (
                  <option key={milestone.id} value={milestone.id}>
                    {milestone.title}
                  </option>
                ))}
              </select>
            </label>
            <label>
              优先级
              <select
                onChange={(event) => setTaskPriority(Number(event.target.value))}
                value={taskPriority}
              >
                {[5, 4, 3, 2, 1].map((value) => (
                  <option key={value} value={value}>
                    P{value}
                  </option>
                ))}
              </select>
            </label>
            <label>
              预计分钟
              <input
                max={1440}
                min={5}
                onChange={(event) => setTaskMinutes(Number(event.target.value))}
                type="number"
                value={taskMinutes}
              />
            </label>
            <label className="growth-today-check">
              <input
                checked={taskForToday}
                onChange={(event) => setTaskForToday(event.target.checked)}
                type="checkbox"
              />
              安排到今天
            </label>
            <label>
              自动提醒（可选）
              <input
                onChange={(event) => setTaskReminderAt(event.target.value)}
                type="datetime-local"
                value={taskReminderAt}
              />
            </label>
            <button
              className="primary-button"
              disabled={!taskTitle.trim() || busy === "create-task"}
              onClick={() => void addTask()}
              type="button"
            >
              {busy === "create-task" ? "创建中…" : "创建任务"}
            </button>
          </div>
        </section>
      ) : null}

      {error ? <div className="growth-feedback growth-error">{error}</div> : null}
      {notice ? <div className="growth-feedback">{notice}</div> : null}

      {loading ? <div className="growth-loading">正在读取成长记录…</div> : null}

      {!loading && tab === "today" ? (
        <div className="growth-today-grid">
          <section className="panel growth-plan-panel">
            <div className="growth-section-head">
              <div>
                <div className="eyebrow">4-HOUR FOCUS</div>
                <h2>今日重点计划</h2>
              </div>
              <span>
                {plan
                  ? `${formatMinutes(plan.total_estimated_minutes)} / ${formatMinutes(plan.capacity_minutes)}`
                  : `可用 ${formatMinutes(overview.today_capacity_minutes)}`}
              </span>
            </div>

            {!plan ? (
              <div className="growth-plan-empty">
                <strong>今天还没有重点计划</strong>
                <p>Jarvis 会从未完成任务中选择最多 3 项，先生成草稿给你确认。</p>
                <button
                  className="primary-button"
                  disabled={busy === "generate-plan"}
                  onClick={() =>
                    void runAction(
                      "generate-plan",
                      () => generateTodayPlan(),
                      "计划草稿已生成，请确认后再排入今天。",
                    )
                  }
                  type="button"
                >
                  生成 4 小时计划草稿
                </button>
              </div>
            ) : (
              <>
                <div className={`growth-plan-state plan-${plan.status}`}>
                  {plan.status === "draft" ? "等待你确认" : "今日计划已确认"}
                </div>
                <div className="growth-plan-list">
                  {plan.tasks.length ? (
                    plan.tasks.map((task, index) => (
                      <div className="growth-plan-item" key={task.id}>
                        <span>{String(index + 1).padStart(2, "0")}</span>
                        <div>
                          <strong>{task.title}</strong>
                          <small>
                            P{task.priority} · {formatMinutes(task.estimated_minutes)}
                          </small>
                        </div>
                      </div>
                    ))
                  ) : (
                    <p className="growth-plan-no-task">
                      还没有可选择的未完成任务，请先新建任务。
                    </p>
                  )}
                </div>
                {plan.generation_note ? (
                  <p className="growth-plan-note">{plan.generation_note}</p>
                ) : null}
                {plan.status === "draft" ? (
                  <button
                    className="primary-button"
                    disabled={!plan.tasks.length || busy === "confirm-plan"}
                    onClick={() =>
                      void runAction(
                        "confirm-plan",
                        () => confirmTodayPlan(),
                        "今日计划已确认，任务日期已更新。",
                      )
                    }
                    type="button"
                  >
                    确认今日计划
                  </button>
                ) : null}
                <button
                  className="growth-reset-plan"
                  onClick={() => {
                    if (
                      window.confirm(
                        "确定重置今日计划吗？未完成任务会回到待安排状态。",
                      )
                    ) {
                      void runAction(
                        "reset-plan",
                        () => resetTodayPlan(),
                        "今日计划已重置。",
                      );
                    }
                  }}
                  type="button"
                >
                  重置今日计划
                </button>
              </>
            )}
          </section>

          <section className="panel growth-today-tasks">
            <div className="growth-section-head">
              <div>
                <div className="eyebrow">TODAY TASKS</div>
                <h2>今日任务</h2>
              </div>
              <span>{todayTasks.length} 项</span>
            </div>
            <div className="growth-task-list">
              {todayTasks.length ? (
                todayTasks.map(renderTask)
              ) : (
                <div className="growth-inline-empty">今天还没有已安排任务。</div>
              )}
            </div>
          </section>

          <section className="panel growth-backlog-panel">
            <div className="growth-section-head">
              <div>
                <div className="eyebrow">NEXT ACTIONS</div>
                <h2>待安排任务</h2>
              </div>
              <button
                className="text-button"
                onClick={() => setShowTaskForm(true)}
                type="button"
              >
                新建
              </button>
            </div>
            <div className="growth-task-list">
              {backlogTasks.length ? (
                backlogTasks.map(renderTask)
              ) : (
                <div className="growth-inline-empty">没有待安排任务。</div>
              )}
            </div>
          </section>
        </div>
      ) : null}

      {!loading && tab === "goals" ? (
        <section className="growth-goals-view">
          <div className="growth-goals-toolbar">
            <div>
              <div className="eyebrow">LONG-TERM DIRECTION</div>
              <h2>长期目标与里程碑</h2>
            </div>
            <button
              className="primary-button"
              onClick={() => setShowGoalForm((current) => !current)}
              type="button"
            >
              {showGoalForm ? "取消" : "+ 新建目标"}
            </button>
          </div>

          {showGoalForm ? (
            <div className="panel growth-goal-form">
              <label>
                目标名称
                <input
                  aria-label="目标名称"
                  onChange={(event) => setGoalTitle(event.target.value)}
                  placeholder="例如：成为 AI 应用工程师"
                  value={goalTitle}
                />
              </label>
              <label>
                领域
                <select
                  onChange={(event) =>
                    setGoalArea(event.target.value as GrowthArea)
                  }
                  value={goalArea}
                >
                  {areaOptions.map((item) => (
                    <option key={item.value} value={item.value}>
                      {item.label}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                目标日期
                <input
                  onChange={(event) => setGoalDate(event.target.value)}
                  type="date"
                  value={goalDate}
                />
              </label>
              <label className="growth-form-wide">
                说明
                <input
                  onChange={(event) => setGoalDescription(event.target.value)}
                  placeholder="为什么重要，以及完成的判断标准"
                  value={goalDescription}
                />
              </label>
              <button
                className="primary-button"
                disabled={!goalTitle.trim() || busy === "create-goal"}
                onClick={() => void addGoal()}
                type="button"
              >
                创建长期目标
              </button>
            </div>
          ) : null}

          <div className="growth-goal-list">
            {goals.length ? (
              goals.map((goal) => (
                <article className="panel growth-goal-card" key={goal.id}>
                  <div className="growth-goal-head">
                    <div>
                      <span>{areaLabel(goal.area)}</span>
                      <h3>{goal.title}</h3>
                      <p>
                        目标日期：{formatDate(goal.target_date)} · {goal.progress.basis}
                      </p>
                    </div>
                    <div className="growth-progress-number">
                      <strong>{goal.progress.percent}%</strong>
                      <span>可追溯进度</span>
                    </div>
                  </div>
                  <div className="growth-progress-track">
                    <i style={{ width: `${goal.progress.percent}%` }} />
                  </div>
                  {goal.description ? (
                    <p className="growth-goal-description">{goal.description}</p>
                  ) : null}

                  <div className="growth-milestones">
                    <div className="growth-subheading">
                      <strong>里程碑</strong>
                      <span>
                        {goal.progress.completed_milestones}/
                        {goal.progress.total_milestones} 已完成
                      </span>
                    </div>
                    {goal.milestones.map((milestone) => (
                      <div className="growth-milestone" key={milestone.id}>
                        <button
                          aria-label={`${milestone.title}${
                            milestone.status === "completed"
                              ? "已完成"
                              : "标记完成"
                          }`}
                          className={
                            milestone.status === "completed"
                              ? "milestone-complete"
                              : ""
                          }
                          onClick={() =>
                            void runAction(
                              milestone.id,
                              () =>
                                updateMilestone(milestone.id, {
                                  status:
                                    milestone.status === "completed"
                                      ? "in_progress"
                                      : "completed",
                                }),
                              milestone.status === "completed"
                                ? "里程碑已重新打开。"
                                : "里程碑已完成。",
                            )
                          }
                          type="button"
                        >
                          {milestone.status === "completed" ? "✓" : ""}
                        </button>
                        <span>{milestone.title}</span>
                        <small>{formatDate(milestone.target_date)}</small>
                      </div>
                    ))}
                    {milestoneGoalId === goal.id ? (
                      <div className="growth-milestone-add">
                        <input
                          aria-label="里程碑名称"
                          autoFocus
                          onChange={(event) =>
                            setMilestoneTitle(event.target.value)
                          }
                          onKeyDown={(event) => {
                            if (event.key === "Enter") {
                              void addMilestone(goal.id);
                            }
                            if (event.key === "Escape") {
                              setMilestoneGoalId(null);
                            }
                          }}
                          placeholder="输入里程碑名称"
                          value={milestoneTitle}
                        />
                        <button
                          disabled={!milestoneTitle.trim()}
                          onClick={() => void addMilestone(goal.id)}
                          type="button"
                        >
                          添加
                        </button>
                        <button
                          onClick={() => setMilestoneGoalId(null)}
                          type="button"
                        >
                          取消
                        </button>
                      </div>
                    ) : (
                      <button
                        className="growth-add-milestone"
                        onClick={() => {
                          setMilestoneGoalId(goal.id);
                          setMilestoneTitle("");
                        }}
                        type="button"
                      >
                        + 添加里程碑
                      </button>
                    )}
                  </div>

                  <div className="growth-goal-actions">
                    <button
                      onClick={() => {
                        setTaskGoalId(goal.id);
                        setTaskMilestoneId("");
                        setShowTaskForm(true);
                        setTab("today");
                      }}
                      type="button"
                    >
                      + 添加关联任务
                    </button>
                    <button
                      onClick={() => {
                        const title = window.prompt("修改目标名称", goal.title);
                        if (title?.trim()) {
                          void runAction(
                            goal.id,
                            () =>
                              updateGoal(goal.id, { title: title.trim() }),
                            "目标已更新。",
                          );
                        }
                      }}
                      type="button"
                    >
                      编辑
                    </button>
                    <button
                      onClick={() =>
                        void runAction(
                          goal.id,
                          () =>
                            updateGoal(goal.id, {
                              status:
                                goal.status === "paused" ? "active" : "paused",
                            }),
                          goal.status === "paused"
                            ? "目标已恢复。"
                            : "目标已暂停。",
                        )
                      }
                      type="button"
                    >
                      {goal.status === "paused" ? "恢复" : "暂停"}
                    </button>
                    <button
                      className="growth-delete-action"
                      onClick={() => {
                        if (
                          window.confirm(
                            `确定删除目标“${goal.title}”吗？关联任务不会被删除。`,
                          )
                        ) {
                          void runAction(
                            goal.id,
                            () => deleteGoal(goal.id),
                            "目标已删除。",
                          );
                        }
                      }}
                      type="button"
                    >
                      删除
                    </button>
                  </div>
                </article>
              ))
            ) : (
              <div className="growth-large-empty">
                <strong>还没有长期目标</strong>
                <p>先建立一个真正重要的方向，再逐步拆成里程碑和任务。</p>
              </div>
            )}
          </div>
        </section>
      ) : null}

      {!loading && tab === "review" ? (
        <section className="growth-review-view">
          <div className="growth-review-toolbar">
            <div>
              <div className="eyebrow">REAL DATA REVIEW</div>
              <h2>本周执行复盘</h2>
              <p>所有数字都来自已确认的任务日期、完成状态和计时事件。</p>
            </div>
            <button
              className="primary-button"
              disabled={busy === "review"}
              onClick={() =>
                void runAction(
                  "review",
                  () => generateWeeklyReview(),
                  "本周复盘已按最新真实记录重新计算。",
                )
              }
              type="button"
            >
              {review ? "重新计算" : "生成本周复盘"}
            </button>
          </div>

          {review ? (
            <>
              <div className="growth-review-stats">
                <article>
                  <span>计划任务</span>
                  <strong>{review.snapshot.planned_tasks ?? 0}</strong>
                </article>
                <article>
                  <span>完成任务</span>
                  <strong>{review.snapshot.completed_tasks ?? 0}</strong>
                </article>
                <article>
                  <span>完成率</span>
                  <strong>{review.snapshot.completion_rate ?? 0}%</strong>
                </article>
                <article>
                  <span>实际投入</span>
                  <strong>
                    {formatMinutes(review.snapshot.actual_minutes ?? 0)}
                  </strong>
                </article>
              </div>
              <article className="panel growth-review-card">
                <div className="growth-section-head">
                  <div>
                    <div className="eyebrow">WEEK SUMMARY</div>
                    <h2>
                      {formatDate(review.week_start)} —{" "}
                      {formatDate(review.week_end)}
                    </h2>
                  </div>
                  <span>
                    {review.status === "confirmed" ? "已确认" : "待确认"}
                  </span>
                </div>
                <p className="growth-review-summary">{review.summary}</p>
                {(review.snapshot.blockers?.length ?? 0) > 0 ? (
                  <div className="growth-review-blockers">
                    <strong>未完成与阻塞</strong>
                    {review.snapshot.blockers?.map((item) => (
                      <p key={`${item.task}-${item.reason}`}>
                        <span>{item.task}</span>
                        {item.reason}
                      </p>
                    ))}
                  </div>
                ) : null}
                <label className="growth-review-note">
                  我的复盘记录
                  <textarea
                    onChange={(event) => setReviewNote(event.target.value)}
                    placeholder="本周做得好的地方、困难，以及下周需要调整的重点"
                    rows={5}
                    value={reviewNote}
                  />
                </label>
                <div className="growth-review-actions">
                  <button
                    onClick={() =>
                      void runAction(
                        review.id,
                        () =>
                          updateWeeklyReview(review.id, {
                            user_note: reviewNote,
                          }),
                        "复盘记录已保存。",
                      )
                    }
                    type="button"
                  >
                    保存记录
                  </button>
                  <button
                    className="primary-button"
                    onClick={() =>
                      void runAction(
                        review.id,
                        () =>
                          updateWeeklyReview(review.id, {
                            user_note: reviewNote,
                            status: "confirmed",
                          }),
                        "本周复盘已确认。",
                      )
                    }
                    type="button"
                  >
                    确认本周复盘
                  </button>
                </div>
              </article>
            </>
          ) : (
            <div className="growth-large-empty">
              <strong>本周还没有复盘</strong>
              <p>完成或暂停任务后，在这里生成基于真实记录的周复盘。</p>
            </div>
          )}
        </section>
      ) : null}
    </main>
  );
}
