"use client";

import { motion, useReducedMotion } from "motion/react";

import type { AIState } from "@/components/ai/AIStatus";
import { JarvisMark } from "@/components/jarvis-mark";

export type LogomarkState =
  | "idle"
  | "listening"
  | "thinking"
  | "executing"
  | "alert";

const STATE_ANIMATION: Record<
  LogomarkState,
  { scale: number[]; duration: number }
> = {
  idle: { scale: [1, 1.02, 1], duration: 4.2 },
  listening: { scale: [1, 1.035, 1], duration: 2.4 },
  thinking: { scale: [1, 1.028, 1], duration: 1.6 },
  executing: { scale: [1, 1.045, 1], duration: 1.1 },
  alert: { scale: [1, 1.03, 1], duration: 0.8 },
};

export function aiStateToLogomark(state: AIState): LogomarkState {
  if (state === "listening") return "listening";
  if (state === "thinking") return "thinking";
  if (state === "speaking") return "executing";
  if (state === "error") return "alert";
  return "idle";
}

type JarvisLogomarkProps = {
  state?: LogomarkState;
  className?: string;
};

/** J.A.R.V.I.S 黑白字标的五态呼吸动效（仅缩放，保持扁平黑白）。 */
export function JarvisLogomark({
  state = "idle",
  className,
}: JarvisLogomarkProps) {
  const reducedMotion = useReducedMotion();
  const animation = STATE_ANIMATION[state];

  return (
    <motion.span
      animate={reducedMotion ? undefined : { scale: animation.scale }}
      className={className}
      style={{ display: "inline-block" }}
      transition={{
        duration: animation.duration,
        ease: "easeInOut",
        repeat: Infinity,
      }}
    >
      <JarvisMark className="jarvis-logomark-svg" />
    </motion.span>
  );
}
