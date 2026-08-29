"use client";

import { snoozeReminder } from "@/lib/api";
import { recordDesktopReliability } from "@/lib/desktop-reliability";
import { useEffect, useState } from "react";

type DesktopActivation = {
  kind?: "notification" | "notification_snooze" | string;
  id?: string;
  minutes?: number;
  actionId?: string;
};

type ActivationWindow = typeof window & {
  __JARVIS_DESKTOP_ACTIVATION__?: DesktopActivation;
};

export function DesktopActivationBridge() {
  const [feedback, setFeedback] = useState<string | null>(null);

  useEffect(() => {
    let disposed = false;
    const consume = async (detail?: DesktopActivation | null) => {
      if (!detail?.id) return;
      delete (window as ActivationWindow).__JARVIS_DESKTOP_ACTIVATION__;
      if (detail.kind === "notification") {
        window.location.assign(`/notifications?focus=${encodeURIComponent(detail.id)}`);
        return;
      }
      if (
        detail.kind === "notification_snooze" &&
        detail.minutes === 10 &&
        detail.actionId
      ) {
        try {
          await snoozeReminder(detail.id, 10, detail.actionId);
          recordDesktopReliability({ kind: "notification_snooze", outcome: "succeeded" });
          if (!disposed) setFeedback("提醒已延后 10 分钟。重复点击不会重复延后。");
        } catch (error) {
          recordDesktopReliability({ kind: "notification_snooze", outcome: "failed" });
          if (!disposed) {
            setFeedback(error instanceof Error ? error.message : "无法延后提醒，请打开通知中心重试。");
          }
        }
      }
    };
    const target = window as ActivationWindow;
    void consume(target.__JARVIS_DESKTOP_ACTIVATION__);
    const listener = (event: Event) => {
      void consume((event as CustomEvent<DesktopActivation>).detail);
    };
    window.addEventListener("jarvis:desktop-activation", listener);
    const closeHintListener = () => {
      setFeedback("关闭主窗口后，Jarvis 默认继续在系统托盘运行。你可以从托盘重新打开，或在设置中改为直接完全退出。");
    };
    window.addEventListener("jarvis:close-hint", closeHintListener);
    const trayFeedbackListener = (event: Event) => {
      const detail = (event as CustomEvent<unknown>).detail;
      if (typeof detail === "string") setFeedback(detail);
    };
    window.addEventListener("jarvis:tray-feedback", trayFeedbackListener);
    return () => {
      disposed = true;
      window.removeEventListener("jarvis:desktop-activation", listener);
      window.removeEventListener("jarvis:close-hint", closeHintListener);
      window.removeEventListener("jarvis:tray-feedback", trayFeedbackListener);
    };
  }, []);

  return feedback ? (
    <div className="desktop-activation-feedback" role="status" aria-live="polite">
      <span>{feedback}</span>
      <button aria-label="关闭桌面通知反馈" onClick={() => setFeedback(null)} type="button">
        关闭
      </button>
    </div>
  ) : null;
}
