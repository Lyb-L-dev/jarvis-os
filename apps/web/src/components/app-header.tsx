"use client";

import { Bell, PanelLeftClose, PanelLeftOpen } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { StatusPulse } from "@/components/motion/StatusPulse";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { getHeaderStatus, type HeaderStatusResponse } from "@/lib/api";
import { providerDisplayNames } from "@/lib/utils";

type CoreState = "checking" | "ready" | "degraded" | "offline";

const CORE_META: Record<CoreState, { label: string }> = {
  checking: { label: "检测中" },
  ready: { label: "在线" },
  degraded: { label: "降级" },
  offline: { label: "离线" },
};

const PROVIDER_LABEL: Record<string, string> = providerDisplayNames;

type AppHeaderProps = {
  onToggleSidebar: () => void;
  showSidebarToggle: boolean;
  sidebarHidden: boolean;
};

export function AppHeader({
  onToggleSidebar,
  showSidebarToggle,
  sidebarHidden,
}: AppHeaderProps) {
  const [status, setStatus] = useState<HeaderStatusResponse | null>(null);
  const [coreState, setCoreState] = useState<CoreState>("checking");
  const [clock, setClock] = useState<Date | null>(null);

  useEffect(() => {
    let disposed = false;

    const refresh = async () => {
      try {
        const data = await getHeaderStatus();
        if (disposed) return;
        setStatus(data);
        setCoreState(data.core);
      } catch {
        if (!disposed) setCoreState("offline");
      }
    };

    void refresh();
    const statusTimer = window.setInterval(() => void refresh(), 15_000);
    const tickClock = () => setClock(new Date());
    tickClock();
    const clockTimer = window.setInterval(tickClock, 30_000);

    return () => {
      disposed = true;
      window.clearInterval(statusTimer);
      window.clearInterval(clockTimer);
    };
  }, []);

  const providerLabel =
    PROVIDER_LABEL[status?.model.provider ?? "mimo"] ??
    status?.model.provider ??
    "MiMo";

  return (
    <header className={`app-header header-core-${coreState}`}>
      <div className="app-header-left">
        {showSidebarToggle ? (
          <Tooltip>
            <TooltipTrigger asChild>
              <button
                aria-controls="jarvis-sidebar"
                aria-expanded={!sidebarHidden}
                aria-label={sidebarHidden ? "显示侧边栏" : "隐藏侧边栏"}
                className="sidebar-toggle"
                onClick={onToggleSidebar}
                type="button"
              >
                {sidebarHidden ? (
                  <PanelLeftOpen aria-hidden="true" />
                ) : (
                  <PanelLeftClose aria-hidden="true" />
                )}
              </button>
            </TooltipTrigger>
            <TooltipContent side="bottom">
              {sidebarHidden ? "显示侧边栏" : "隐藏侧边栏"}
            </TooltipContent>
          </Tooltip>
        ) : null}
        <span className="app-header-core">
          <StatusPulse
            size={8}
            tone={
              coreState === "ready"
                ? "success"
                : coreState === "degraded"
                  ? "warning"
                  : "danger"
            }
          />
          {CORE_META[coreState].label}
        </span>
        <span className="app-header-divider" aria-hidden="true" />
        <span className="app-header-model">
          模型 <b>{providerLabel}</b>
          {status ? <code>{status.model.mode}</code> : null}
        </span>
        {status?.quiet_hours?.enabled ? (
          <span
            className={`app-header-quiet${
              status.quiet_hours.active ? " app-header-quiet-active" : ""
            }`}
          >
            静默 {status.quiet_hours.start}–{status.quiet_hours.end}
          </span>
        ) : null}
      </div>

      <div className="app-header-right">
        {status && status.unread_notifications > 0 ? (
          <Link
            aria-label={`${status.unread_notifications} 条未读提醒`}
            className="app-header-bell"
            href="/notifications"
          >
            <Bell size={14} />
            <b>{status.unread_notifications}</b>
          </Link>
        ) : null}
        <span className="app-header-clock">
          {clock
            ? clock.toLocaleTimeString("zh-CN", {
                hour: "2-digit",
                minute: "2-digit",
              })
            : ""}
        </span>
      </div>
    </header>
  );
}
