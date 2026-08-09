/** V3 on-demand orchestrator pilot and Draft Review client. */

import { API_BASE_URL, request } from "./client";
import type { ApprovalCenterItem } from "./tools";

export type OrchestrationPlan = {
  id: string;
  goal_kind: string;
  goal_ref: string;
  context_refs: Array<{ kind: string; ref_id: string }>;
  title: string;
  summary: string;
  complexity: number;
  requires_pause_resume: boolean;
  status: "draft" | "confirmed" | "rejected";
};

export async function createResearchGrowthPreview(
  researchReportId: string,
): Promise<OrchestrationPlan> {
  return request<OrchestrationPlan>(
    `${API_BASE_URL}/orchestrator/previews`,
    {
      method: "POST",
      body: {
        complexity: 8,
        max_tasks: 5,
        requires_pause_resume: true,
        research_report_id: researchReportId,
      },
      action: "Creating an orchestration plan preview",
    },
  );
}

export async function decideDraftReview(
  item: ApprovalCenterItem,
  decision: "approve" | "reject",
): Promise<unknown> {
  const draftRef = item.preview.draft_ref;
  const draftKind = item.preview.draft_kind;
  if (typeof draftRef !== "string" || typeof draftKind !== "string") {
    throw new Error("Draft Review reference is missing");
  }
  if (draftKind === "orchestration_plan") {
    const plan = await request<OrchestrationPlan>(
      `${API_BASE_URL}/orchestrator/previews/${draftRef}/decision`,
      {
        method: "POST",
        body: { action: decision },
        action: `${decision} orchestration plan`,
      },
    );
    if (decision === "reject") return plan;
    return request(
      `${API_BASE_URL}/orchestrator/runs`,
      {
        method: "POST",
        body: { context_refs: plan.context_refs, goal_ref: plan.id },
        action: "Starting the confirmed orchestration plan",
      },
    );
  }
  if (draftKind === "growth_task_draft" && item.run_id) {
    return request(
      `${API_BASE_URL}/orchestrator/runs/${item.run_id}/resume`,
      {
        method: "POST",
        body: { action: decision, decision_ref: item.id },
        action: `${decision} growth task draft`,
      },
    );
  }
  throw new Error("This Draft Review cannot be decided from the Approval Center");
}
