"use client";

import {
  Bell,
  BookOpen,
  Brain,
  BriefcaseBusiness,
  GraduationCap,
  Languages,
  MessageSquareText,
  Route,
  Settings,
  ShieldCheck,
} from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { JarvisMark } from "@/components/jarvis-mark";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { getReadiness } from "@/lib/api";

const primaryNavigation = [
  {
    label: "对话工作台",
    href: "/chat",
    icon: MessageSquareText,
    group: "核心",
  },
  {
    label: "学习教练",
    href: "/learning",
    icon: GraduationCap,
    group: "核心",
  },
  { label: "成长中心", href: "/growth", icon: Route, group: "模块" },
  { label: "英语教练", href: "/english", icon: Languages, group: "模块" },
  {
    label: "职业雷达",
    href: "/career",
    icon: BriefcaseBusiness,
    group: "模块",
  },
  { label: "知识库", href: "/knowledge", icon: BookOpen, group: "模块" },
  { label: "记忆", href: "/memory", icon: Brain, group: "模块" },
];

const utilityNavigation = [
  { label: "审批", href: "/approvals", icon: ShieldCheck },
  { label: "提醒", href: "/notifications", icon: Bell },
];

function routeIsActive(pathname: string, href: string) {
  return (
    pathname === href ||
    (href !== "/" && pathname.startsWith(`${href}/`))
  );
}

export function Sidebar({ hidden }: { hidden: boolean }) {
  const pathname = usePathname();
  const reducedMotion = useReducedMotion();
  const [coreStatus, setCoreStatus] = useState<
    "checking" | "online" | "degraded" | "offline"
  >("checking");

  const refreshCoreStatus = useCallback(async () => {
    try {
      const readiness = await getReadiness();
      setCoreStatus(readiness.status === "ready" ? "online" : "degraded");
    } catch {
      setCoreStatus("offline");
    }
  }, []);

  useEffect(() => {
    const initialTimer = window.setTimeout(
      () => void refreshCoreStatus(),
      0,
    );
    const timer = window.setInterval(() => void refreshCoreStatus(), 15_000);
    return () => {
      window.clearTimeout(initialTimer);
      window.clearInterval(timer);
    };
  }, [refreshCoreStatus]);

  if (hidden) {
    return null;
  }

  return (
    <motion.aside
      animate={{ opacity: 1, x: 0 }}
      className="sidebar"
      id="jarvis-sidebar"
      initial={reducedMotion ? false : { opacity: 0, x: -18 }}
      transition={{ damping: 28, stiffness: 240, type: "spring" }}
    >
      <div className="sidebar-ambient" aria-hidden="true" />
      <div className="brand">
        <div className="brand-mark" aria-hidden="true">
          <JarvisMark showText={false} />
        </div>
        <div className="brand-copy">
          <div className="brand-name">JARVIS</div>
          <div className="brand-version">PERSONAL AI OS</div>
        </div>
      </div>

      <div className={`sidebar-life-status status-${coreStatus}`}>
        <span />
        <div>
          <strong>
            {coreStatus === "online"
              ? "Online"
              : coreStatus === "degraded"
                ? "Partial"
                : coreStatus === "offline"
                  ? "Disconnected"
                  : "Connecting"}
          </strong>
          <small>
            {coreStatus === "online"
              ? "Jarvis is awake"
              : coreStatus === "offline"
                ? "Core link interrupted"
                : "Checking core services"}
          </small>
        </div>
      </div>

      <nav className="nav" aria-label="主导航">
        {primaryNavigation.map((item, index) => {
          const active = routeIsActive(pathname, item.href);
          const showGroup =
            index === 0 || primaryNavigation[index - 1].group !== item.group;
          const Icon = item.icon;
          return (
            <div className="nav-entry" key={item.href}>
              {showGroup ? (
                <div className="nav-group-label">
                  <span>{item.group}</span>
                  <i />
                </div>
              ) : null}
              <Link
                className={`nav-item ${active ? "nav-item-active" : ""}`}
                href={item.href}
              >
                {active ? (
                  <motion.span
                    className="nav-active-surface"
                    layoutId="sidebar-active-route"
                    transition={{ damping: 30, stiffness: 330, type: "spring" }}
                  />
                ) : null}
                <Icon
                  aria-hidden="true"
                  className="nav-glyph"
                  strokeWidth={1.6}
                />
                <span className="nav-label">{item.label}</span>
                {active ? <i className="nav-active-beacon" /> : null}
              </Link>
            </div>
          );
        })}
      </nav>

      <div className="sidebar-utility">
        <div className="nav-group-label">
          <span>安全与提醒</span>
          <i />
        </div>
        <div className="sidebar-utility-grid">
          {utilityNavigation.map((item) => {
            const Icon = item.icon;
            const active = routeIsActive(pathname, item.href);
            return (
              <Tooltip key={item.href}>
                <TooltipTrigger asChild>
                  <Link
                    aria-label={item.label}
                    className={active ? "is-active" : ""}
                    href={item.href}
                  >
                    <Icon aria-hidden="true" strokeWidth={1.5} />
                    <span>{item.label}</span>
                  </Link>
                </TooltipTrigger>
                <TooltipContent side="top">{item.label}</TooltipContent>
              </Tooltip>
            );
          })}
        </div>
      </div>

      <div className="sidebar-bottom">
        <Link
          className={`nav-item ${
            routeIsActive(pathname, "/settings") ? "nav-item-active" : ""
          }`}
          href="/settings"
        >
          <Settings aria-hidden="true" className="nav-glyph" strokeWidth={1.6} />
          <span className="nav-label">Settings</span>
        </Link>
        <div className="sidebar-core-status">
          <div className="sidebar-core-orbit">
            <span />
          </div>
          <div>
            <strong>LOCAL FIRST</strong>
            <small>Private by default</small>
          </div>
        </div>
      </div>
    </motion.aside>
  );
}
