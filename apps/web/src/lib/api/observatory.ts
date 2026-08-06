/**
 * Observatory API client: agent runs, tool executions, approvals, errors, metrics.
 */

import { API_BASE_URL, request } from "./client";

export type ObservatoryMetricsPoint = {
  date: string;
  runs: number;
  succeeded: number;
  failed: number;
};

export type ObservatoryErrorCount = {
  code: string;
  count: number;
};

export type ObservatoryMetricsResponse = {
  total_runs: number;
  success_rate: number;
  avg_duration_ms?: number | null;
  by_day: ObservatoryMetricsPoint[];
  errors: ObservatoryErrorCount[];
};

export async function getObservatoryMetrics(
  signal?: AbortSignal,
): Promise<ObservatoryMetricsResponse> {
  return request<ObservatoryMetricsResponse>(
    `${API_BASE_URL}/observatory/metrics`,
    {
      cache: "no-store",
      signal,
      errorMessage: (status) => `Observatory metrics failed with ${status}`,
    },
  );
}

export type ObservatoryAgentCount = {
  agent_id: string;
  total: number;
  active: number;
  paused: number;
  failed: number;
};

export type ObservatoryOverview = {
  generated_at: string;
  privacy_note: string;
  flags: Record<string, boolean>;
  runs: {
    total: number;
    active: number;
    paused: number;
    completed: number;
    failed: number;
    cancelled: number;
    steps_total: number;
    steps_failed: number;
  };
  tools: {
    total: number;
    succeeded: number;
    failed: number;
    pending_approval: number;
    expired: number;
  };
  approvals: {
    pending: number;
    approved: number;
    rejected: number;
  };
  errors_recent: number;
  agents: ObservatoryAgentCount[];
};

export type ObservatoryRunSummary = {
  id: string;
  request_type: string;
  agent_id: string;
  agent_version: string;
  runtime: string;
  workflow_version: string;
  status: string;
  current_step?: string | null;
  pending_kind?: string | null;
  pending_label?: string | null;
  model_preference: string;
  selected_provider?: string | null;
  provider_used?: string | null;
  model_used?: string | null;
  paid_model_confirmed: boolean;
  total_tokens?: number | null;
  error_code?: string | null;
  created_at: string;
  updated_at: string;
  completed_at?: string | null;
  duration_ms?: number | null;
  steps_count: number;
  tool_execution_count: number;
};

export type ObservatoryRunStep = {
  sequence: number;
  step_key: string;
  kind: string;
  status: string;
  input_refs: Array<Record<string, string>>;
  output_refs: Array<Record<string, string>>;
  retry_count: number;
  error_code?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  duration_ms?: number | null;
};

export type ObservatoryRunApproval = {
  kind: string;
  status: string;
  title: string;
  reason_code: string;
  provider?: string | null;
  created_at: string;
  decided_at?: string | null;
};

export type ObservatoryRunTool = {
  id: string;
  tool_id: string;
  tool_version: string;
  action_kind: string;
  risk_level: string;
  status: string;
  started_at?: string | null;
  completed_at?: string | null;
  error_code?: string | null;
};

export type ObservatoryRunDetail = ObservatoryRunSummary & {
  steps: ObservatoryRunStep[];
  approvals: ObservatoryRunApproval[];
  tool_executions: ObservatoryRunTool[];
};

export type ObservatoryToolExecution = {
  id: string;
  agent_id: string;
  agent_run_id?: string | null;
  tool_id: string;
  tool_version: string;
  action_kind: string;
  risk_level: string;
  status: string;
  external_side_effect: boolean;
  retry_count: number;
  approval_status?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  error_code?: string | null;
  error_message?: string | null;
};

export type ObservatoryApproval = {
  id: string;
  source: "tool" | "model";
  kind: string;
  status: string;
  title: string;
  reason_code: string;
  risk_level: string;
  agent_id: string;
  tool_id?: string | null;
  provider?: string | null;
  created_at: string;
  decided_at?: string | null;
  expires_at?: string | null;
};

export type ObservatoryError = {
  id: string;
  source: "agent_run" | "tool_execution";
  agent_id: string;
  tool_id?: string | null;
  request_type?: string | null;
  status: string;
  error_code?: string | null;
  error_message?: string | null;
  occurred_at: string;
};

export async function getObservatoryOverview(
  signal?: AbortSignal,
): Promise<ObservatoryOverview> {
  return request<ObservatoryOverview>(
    `${API_BASE_URL}/observatory/overview`,
    {
      cache: "no-store",
      signal,
      action: "读取运行观测台",
    },
  );
}

export async function listObservatoryRuns(
  options: {
    status?: string;
    agentId?: string;
    limit?: number;
    signal?: AbortSignal;
  } = {},
): Promise<ObservatoryRunSummary[]> {
  const url = new URL(`${API_BASE_URL}/observatory/runs`);
  if (options.status) url.searchParams.set("status", options.status);
  if (options.agentId) url.searchParams.set("agent_id", options.agentId);
  url.searchParams.set("limit", String(options.limit ?? 50));
  return request<ObservatoryRunSummary[]>(
    url,
    {
      cache: "no-store",
      signal: options.signal,
      action: "读取 Agent 运行记录",
    },
  );
}

export async function getObservatoryRun(
  runId: string,
  signal?: AbortSignal,
): Promise<ObservatoryRunDetail> {
  return request<ObservatoryRunDetail>(
    `${API_BASE_URL}/observatory/runs/${runId}`,
    {
      cache: "no-store",
      signal,
      action: "读取运行详情",
    },
  );
}

export async function listObservatoryToolExecutions(
  options: {
    status?: string;
    toolId?: string;
    limit?: number;
    signal?: AbortSignal;
  } = {},
): Promise<ObservatoryToolExecution[]> {
  const url = new URL(`${API_BASE_URL}/observatory/tool-executions`);
  if (options.status) url.searchParams.set("status", options.status);
  if (options.toolId) url.searchParams.set("tool_id", options.toolId);
  url.searchParams.set("limit", String(options.limit ?? 50));
  return request<ObservatoryToolExecution[]>(
    url,
    {
      cache: "no-store",
      signal: options.signal,
      action: "读取工具执行记录",
    },
  );
}

export async function listObservatoryApprovals(
  options: {
    status?: string;
    limit?: number;
    signal?: AbortSignal;
  } = {},
): Promise<ObservatoryApproval[]> {
  const url = new URL(`${API_BASE_URL}/observatory/approvals`);
  if (options.status) url.searchParams.set("status", options.status);
  url.searchParams.set("limit", String(options.limit ?? 100));
  return request<ObservatoryApproval[]>(
    url,
    {
      cache: "no-store",
      signal: options.signal,
      action: "读取审批观测记录",
    },
  );
}

export async function listObservatoryErrors(
  options: {
    limit?: number;
    signal?: AbortSignal;
  } = {},
): Promise<ObservatoryError[]> {
  const url = new URL(`${API_BASE_URL}/observatory/errors`);
  url.searchParams.set("limit", String(options.limit ?? 50));
  return request<ObservatoryError[]>(
    url,
    {
      cache: "no-store",
      signal: options.signal,
      action: "读取运行错误记录",
    },
  );
}
