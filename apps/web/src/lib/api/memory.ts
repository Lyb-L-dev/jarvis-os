/**
 * Memory API client: memories, memory shadow lab.
 */

import { API_BASE_URL, request, requestVoid } from "./client";

export type MemoryShadowEngine = "rule" | "qwen" | "mem0";

export type MemoryShadowCase = {
  id: string;
  version: number;
  title: string;
  description: string;
  category: string;
  input_preview: string;
  expected_count: number;
};

export type MemoryShadowCandidate = {
  id: string;
  engine: MemoryShadowEngine;
  ordinal: number;
  memory_type: string;
  content: string;
  source_attribution: string;
  confidence?: number | null;
  expected_match: boolean;
  match_score: number;
  blocked_reason?: string | null;
  review_verdict?: "correct" | "partial" | "incorrect" | null;
  reviewed_at?: string | null;
  created_at: string;
};

export type MemoryShadowEngineMetrics = {
  status: "completed" | "failed";
  candidate_count?: number;
  expected_count?: number;
  matched_count?: number;
  precision?: number;
  recall?: number;
  f1?: number;
  sensitive_blocks?: number;
  negative_case_violations?: number;
  latency_ms?: number;
  model?: string;
  local_only: boolean;
  error_type?: string;
  error_message?: string;
};

export type MemoryShadowRun = {
  id: string;
  case_id: string;
  case_version: number;
  source_type: string;
  status: "running" | "completed" | "partial" | "failed";
  engines: MemoryShadowEngine[];
  engine_results: Partial<
    Record<MemoryShadowEngine, MemoryShadowEngineMetrics>
  >;
  aggregate_score?: number | null;
  threshold_passed: boolean;
  completed_at?: string | null;
  created_at: string;
  candidates: MemoryShadowCandidate[];
};

export type MemoryShadowEngineSummary = {
  engine: MemoryShadowEngine;
  evaluated_cases: number;
  total_cases: number;
  average_f1?: number | null;
  safety_violations: number;
};

export type MemoryShadowStatus = {
  enabled: boolean;
  configured: boolean;
  dependency_installed: boolean;
  postgresql_ready: boolean;
  ollama_ready: boolean;
  qwen_model_ready: boolean;
  mem0_model_ready: boolean;
  embedding_model_ready: boolean;
  telemetry_enabled: boolean;
  cloud_models_used: boolean;
  chat_auto_shadow_enabled: boolean;
  authoritative_memory_writes: boolean;
  collection_name: string;
  accuracy_threshold: number;
  advancement_ready: boolean;
  advancement_reason: string;
  engines: MemoryShadowEngineSummary[];
};

export type MemoryType =
  | "profile"
  | "preference"
  | "episodic"
  | "skill"
  | "english"
  | "career"
  | "investment"
  | "conversation_summary";

export type MemoryStatus =
  | "pending"
  | "active"
  | "inactive"
  | "rejected"
  | "superseded"
  | "deleted";

