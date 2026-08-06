import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

import { Sparkline } from "./Sparkline";

type StatCardProps = {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  icon?: ReactNode;
  trend?: number[];
  className?: string;
};

/** 大数字统计卡：标签 + 数值 + 说明 + 可选图标与迷你趋势。 */
export function StatCard({
  label,
  value,
  hint,
  icon,
  trend,
  className,
}: StatCardProps) {
  return (
    <article className={cn("stat-card", className)}>
      {icon ? <span>{icon}</span> : null}
      <div>
        <small>{label}</small>
        <strong>{value}</strong>
        {hint ? <p>{hint}</p> : null}
        {trend && trend.length > 1 ? (
          <Sparkline className="stat-trend" data={trend} />
        ) : null}
      </div>
    </article>
  );
}
