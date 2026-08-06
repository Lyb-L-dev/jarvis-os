"use client";

import { useMemo, useState } from "react";

import { SpecialistHeader } from "@/components/agents/SpecialistHeader";
import { GrowthGoalsView } from "@/components/growth/growth-goals-view";
import { GrowthReviewView } from "@/components/growth/growth-review-view";
import { GrowthTaskForm } from "@/components/growth/growth-task-form";
import { GrowthTodayView } from "@/components/growth/growth-today-view";
import type {
  GrowthFeedback,
  GrowthTab,
} from "@/components/growth/growth-utils";
import { formatMinutes, runAction } from "@/components/growth/growth-utils";
import { useGoalForm } from "@/components/growth/use-goal-form";
import { useGrowthData } from "@/components/growth/use-growth-data";
import { useTaskActions } from "@/components/growth/use-task-actions";
import { useTaskForm } from "@/components/growth/use-task-form";
import { GrowthWorkflowPlanner } from "@/components/growth-workflow-planner";

import type { Goal } from "@/lib/api";

export function GrowthCenter() {
  const [tab, setTab] = useState<GrowthTab>("today");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const feedback = useMemo<GrowthFeedback>(
    () => ({ busy, setBusy, setError, setNotice }),
    [busy, setError, setNotice],
  );

  const data = useGrowthData({ feedback });
  const taskForm = useTaskForm({
    feedback,
    refresh: data.refresh,
    goals: data.goals,
  });
  const goalForm = useGoalForm({
    feedback,
    refresh: data.refresh,
    goals: data.goals,
  });
  const taskActions = useTaskActions({
    feedback,
    refresh: data.refresh,
  });

  const doAction = (
    key: string,
    action: () => Promise<unknown>,
    success: string,
  ) => runAction(feedback, data.refresh, key, action, success);

  function addTaskToGoal(goal: Goal) {
    taskForm.setTaskGoalId(goal.id);
    taskForm.setTaskMilestoneId("");
    taskForm.setShowTaskForm(true);
    setTab("today");
  }

  return (
    <main className="dashboard growth-page specialist-page specialist-growth">
      <SpecialistHeader
        accent="成长中心"
        activeAgent="growth"
        description="把长期目标变成今天可以开始、可以计时、可以复盘的真实行动。"
        eyebrow="GOAL · ACTION · REVIEW"
        status={data.overview.today_tasks ? "PLAN IN MOTION" : "READY TO PLAN"}
        title="Jarvis "
        actions={
          <button
            className="primary-button"
            onClick={() => taskForm.setShowTaskForm((current) => !current)}
            type="button"
          >
            {taskForm.showTaskForm ? "收起" : "+ 新建任务"}
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
          <strong>{data.overview.active_goals}</strong>
        </article>
        <article>
          <span>今日完成</span>
          <strong>
            {data.overview.today_completed}
            <small> / {data.overview.today_tasks}</small>
          </strong>
        </article>
        <article>
          <span>本周完成</span>
          <strong>{data.overview.week_completed}</strong>
        </article>
        <article>
          <span>本周真实投入</span>
          <strong>{formatMinutes(data.overview.week_actual_minutes)}</strong>
        </article>
      </section>

      <GrowthWorkflowPlanner onApplied={data.refresh} />

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

      {taskForm.showTaskForm ? (
        <GrowthTaskForm form={taskForm} goals={data.goals} busy={busy} />
      ) : null}

      {error ? <div className="growth-feedback growth-error">{error}</div> : null}
      {notice ? <div className="growth-feedback">{notice}</div> : null}

      {data.loading ? <div className="growth-loading">正在读取成长记录…</div> : null}

      {!data.loading && tab === "today" ? (
        <GrowthTodayView
          plan={data.plan}
          overview={data.overview}
          todayTasks={data.todayTasks}
          backlogTasks={data.backlogTasks}
          busy={busy}
          doAction={doAction}
          taskActions={taskActions}
          onNewTask={() => taskForm.setShowTaskForm(true)}
        />
      ) : null}

      {!data.loading && tab === "goals" ? (
        <GrowthGoalsView
          goals={data.goals}
          busy={busy}
          goalForm={goalForm}
          doAction={doAction}
          onAddTaskToGoal={addTaskToGoal}
        />
      ) : null}

      {!data.loading && tab === "review" ? (
        <GrowthReviewView
          review={data.review}
          busy={busy}
          reviewNote={data.reviewNote}
          setReviewNote={data.setReviewNote}
          doAction={doAction}
        />
      ) : null}
    </main>
  );
}
