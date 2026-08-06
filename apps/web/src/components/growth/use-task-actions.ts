import {
  deleteGrowthTask,
  logGrowthTaskTime,
  transitionGrowthTask,
  updateGrowthTask,
  type GrowthTask,
} from "@/lib/api";

import {
  runAction,
  type GrowthFeedback,
} from "@/components/growth/growth-utils";

export function useTaskActions({
  feedback,
  refresh,
}: {
  feedback: GrowthFeedback;
  refresh: () => Promise<void>;
}) {
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
      feedback.setError("预计时长需要是 5～1440 分钟的整数。");
      return;
    }
    void runAction(
      feedback,
      refresh,
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
      feedback.setError("实际投入时间格式不正确。");
      return;
    }
    const evidence = window.prompt(
      "可以填写完成证据（可留空）",
      task.completion_evidence ?? "",
    );
    if (evidence === null) return;
    void runAction(
      feedback,
      refresh,
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
      feedback,
      refresh,
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
      feedback.setError("投入时间需要是 1～1440 分钟的整数。");
      return;
    }
    void runAction(
      feedback,
      refresh,
      task.id,
      () => logGrowthTaskTime(task.id, minutes),
      `已记录 ${minutes} 分钟投入。`,
    );
  }

  function removeTask(task: GrowthTask) {
    if (!window.confirm(`确定删除任务“${task.title}”吗？`)) return;
    void runAction(
      feedback,
      refresh,
      task.id,
      () => deleteGrowthTask(task.id),
      "任务已删除。",
    );
  }

  function startTask(task: GrowthTask) {
    void runAction(
      feedback,
      refresh,
      task.id,
      () => transitionGrowthTask(task.id, "start"),
      "任务已开始。",
    );
  }

  return {
    editTask,
    completeTask,
    pauseTask,
    logTime,
    removeTask,
    startTask,
  };
}

export type TaskActions = ReturnType<typeof useTaskActions>;
