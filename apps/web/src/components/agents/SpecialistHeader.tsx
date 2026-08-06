"use client";

import type { ReactNode } from "react";
import { motion } from "motion/react";

import { AgentSelector, type AgentId } from "@/components/agents/AgentSelector";

type SpecialistHeaderProps = {
  activeAgent: AgentId;
  eyebrow: string;
  title: string;
  accent: string;
  description: string;
  status?: string;
  actions?: ReactNode;
};

export function SpecialistHeader({
  activeAgent,
  eyebrow,
  title,
  accent,
  description,
  status = "ONLINE",
  actions,
}: SpecialistHeaderProps) {
  return (
    <motion.header
      animate={{ opacity: 1, y: 0 }}
      className={`specialist-header specialist-header--${activeAgent}`}
      initial={{ opacity: 0, y: -8 }}
      transition={{ damping: 28, stiffness: 260, type: "spring" }}
    >
      <div className="specialist-title">
        <div className="specialist-eyebrow">
          <i aria-hidden="true" />
          <span>{eyebrow}</span>
        </div>
        <h1>
          {title}
          <span>{accent}</span>
        </h1>
        <p>{description}</p>
      </div>

      <AgentSelector activeAgent={activeAgent} />

      <div className="specialist-header-tools">
        <div className="specialist-live">
          <motion.i
            animate={{ opacity: [0.55, 1, 0.55], scale: [0.86, 1, 0.86] }}
            aria-hidden="true"
            transition={{ duration: 2.8, ease: "easeInOut", repeat: Infinity }}
          />
          <span>{status}</span>
        </div>
        {actions}
      </div>
    </motion.header>
  );
}