export type Memory = {
  id: string;
  memory_type: MemoryType;
  content: string;
  source_type: string;
  source_conversation_id?: string | null;
  source_message_id?: string | null;
  confidence: number;
  importance: number;
  status: MemoryStatus;
  user_confirmed: boolean;
  cloud_allowed: boolean;
  expires_at?: string | null;
  last_used_at?: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type MemoryStats = {
  pending: number;
  active: number;
  inactive: number;
  total: number;
};

export async function getMemoryShadowStatus(
  signal?: AbortSignal,
): Promise<MemoryShadowStatus> {
  return request<MemoryShadowStatus>(
    `${API_BASE_URL}/memory-shadow/status`,
    {
      cache: "no-store",
      signal,
      action: "Loading memory shadow status",
    },
  );
}

export async function getMemoryShadowCases(
  signal?: AbortSignal,
): Promise<MemoryShadowCase[]> {
  return request<MemoryShadowCase[]>(
    `${API_BASE_URL}/memory-shadow/cases`,
    {
      cache: "no-store",
      signal,
      action: "Loading memory shadow cases",
    },
  );
}

export async function getMemoryShadowRuns(
  limit = 12,
  signal?: AbortSignal,
): Promise<MemoryShadowRun[]> {
  return request<MemoryShadowRun[]>(
    `${API_BASE_URL}/memory-shadow/runs?limit=${encodeURIComponent(limit)}`,
    {
      cache: "no-store",
      signal,
      action: "Loading memory shadow runs",
    },
  );
}

export async function runMemoryShadowCase(
  caseId: string,
): Promise<MemoryShadowRun> {
  return request<MemoryShadowRun>(
    `${API_BASE_URL}/memory-shadow/runs`,
    {
      method: "POST",
      body: { case_id: caseId, engines: ["rule", "qwen", "mem0"], },
      action: "Running memory shadow evaluation",
    },
  );
}

export async function reviewMemoryShadowCandidate(
  candidateId: string,
  verdict: "correct" | "partial" | "incorrect",
): Promise<MemoryShadowCandidate> {
  return request<MemoryShadowCandidate>(
    `${API_BASE_URL}/memory-shadow/candidates/${candidateId}/review`,
    {
      method: "PUT",
      body: { verdict },
      action: "Reviewing memory shadow candidate",
    },
  );
}

export async function listMemories(
  options: {
    query?: string;
    status?: MemoryStatus | "all";
    memoryType?: MemoryType | "all";
    signal?: AbortSignal;
  } = {},
): Promise<Memory[]> {
  const url = new URL(`${API_BASE_URL}/memories`);
  if (options.query?.trim()) {
    url.searchParams.set("q", options.query.trim());
  }
  if (options.status && options.status !== "all") {
    url.searchParams.set("status", options.status);
  }
  if (options.memoryType && options.memoryType !== "all") {
    url.searchParams.set("memory_type", options.memoryType);
  }
  return request<Memory[]>(
    url,
    {
      cache: "no-store",
      signal: options.signal,
      action: "Loading memories",
    },
  );
}

export async function getMemoryStats(
  signal?: AbortSignal,
): Promise<MemoryStats> {
  return request<MemoryStats>(
    `${API_BASE_URL}/memories/stats`,
    {
      cache: "no-store",
      signal,
      action: "Loading memory stats",
    },
  );
}

export async function createMemory(payload: {
  memory_type: MemoryType;
  content: string;
  importance: number;
  cloud_allowed: boolean;
}): Promise<Memory> {
  return request<Memory>(
    `${API_BASE_URL}/memories`,
    {
      method: "POST",
      body: payload,
      action: "Creating memory",
    },
  );
}

export async function updateMemory(
  memoryId: string,
  payload: Partial<{
    memory_type: MemoryType;
    content: string;
    importance: number;
    cloud_allowed: boolean;
    status: "active" | "inactive";
  }>,
): Promise<Memory> {
  return request<Memory>(
    `${API_BASE_URL}/memories/${memoryId}`,
    {
      method: "PATCH",
      body: payload,
      action: "Updating memory",
    },
  );
}

async function memoryAction(
  memoryId: string,
  action: "confirm" | "reject",
): Promise<Memory> {
  return request<Memory>(
    `${API_BASE_URL}/memories/${memoryId}/${action}`,
    {
      method: "POST",
      action: `${action} memory`,
    },
  );
}

export function confirmMemory(memoryId: string): Promise<Memory> {
  return memoryAction(memoryId, "confirm");
}

export function rejectMemory(memoryId: string): Promise<Memory> {
  return memoryAction(memoryId, "reject");
}

export async function deleteMemory(memoryId: string): Promise<void> {
  await requestVoid(
    `${API_BASE_URL}/memories/${memoryId}`,
    {
      method: "DELETE",
      action: "Deleting memory",
    },
  );
}

export async function rememberMessage(
  messageId: string,
): Promise<{ memory: Memory; created: boolean }> {
  return request<{ memory: Memory; created: boolean }>(
    `${API_BASE_URL}/memories/from-message/${messageId}`,
    {
      method: "POST",
      action: "Remembering message",
    },
  );
}
