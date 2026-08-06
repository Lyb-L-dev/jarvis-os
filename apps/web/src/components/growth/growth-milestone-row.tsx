import type { Goal } from "@/lib/api";

import { formatDate } from "@/lib/utils";

export function GrowthMilestoneRow({
  milestone,
  onToggle,
}: {
  milestone: Goal["milestones"][number];
  onToggle: (milestone: Goal["milestones"][number]) => void;
}) {
  return (
    <div className="growth-milestone">
      <button
        aria-label={`${milestone.title}${
          milestone.status === "completed" ? "已完成" : "标记完成"
        }`}
        className={
          milestone.status === "completed" ? "milestone-complete" : ""
        }
        onClick={() => onToggle(milestone)}
        type="button"
      >
        {milestone.status === "completed" ? "✓" : ""}
      </button>
      <span>{milestone.title}</span>
      <small>{formatDate(milestone.target_date)}</small>
    </div>
  );
}
