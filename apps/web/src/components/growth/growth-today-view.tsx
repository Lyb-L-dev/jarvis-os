import {
  confirmTodayPlan,
  generateTodayPlan,
  resetTodayPlan,
  type DailyPlan,
  type GrowthOverview,
  type GrowthTask,
} from "@/lib/api";

import { formatMinutes } from "@/components/growth/growth-utils";
import { GrowthTaskCard } from "@/components/growth/growth-task-card";
import type { TaskActions } from "@/components/growth/use-task-actions";

export function GrowthTodayView({
  plan,
  overview,
  todayTasks,
  backlogTasks,
  busy,
  doAction,
  taskActions,
  onNewTask,
}: {
  plan: DailyPlan | null;
  overview: GrowthOverview;
  todayTasks: GrowthTask[];
  backlogTasks: GrowthTask[];
  busy: string | null;
  doAction: (
    key: string,
    action: () => Promise<unknown>,
    success: string,
  ) => void;
  taskActions: TaskActions;
  onNewTask: () => void;
}) {
  return (
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
                void doAction(
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
                  void doAction(
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
                  void doAction(
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
            todayTasks.map((task) => (
              <GrowthTaskCard
                busy={busy}
                key={task.id}
                onComplete={taskActions.completeTask}
                onEdit={taskActions.editTask}
                onLogTime={taskActions.logTime}
                onPause={taskActions.pauseTask}
                onRemove={taskActions.removeTask}
                onStart={taskActions.startTask}
                task={task}
              />
            ))
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
          <button className="text-button" onClick={onNewTask} type="button">
            新建
          </button>
        </div>
        <div className="growth-task-list">
          {backlogTasks.length ? (
            backlogTasks.map((task) => (
              <GrowthTaskCard
                busy={busy}
                key={task.id}
                onComplete={taskActions.completeTask}
                onEdit={taskActions.editTask}
                onLogTime={taskActions.logTime}
                onPause={taskActions.pauseTask}
                onRemove={taskActions.removeTask}
                onStart={taskActions.startTask}
                task={task}
              />
            ))
          ) : (
            <div className="growth-inline-empty">没有待安排任务。</div>
          )}
        </div>
      </section>
    </div>
  );
}
