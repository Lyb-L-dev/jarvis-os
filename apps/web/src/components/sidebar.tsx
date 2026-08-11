"use client";

import {
  Activity,
  Bell,
  BriefcaseBusiness,
  BookOpen,
  Brain,
  ChartNoAxesCombined,
  CircleDollarSign,
  Computer,
  Filter,
  FlaskConical,
  Languages,
  LayoutDashboard,
  MessageSquareText,
  PartyPopper,
  Radar,
  ScanSearch,
  Route,
  Settings,
  ShieldCheck,
  Smile,
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
    label: "Command Center",
    href: "/",
    icon: LayoutDashboard,
    group: "CORE",
  },
  {
    label: "Conversation",
    href: "/chat",
    icon: MessageSquareText,
    group: "CORE",
  },
  {
    label: "English Coach",
    href: "/english",
    icon: Languages,
    group: "SPECIALISTS",
  },
  {
    label: "Information",
    href: "/intelligence",
    icon: Radar,
    group: "SPECIALISTS",
  },
  {
    label: "Market Monitor",
    href: "/monitoring",
    icon: ScanSearch,
    group: "SPECIALISTS",
  },
  { label: "Growth", href: "/growth", icon: Route, group: "SPECIALISTS" },
  {
    label: "Career Radar",
    href: "/career",
    icon: BriefcaseBusiness,
    group: "SPECIALISTS",
  },
  { label: "Memory", href: "/memory", icon: Brain, group: "SPECIALISTS" },
  {
    label: "Observatory",
    href: "/observatory",
    icon: Activity,
    group: "SYSTEMS",
  },
  {
    label: "Cost Center",
    href: "/cost",
    icon: CircleDollarSign,
    group: "SYSTEMS",
  },
  {
    label: "Context",
    href: "/context",
    icon: Filter,
    group: "SYSTEMS",
  },
  {
    label: "Personality",
    href: "/personality",
    icon: Smile,
    group: "SYSTEMS",
  },
  {
    label: "Proactive",
    href: "/proactive",
    icon: PartyPopper,
    group: "SYSTEMS",
  },
  {
    label: "Computer Use",
    href: "/computer",
    icon: Computer,
    group: "SYSTEMS",
  },
];

const utilityNavigation = [
  { label: "审批", href: "/approvals", icon: ShieldCheck },
  { label: "投资", href: "/investment", icon: ChartNoAxesCombined },
  { label: "知识库", href: "/knowledge", icon: BookOpen },
  { label: "提醒", href: "/notifications", icon: Bell },
  { label: "评测", href: "/evaluation", icon: FlaskConical },
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
          <span>SYSTEMS</span>
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
