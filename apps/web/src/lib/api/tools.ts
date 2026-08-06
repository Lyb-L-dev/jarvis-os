/**
 * Tools API client: tool gateway, approvals, n8n provider.
 */

import { API_BASE_URL, request } from "./client";

export type ToolCatalogItem = {
  tool_id: string;
  version: string;
  display_name: string;
  description: string;
  action_kind: string;
  risk_level: "R0" | "R1" | "R2" | string;
  requires_approval: boolean;
  input_schema: Record<string, unknown>;
  output_schema: Record<string, unknown>;
  scope: string;
  data_sensitivity: string;
  external_side_effect: boolean;
  idempotency_strategy: string;
  timeout_seconds: number;
  max_retries: number;
  allowed_agents: string[];
  credential_scope?: string | null;
  audit_fields: string[];
  failure_policy: string;
  available: boolean;
  unavailable_reason?: string | null;
};

export type ToolApproval = {
  id: string;
  kind: string;
  status: string;
  title: string;
  reason_code: string;
  risk_level: string;
  preview: Record<string, unknown>;
  proposed_parameters: Record<string, unknown>;
  parameters_hash: string;
  decision_note?: string | null;
  edited_at?: string | null;
  expires_at: string;
  decided_at?: string | null;
  consumed_at?: string | null;
  created_at: string;
  updated_at: string;
};

export type ToolExecutionEvent = {
  id: string;
  event_type: string;
  actor: string;
  from_status?: string | null;
  to_status?: string | null;
  details: Record<string, unknown>;
  created_at: string;
};

export type ToolExecution = {
  id: string;
  agent_run_id?: string | null;
  agent_id: string;
  tool_id: string;
  tool_version: string;
  action_kind: string;
  risk_level: string;
  status: string;
  idempotency_key: string;
  parameters_hash: string;
  input_parameters: Record<string, unknown>;
  output_summary?: Record<string, unknown> | null;
  side_effect_proof?: Record<string, unknown> | null;
  external_side_effect: boolean;
  retry_count: number;
  started_at?: string | null;
  completed_at?: string | null;
  error_code?: string | null;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
  approval?: ToolApproval | null;
  events: ToolExecutionEvent[];
};

export type ApprovalCenterItem = {
  id: string;
  source: "tool" | "model";
  status: string;
  title: string;
  reason_code: string;
  risk_level: string;
  agent_id: string;
  tool_id?: string | null;
  provider?: string | null;
  preview: Record<string, unknown>;
  proposed_parameters: Record<string, unknown>;
  execution_id?: string | null;
  run_id?: string | null;
  expires_at?: string | null;
  decided_at?: string | null;
  consumed_at?: string | null;
  created_at: string;
  updated_at: string;
};

export type ApprovalCenterResponse = {
  enabled: boolean;
  tool_gateway_enabled: boolean;
  pending_count: number;
  approved_count: number;
  history_count: number;
  permanent_blocks: string[];
  items: ApprovalCenterItem[];
};

export type N8nProviderStatus = {
  enabled: boolean;
  configured: boolean;
  status: "ready" | "offline" | "disabled" | string;
  isolated: boolean;
  signed_webhooks: boolean;
  redis_used: boolean;
  editor_exposed: boolean;
  real_accounts_connected: boolean;
  external_writes_enabled: boolean;
  workflows: string[];
  detail?: string | null;
};

export async function getN8nProviderStatus(
  signal?: AbortSignal,
): Promise<N8nProviderStatus> {
  return request<N8nProviderStatus>(
    `${API_BASE_URL}/providers/n8n/status`,
    {
      cache: "no-store",
      signal,
      action: "Loading n8n provider status",
    },
  );
}

export async function listToolCatalog(
  signal?: AbortSignal,
): Promise<ToolCatalogItem[]> {
  return request<ToolCatalogItem[]>(
    `${API_BASE_URL}/tool-gateway/catalog`,
    {
      cache: "no-store",
      signal,
      action: "Loading Tool Gateway catalog",
    },
  );
}

export async function getApprovalCenter(
  signal?: AbortSignal,
): Promise<ApprovalCenterResponse> {
  return request<ApprovalCenterResponse>(
    `${API_BASE_URL}/approval-center`,
    {
      cache: "no-store",
      signal,
      action: "Loading Approval Center",
    },
  );
}

export async function createToolExecution(input: {
  agent_id: string;
  agent_run_id?: string | null;
  tool_id: string;
  idempotency_key: string;
  parameters: Record<string, unknown>;
}): Promise<ToolExecution> {
  return request<ToolExecution>(
    `${API_BASE_URL}/tool-gateway/executions`,
    {
      method: "POST",
      body: input,
      action: "Creating a tool proposal",
    },
  );
}

export async function updateToolProposal(
  approvalId: string,
  parameters: Record<string, unknown>,
): Promise<ToolExecution> {
  return request<ToolExecution>(
    `${API_BASE_URL}/approval-center/${approvalId}/proposal`,
    {
      method: "PATCH",
      body: { parameters },
      action: "Updating the approval preview",
    },
  );
}

export async function decideToolApproval(
  approvalId: string,
  decision: "approve" | "reject",
  note?: string,
): Promise<ToolExecution> {
  return request<ToolExecution>(
    `${API_BASE_URL}/approval-center/${approvalId}/${decision}`,
    {
      method: "POST",
      body: { note: note || null },
      action: `${decision} tool proposal`,
    },
  );
}

export async function executeApprovedTool(
  executionId: string,
): Promise<ToolExecution> {
  return request<ToolExecution>(
    `${API_BASE_URL}/tool-gateway/executions/${executionId}/execute`,
    {
      method: "POST",
      action: "Executing approved tool",
    },
  );
}
