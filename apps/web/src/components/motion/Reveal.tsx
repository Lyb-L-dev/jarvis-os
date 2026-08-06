"use client";

import type { ReactNode } from "react";

import { motion, useReducedMotion } from "motion/react";

type RevealProps = {
  children: ReactNode;
  delay?: number;
  className?: string;
};

/** 进入视口淡入 + 上移（500ms，苹果式缓动；遵守"减少动态效果"）。 */
export function Reveal({ children, delay = 0, className }: RevealProps) {
  const reducedMotion = useReducedMotion();

  return (
    <motion.div
      className={className}
      initial={reducedMotion ? false : { opacity: 0, y: 16 }}
      transition={{ duration: 0.5, delay, ease: [0.32, 0.72, 0, 1] }}
      viewport={{ once: true, margin: "-60px" }}
      whileInView={reducedMotion ? undefined : { opacity: 1, y: 0 }}
    >
      {children}
    </motion.div>
  );
}
