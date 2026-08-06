import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export type BadgeTone =
  | "neutral"
  | "energy"
  | "success"
  | "warning"
  | "danger"
  | "violet"
  | "blue";

const TONE_CLASS: Record<BadgeTone, string> = {
  neutral: "badge-neutral",
  energy: "badge-energy",
  success: "badge-success",
  warning: "badge-warning",
  danger: "badge-danger",
  violet: "badge-violet",
  blue: "badge-blue",
};

type BadgeProps = {
  children: ReactNode;
  tone?: BadgeTone;
  className?: string;
};

/** 状态/类型标签。 */
export function Badge({ children, tone = "neutral", className }: BadgeProps) {
  return <span className={cn("badge", TONE_CLASS[tone], className)}>{children}</span>;
}
