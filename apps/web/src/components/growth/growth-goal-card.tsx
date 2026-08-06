import {
  deleteGoal,
  updateGoal,
  updateMilestone,
  type Goal,
} from "@/lib/api";

import { formatDate } from "@/lib/utils";

import { areaLabel } from "@/components/growth/growth-utils";
import { GrowthMilestoneRow } from "@/components/growth/growth-milestone-row";

export function GrowthGoalCard({
  goal,
  doAction,
  milestoneGoalId,
  setMilestoneGoalId,
  milestoneTitle,
  setMilestoneTitle,
  onAddMilestone,
  onCancelMilestone,
  onAddTaskToGoal,
}: {
  goal: Goal;
  doAction: (
    key: string,
    action: () => Promise<unknown>,
    success: string,
  ) => void;
  milestoneGoalId: string | null;
  setMilestoneGoalId: (value: string | null) => void;
  milestoneTitle: string;
  setMilestoneTitle: (value: string) => void;
  onAddMilestone: (goalId: string) => void;
  onCancelMilestone: () => void;
  onAddTaskToGoal: (goal: Goal) => void;
}) {
  return (
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
          <GrowthMilestoneRow
            key={milestone.id}
            milestone={milestone}
            onToggle={(item) =>
              void doAction(
                item.id,
                () =>
                  updateMilestone(item.id, {
                    status:
                      item.status === "completed"
                        ? "in_progress"
                        : "completed",
                  }),
                item.status === "completed"
                  ? "里程碑已重新打开。"
                  : "里程碑已完成。",
              )
            }
          />
        ))}
        {milestoneGoalId === goal.id ? (
          <div className="growth-milestone-add">
            <input
              aria-label="里程碑名称"
              autoFocus
              onChange={(event) => setMilestoneTitle(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  void onAddMilestone(goal.id);
                }
                if (event.key === "Escape") {
                  onCancelMilestone();
                }
              }}
              placeholder="输入里程碑名称"
              value={milestoneTitle}
            />
            <button
              disabled={!milestoneTitle.trim()}
              onClick={() => void onAddMilestone(goal.id)}
              type="button"
            >
              添加
            </button>
            <button onClick={onCancelMilestone} type="button">
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
        <button onClick={() => onAddTaskToGoal(goal)} type="button">
          + 添加关联任务
        </button>
        <button
          onClick={() => {
            const title = window.prompt("修改目标名称", goal.title);
            if (title?.trim()) {
              void doAction(
                goal.id,
                () => updateGoal(goal.id, { title: title.trim() }),
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
            void doAction(
              goal.id,
              () =>
                updateGoal(goal.id, {
                  status: goal.status === "paused" ? "active" : "paused",
                }),
              goal.status === "paused" ? "目标已恢复。" : "目标已暂停。",
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
              void doAction(
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
  );
}
