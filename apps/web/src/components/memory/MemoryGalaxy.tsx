"use client";

import {
  BriefcaseBusiness,
  CalendarClock,
  Languages,
  MessageSquareText,
  SlidersHorizontal,
  Sparkles,
  TrendingUp,
  UserRound,
} from "lucide-react";
import { motion } from "motion/react";

import type { Memory, MemoryType } from "@/lib/api";

const galaxyNodes = [
  { type: "profile", label: "个人", hint: "Profile", x: 400, y: 62, icon: UserRound },
  {
    type: "preference",
    label: "偏好",
    hint: "Preference",
    x: 620,
    y: 110,
    icon: SlidersHorizontal,
  },
  { type: "skill", label: "技能", hint: "Skills", x: 710, y: 250, icon: Sparkles },
  {
    type: "career",
    label: "职业",
    hint: "Career",
    x: 610,
    y: 390,
    icon: BriefcaseBusiness,
  },
  {
    type: "investment",
    label: "投资",
    hint: "Investment",
    x: 400,
    y: 442,
    icon: TrendingUp,
  },
  {
    type: "episodic",
    label: "经历",
    hint: "Episodes",
    x: 190,
    y: 390,
    icon: CalendarClock,
  },
  {
    type: "conversation_summary",
    label: "对话",
    hint: "Conversation",
    x: 90,
    y: 250,
    icon: MessageSquareText,
  },
  {
    type: "english",
    label: "英语",
    hint: "English",
    x: 180,
    y: 110,
    icon: Languages,
  },
] as const satisfies Array<{
  type: MemoryType;
  label: string;
  hint: string;
  x: number;
  y: number;
  icon: typeof UserRound;
}>;

export function MemoryGalaxy({
  memories,
  activeType,
  loading = false,
  onSelectType,
}: {
  memories: Memory[];
  activeType: MemoryType | "all";
  loading?: boolean;
  onSelectType: (type: MemoryType | "all") => void;
}) {
  const activeCount = memories.filter((memory) => memory.status === "active").length;

  return (
    <section className="memory-galaxy" aria-label="长期记忆星系">
      <header className="memory-galaxy-heading">
        <div>
          <span>MEMORY GALAXY</span>
          <h2>你的认知地图</h2>
        </div>
        <p>选择一个轨道，查看 Jarvis 在该领域真正记住了什么。</p>
      </header>

      <div className="memory-galaxy-stage">
        <svg aria-hidden="true" className="memory-galaxy-map" viewBox="0 0 800 500">
          <defs>
            <linearGradient id="memory-link" x1="0" x2="1">
              <stop offset="0" stopColor="#22d3ee" stopOpacity="0.06" />
              <stop offset="0.5" stopColor="#818cf8" stopOpacity="0.38" />
              <stop offset="1" stopColor="#22d3ee" stopOpacity="0.06" />
            </linearGradient>
          </defs>
          <ellipse cx="400" cy="250" fill="none" rx="305" ry="194" />
          <ellipse cx="400" cy="250" fill="none" rx="218" ry="136" />
          {galaxyNodes.map((node) => (
            <line
              key={node.type}
              x1="400"
              x2={node.x}
              y1="250"
              y2={node.y}
            />
          ))}
        </svg>

        <motion.button
          aria-label="显示全部长期记忆"
          aria-pressed={activeType === "all"}
          className={`memory-galaxy-core ${activeType === "all" ? "is-active" : ""}`}
          onClick={() => onSelectType("all")}
          type="button"
          whileHover={{ scale: 1.035 }}
          whileTap={{ scale: 0.98 }}
        >
          <motion.i
            animate={{ opacity: [0.4, 0.9, 0.4], scale: [0.94, 1.04, 0.94] }}
            aria-hidden="true"
            transition={{ duration: 4, ease: "easeInOut", repeat: Infinity }}
          />
          <span>{loading ? "SYNCING" : "PERSONAL CORE"}</span>
          <strong>YOU</strong>
          <small>{activeCount} 条记忆正在参与回答</small>
        </motion.button>

        {galaxyNodes.map((node, index) => {
          const Icon = node.icon;
          const count = memories.filter(
            (memory) => memory.memory_type === node.type,
          ).length;
          const selected = activeType === node.type;
          return (
            <motion.button
              animate={{ opacity: 1, scale: 1 }}
              aria-pressed={selected}
              className={`memory-galaxy-node ${selected ? "is-active" : ""}`}
              initial={{ opacity: 0, scale: 0.88 }}
              key={node.type}
              onClick={() => onSelectType(node.type)}
              style={{ left: `${node.x / 8}%`, top: `${node.y / 5}%` }}
              transition={{
                damping: 24,
                delay: 0.035 * index,
                stiffness: 240,
                type: "spring",
              }}
              type="button"
              whileHover={{ scale: 1.045, y: -2 }}
              whileTap={{ scale: 0.98 }}
            >
              <i aria-hidden="true">
                <Icon strokeWidth={1.45} />
              </i>
              <span>
                <strong>{node.label}</strong>
                <small>
                  {node.hint} · {count}
                </small>
              </span>
            </motion.button>
          );
        })}
      </div>

      <footer className="memory-galaxy-legend">
        <span><i className="memory-legend-active" />正在使用</span>
        <span><i className="memory-legend-pending" />等待确认</span>
        <span><i className="memory-legend-local" />本地优先</span>
      </footer>
    </section>
  );
}
