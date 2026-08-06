/**
 * Knowledge API client: Obsidian vault, semantic index, captures, insights, archive.
 */

import { API_BASE_URL, request } from "./client";

export type KnowledgeVaultStatus = {
  configured: boolean;
  connected: boolean;
  vault_path?: string | null;
  root_folder: string;
  status: string;
  document_count: number;
  retrieval_enabled_count: number;
  cloud_allowed_count: number;
  last_scanned_at?: string | null;
  last_error?: string | null;
  allowed_directories: string[];
};

export type SemanticIndexStatus = {
  enabled: boolean;
  status: "disabled" | "empty" | "rebuilding" | "ready" | "degraded" | string;
  embedding_model: string;
  embedding_dimensions: number;
  index_version: string;
  local_model_available: boolean;
  memory_eligible_count: number;
  memory_indexed_count: number;
  knowledge_eligible_count: number;
  knowledge_indexed_count: number;
  chunk_count: number;
  coverage_percent: number;
  fallback_active: boolean;
  last_completed_at?: string | null;
  last_error?: string | null;
};

export type KnowledgeDocument = {
  id: string;
  relative_path: string;
  title: string;
  document_type: string;
  content_preview: string;
  content_hash: string;
  file_modified_at: string;
  size_bytes: number;
  retrieval_enabled: boolean;
  cloud_allowed: boolean;
  obsidian_uri: string;
};

export type KnowledgeScanResponse = {
  status: "completed";
  scanned: number;
  created: number;
  updated: number;
  unchanged: number;
  removed: number;
  skipped: number;
  completed_at: string;
};

export type KnowledgeCaptureDraft = {
  id: string;
  conversation_id: string;
  source_through_message_id: string;
  title: string;
  content: string;
  status: "draft" | "archived" | "discarded" | "conflict";
  message_count: number;
  cloud_allowed: boolean;
  target_relative_path?: string | null;
  archived_at?: string | null;
  insights_extracted_at?: string | null;
  created_at: string;
  updated_at: string;
};

export type KnowledgeInsightCandidate = {
  id: string;
  capture_id: string;
  candidate_type: "memory" | "task" | "question";
  source_title: string;
  title: string;
  content: string;
  rationale?: string | null;
  status: "pending" | "accepted" | "ignored";
  memory_id?: string | null;
  task_id?: string | null;
  accepted_at?: string | null;
  ignored_at?: string | null;
  created_at: string;
  updated_at: string;
};

export type KnowledgeArchiveCandidate = {
  source_type: string;
  source_id: string;
  title: string;
  summary: string;
  updated_at: string;
  archive_status?: string | null;
  target_relative_path?: string | null;
  review_relative_path?: string | null;
};

export type KnowledgeArchiveOutcome = {
  source_type: string;
  source_id: string;
  status: "created" | "updated" | "unchanged" | "user_modified" | "conflict";
  target_relative_path: string;
  review_relative_path?: string | null;
  target_obsidian_uri: string;
  review_obsidian_uri?: string | null;
};

export type KnowledgeArchiveBatch = {
  processed: number;
  created: number;
  updated: number;
  unchanged: number;
  user_modified: number;
  conflicts: number;
  errors: number;
};

export type KnowledgeArchiveRecord = {
  id: string;
  source_type: string;
  source_id: string;
  status: string;
  target_relative_path: string;
  review_relative_path?: string | null;
  last_archived_at?: string | null;
  last_checked_at: string;
  target_obsidian_uri: string;
  review_obsidian_uri?: string | null;
};

export async function getKnowledgeStatus(
  signal?: AbortSignal,
): Promise<KnowledgeVaultStatus> {
  return request<KnowledgeVaultStatus>(
    `${API_BASE_URL}/knowledge/status`,
    {
      cache: "no-store",
      signal,
      action: "读取 Obsidian 状态",
    },
  );
}

export async function getSemanticIndexStatus(
  signal?: AbortSignal,
): Promise<SemanticIndexStatus> {
  return request<SemanticIndexStatus>(
    `${API_BASE_URL}/semantic/status`,
    {
      cache: "no-store",
      signal,
      action: "读取本地语义索引状态",
    },
  );
}

export async function rebuildSemanticIndex(): Promise<SemanticIndexStatus> {
  return request<SemanticIndexStatus>(
    `${API_BASE_URL}/semantic/rebuild`,
    {
      method: "POST",
      action: "重建本地语义索引",
    },
  );
}

export async function configureKnowledgeVault(
  vaultPath: string,
): Promise<KnowledgeVaultStatus> {
  return request<KnowledgeVaultStatus>(
    `${API_BASE_URL}/knowledge/config`,
    {
      method: "PUT",
      body: { vault_path: vaultPath },
      action: "连接 Obsidian Vault",
    },
  );
}

export async function scanKnowledgeVault(): Promise<KnowledgeScanResponse> {
  return request<KnowledgeScanResponse>(
    `${API_BASE_URL}/knowledge/scan`,
    {
      method: "POST",
      action: "扫描 Obsidian 知识库",
    },
  );
}

