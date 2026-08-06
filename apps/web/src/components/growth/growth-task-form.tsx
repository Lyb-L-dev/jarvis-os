import type { Goal, GrowthArea } from "@/lib/api";

import { areaOptions } from "@/components/growth/growth-utils";
import type { TaskForm } from "@/components/growth/use-task-form";

export function GrowthTaskForm({
  form,
  goals,
  busy,
}: {
  form: TaskForm;
  goals: Goal[];
  busy: string | null;
}) {
  const {
    taskTitle,
    setTaskTitle,
    taskArea,
    setTaskArea,
    taskGoalId,
    setTaskGoalId,
    taskMilestoneId,
    setTaskMilestoneId,
    taskPriority,
    setTaskPriority,
    taskMinutes,
    setTaskMinutes,
    taskForToday,
    setTaskForToday,
    taskReminderAt,
    setTaskReminderAt,
    selectedGoal,
    addTask,
  } = form;

  return (
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
            onChange={(event) => setTaskArea(event.target.value as GrowthArea)}
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
  );
}
