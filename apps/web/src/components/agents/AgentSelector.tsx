"use client";

import { Bot, Languages, Radar, Route } from "lucide-react";
import { motion } from "motion/react";
import Link from "next/link";

const agents = [
  {
    id: "general",
    label: "General Jarvis",
    description: "综合协作",
    href: "/chat",
    icon: Bot,
  },
  {
    id: "growth",
    label: "Growth Manager",
    description: "目标与行动",
    href: "/growth",
    icon: Route,
  },
  {
    id: "english",
    label: "English Coach",
    description: "语言训练",
    href: "/english",
    icon: Languages,
  },
  {
    id: "research",
    label: "Research Agent",
    description: "情报研究",
    href: "/intelligence",
    icon: Radar,
  },
] as const;

export type AgentId = (typeof agents)[number]["id"];

export function AgentSelector({
  activeAgent = "general",
  modelHint,
  routeReason,
  runtime,
}: {
  activeAgent?: AgentId;
  modelHint?: string;
  routeReason?: string;
  runtime?: "direct" | "workflow";
}) {
  const active = agents.find((agent) => agent.id === activeAgent) ?? agents[0];

  return (
    <div className="agent-selector">
      <div className="agent-selector-label">
        <span>{runtime ? `ROUTED · ${runtime.toUpperCase()}` : "ACTIVE AGENT"}</span>
        <strong>{active.label}</strong>
        {routeReason ? (
          <small title={`${routeReason}${modelHint ? ` ${modelHint}` : ""}`}>
            {routeReason} {modelHint}
          </small>
        ) : null}
      </div>
      <div className="agent-selector-options" aria-label="切换专用 Agent">
        {agents.map((agent) => {
          const Icon = agent.icon;
          const selected = agent.id === activeAgent;
          return (
            <Link
              aria-current={selected ? "page" : undefined}
              href={agent.href}
              key={agent.id}
              title={`${agent.label} · ${agent.description}`}
            >
              {selected ? (
                <motion.span
                  className="agent-selector-active"
                  layoutId="active-agent"
                  transition={{ damping: 30, stiffness: 330, type: "spring" }}
                />
              ) : null}
              <Icon aria-hidden="true" strokeWidth={1.55} />
              <span>{agent.label}</span>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
