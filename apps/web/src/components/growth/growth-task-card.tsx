import type { GrowthTask } from "@/lib/api";

import {
  areaLabel,
  formatMinutes,
  taskStatusLabels,
} from "@/components/growth/growth-utils";

export function GrowthTaskCard({
  task,
  busy,
  onStart,
  onComplete,
  onPause,
  onLogTime,
  onEdit,
  onRemove,
}: {
  task: GrowthTask;
  busy: string | null;
  onStart: (task: GrowthTask) => void;
  onComplete: (task: GrowthTask) => void;
  onPause: (task: GrowthTask) => void;
  onLogTime: (task: GrowthTask) => void;
  onEdit: (task: GrowthTask) => void;
  onRemove: (task: GrowthTask) => void;
}) {
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
        onClick={() => onComplete(task)}
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
            onClick={() => onStart(task)}
            type="button"
          >
            开始
          </button>
        ) : null}
        {task.status === "in_progress" ? (
          <button onClick={() => onPause(task)} type="button">
            暂停
          </button>
        ) : null}
        {!["completed", "cancelled"].includes(task.status) ? (
          <button onClick={() => onLogTime(task)} type="button">
            记时
          </button>
        ) : null}
        <button onClick={() => onEdit(task)} type="button">
          编辑
        </button>
        <button
          className="growth-delete-action"
          onClick={() => onRemove(task)}
          type="button"
        >
          删除
        </button>
      </div>
    </article>
  );
}
