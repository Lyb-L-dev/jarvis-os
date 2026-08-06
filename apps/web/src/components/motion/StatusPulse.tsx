"use client";

import { motion, useReducedMotion } from "motion/react";

import type { StatusTone } from "@/components/common/StatusDot";
import { cn } from "@/lib/utils";

const TONE_COLOR: Record<StatusTone, string> = {
  neutral: "#71717a",
  idle: "#a1a1aa",
  listen: "#22d3ee",
  think: "#6366f1",
  execute: "#3b82f6",
  alert: "#f6bd68",
  success: "#62e4aa",
  warning: "#f6bd68",
  danger: "#ff667a",
  violet: "#6366f1",
  blue: "#3b82f6",
};

type StatusPulseProps = {
  tone?: StatusTone;
  label?: string;
  size?: number;
  className?: string;
};

/** 核心状态呼吸灯：中心圆点 + 扩散环。 */
export function StatusPulse({
  tone = "neutral",
  label,
  size = 14,
  className,
}: StatusPulseProps) {
  const reducedMotion = useReducedMotion();
  const color = TONE_COLOR[tone];

  return (
    <span
      className={cn("status-pulse", className)}
      style={{ height: size, width: size }}
    >
      {reducedMotion ? null : (
        <motion.span
          animate={{ opacity: [0.5, 0], scale: [1, 2.2] }}
          className="status-pulse-ring"
          style={{ borderColor: color }}
          transition={{ duration: 2, ease: "easeOut", repeat: Infinity }}
        />
      )}
      <span
        aria-label={label}
        className="status-pulse-core"
        role="img"
        style={{ background: color }}
      />
    </span>
  );
}
