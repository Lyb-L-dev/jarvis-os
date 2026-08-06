"use client";

import { useEffect, useState } from "react";

import {
  getModelStatus,
  getReadiness,
  type ModelProviderStatus,
  type ReadinessResponse,
} from "@/lib/api";

type ViewState =
  | { kind: "loading" }
  | {
      kind: "ready";
      readiness: ReadinessResponse;
      providers: ModelProviderStatus[];
    }
  | { kind: "offline"; message: string };

export function SystemStatus() {
  const [state, setState] = useState<ViewState>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;

    Promise.all([getReadiness(), getModelStatus()])
      .then(([readiness, models]) => {
        if (cancelled) return;
        setState({
          kind: "ready",
          readiness,
          providers: models.providers,
        });
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setState({
            kind: "offline",
            message: error instanceof Error ? error.message : "连接失败",
          });
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  if (state.kind === "loading") {
    return (
      <div className="system-status-line">
        <span className="status-dot status-dot-wait" />
        正在连接 Jarvis Core…
      </div>
    );
  }

  if (state.kind === "offline") {
    return (
      <div className="system-status-line system-status-offline">
        <span className="status-dot status-dot-offline" />
        后端尚未启动
        <span className="status-detail">{state.message}</span>
      </div>
    );
  }

  const configuredCount = state.providers.filter(
    (provider) => provider.configured,
  ).length;
  const tokenPlanRiskAcknowledged = state.providers.some(
    (provider) =>
      provider.provider === "mimo" &&
      provider.configuration_issue ===
        "token_plan_custom_backend_usage_risk_acknowledged",
  );

  return (
    <div className="system-status-line">
      <span
        className={`status-dot ${
          state.readiness.status === "ready"
            ? "status-dot-ready"
            : "status-dot-wait"
        }`}
      />
      Jarvis Core {state.readiness.status === "ready" ? "已就绪" : "部分就绪"}
      <span className="status-detail">
        {configuredCount}/{state.providers.length} 个模型已配置
        {tokenPlanRiskAcknowledged ? " · MiMo Token Plan 已启用" : ""}
      </span>
    </div>
  );
}