export async function listKnowledgeDocuments(
  query?: string,
  documentType?: string,
  signal?: AbortSignal,
): Promise<KnowledgeDocument[]> {
  const params = new URLSearchParams();
  if (query?.trim()) params.set("q", query.trim());
  if (documentType) params.set("document_type", documentType);
  const suffix = params.size ? `?${params.toString()}` : "";
  return request<KnowledgeDocument[]>(
    `${API_BASE_URL}/knowledge/documents${suffix}`,
    {
      cache: "no-store",
      signal,
      action: "搜索 Obsidian 知识库",
    },
  );
}

export async function updateKnowledgeDocument(
  documentId: string,
  changes: {
    retrieval_enabled?: boolean;
    cloud_allowed?: boolean;
  },
): Promise<KnowledgeDocument> {
  return request<KnowledgeDocument>(
    `${API_BASE_URL}/knowledge/documents/${documentId}`,
    {
      method: "PATCH",
      body: changes,
      action: "更新知识笔记权限",
    },
  );
}

export async function createConversationKnowledgeCapture(
  conversationId: string,
): Promise<KnowledgeCaptureDraft> {
  return request<KnowledgeCaptureDraft>(
    `${API_BASE_URL}/knowledge/captures/conversations/${conversationId}`,
    {
      method: "POST",
      action: "生成本地知识草稿",
    },
  );
}

export async function listKnowledgeCaptures(
  signal?: AbortSignal,
): Promise<KnowledgeCaptureDraft[]> {
  return request<KnowledgeCaptureDraft[]>(
    `${API_BASE_URL}/knowledge/captures`,
    {
      cache: "no-store",
      signal,
      action: "读取知识草稿",
    },
  );
}

export async function updateKnowledgeCapture(
  captureId: string,
  payload: { title: string; content: string },
): Promise<KnowledgeCaptureDraft> {
  return request<KnowledgeCaptureDraft>(
    `${API_BASE_URL}/knowledge/captures/${captureId}`,
    {
      method: "PATCH",
      body: payload,
      action: "保存知识草稿",
    },
  );
}

export async function discardKnowledgeCapture(
  captureId: string,
): Promise<KnowledgeCaptureDraft> {
  return request<KnowledgeCaptureDraft>(
    `${API_BASE_URL}/knowledge/captures/${captureId}/discard`,
    {
      method: "POST",
      action: "放弃知识草稿",
    },
  );
}

export async function archiveKnowledgeCapture(
  captureId: string,
): Promise<KnowledgeArchiveOutcome> {
  return request<KnowledgeArchiveOutcome>(
    `${API_BASE_URL}/knowledge/captures/${captureId}/archive`,
    {
      method: "POST",
      action: "确认归档知识草稿",
    },
  );
}

export async function listKnowledgeInsights(
  signal?: AbortSignal,
): Promise<KnowledgeInsightCandidate[]> {
  return request<KnowledgeInsightCandidate[]>(
    `${API_BASE_URL}/knowledge/insights`,
    {
      cache: "no-store",
      signal,
      action: "读取知识提炼候选",
    },
  );
}

export async function extractKnowledgeInsights(
  captureId: string,
): Promise<KnowledgeInsightCandidate[]> {
  return request<KnowledgeInsightCandidate[]>(
    `${API_BASE_URL}/knowledge/insights/captures/${captureId}/extract`,
    {
      method: "POST",
      action: "本地提炼知识候选",
    },
  );
}

export async function acceptKnowledgeInsight(
  candidateId: string,
): Promise<KnowledgeInsightCandidate> {
  return request<KnowledgeInsightCandidate>(
    `${API_BASE_URL}/knowledge/insights/${candidateId}/accept`,
    {
      method: "POST",
      action: "确认知识候选",
    },
  );
}

export async function ignoreKnowledgeInsight(
  candidateId: string,
): Promise<KnowledgeInsightCandidate> {
  return request<KnowledgeInsightCandidate>(
    `${API_BASE_URL}/knowledge/insights/${candidateId}/ignore`,
    {
      method: "POST",
      action: "忽略知识候选",
    },
  );
}

export async function archiveAutomaticKnowledge(): Promise<KnowledgeArchiveBatch> {
  return request<KnowledgeArchiveBatch>(
    `${API_BASE_URL}/knowledge/archive/auto`,
    {
      method: "POST",
      action: "自动归档长期记忆与每日情报",
    },
  );
}

export async function listKnowledgeArchiveCandidates(
  signal?: AbortSignal,
): Promise<KnowledgeArchiveCandidate[]> {
  return request<KnowledgeArchiveCandidate[]>(
    `${API_BASE_URL}/knowledge/archive/candidates`,
    {
      cache: "no-store",
      signal,
      action: "读取待归档内容",
    },
  );
}

export async function archiveKnowledgeSource(
  sourceType: string,
  sourceId: string,
): Promise<KnowledgeArchiveOutcome> {
  return request<KnowledgeArchiveOutcome>(
    `${API_BASE_URL}/knowledge/archive/${sourceType}/${sourceId}`,
    {
      method: "POST",
      action: "归档到 Obsidian",
    },
  );
}

export async function listKnowledgeArchiveRecords(
  signal?: AbortSignal,
): Promise<KnowledgeArchiveRecord[]> {
  return request<KnowledgeArchiveRecord[]>(
    `${API_BASE_URL}/knowledge/archive/records`,
    {
      cache: "no-store",
      signal,
      action: "读取归档记录",
    },
  );
}
