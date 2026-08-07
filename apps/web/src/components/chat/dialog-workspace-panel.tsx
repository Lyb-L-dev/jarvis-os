"use client";

import { useEffect, useRef, useState } from "react";

import {
  getDialogWorkspace,
  isDialogUnavailable,
  subscribeUiEvents,
  type DialogWorkspaceResponse,
} from "@/lib/api";

/**
 * V3-0 dialog workspace information panel.
 *
 * Read-only snapshot of the dialog workspace: active Agent runs, pending
 * R2/R3 approvals (approval itself stays in /approvals — this is preview
 * only), proactive suggestions (actions arrive in V3-3) and today's summary.
 *
 * Degradation: when the backend returns 404 (feature flag off) or is
 * unreachable, the panel renders nothing and the classic chat view keeps
 * working untouched. SSE is only subscribed after the first successful fetch
 * so a disabled backend does not create a reconnecting EventSource.
 */
export function DialogWorkspacePanel() {
  const [dialog, setDialog] = useState<DialogWorkspaceResponse | null>(null);
  const [disabled, setDisabled] = useState(false);
  const lastVersionRef = useRef<number | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    let unsubscribe: (() => void) | null = null;
    let active = true;

    async function refresh(signal: AbortSignal): Promise<void> {
      try {
        const payload = await getDialogWorkspace(signal);
        if (!active) return;
        lastVersionRef.current = payload.data_version;
        setDialog(payload);
      } catch (error) {
        if (active && isDialogUnavailable(error)) {
          setDisabled(true);
        }
      }
    }

    async function bootstrap(): Promise<void> {
      try {
        const payload = await getDialogWorkspace(controller.signal);
        if (!active) return;
        lastVersionRef.current = payload.data_version;
        setDialog(payload);
        unsubscribe = subscribeUiEvents((event) => {
          if (event.type === "snapshot" || event.type === "dialog") {
            // The catch-all UiEvent member widens `data` to unknown; the
            // snapshot/dialog members both carry this exact shape.
            const version = (event.data as { data_version: number })
              .data_version;
            if (version !== lastVersionRef.current) {
              lastVersionRef.current = version;
              void refresh(controller.signal);
            }
          }
        });
      } catch (error) {
        if (active && isDialogUnavailable(error)) {
          setDisabled(true);
        }
      }
    }

    void bootstrap();

    return () => {
      active = false;
      controller.abort();
      unsubscribe?.();
    };
  }, []);

  if (disabled || dialog === null) {
    return null;
  }

  const hasActionableContent =
    dialog.active_runs.length > 0 ||
    dialog.pending_approvals.length > 0 ||
    dialog.proactive_suggestions.length > 0 ||
    dialog.today_summary.tasks_due > 0 ||
    dialog.today_summary.reviews_due > 0 ||
    dialog.today_summary.brief_ready;

  if (!hasActionableContent) {
    return null;
  }

  return (
    <section className="dialog-workspace-panel" aria-label="对话工作台信息">
      <div className="dialog-workspace-cards">
        {dialog.active_runs.length > 0 ? (
          <div className="dialog-card dialog-card-runs">
            <h3>任务执行</h3>
            <ul>
              {dialog.active_runs.map((run) => (
                <li key={run.id}>
                  <span className="dialog-run-agent">{run.agent_name}</span>
                  <span className="dialog-run-status">{run.status}</span>
                  {run.current_step ? (
                    <p className="dialog-run-step">{run.current_step}</p>
                  ) : null}
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        {dialog.pending_approvals.length > 0 ? (
          <div className="dialog-card dialog-card-approvals">
            <h3>待审批</h3>
            <ul>
              {dialog.pending_approvals.map((approval) => (
                <li key={approval.id}>
                  <a href="/approvals">
                    <span className="dialog-approval-title">
                      {approval.title}
                    </span>
                    <span
                      className={`dialog-risk dialog-risk-${approval.risk_level.toLowerCase()}`}
                    >
                      {approval.risk_level}
                    </span>
                  </a>
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        {dialog.proactive_suggestions.length > 0 ? (
          <div className="dialog-card dialog-card-suggestions">
            <h3>建议</h3>
            <ul>
              {dialog.proactive_suggestions.map((suggestion) => (
                <li key={suggestion.id}>
                  <strong>{suggestion.title}</strong>
                  {suggestion.rationale ? (
                    <p className="dialog-suggestion-rationale">
                      {suggestion.rationale}
                    </p>
                  ) : null}
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        <div className="dialog-card dialog-card-today">
          <h3>今日</h3>
          <ul>
            <li>
              任务 <strong>{dialog.today_summary.tasks_due}</strong>
            </li>
            <li>
              复习 <strong>{dialog.today_summary.reviews_due}</strong>
            </li>
            <li>
              {dialog.today_summary.brief_ready
                ? "晨间简报已就绪"
                : "晨间简报未生成"}
            </li>
          </ul>
        </div>
      </div>
    </section>
  );
}
