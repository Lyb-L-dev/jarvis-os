import type { GrowthArea, GrowthTask } from "@/lib/api";

export type GrowthTab = "today" | "goals" | "review";

export type GrowthFeedback = {
  busy: string | null;
  setBusy: (busy: string | null) => void;
  setError: (error: string | null) => void;
  setNotice: (notice: string | null) => void;
};

export const areaOptions: Array<{ value: GrowthArea; label: string }> = [
  { value: "technology", label: "技术" },
  { value: "career", label: "职业" },
  { value: "english", label: "英语" },
  { value: "investment", label: "投资" },
  { value: "personal", label: "个人" },
];

export const taskStatusLabels: Record<GrowthTask["status"], string> = {
  todo: "待开始",
  in_progress: "进行中",
  paused: "已暂停",
  completed: "已完成",
  cancelled: "已取消",
};

export function areaLabel(area: GrowthArea) {
  return areaOptions.find((item) => item.value === area)?.label ?? area;
}

export function formatMinutes(minutes: number) {
  if (minutes < 60) return `${minutes} 分钟`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest ? `${hours} 小时 ${rest} 分钟` : `${hours} 小时`;
}

export async function runAction(
  feedback: GrowthFeedback,
  refresh: () => Promise<void>,
  key: string,
  action: () => Promise<unknown>,
  success: string,
) {
  feedback.setBusy(key);
  feedback.setError(null);
  feedback.setNotice(null);
  try {
    await action();
    feedback.setNotice(success);
    await refresh();
  } catch (actionError) {
    feedback.setError(
      actionError instanceof Error ? actionError.message : "操作失败",
    );
  } finally {
    feedback.setBusy(null);
  }
}
