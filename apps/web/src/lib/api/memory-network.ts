/**
 * V3-1 memory network API client (frozen contract:
 * docs/JARVIS_OS_V3_PLAN.md §15). Owned by Frontend API Layer.
 */

import { API_BASE_URL, request } from "./client";

export type MemoryCandidateKind = "entity" | "relation" | "event";

export type MemoryEntityDTO = {
  id: string;
  entity_type: string;
  name: string;
  normalized_key: string;
  status: string;
  source_kind: string;
  source_id: string | null;
  importance: number;
  cloud_allowed: boolean;
  created_at: string;
};

export type MemoryRelationDTO = {
  id: string;
  from_entity_id: string;
  relation_type: string;
  to_entity_id: string;
  confidence: number;
  status: string;
  source_kind: string;
  source_id: string | null;
  properties: Record<string, unknown>;
  created_at: string;
};

export type MemoryEventDTO = {
  id: string;
  entity_ids: string[] | null;
  event_type: string;
  happened_at: string;
  ingested_at: string;
  summary: string;
  source_kind: string;
  source_id: string | null;
  ref_json: Record<string, unknown>;
  status: string;
  created_at: string;
};

export type MemoryNetworkCandidatesResponse = {
  entities: MemoryEntityDTO[];
  relations: MemoryRelationDTO[];
  events: MemoryEventDTO[];
};

export type MemoryNetworkExtractResponse = {
  created: { entities: number; relations: number; events: number };
  degraded: boolean;
};

export type MemoryNetworkMutationResponse = {
  kind: MemoryCandidateKind;
  id: string;
  status: string;
  entity?: MemoryEntityDTO | null;
  relation?: MemoryRelationDTO | null;
  event?: MemoryEventDTO | null;
  merged_ids: string[];
};

export type MemoryNetworkQueryResponse = {
  entities: MemoryEntityDTO[];
  relations: MemoryRelationDTO[];
  events: MemoryEventDTO[];
  provenance: {
    kind: MemoryCandidateKind;
    id: string;
    source_kind: string;
    source_id: string | null;
  }[];
  token_budget: { used: number; limit: number };
};

export async function getMemoryCandidates(
  status?: string,
  signal?: AbortSignal,
): Promise<MemoryNetworkCandidatesResponse> {
  const suffix = status ? `?status=${encodeURIComponent(status)}` : "";
  return request(`${API_BASE_URL}/memory-network/candidates${suffix}`, {
    signal,
    action: "Loading memory candidates",
  });
}

export async function runMemoryExtraction(
  scope: "structured" | "unstructured" | "all" = "all",
): Promise<MemoryNetworkExtractResponse> {
  return request(`${API_BASE_URL}/memory-network/extract`, {
    method: "POST",
    body: { scope },
    action: "Extracting memory candidates",
  });
}

export async function confirmMemoryCandidate(
  candidateId: string,
): Promise<MemoryNetworkMutationResponse> {
  return request(
    `${API_BASE_URL}/memory-network/candidates/${candidateId}/confirm`,
    { method: "POST", action: "Confirming memory candidate" },
  );
}

export async function ignoreMemoryCandidate(
  candidateId: string,
): Promise<MemoryNetworkMutationResponse> {
  return request(
    `${API_BASE_URL}/memory-network/candidates/${candidateId}/ignore`,
    { method: "POST", action: "Ignoring memory candidate" },
  );
}

export async function mergeMemoryCandidate(
  candidateId: string,
  intoEntityId: string,
): Promise<MemoryNetworkMutationResponse> {
  return request(
    `${API_BASE_URL}/memory-network/candidates/${candidateId}/merge?into=${encodeURIComponent(intoEntityId)}`,
    { method: "POST", action: "Merging memory candidate" },
  );
}

/**
 * True when the memory network API is unavailable because the feature flag
 * is off (HTTP 404) or the backend/network is unreachable.
 */
export function isMemoryNetworkUnavailable(error: unknown): boolean {
  if (error instanceof Error) {
    return /404|memory network is disabled|failed to fetch|networkerror|load failed|aborted/i.test(
      error.message,
    );
  }
  return false;
}
