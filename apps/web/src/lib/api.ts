export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1";

export type DependencyStatus = {
  name: string;
  status: "ready" | "not_configured" | "unavailable";
  detail?: string | null;
};

export type ReadinessResponse = {
  status: "ready" | "degraded";
  dependencies: DependencyStatus[];
};

export type BackupRecord = {
  id: string;
  created_at: string;
  file_name: string;
  size_bytes: number;
  sha256: string;
  archive_verified: boolean;
  restore_verified_at?: string | null;
  verified_table_count?: number | null;
  alembic_version?: string | null;
};

export type BackupStatus = {
  enabled: boolean;
  backup_directory: string;
  interval_hours: number;
  retention_count: number;
  backup_count: number;
  latest_backup?: BackupRecord | null;
  worker_error?: string | null;
};

export type BackupListResponse = {
  status: BackupStatus;
  backups: BackupRecord[];
};

export type BackupActionResponse = {
  status: "created" | "verified";
  message: string;
  backup: BackupRecord;
};

export async function listSystemBackups(
  signal?: AbortSignal,
): Promise<BackupListResponse> {
  const response = await fetch(`${API_BASE_URL}/system/backups`, {
    cache: "no-store",
    signal,
  });
  if (!response.ok) {
    throw await responseError(response, "Loading local backups");
  }
  return response.json() as Promise<BackupListResponse>;
}

export async function createSystemBackup(): Promise<BackupActionResponse> {
  const response = await fetch(`${API_BASE_URL}/system/backups`, {
    method: "POST",
  });
  if (!response.ok) {
    throw await responseError(response, "Creating local backup");
  }
  return response.json() as Promise<BackupActionResponse>;
}

export async function verifySystemBackup(
  backupId: string,
): Promise<BackupActionResponse> {
  const response = await fetch(
    `${API_BASE_URL}/system/backups/${backupId}/verify`,
    { method: "POST" },
  );
  if (!response.ok) {
    throw await responseError(response, "Verifying local backup");
  }
  return response.json() as Promise<BackupActionResponse>;
}

export async function downloadUserDataExport(): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/system/export`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw await responseError(response, "Exporting personal data");
  }

  const disposition = response.headers.get("Content-Disposition") ?? "";
  const fileName =
    disposition.match(/filename="([^"]+)"/)?.[1] ??
    "jarvis-user-data-export.json";
  const objectUrl = URL.createObjectURL(await response.blob());
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = fileName;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(objectUrl);
}

export type ModelProviderStatus = {
  provider: "mimo" | "deepseek" | "ollama";
  configured: boolean;
  base_url: string;
  model: string;
  role: string;
  configuration_issue?: string | null;
};

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
  const response = await fetch(`${API_BASE_URL}/knowledge/status`, {
    cache: "no-store",
    signal,
  });
  if (!response.ok) {
    throw await responseError(response, "读取 Obsidian 状态");
  }
  return response.json() as Promise<KnowledgeVaultStatus>;
}

export async function getSemanticIndexStatus(
  signal?: AbortSignal,
): Promise<SemanticIndexStatus> {
  const response = await fetch(`${API_BASE_URL}/semantic/status`, {
    cache: "no-store",
    signal,
  });
  if (!response.ok) {
    throw await responseError(response, "读取本地语义索引状态");
  }
  return response.json() as Promise<SemanticIndexStatus>;
}

export async function rebuildSemanticIndex(): Promise<SemanticIndexStatus> {
  const response = await fetch(`${API_BASE_URL}/semantic/rebuild`, {
    method: "POST",
  });
  if (!response.ok) {
    throw await responseError(response, "重建本地语义索引");
  }
  return response.json() as Promise<SemanticIndexStatus>;
}

export async function configureKnowledgeVault(
  vaultPath: string,
): Promise<KnowledgeVaultStatus> {
  const response = await fetch(`${API_BASE_URL}/knowledge/config`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ vault_path: vaultPath }),
  });
  if (!response.ok) {
    throw await responseError(response, "连接 Obsidian Vault");
  }
  return response.json() as Promise<KnowledgeVaultStatus>;
}

export async function scanKnowledgeVault(): Promise<KnowledgeScanResponse> {
  const response = await fetch(`${API_BASE_URL}/knowledge/scan`, {
    method: "POST",
  });
  if (!response.ok) {
    throw await responseError(response, "扫描 Obsidian 知识库");
  }
  return response.json() as Promise<KnowledgeScanResponse>;
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
  const response = await fetch(
    `${API_BASE_URL}/knowledge/documents${suffix}`,
    { cache: "no-store", signal },
  );
  if (!response.ok) {
    throw await responseError(response, "搜索 Obsidian 知识库");
  }
  return response.json() as Promise<KnowledgeDocument[]>;
}

export async function updateKnowledgeDocument(
  documentId: string,
  changes: {
    retrieval_enabled?: boolean;
    cloud_allowed?: boolean;
  },
): Promise<KnowledgeDocument> {
  const response = await fetch(
    `${API_BASE_URL}/knowledge/documents/${documentId}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(changes),
    },
  );
  if (!response.ok) {
    throw await responseError(response, "更新知识笔记权限");
  }
  return response.json() as Promise<KnowledgeDocument>;
}

export async function createConversationKnowledgeCapture(
  conversationId: string,
): Promise<KnowledgeCaptureDraft> {
  const response = await fetch(
    `${API_BASE_URL}/knowledge/captures/conversations/${conversationId}`,
    { method: "POST" },
  );
  if (!response.ok) {
    throw await responseError(response, "生成本地知识草稿");
  }
  return response.json() as Promise<KnowledgeCaptureDraft>;
}

export async function listKnowledgeCaptures(
  signal?: AbortSignal,
): Promise<KnowledgeCaptureDraft[]> {
  const response = await fetch(`${API_BASE_URL}/knowledge/captures`, {
    cache: "no-store",
    signal,
  });
  if (!response.ok) {
    throw await responseError(response, "读取知识草稿");
  }
  return response.json() as Promise<KnowledgeCaptureDraft[]>;
}

export async function updateKnowledgeCapture(
  captureId: string,
  payload: { title: string; content: string },
): Promise<KnowledgeCaptureDraft> {
  const response = await fetch(
    `${API_BASE_URL}/knowledge/captures/${captureId}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
  if (!response.ok) {
    throw await responseError(response, "保存知识草稿");
  }
  return response.json() as Promise<KnowledgeCaptureDraft>;
}

export async function discardKnowledgeCapture(
  captureId: string,
): Promise<KnowledgeCaptureDraft> {
  const response = await fetch(
    `${API_BASE_URL}/knowledge/captures/${captureId}/discard`,
    { method: "POST" },
  );
  if (!response.ok) {
    throw await responseError(response, "放弃知识草稿");
  }
  return response.json() as Promise<KnowledgeCaptureDraft>;
}

export async function archiveKnowledgeCapture(
  captureId: string,
): Promise<KnowledgeArchiveOutcome> {
  const response = await fetch(
    `${API_BASE_URL}/knowledge/captures/${captureId}/archive`,
    { method: "POST" },
  );
  if (!response.ok) {
    throw await responseError(response, "确认归档知识草稿");
  }
  return response.json() as Promise<KnowledgeArchiveOutcome>;
}

export async function listKnowledgeInsights(
  signal?: AbortSignal,
): Promise<KnowledgeInsightCandidate[]> {
  const response = await fetch(`${API_BASE_URL}/knowledge/insights`, {
    cache: "no-store",
    signal,
  });
  if (!response.ok) {
    throw await responseError(response, "读取知识提炼候选");
  }
  return response.json() as Promise<KnowledgeInsightCandidate[]>;
}

export async function extractKnowledgeInsights(
  captureId: string,
): Promise<KnowledgeInsightCandidate[]> {
  const response = await fetch(
    `${API_BASE_URL}/knowledge/insights/captures/${captureId}/extract`,
    { method: "POST" },
  );
  if (!response.ok) {
    throw await responseError(response, "本地提炼知识候选");
  }
  return response.json() as Promise<KnowledgeInsightCandidate[]>;
}

export async function acceptKnowledgeInsight(
  candidateId: string,
): Promise<KnowledgeInsightCandidate> {
  const response = await fetch(
    `${API_BASE_URL}/knowledge/insights/${candidateId}/accept`,
    { method: "POST" },
  );
  if (!response.ok) {
    throw await responseError(response, "确认知识候选");
  }
  return response.json() as Promise<KnowledgeInsightCandidate>;
}

export async function ignoreKnowledgeInsight(
  candidateId: string,
): Promise<KnowledgeInsightCandidate> {
  const response = await fetch(
    `${API_BASE_URL}/knowledge/insights/${candidateId}/ignore`,
    { method: "POST" },
  );
  if (!response.ok) {
    throw await responseError(response, "忽略知识候选");
  }
  return response.json() as Promise<KnowledgeInsightCandidate>;
}

export async function archiveAutomaticKnowledge(): Promise<KnowledgeArchiveBatch> {
  const response = await fetch(`${API_BASE_URL}/knowledge/archive/auto`, {
    method: "POST",
  });
  if (!response.ok) {
    throw await responseError(response, "自动归档长期记忆与每日情报");
  }
  return response.json() as Promise<KnowledgeArchiveBatch>;
}

export async function listKnowledgeArchiveCandidates(
  signal?: AbortSignal,
): Promise<KnowledgeArchiveCandidate[]> {
  const response = await fetch(
    `${API_BASE_URL}/knowledge/archive/candidates`,
    { cache: "no-store", signal },
  );
  if (!response.ok) {
    throw await responseError(response, "读取待归档内容");
  }
  return response.json() as Promise<KnowledgeArchiveCandidate[]>;
}

export async function archiveKnowledgeSource(
  sourceType: string,
  sourceId: string,
): Promise<KnowledgeArchiveOutcome> {
  const response = await fetch(
    `${API_BASE_URL}/knowledge/archive/${sourceType}/${sourceId}`,
    { method: "POST" },
  );
  if (!response.ok) {
    throw await responseError(response, "归档到 Obsidian");
  }
  return response.json() as Promise<KnowledgeArchiveOutcome>;
}

export async function listKnowledgeArchiveRecords(
  signal?: AbortSignal,
): Promise<KnowledgeArchiveRecord[]> {
  const response = await fetch(`${API_BASE_URL}/knowledge/archive/records`, {
    cache: "no-store",
    signal,
  });
  if (!response.ok) {
    throw await responseError(response, "读取归档记录");
  }
  return response.json() as Promise<KnowledgeArchiveRecord[]>;
}

export type ModelStatusResponse = {
  default_provider: string;
  providers: ModelProviderStatus[];
};

export type ProfileResponse = {
  user_id: string;
  name: string;
  timezone: string;
  onboarding_completed: boolean;
  onboarding_completed_at?: string | null;
  profile: {
    education_level?: string | null;
    major?: string | null;
    career_goals: string[];
    current_skills: string[];
    weaknesses: string[];
    daily_available_minutes: number;
    extra: Record<string, unknown>;
  };
  preferences: {
    information_interests: Record<string, string>;
    notification_settings: Record<string, unknown>;
    privacy_settings: Record<string, unknown>;
    model_preferences: Record<string, string>;
  };
};

export type OnboardingSession = {
  id: string;
  user_id: string;
  status: string;
  current_step: number;
  answers: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type ModelMode = "standard" | "deep" | "local" | "auto";

export type ConversationSummary = {
  id: string;
  title: string;
  model_mode: ModelMode;
  last_message_at: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  last_message_preview?: string | null;
  has_summary: boolean;
  summary_updated_at?: string | null;
};

export type KnowledgeReference = {
  document_id: string;
  title: string;
  relative_path: string;
  document_type: string;
  obsidian_uri: string;
  cloud_allowed: boolean;
};

export type ChatMessage = {
  id: string;
  conversation_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  status: "completed" | "error" | "cancelled";
  provider?: string | null;
  model?: string | null;
  prompt_tokens?: number | null;
  completion_tokens?: number | null;
  latency_ms?: number | null;
  metadata: {
    requested_provider?: string | null;
    fallback_reason?: string | null;
    knowledge_sources?: KnowledgeReference[];
    [key: string]: unknown;
  };
  created_at: string;
};

export type ConversationDetail = ConversationSummary & {
  messages: ChatMessage[];
};

export type AgentRouting = {
  agent_id:
    | "jarvis_core"
    | "english_coach"
    | "research"
    | "growth"
    | "local_document"
    | "investment_intelligence";
  agent_version: string;
  agent_name: string;
  intent_type: string;
  runtime: "direct" | "workflow";
  complexity: number;
  privacy_level: "public" | "personal" | "private_local";
  risk_level: "R0" | "R1" | "R2" | "R3";
  disposition:
    | "allow_automatically"
    | "require_confirmation"
    | "prohibit_agent_execution";
  requested_action: string;
  routing_reason: string;
  runtime_reason: string;
  shadow_only: true;
  model: {
    recommended_provider: string;
    recommended_model: string;
    selected_provider: string;
    selected_model: string;
    requires_confirmation: boolean;
    recommendation_reason: string;
    alternatives: string[];
    deepseek_disclosure?: {
      purpose: string;
      covered_steps: string[];
      data_categories: string[];
      alternatives: string[];
    } | null;
  };
};

export type ChatSendResponse = {
  conversation: ConversationSummary;
  user_message: ChatMessage;
  assistant_message: ChatMessage;
  routing: {
    requested_mode: ModelMode;
    requested_provider: string;
    provider_used: string;
    model_used: string;
    fallback_reason?: string | null;
  };
  agent_routing?: AgentRouting | null;
  memory_candidates_created: number;
  knowledge_sources: KnowledgeReference[];
  context?: ContextAssemblyInfo | null;
};

export type ChatStreamMeta = {
  user_message: ChatMessage;
  routing: ChatSendResponse["routing"];
  agent_routing?: AgentRouting | null;
  knowledge_sources: KnowledgeReference[];
};

export type ChatStreamHandlers = {
  onMeta?: (meta: ChatStreamMeta) => void;
  onDelta?: (content: string) => void;
  onDone?: (response: ChatSendResponse) => void;
  onError?: (message: string) => void;
};

export type ModelCallLog = {
  id: string;
  conversation_id: string;
  assistant_message_id?: string | null;
  requested_mode: string;
  requested_provider: string;
  provider_used: string;
  model_used: string;
  route_reason: string;
  fallback_reason?: string | null;
  success: boolean;
  latency_ms: number;
  prompt_tokens?: number | null;
  completion_tokens?: number | null;
  total_tokens?: number | null;
  first_token_ms?: number | null;
  tokens_per_second?: number | null;
  knowledge_reference_count: number;
  error_type?: string | null;
  user_confirmed: boolean;
  feedback_rating?: "helpful" | "not_helpful" | null;
  task_completed?: boolean | null;
  feedback_at?: string | null;
  created_at: string;
};

export type ModelTraceStep = {
  key: string;
  label: string;
  status: "completed" | "failed" | "skipped";
  duration_ms?: number | null;
  details: Record<string, unknown>;
};

export type ModelExecutionTrace = {
  model_call_id: string;
  conversation_id: string;
  status: "completed" | "failed";
  privacy_note: string;
  created_at: string;
  steps: ModelTraceStep[];
};

export type EvaluationProvider = "mimo" | "deepseek" | "ollama";

export type EvaluationCase = {
  id: string;
  version: number;
  title: string;
  description: string;
  category: string;
};

export type EvaluationCheck = {
  label: string;
  passed: boolean;
};

export type EvaluationRun = {
  id: string;
  case_id: string;
  case_version: number;
  category: string;
  provider: EvaluationProvider;
  model: string;
  status: "running" | "completed" | "failed";
  latency_ms?: number | null;
  first_token_ms?: number | null;
  tokens_per_second?: number | null;
  prompt_tokens?: number | null;
  completion_tokens?: number | null;
  total_tokens?: number | null;
  score?: number | null;
  checks: EvaluationCheck[];
  response_text?: string | null;
  error_type?: string | null;
  paid_call_confirmed: boolean;
  feedback_rating?: "helpful" | "not_helpful" | null;
  created_at: string;
};

export type ProviderEvaluationSummary = {
  provider: EvaluationProvider;
  model: string;
  configured: boolean;
  chat_call_count: number;
  chat_success_rate?: number | null;
  average_latency_ms?: number | null;
  average_first_token_ms?: number | null;
  average_tokens_per_second?: number | null;
  helpful_rate?: number | null;
  evaluation_run_count: number;
  average_evaluation_score?: number | null;
};

export type EvaluationOverview = {
  providers: ProviderEvaluationSummary[];
  privacy_note: string;
};

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

export type GrowthArea =
  | "technology"
  | "career"
  | "english"
  | "investment"
  | "personal";

export type Milestone = {
  id: string;
  goal_id: string;
  title: string;
  description?: string | null;
  status: "pending" | "in_progress" | "completed" | "cancelled";
  order_index: number;
  target_date?: string | null;
  completed_at?: string | null;
  created_at: string;
  updated_at: string;
};

export type Goal = {
  id: string;
  user_id: string;
  title: string;
  description?: string | null;
  area: GrowthArea;
  status: "active" | "paused" | "completed" | "cancelled";
  target_date?: string | null;
  completed_at?: string | null;
  milestones: Milestone[];
  progress: {
    percent: number;
    completed_milestones: number;
    total_milestones: number;
    completed_tasks: number;
    total_tasks: number;
    actual_minutes: number;
    basis: string;
  };
  created_at: string;
  updated_at: string;
};

export type GrowthTask = {
  id: string;
  user_id: string;
  goal_id?: string | null;
  milestone_id?: string | null;
  title: string;
  description?: string | null;
  area: GrowthArea;
  status: "todo" | "in_progress" | "paused" | "completed" | "cancelled";
  priority: number;
  planned_date?: string | null;
  due_at?: string | null;
  reminder_at?: string | null;
  estimated_minutes: number;
  actual_minutes: number;
  started_at?: string | null;
  completed_at?: string | null;
  blocker_reason?: string | null;
  completion_evidence?: string | null;
  source_type: string;
  created_at: string;
  updated_at: string;
};

export type DailyPlan = {
  id: string;
  plan_date: string;
  status: "draft" | "confirmed" | "completed";
  capacity_minutes: number;
  total_estimated_minutes: number;
  tasks: GrowthTask[];
  generation_note?: string | null;
  confirmed_at?: string | null;
  created_at: string;
  updated_at: string;
};

export type WeeklyReview = {
  id: string;
  week_start: string;
  week_end: string;
  status: "generated" | "confirmed";
  snapshot: {
    planned_tasks?: number;
    completed_tasks?: number;
    unfinished_tasks?: number;
    completion_rate?: number;
    estimated_minutes?: number;
    actual_minutes?: number;
    blockers?: Array<{ task: string; reason: string }>;
    completed_task_titles?: string[];
    [key: string]: unknown;
  };
  summary: string;
  user_note?: string | null;
  created_at: string;
  updated_at: string;
};

export type GrowthOverview = {
  active_goals: number;
  today_tasks: number;
  today_completed: number;
  week_completed: number;
  week_actual_minutes: number;
  today_capacity_minutes: number;
};

export type GrowthWorkflowStatus =
  | "created"
  | "running"
  | "waiting_for_input"
  | "waiting_for_model_approval"
  | "waiting_for_draft_review"
  | "completed"
  | "rejected"
  | "cancelled"
  | "failed";

export type GrowthModelPreference = "auto" | "deep" | "mimo" | "local";

export type GrowthDraftMilestone = {
  title: string;
  description: string;
  order_index: number;
};

export type GrowthDraftTask = {
  title: string;
  description: string;
  milestone_index: number;
  priority: number;
  estimated_minutes: number;
};

export type GrowthPlanDraft = {
  id: string;
  run_id: string;
  title: string;
  summary: string;
  milestones: GrowthDraftMilestone[];
  tasks: GrowthDraftTask[];
  status: "draft" | "confirmed" | "rejected";
  provider_used: string;
  model_used: string;
  created_goal_id?: string | null;
  created_task_ids: string[];
  confirmed_at?: string | null;
  rejected_at?: string | null;
  created_at: string;
  updated_at: string;
};

export type GrowthWorkflowRun = {
  id: string;
  status: GrowthWorkflowStatus;
  current_step?: string | null;
  pending_kind?: string | null;
  pending_payload?: Record<string, unknown> | null;
  model_preference: GrowthModelPreference;
  selected_provider?: string | null;
  provider_used?: string | null;
  model_used?: string | null;
  paid_model_confirmed: boolean;
  checkpoint_backend: "postgres" | "memory";
  request: {
    id: string;
    objective: string;
    constraints?: string | null;
    target_date?: string | null;
    weekly_hours?: number | null;
    cloud_allowed: boolean;
  };
  draft?: GrowthPlanDraft | null;
  created_at: string;
  updated_at: string;
  completed_at?: string | null;
};

export type ResearchModelPreference = "auto" | "deep" | "mimo" | "local";

export type ResearchFact = {
  statement: string;
  source_refs: string[];
};

export type ResearchViewpoint = {
  statement: string;
  attribution: string;
  source_refs: string[];
};

export type ResearchInference = {
  statement: string;
  basis_refs: string[];
  confidence: "low" | "medium" | "high";
};

export type ResearchReport = {
  id: string;
  run_id: string;
  request_id: string;
  title: string;
  executive_summary: string;
  facts: ResearchFact[];
  viewpoints: ResearchViewpoint[];
  inferences: ResearchInference[];
  uncertainties: string[];
  recommended_actions: string[];
  status: "draft" | "confirmed" | "rejected" | "archived" | "conflict";
  provider_used: string;
  model_used: string;
  confirmed_at?: string | null;
  rejected_at?: string | null;
  archived_at?: string | null;
  archive_path?: string | null;
  created_at: string;
  updated_at: string;
};

export type ResearchSource = {
  id: string;
  citation_key: string;
  source_kind: "intelligence" | "manual";
  source_name: string;
  title: string;
  url: string;
  canonical_url: string;
  published_at?: string | null;
  excerpt: string;
  trust_score: number;
  created_at: string;
};

export type ResearchWorkflowRun = {
  id: string;
  status:
    | "created"
    | "running"
    | "waiting_for_sources"
    | "waiting_for_model_approval"
    | "waiting_for_report_review"
    | "completed"
    | "rejected"
    | "cancelled"
    | "failed";
  current_step?: string | null;
  pending_kind?: string | null;
  pending_payload?: Record<string, unknown> | null;
  model_preference: ResearchModelPreference;
  selected_provider?: string | null;
  provider_used?: string | null;
  model_used?: string | null;
  paid_model_confirmed: boolean;
  checkpoint_backend: "postgres" | "memory";
  request: {
    id: string;
    question: string;
    scope?: string | null;
    category?: NewsCategory | null;
    max_sources: number;
    cloud_allowed: boolean;
    research_plan: Record<string, unknown>;
  };
  sources: ResearchSource[];
  report?: ResearchReport | null;
  created_at: string;
  updated_at: string;
  completed_at?: string | null;
};

export type EnglishSessionType =
  | "free"
  | "topic"
  | "interview"
  | "technical";

export type EnglishCorrectionMode = "instant" | "gentle" | "summary";
export type EnglishLevel = "A1" | "A2" | "B1" | "B2" | "C1" | "C2";
export type EnglishProcessingMode = "standard" | "local";
export type EnglishMistakeStatus =
  | "pending"
  | "learning"
  | "mastered"
  | "disputed"
  | "rejected";
export type EnglishReviewResult =
  | "again"
  | "hard"
  | "good"
  | "easy"
  | "mastered"
  | "incorrect_explanation";

export type EnglishMessage = {
  id: string;
  session_id: string;
  role: "user" | "assistant";
  content: string;
  sequence_number: number;
  status: string;
  input_mode: "text" | "voice_transcript";
  transcript_edited: boolean;
  correction_ids: string[];
  requested_provider?: string | null;
  provider_used?: string | null;
  model_used?: string | null;
  route_reason?: string | null;
  fallback_reason?: string | null;
  latency_ms?: number | null;
  created_at: string;
};

export type EnglishSession = {
  id: string;
  user_id: string;
  session_type: EnglishSessionType;
  topic?: string | null;
  correction_mode: EnglishCorrectionMode;
  level: EnglishLevel;
  processing_mode: EnglishProcessingMode;
  status: "active" | "completed";
  summary?: string | null;
  message_count: number;
  mistake_count: number;
  completed_at?: string | null;
  created_at: string;
  updated_at: string;
};

export type EnglishSessionDetail = EnglishSession & {
  messages: EnglishMessage[];
};

export type EnglishMistake = {
  id: string;
  user_id: string;
  source_session_id?: string | null;
  source_message_id?: string | null;
  original_text: string;
  corrected_text: string;
  category: string;
  explanation: string;
  context: string;
  contexts: string[];
  cefr: EnglishLevel;
  occurrence_count: number;
  status: EnglishMistakeStatus;
  interval_days: number;
  first_seen_at: string;
  last_seen_at: string;
  confirmed_at?: string | null;
  last_reviewed_at?: string | null;
  next_review_at?: string | null;
  created_at: string;
  updated_at: string;
};

export type EnglishReview = {
  id: string;
  user_id: string;
  mistake_id: string;
  scheduled_for: string;
  status: "scheduled" | "completed" | "cancelled";
  prompt: string;
  expected_answer: string;
  submitted_answer?: string | null;
  result?: EnglishReviewResult | null;
  answered_at?: string | null;
  next_review_at?: string | null;
  mistake: EnglishMistake;
  created_at: string;
  updated_at: string;
};

export type EnglishOverview = {
  active_session_id?: string | null;
  total_sessions: number;
  completed_sessions: number;
  pending_mistakes: number;
  learning_mistakes: number;
  mastered_mistakes: number;
  due_reviews: number;
};

export type EnglishSendResponse = {
  user_message: EnglishMessage;
  assistant_message: EnglishMessage;
  mistakes: EnglishMistake[];
};

export type NewsCategory =
  | "ai"
  | "career"
  | "technology"
  | "english"
  | "investment"
  | "international";

export type IntelligencePreferences = Record<NewsCategory, number>;

export type NewsSource = {
  id: string;
  name: string;
  feed_url: string;
  site_url?: string | null;
  source_type: "rss" | "manual" | "trusted_api";
  default_category: NewsCategory;
  language: string;
  trust_score: number;
  enabled: boolean;
  is_default: boolean;
  refresh_interval_minutes: number;
  last_fetched_at?: string | null;
  last_success_at?: string | null;
  last_error?: string | null;
  consecutive_failures: number;
  last_item_count: number;
  created_at: string;
  updated_at: string;
};

export type NewsItem = {
  id: string;
  source_id?: string | null;
  source_name: string;
  duplicate_of_id?: string | null;
  title: string;
  url: string;
  canonical_url: string;
  published_at?: string | null;
  fetched_at: string;
  source_excerpt: string;
  summary: string;
  analysis_text: string;
  suggestion_text: string;
  category: NewsCategory;
  geo?: {
    lat: number;
    lng: number;
    country: string;
  } | null;
  tags: string[];
  relevance_score: number;
  trust_score: number;
  language: string;
  status: "new" | "read" | "saved" | "ignored" | "task_created";
  investment_related: boolean;
  portfolio_related: boolean;
  requested_provider?: string | null;
  provider_used?: string | null;
  model_used?: string | null;
  fallback_reason?: string | null;
  read_at?: string | null;
  saved_at?: string | null;
  ignored_at?: string | null;
  links: Array<{
    link_type: string;
    linked_id: string;
    relationship_note?: string | null;
  }>;
  created_at: string;
  updated_at: string;
};

export type DailyBrief = {
  id: string;
  brief_date: string;
  status: "ready" | "failed";
  title: string;
  overview: string;
  item_count: number;
  items: NewsItem[];
  generation_note: string;
  processing_mode: "standard" | "local";
  requested_provider?: string | null;
  provider_used?: string | null;
  model_used?: string | null;
  fallback_reason?: string | null;
  generated_at: string;
  read_at?: string | null;
  reminder_scheduled: boolean;
  created_at: string;
  updated_at: string;
};

export type IntelligenceOverview = {
  today_items: number;
  unread_items: number;
  saved_items: number;
  active_sources: number;
  source_errors: number;
  today_brief_ready: boolean;
  today_brief_count: number;
  last_refresh_at?: string | null;
  interests: IntelligencePreferences;
};

export type SourceRefresh = {
  source_id: string;
  source_name: string;
  fetched_entries: number;
  created_items: number;
  duplicate_items: number;
  updated_items: number;
  status: "ok" | "not_modified" | "failed";
  error?: string | null;
};

export type RefreshAllSources = {
  source_count: number;
  successful_sources: number;
  failed_sources: number;
  created_items: number;
  duplicate_items: number;
  results: SourceRefresh[];
};

export type MoneyValue = number | string;
export type InvestmentRisk = "low" | "medium" | "high" | "very_high";
export type InvestmentAssetType =
  | "stock"
  | "etf"
  | "fund"
  | "bond"
  | "crypto"
  | "cash"
  | "other";

export type InvestmentAsset = {
  id: string;
  name: string;
  symbol: string;
  market: string;
  asset_type: InvestmentAssetType;
  currency: string;
  latest_price?: MoneyValue | null;
  latest_price_date?: string | null;
  notes?: string | null;
  created_at: string;
  updated_at: string;
};

export type PortfolioPosition = {
  id: string;
  asset: InvestmentAsset;
  quantity: MoneyValue;
  average_cost: MoneyValue;
  cost_basis: MoneyValue;
  realized_pnl: MoneyValue;
  dividend_income: MoneyValue;
  target_allocation?: MoneyValue | null;
  risk_level: InvestmentRisk;
  opened_on?: string | null;
  closed_on?: string | null;
  market_value?: MoneyValue | null;
  unrealized_pnl?: MoneyValue | null;
  unrealized_pnl_percent?: MoneyValue | null;
  latest_price_missing: boolean;
  related_news_count: number;
  created_at: string;
  updated_at: string;
};

export type InvestmentTransactionType =
  | "opening"
  | "buy"
  | "sell"
  | "dividend";

export type InvestmentTransaction = {
  id: string;
  asset: InvestmentAsset;
  transaction_type: InvestmentTransactionType;
  transaction_date: string;
  quantity?: MoneyValue | null;
  unit_price?: MoneyValue | null;
  cash_amount?: MoneyValue | null;
  fees: MoneyValue;
  currency: string;
  reason?: string | null;
  notes?: string | null;
  calculated_amount: MoneyValue;
  realized_pnl: MoneyValue;
  quantity_after: MoneyValue;
  average_cost_after: MoneyValue;
  cost_basis_after: MoneyValue;
  created_at: string;
  updated_at: string;
};

export type InvestmentThesis = {
  id: string;
  asset: InvestmentAsset;
  title: string;
  original_reason: string;
  current_view?: string | null;
  key_assumptions: string[];
  watch_events: string[];
  invalidation_conditions: string[];
  risk_level: InvestmentRisk;
  status: "active" | "changed" | "invalidated" | "closed" | "superseded";
  is_current: boolean;
  cloud_allowed: boolean;
  created_at: string;
  updated_at: string;
};

export type InvestmentReview = {
  id: string;
  asset: InvestmentAsset;
  thesis_id?: string | null;
  review_type: "weekly" | "monthly" | "manual";
  period_start: string;
  period_end: string;
  status: "draft" | "confirmed";
  thesis_assessment:
    | "unchanged"
    | "strengthened"
    | "weakened"
    | "invalidated"
    | "uncertain";
  summary: string;
  risks: string[];
  questions: string[];
  user_note?: string | null;
  snapshot: Record<string, unknown>;
  generated_by: string;
  disclaimer: string;
  created_at: string;
  updated_at: string;
};

export type InvestmentOverview = {
  active_positions: number;
  closed_positions: number;
  asset_count: number;
  transaction_count: number;
  current_theses: number;
  linked_news: number;
  totals_by_currency: Array<{
    currency: string;
    cost_basis: MoneyValue;
    market_value?: MoneyValue | null;
    unrealized_pnl?: MoneyValue | null;
    realized_pnl: MoneyValue;
    dividend_income: MoneyValue;
    priced_positions: number;
    total_positions: number;
  }>;
  positions: PortfolioPosition[];
  recent_transactions: InvestmentTransaction[];
  disclaimer: string;
};

export type MonitorType = "asset" | "macro" | "international";
export type ImpactDirection =
  | "positive"
  | "negative"
  | "mixed"
  | "uncertain";

export type MonitorRule = {
  id: string;
  name: string;
  monitor_type: MonitorType;
  asset_id?: string | null;
  asset_name?: string | null;
  asset_symbol?: string | null;
  thesis_id?: string | null;
  keywords: string[];
  regions: string[];
  risk_channels: string[];
  min_severity: number;
  cooldown_minutes: number;
  notify_enabled: boolean;
  enabled: boolean;
  cloud_allowed: boolean;
  last_evaluated_at?: string | null;
  new_event_count: number;
  created_at: string;
  updated_at: string;
};

export type MonitorEvent = {
  id: string;
  rule_id: string;
  rule_name: string;
  monitor_type: MonitorType;
  news_item_id: string;
  news_title: string;
  source_name: string;
  source_url: string;
  published_at?: string | null;
  asset_id?: string | null;
  asset_name?: string | null;
  asset_symbol?: string | null;
  thesis_id?: string | null;
  status: "new" | "acknowledged" | "dismissed";
  impact_direction: ImpactDirection;
  severity: number;
  confidence: number;
  time_horizon: "immediate" | "short" | "medium" | "long" | "unknown";
  matched_terms: string[];
  fact_summary: string;
  why_relevant: string;
  impact_mechanism: string;
  watch_next: string[];
  analysis_method: string;
  notification_scheduled: boolean;
  detected_at: string;
  acknowledged_at?: string | null;
  dismissed_at?: string | null;
  created_at: string;
  updated_at: string;
};

export type MonitoringOverview = {
  active_rules: number;
  asset_rules: number;
  topic_rules: number;
  new_events: number;
  critical_events: number;
  linked_assets: number;
  latest_event_at?: string | null;
  price_mode: "manual_or_timestamped";
  disclaimer: string;
};

export type MonitoringScanResult = {
  rules_evaluated: number;
  items_examined: number;
  events_created: number;
  notifications_scheduled: number;
  scanned_at: string;
};

export type RelatedInvestmentNews = {
  id: string;
  title: string;
  url: string;
  source_name: string;
  summary: string;
  category: string;
  published_at?: string | null;
  relationship_note?: string | null;
  linked: boolean;
};

export type EnglishSessionCompleteResponse = {
  session: EnglishSession;
  mistakes: EnglishMistake[];
};

export type NotificationChannel = "desktop" | "voice";
export type VoiceEngine = "auto" | "local_neural" | "windows";
export type VoicePersona = "calm" | "concise" | "plain";

export type NotificationPreference = {
  desktop_enabled: boolean;
  voice_enabled: boolean;
  quiet_enabled: boolean;
  quiet_start: string;
  quiet_end: string;
  max_daily_notifications: number;
  max_hourly_voice: number;
  default_snooze_minutes: number;
  voice_rate: number;
  voice_volume: number;
  voice_engine: VoiceEngine;
  voice_persona: VoicePersona;
  sensitive_voice_enabled: boolean;
  paused_until?: string | null;
  updated_at: string;
};

export type DeliveryAttempt = {
  channel: NotificationChannel;
  device_id: string;
  success: boolean;
  error_message?: string | null;
  created_at: string;
};

export type JarvisNotification = {
  id: string;
  scheduled_job_id?: string | null;
  task_id?: string | null;
  title: string;
  message: string;
  category: string;
  priority: number;
  status:
    | "pending"
    | "claimed"
    | "snoozed"
    | "delivered"
    | "dismissed"
    | "cancelled"
    | "failed";
  requested_channels: NotificationChannel[];
  claimed_channels: NotificationChannel[];
  sensitive: boolean;
  available_at: string;
  claimed_at?: string | null;
  delivered_at?: string | null;
  read_at?: string | null;
  dismissed_at?: string | null;
  snooze_count: number;
  attempt_count: number;
  error_message?: string | null;
  attempts: DeliveryAttempt[];
  created_at: string;
  updated_at: string;
};

export type CompanionDevice = {
  device_id: string;
  display_name: string;
  platform: string;
  capabilities: NotificationChannel[];
  last_seen_at: string;
  online: boolean;
  last_error?: string | null;
  voice_status?: {
    local_neural_ready: boolean;
    chinese_neural_ready: boolean;
    english_neural_ready: boolean;
    bilingual_neural_ready: boolean;
    windows_voice_ready: boolean;
    selected_engine: string;
    local_model_name?: string | null;
    english_model_name?: string | null;
    windows_voice_name?: string | null;
    fallback_reason?: string | null;
  } | null;
};

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
  const response = await fetch(`${API_BASE_URL}/providers/n8n/status`, {
    cache: "no-store",
    signal,
  });
  if (!response.ok) {
    throw await responseError(response, "Loading n8n provider status");
  }
  return response.json() as Promise<N8nProviderStatus>;
}

export async function listToolCatalog(
  signal?: AbortSignal,
): Promise<ToolCatalogItem[]> {
  const response = await fetch(`${API_BASE_URL}/tool-gateway/catalog`, {
    cache: "no-store",
    signal,
  });
  if (!response.ok) {
    throw await responseError(response, "Loading Tool Gateway catalog");
  }
  return response.json() as Promise<ToolCatalogItem[]>;
}

export async function getApprovalCenter(
  signal?: AbortSignal,
): Promise<ApprovalCenterResponse> {
  const response = await fetch(`${API_BASE_URL}/approval-center`, {
    cache: "no-store",
    signal,
  });
  if (!response.ok) {
    throw await responseError(response, "Loading Approval Center");
  }
  return response.json() as Promise<ApprovalCenterResponse>;
}

export async function createToolExecution(input: {
  agent_id: string;
  agent_run_id?: string | null;
  tool_id: string;
  idempotency_key: string;
  parameters: Record<string, unknown>;
}): Promise<ToolExecution> {
  const response = await fetch(`${API_BASE_URL}/tool-gateway/executions`, {
    body: JSON.stringify(input),
    headers: { "Content-Type": "application/json" },
    method: "POST",
  });
  if (!response.ok) {
    throw await responseError(response, "Creating a tool proposal");
  }
  return response.json() as Promise<ToolExecution>;
}

export async function updateToolProposal(
  approvalId: string,
  parameters: Record<string, unknown>,
): Promise<ToolExecution> {
  const response = await fetch(
    `${API_BASE_URL}/approval-center/${approvalId}/proposal`,
    {
      body: JSON.stringify({ parameters }),
      headers: { "Content-Type": "application/json" },
      method: "PATCH",
    },
  );
  if (!response.ok) {
    throw await responseError(response, "Updating the approval preview");
  }
  return response.json() as Promise<ToolExecution>;
}

export async function decideToolApproval(
  approvalId: string,
  decision: "approve" | "reject",
  note?: string,
): Promise<ToolExecution> {
  const response = await fetch(
    `${API_BASE_URL}/approval-center/${approvalId}/${decision}`,
    {
      body: JSON.stringify({ note: note || null }),
      headers: { "Content-Type": "application/json" },
      method: "POST",
    },
  );
  if (!response.ok) {
    throw await responseError(response, `${decision} tool proposal`);
  }
  return response.json() as Promise<ToolExecution>;
}

export async function executeApprovedTool(
  executionId: string,
): Promise<ToolExecution> {
  const response = await fetch(
    `${API_BASE_URL}/tool-gateway/executions/${executionId}/execute`,
    { method: "POST" },
  );
  if (!response.ok) {
    throw await responseError(response, "Executing approved tool");
  }
  return response.json() as Promise<ToolExecution>;
}

async function responseError(response: Response, action: string): Promise<Error> {
  let detail = "";
  try {
    const body = (await response.json()) as { detail?: string };
    detail = body.detail ? `: ${body.detail}` : "";
  } catch {
    // The status code still gives a useful fallback when a response is not JSON.
  }
  return new Error(`${action} failed with ${response.status}${detail}`);
}

export async function getReadiness(
  signal?: AbortSignal,
): Promise<ReadinessResponse> {
  const response = await fetch(`${API_BASE_URL}/health/ready`, {
    cache: "no-store",
    signal,
  });

  if (!response.ok) {
    throw new Error(`Health request failed with ${response.status}`);
  }

  return response.json() as Promise<ReadinessResponse>;
}

export type HeaderStatusResponse = {
  core: "ready" | "degraded" | "offline";
  model: {
    provider: string;
    model?: string | null;
    mode: string;
  };
  quiet_hours?: {
    enabled: boolean;
    start?: string | null;
    end?: string | null;
    active: boolean;
  } | null;
  unread_notifications: number;
  server_time: string;
};

export async function getHeaderStatus(
  signal?: AbortSignal,
): Promise<HeaderStatusResponse> {
  const response = await fetch(`${API_BASE_URL}/ui/header-status`, {
    cache: "no-store",
    signal,
  });

  if (!response.ok) {
    throw new Error(`Header status failed with ${response.status}`);
  }

  return response.json() as Promise<HeaderStatusResponse>;
}

export type TabletTodayTask = {
  id: string;
  title: string;
  status: string;
};

export type TabletBootstrapResponse = {
  core: "ready" | "degraded" | "offline";
  model: {
    provider: string;
    model?: string | null;
    mode: string;
  };
  quiet_hours?: {
    enabled: boolean;
    start?: string | null;
    end?: string | null;
    active: boolean;
  } | null;
  unread_notifications: number;
  profile_name?: string | null;
  configured_models: number;
  total_models: number;
  today_tasks: TabletTodayTask[];
  unread_intelligence: number;
  memory_active: number;
  server_time: string;
};

export async function getTabletBootstrap(
  signal?: AbortSignal,
): Promise<TabletBootstrapResponse> {
  const response = await fetch(`${API_BASE_URL}/ui/tablet-bootstrap`, {
    cache: "no-store",
    signal,
  });
  if (!response.ok) {
    throw new Error(`Tablet bootstrap failed with ${response.status}`);
  }
  return response.json() as Promise<TabletBootstrapResponse>;
}

export type GrowthProgressPoint = {
  date: string;
  minutes: number;
};

export type GoalProgressItem = {
  goal_id: string;
  title: string;
  progress: number;
  completed_milestones: number;
  total_milestones: number;
};

export type GrowthProgressResponse = {
  weekly_minutes: GrowthProgressPoint[];
  goals: GoalProgressItem[];
};

export async function getGrowthProgress(
  signal?: AbortSignal,
): Promise<GrowthProgressResponse> {
  const response = await fetch(`${API_BASE_URL}/growth/progress`, {
    cache: "no-store",
    signal,
  });
  if (!response.ok) {
    throw new Error(`Growth progress failed with ${response.status}`);
  }
  return response.json() as Promise<GrowthProgressResponse>;
}

export type InvestmentPerformancePoint = {
  date: string;
  cost: number;
};

export type CurrencyPerformanceSeries = {
  currency: string;
  points: InvestmentPerformancePoint[];
  current_cost_basis: number;
  current_market_value?: number | null;
};

export type InvestmentPerformanceResponse = {
  series: CurrencyPerformanceSeries[];
  disclaimer: string;
};

export async function getInvestmentPerformance(
  signal?: AbortSignal,
): Promise<InvestmentPerformanceResponse> {
  const response = await fetch(`${API_BASE_URL}/investment/performance`, {
    cache: "no-store",
    signal,
  });
  if (!response.ok) {
    throw new Error(`Investment performance failed with ${response.status}`);
  }
  return response.json() as Promise<InvestmentPerformanceResponse>;
}

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
  const response = await fetch(`${API_BASE_URL}/observatory/metrics`, {
    cache: "no-store",
    signal,
  });
  if (!response.ok) {
    throw new Error(`Observatory metrics failed with ${response.status}`);
  }
  return response.json() as Promise<ObservatoryMetricsResponse>;
}

export async function getModelStatus(
  signal?: AbortSignal,
): Promise<ModelStatusResponse> {
  const response = await fetch(`${API_BASE_URL}/models/status`, {
    cache: "no-store",
    signal,
  });

  if (!response.ok) {
    throw new Error(`Model status request failed with ${response.status}`);
  }

  return response.json() as Promise<ModelStatusResponse>;
}

export async function getProfile(
  signal?: AbortSignal,
): Promise<ProfileResponse | null> {
  const response = await fetch(`${API_BASE_URL}/profile`, {
    cache: "no-store",
    signal,
  });

  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw new Error(`Profile request failed with ${response.status}`);
  }

  return response.json() as Promise<ProfileResponse>;
}

export async function createOnboardingSession(payload: {
  user_name: string;
  timezone: string;
}): Promise<OnboardingSession> {
  const response = await fetch(`${API_BASE_URL}/onboarding/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`Creating onboarding failed with ${response.status}`);
  }

  return response.json() as Promise<OnboardingSession>;
}

export async function updateOnboardingSession(
  sessionId: string,
  payload: {
    current_step: number;
    answers: Record<string, unknown>;
  },
): Promise<OnboardingSession> {
  const response = await fetch(
    `${API_BASE_URL}/onboarding/sessions/${sessionId}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );

  if (!response.ok) {
    throw new Error(`Updating onboarding failed with ${response.status}`);
  }

  return response.json() as Promise<OnboardingSession>;
}

export async function completeOnboardingSession(
  sessionId: string,
): Promise<void> {
  const response = await fetch(
    `${API_BASE_URL}/onboarding/sessions/${sessionId}/complete`,
    { method: "POST" },
  );

  if (!response.ok) {
    throw new Error(`Completing onboarding failed with ${response.status}`);
  }
}

export async function listConversations(
  signal?: AbortSignal,
  query?: string,
): Promise<ConversationSummary[]> {
  const search = query?.trim();
  const url = new URL(`${API_BASE_URL}/chat/conversations`);
  if (search) {
    url.searchParams.set("q", search);
  }
  const response = await fetch(url, {
    cache: "no-store",
    signal,
  });
  if (!response.ok) {
    throw await responseError(response, "Loading conversations");
  }
  return response.json() as Promise<ConversationSummary[]>;
}

export async function renameConversation(
  conversationId: string,
  title: string,
): Promise<ConversationSummary> {
  const response = await fetch(
    `${API_BASE_URL}/chat/conversations/${conversationId}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title }),
    },
  );
  if (!response.ok) {
    throw await responseError(response, "Renaming conversation");
  }
  return response.json() as Promise<ConversationSummary>;
}

export async function previewAgentRouting(payload: {
  content: string;
  mode: ModelMode;
  sensitive: boolean;
  paid_call_confirmed: boolean;
}): Promise<AgentRouting | null> {
  const response = await fetch(`${API_BASE_URL}/chat/routing/preview`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw await responseError(response, "Previewing Agent route");
  }
  return response.json() as Promise<AgentRouting | null>;
}

export async function createConversation(payload: {
  title?: string;
  model_mode: ModelMode;
}): Promise<ConversationSummary> {
  const response = await fetch(`${API_BASE_URL}/chat/conversations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw await responseError(response, "Creating conversation");
  }
  return response.json() as Promise<ConversationSummary>;
}

export async function getConversation(
  conversationId: string,
  signal?: AbortSignal,
): Promise<ConversationDetail> {
  const response = await fetch(
    `${API_BASE_URL}/chat/conversations/${conversationId}`,
    { cache: "no-store", signal },
  );
  if (!response.ok) {
    throw await responseError(response, "Loading conversation");
  }
  return response.json() as Promise<ConversationDetail>;
}

export async function archiveConversation(
  conversationId: string,
): Promise<void> {
  const response = await fetch(
    `${API_BASE_URL}/chat/conversations/${conversationId}/archive`,
    { method: "POST" },
  );
  if (!response.ok) {
    throw await responseError(response, "Archiving conversation");
  }
}

export async function sendChatMessage(
  conversationId: string,
  payload: {
    content: string;
    mode: ModelMode;
    sensitive: boolean;
    paid_call_confirmed: boolean;
  },
): Promise<ChatSendResponse> {
  const response = await fetch(
    `${API_BASE_URL}/chat/conversations/${conversationId}/messages`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
  if (!response.ok) {
    throw await responseError(response, "Sending message");
  }
  return response.json() as Promise<ChatSendResponse>;
}

async function consumeChatStream(
  url: string,
  payload: unknown,
  handlers: ChatStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal,
  });
  if (!response.ok) {
    throw await responseError(response, "Streaming message");
  }
  if (!response.body) {
    throw new Error("浏览器未能建立流式连接。");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let sawDone = false;

  const dispatchBlock = (rawBlock: string) => {
    const block = rawBlock.replaceAll("\r\n", "\n").trim();
    if (!block) {
      return;
    }

    let eventName = "message";
    const dataLines: string[] = [];
    for (const line of block.split("\n")) {
      if (line.startsWith("event:")) {
        eventName = line.slice("event:".length).trim();
      } else if (line.startsWith("data:")) {
        dataLines.push(line.slice("data:".length).trimStart());
      }
    }
    if (dataLines.length === 0) {
      return;
    }

    const eventPayload = JSON.parse(dataLines.join("\n")) as unknown;
    if (eventName === "meta") {
      handlers.onMeta?.(eventPayload as ChatStreamMeta);
    } else if (eventName === "delta") {
      const delta = eventPayload as { content?: string };
      if (delta.content) {
        handlers.onDelta?.(delta.content);
      }
    } else if (eventName === "error") {
      const error = eventPayload as { message?: string };
      handlers.onError?.(error.message ?? "生成回复时发生错误。");
    } else if (eventName === "done") {
      sawDone = true;
      handlers.onDone?.(eventPayload as ChatSendResponse);
    }
  };

  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    buffer = buffer.replaceAll("\r\n", "\n");

    let boundary = buffer.indexOf("\n\n");
    while (boundary >= 0) {
      dispatchBlock(buffer.slice(0, boundary));
      buffer = buffer.slice(boundary + 2);
      boundary = buffer.indexOf("\n\n");
    }
    if (done) {
      break;
    }
  }

  if (buffer.trim()) {
    dispatchBlock(buffer);
  }
  if (!sawDone && !signal?.aborted) {
    throw new Error("流式连接提前结束，请重试。");
  }
}

export async function streamChatMessage(
  conversationId: string,
  payload: {
    content: string;
    mode: ModelMode;
    sensitive: boolean;
    request_id: string;
    paid_call_confirmed: boolean;
    use_knowledge: boolean;
  },
  handlers: ChatStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  return consumeChatStream(
    `${API_BASE_URL}/chat/conversations/${conversationId}/stream`,
    payload,
    handlers,
    signal,
  );
}

export async function streamRegenerateMessage(
  conversationId: string,
  assistantMessageId: string,
  payload: {
    mode: ModelMode;
    sensitive: boolean;
    request_id: string;
    paid_call_confirmed: boolean;
    use_knowledge: boolean;
  },
  handlers: ChatStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  return consumeChatStream(
    `${API_BASE_URL}/chat/conversations/${conversationId}/messages/${assistantMessageId}/regenerate/stream`,
    payload,
    handlers,
    signal,
  );
}

export async function cancelChatStream(requestId: string): Promise<void> {
  const response = await fetch(
    `${API_BASE_URL}/chat/streams/${requestId}/cancel`,
    { method: "POST" },
  );
  if (!response.ok) {
    throw await responseError(response, "Stopping generation");
  }
}

export async function getModelCalls(
  limit = 20,
  signal?: AbortSignal,
): Promise<ModelCallLog[]> {
  const response = await fetch(
    `${API_BASE_URL}/chat/model-calls?limit=${encodeURIComponent(limit)}`,
    { cache: "no-store", signal },
  );
  if (!response.ok) {
    throw await responseError(response, "Loading model calls");
  }
  return response.json() as Promise<ModelCallLog[]>;
}

export async function updateModelCallFeedback(
  modelCallId: string,
  payload: {
    rating: "helpful" | "not_helpful";
    task_completed?: boolean | null;
  },
): Promise<ModelCallLog> {
  const response = await fetch(
    `${API_BASE_URL}/chat/model-calls/${modelCallId}/feedback`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
  if (!response.ok) {
    throw await responseError(response, "Saving model feedback");
  }
  return response.json() as Promise<ModelCallLog>;
}

export async function getModelCallTrace(
  modelCallId: string,
  signal?: AbortSignal,
): Promise<ModelExecutionTrace> {
  const response = await fetch(
    `${API_BASE_URL}/chat/model-calls/${modelCallId}/trace`,
    { cache: "no-store", signal },
  );
  if (!response.ok) {
    throw await responseError(response, "Loading execution trace");
  }
  return response.json() as Promise<ModelExecutionTrace>;
}

export async function getEvaluationCases(
  signal?: AbortSignal,
): Promise<EvaluationCase[]> {
  const response = await fetch(`${API_BASE_URL}/evaluation/cases`, {
    cache: "no-store",
    signal,
  });
  if (!response.ok) {
    throw await responseError(response, "Loading evaluation cases");
  }
  return response.json() as Promise<EvaluationCase[]>;
}

export async function getEvaluationOverview(
  signal?: AbortSignal,
): Promise<EvaluationOverview> {
  const response = await fetch(`${API_BASE_URL}/evaluation/overview`, {
    cache: "no-store",
    signal,
  });
  if (!response.ok) {
    throw await responseError(response, "Loading evaluation overview");
  }
  return response.json() as Promise<EvaluationOverview>;
}

export async function getEvaluationRuns(
  limit = 30,
  signal?: AbortSignal,
): Promise<EvaluationRun[]> {
  const response = await fetch(
    `${API_BASE_URL}/evaluation/runs?limit=${encodeURIComponent(limit)}`,
    { cache: "no-store", signal },
  );
  if (!response.ok) {
    throw await responseError(response, "Loading evaluation runs");
  }
  return response.json() as Promise<EvaluationRun[]>;
}

export async function runEvaluation(payload: {
  case_id: string;
  provider: EvaluationProvider;
  paid_call_confirmed: boolean;
}): Promise<EvaluationRun> {
  const response = await fetch(`${API_BASE_URL}/evaluation/runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw await responseError(response, "Running evaluation");
  }
  return response.json() as Promise<EvaluationRun>;
}

export async function updateEvaluationFeedback(
  runId: string,
  rating: "helpful" | "not_helpful",
): Promise<EvaluationRun> {
  const response = await fetch(
    `${API_BASE_URL}/evaluation/runs/${runId}/feedback`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rating }),
    },
  );
  if (!response.ok) {
    throw await responseError(response, "Saving evaluation feedback");
  }
  return response.json() as Promise<EvaluationRun>;
}

export async function getMemoryShadowStatus(
  signal?: AbortSignal,
): Promise<MemoryShadowStatus> {
  const response = await fetch(`${API_BASE_URL}/memory-shadow/status`, {
    cache: "no-store",
    signal,
  });
  if (!response.ok) {
    throw await responseError(response, "Loading memory shadow status");
  }
  return response.json() as Promise<MemoryShadowStatus>;
}

export async function getMemoryShadowCases(
  signal?: AbortSignal,
): Promise<MemoryShadowCase[]> {
  const response = await fetch(`${API_BASE_URL}/memory-shadow/cases`, {
    cache: "no-store",
    signal,
  });
  if (!response.ok) {
    throw await responseError(response, "Loading memory shadow cases");
  }
  return response.json() as Promise<MemoryShadowCase[]>;
}

export async function getMemoryShadowRuns(
  limit = 12,
  signal?: AbortSignal,
): Promise<MemoryShadowRun[]> {
  const response = await fetch(
    `${API_BASE_URL}/memory-shadow/runs?limit=${encodeURIComponent(limit)}`,
    { cache: "no-store", signal },
  );
  if (!response.ok) {
    throw await responseError(response, "Loading memory shadow runs");
  }
  return response.json() as Promise<MemoryShadowRun[]>;
}

export async function runMemoryShadowCase(
  caseId: string,
): Promise<MemoryShadowRun> {
  const response = await fetch(`${API_BASE_URL}/memory-shadow/runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      case_id: caseId,
      engines: ["rule", "qwen", "mem0"],
    }),
  });
  if (!response.ok) {
    throw await responseError(response, "Running memory shadow evaluation");
  }
  return response.json() as Promise<MemoryShadowRun>;
}

export async function reviewMemoryShadowCandidate(
  candidateId: string,
  verdict: "correct" | "partial" | "incorrect",
): Promise<MemoryShadowCandidate> {
  const response = await fetch(
    `${API_BASE_URL}/memory-shadow/candidates/${candidateId}/review`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ verdict }),
    },
  );
  if (!response.ok) {
    throw await responseError(response, "Reviewing memory shadow candidate");
  }
  return response.json() as Promise<MemoryShadowCandidate>;
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
  const response = await fetch(url, {
    cache: "no-store",
    signal: options.signal,
  });
  if (!response.ok) {
    throw await responseError(response, "Loading memories");
  }
  return response.json() as Promise<Memory[]>;
}

export async function getMemoryStats(
  signal?: AbortSignal,
): Promise<MemoryStats> {
  const response = await fetch(`${API_BASE_URL}/memories/stats`, {
    cache: "no-store",
    signal,
  });
  if (!response.ok) {
    throw await responseError(response, "Loading memory stats");
  }
  return response.json() as Promise<MemoryStats>;
}

export async function createMemory(payload: {
  memory_type: MemoryType;
  content: string;
  importance: number;
  cloud_allowed: boolean;
}): Promise<Memory> {
  const response = await fetch(`${API_BASE_URL}/memories`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw await responseError(response, "Creating memory");
  }
  return response.json() as Promise<Memory>;
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
  const response = await fetch(`${API_BASE_URL}/memories/${memoryId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw await responseError(response, "Updating memory");
  }
  return response.json() as Promise<Memory>;
}

async function memoryAction(
  memoryId: string,
  action: "confirm" | "reject",
): Promise<Memory> {
  const response = await fetch(
    `${API_BASE_URL}/memories/${memoryId}/${action}`,
    { method: "POST" },
  );
  if (!response.ok) {
    throw await responseError(response, `${action} memory`);
  }
  return response.json() as Promise<Memory>;
}

export function confirmMemory(memoryId: string): Promise<Memory> {
  return memoryAction(memoryId, "confirm");
}

export function rejectMemory(memoryId: string): Promise<Memory> {
  return memoryAction(memoryId, "reject");
}

export async function deleteMemory(memoryId: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/memories/${memoryId}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    throw await responseError(response, "Deleting memory");
  }
}

export async function rememberMessage(
  messageId: string,
): Promise<{ memory: Memory; created: boolean }> {
  const response = await fetch(
    `${API_BASE_URL}/memories/from-message/${messageId}`,
    { method: "POST" },
  );
  if (!response.ok) {
    throw await responseError(response, "Remembering message");
  }
  return response.json() as Promise<{ memory: Memory; created: boolean }>;
}

export async function listGrowthWorkflows(
  signal?: AbortSignal,
): Promise<GrowthWorkflowRun[]> {
  const response = await fetch(`${API_BASE_URL}/growth/workflows`, {
    cache: "no-store",
    signal,
  });
  if (!response.ok) {
    throw await responseError(response, "Loading growth planning workflows");
  }
  return response.json() as Promise<GrowthWorkflowRun[]>;
}

export async function startGrowthWorkflow(payload: {
  objective: string;
  constraints?: string;
  target_date?: string;
  weekly_hours?: number;
  model_preference: GrowthModelPreference;
  cloud_allowed: boolean;
}): Promise<GrowthWorkflowRun> {
  const response = await fetch(`${API_BASE_URL}/growth/workflows`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw await responseError(response, "Starting growth planning workflow");
  }
  return response.json() as Promise<GrowthWorkflowRun>;
}

export async function supplementGrowthWorkflow(
  runId: string,
  payload: {
    constraints?: string;
    target_date?: string;
    weekly_hours?: number;
  },
): Promise<GrowthWorkflowRun> {
  const response = await fetch(
    `${API_BASE_URL}/growth/workflows/${runId}/supplement`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
  if (!response.ok) {
    throw await responseError(response, "Supplementing growth planning workflow");
  }
  return response.json() as Promise<GrowthWorkflowRun>;
}

export async function resumeGrowthWorkflow(
  runId: string,
  action:
    | "approve_deepseek"
    | "use_mimo"
    | "use_local"
    | "approve_draft"
    | "reject_draft",
): Promise<GrowthWorkflowRun> {
  const response = await fetch(
    `${API_BASE_URL}/growth/workflows/${runId}/resume`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action }),
    },
  );
  if (!response.ok) {
    throw await responseError(response, "Resuming growth planning workflow");
  }
  return response.json() as Promise<GrowthWorkflowRun>;
}

export async function updateGrowthWorkflowDraft(
  runId: string,
  payload: Pick<
    GrowthPlanDraft,
    "title" | "summary" | "milestones" | "tasks"
  >,
): Promise<GrowthWorkflowRun> {
  const response = await fetch(
    `${API_BASE_URL}/growth/workflows/${runId}/draft`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
  if (!response.ok) {
    throw await responseError(response, "Updating growth plan draft");
  }
  return response.json() as Promise<GrowthWorkflowRun>;
}

export async function cancelGrowthWorkflow(
  runId: string,
): Promise<GrowthWorkflowRun> {
  const response = await fetch(
    `${API_BASE_URL}/growth/workflows/${runId}/cancel`,
    { method: "POST" },
  );
  if (!response.ok) {
    throw await responseError(response, "Cancelling growth planning workflow");
  }
  return response.json() as Promise<GrowthWorkflowRun>;
}

export async function listResearchWorkflows(
  signal?: AbortSignal,
): Promise<ResearchWorkflowRun[]> {
  const response = await fetch(`${API_BASE_URL}/research/workflows`, {
    cache: "no-store",
    signal,
  });
  if (!response.ok) {
    throw await responseError(response, "读取研究工作流");
  }
  return response.json() as Promise<ResearchWorkflowRun[]>;
}

export async function startResearchWorkflow(payload: {
  question: string;
  scope?: string;
  category?: NewsCategory;
  max_sources: number;
  source_item_ids: string[];
  model_preference: ResearchModelPreference;
  cloud_allowed: boolean;
}): Promise<ResearchWorkflowRun> {
  const response = await fetch(`${API_BASE_URL}/research/workflows`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw await responseError(response, "启动多来源研究");
  }
  return response.json() as Promise<ResearchWorkflowRun>;
}

export async function addResearchIntelligenceSource(
  runId: string,
  itemId: string,
): Promise<ResearchWorkflowRun> {
  const response = await fetch(
    `${API_BASE_URL}/research/workflows/${runId}/sources/items/${itemId}`,
    { method: "POST" },
  );
  if (!response.ok) {
    throw await responseError(response, "添加情报来源");
  }
  return response.json() as Promise<ResearchWorkflowRun>;
}

export async function addResearchManualSource(
  runId: string,
  payload: {
    title: string;
    url: string;
    source_name: string;
    excerpt: string;
    trust_score: number;
  },
): Promise<ResearchWorkflowRun> {
  const response = await fetch(
    `${API_BASE_URL}/research/workflows/${runId}/sources`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
  if (!response.ok) {
    throw await responseError(response, "添加公开研究来源");
  }
  return response.json() as Promise<ResearchWorkflowRun>;
}

export async function resumeResearchWorkflow(
  runId: string,
  action:
    | "sources_ready"
    | "approve_deepseek"
    | "use_mimo"
    | "use_local"
    | "approve_report"
    | "reject_report",
): Promise<ResearchWorkflowRun> {
  const response = await fetch(
    `${API_BASE_URL}/research/workflows/${runId}/resume`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action }),
    },
  );
  if (!response.ok) {
    throw await responseError(response, "继续研究工作流");
  }
  return response.json() as Promise<ResearchWorkflowRun>;
}

export async function updateResearchReport(
  runId: string,
  payload: Pick<
    ResearchReport,
    | "title"
    | "executive_summary"
    | "facts"
    | "viewpoints"
    | "inferences"
    | "uncertainties"
    | "recommended_actions"
  >,
): Promise<ResearchWorkflowRun> {
  const response = await fetch(
    `${API_BASE_URL}/research/workflows/${runId}/report`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
  if (!response.ok) {
    throw await responseError(response, "保存研究报告草稿");
  }
  return response.json() as Promise<ResearchWorkflowRun>;
}

export async function cancelResearchWorkflow(
  runId: string,
): Promise<ResearchWorkflowRun> {
  const response = await fetch(
    `${API_BASE_URL}/research/workflows/${runId}/cancel`,
    { method: "POST" },
  );
  if (!response.ok) {
    throw await responseError(response, "取消研究工作流");
  }
  return response.json() as Promise<ResearchWorkflowRun>;
}

export async function getGrowthOverview(
  signal?: AbortSignal,
): Promise<GrowthOverview> {
  const response = await fetch(`${API_BASE_URL}/growth/overview`, {
    cache: "no-store",
    signal,
  });
  if (!response.ok) {
    throw await responseError(response, "Loading growth overview");
  }
  return response.json() as Promise<GrowthOverview>;
}

export async function listGoals(signal?: AbortSignal): Promise<Goal[]> {
  const response = await fetch(`${API_BASE_URL}/goals`, {
    cache: "no-store",
    signal,
  });
  if (!response.ok) {
    throw await responseError(response, "Loading goals");
  }
  return response.json() as Promise<Goal[]>;
}

export async function createGoal(payload: {
  title: string;
  description?: string;
  area: GrowthArea;
  target_date?: string;
}): Promise<Goal> {
  const response = await fetch(`${API_BASE_URL}/goals`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw await responseError(response, "Creating goal");
  }
  return response.json() as Promise<Goal>;
}

export async function updateGoal(
  goalId: string,
  payload: Partial<{
    title: string;
    description: string | null;
    area: GrowthArea;
    status: Goal["status"];
    target_date: string | null;
  }>,
): Promise<Goal> {
  const response = await fetch(`${API_BASE_URL}/goals/${goalId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw await responseError(response, "Updating goal");
  }
  return response.json() as Promise<Goal>;
}

export async function deleteGoal(goalId: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/goals/${goalId}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    throw await responseError(response, "Deleting goal");
  }
}

export async function createMilestone(
  goalId: string,
  payload: {
    title: string;
    description?: string;
    target_date?: string;
    order_index?: number;
  },
): Promise<Milestone> {
  const response = await fetch(
    `${API_BASE_URL}/goals/${goalId}/milestones`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
  if (!response.ok) {
    throw await responseError(response, "Creating milestone");
  }
  return response.json() as Promise<Milestone>;
}

export async function updateMilestone(
  milestoneId: string,
  payload: Partial<{
    title: string;
    description: string | null;
    status: Milestone["status"];
    target_date: string | null;
    order_index: number;
  }>,
): Promise<Milestone> {
  const response = await fetch(
    `${API_BASE_URL}/milestones/${milestoneId}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
  if (!response.ok) {
    throw await responseError(response, "Updating milestone");
  }
  return response.json() as Promise<Milestone>;
}

export async function listGrowthTasks(
  signal?: AbortSignal,
): Promise<GrowthTask[]> {
  const response = await fetch(`${API_BASE_URL}/tasks`, {
    cache: "no-store",
    signal,
  });
  if (!response.ok) {
    throw await responseError(response, "Loading tasks");
  }
  return response.json() as Promise<GrowthTask[]>;
}

export async function createGrowthTask(payload: {
  title: string;
  description?: string;
  area: GrowthArea;
  goal_id?: string;
  milestone_id?: string;
  priority: number;
  planned_date?: string;
  due_at?: string;
  reminder_at?: string;
  estimated_minutes: number;
  source_type?: string;
}): Promise<GrowthTask> {
  const response = await fetch(`${API_BASE_URL}/tasks`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw await responseError(response, "Creating task");
  }
  return response.json() as Promise<GrowthTask>;
}

export async function updateGrowthTask(
  taskId: string,
  payload: Partial<{
    title: string;
    description: string | null;
    area: GrowthArea;
    goal_id: string | null;
    milestone_id: string | null;
    priority: number;
    planned_date: string | null;
    due_at: string | null;
    reminder_at: string | null;
    estimated_minutes: number;
    blocker_reason: string | null;
  }>,
): Promise<GrowthTask> {
  const response = await fetch(`${API_BASE_URL}/tasks/${taskId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw await responseError(response, "Updating task");
  }
  return response.json() as Promise<GrowthTask>;
}

export async function transitionGrowthTask(
  taskId: string,
  action: "start" | "pause" | "complete" | "cancel",
  payload: {
    actual_minutes?: number;
    note?: string;
    blocker_reason?: string;
    completion_evidence?: string;
  } = {},
): Promise<GrowthTask> {
  const response = await fetch(
    `${API_BASE_URL}/tasks/${taskId}/${action}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
  if (!response.ok) {
    throw await responseError(response, `${action} task`);
  }
  return response.json() as Promise<GrowthTask>;
}

export async function logGrowthTaskTime(
  taskId: string,
  minutes: number,
  note?: string,
): Promise<GrowthTask> {
  const response = await fetch(`${API_BASE_URL}/tasks/${taskId}/time`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ minutes, note }),
  });
  if (!response.ok) {
    throw await responseError(response, "Logging task time");
  }
  return response.json() as Promise<GrowthTask>;
}

export async function deleteGrowthTask(taskId: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/tasks/${taskId}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    throw await responseError(response, "Deleting task");
  }
}

export async function getNotificationPreferences(
  signal?: AbortSignal,
): Promise<NotificationPreference> {
  const response = await fetch(`${API_BASE_URL}/notifications/preferences`, {
    cache: "no-store",
    signal,
  });
  if (!response.ok) {
    throw await responseError(response, "Loading reminder settings");
  }
  return response.json() as Promise<NotificationPreference>;
}

export async function updateNotificationPreferences(
  payload: Partial<
    Omit<NotificationPreference, "updated_at">
  >,
): Promise<NotificationPreference> {
  const response = await fetch(`${API_BASE_URL}/notifications/preferences`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw await responseError(response, "Saving reminder settings");
  }
  return response.json() as Promise<NotificationPreference>;
}

export async function listNotifications(
  signal?: AbortSignal,
): Promise<JarvisNotification[]> {
  const response = await fetch(`${API_BASE_URL}/notifications`, {
    cache: "no-store",
    signal,
  });
  if (!response.ok) {
    throw await responseError(response, "Loading reminders");
  }
  return response.json() as Promise<JarvisNotification[]>;
}

export async function listCompanionDevices(
  signal?: AbortSignal,
): Promise<CompanionDevice[]> {
  const response = await fetch(
    `${API_BASE_URL}/notifications/devices/status`,
    {
      cache: "no-store",
      signal,
    },
  );
  if (!response.ok) {
    throw await responseError(response, "Loading Windows Companion");
  }
  return response.json() as Promise<CompanionDevice[]>;
}

export async function createReminder(payload: {
  title: string;
  message: string;
  scheduled_for: string;
  task_id?: string;
  channels: NotificationChannel[];
  priority?: number;
  sensitive?: boolean;
}): Promise<JarvisNotification> {
  const response = await fetch(`${API_BASE_URL}/notifications`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw await responseError(response, "Creating reminder");
  }
  return response.json() as Promise<JarvisNotification>;
}

export async function snoozeReminder(
  notificationId: string,
  minutes: number,
): Promise<JarvisNotification> {
  const response = await fetch(
    `${API_BASE_URL}/notifications/${notificationId}/snooze`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ minutes }),
    },
  );
  if (!response.ok) {
    throw await responseError(response, "Snoozing reminder");
  }
  return response.json() as Promise<JarvisNotification>;
}

export async function dismissReminder(
  notificationId: string,
): Promise<JarvisNotification> {
  const response = await fetch(
    `${API_BASE_URL}/notifications/${notificationId}/dismiss`,
    { method: "POST" },
  );
  if (!response.ok) {
    throw await responseError(response, "Dismissing reminder");
  }
  return response.json() as Promise<JarvisNotification>;
}

export async function retryReminder(
  notificationId: string,
): Promise<JarvisNotification> {
  const response = await fetch(
    `${API_BASE_URL}/notifications/${notificationId}/retry`,
    { method: "POST" },
  );
  if (!response.ok) {
    throw await responseError(response, "Retrying reminder");
  }
  return response.json() as Promise<JarvisNotification>;
}

export async function deleteReminder(notificationId: string): Promise<void> {
  const response = await fetch(
    `${API_BASE_URL}/notifications/${notificationId}`,
    { method: "DELETE" },
  );
  if (!response.ok) {
    throw await responseError(response, "Deleting reminder history");
  }
}

export async function getTodayPlan(
  signal?: AbortSignal,
): Promise<DailyPlan | null> {
  const response = await fetch(`${API_BASE_URL}/plans/today`, {
    cache: "no-store",
    signal,
  });
  if (!response.ok) {
    throw await responseError(response, "Loading today's plan");
  }
  return response.json() as Promise<DailyPlan | null>;
}

export async function generateTodayPlan(
  capacityMinutes?: number,
): Promise<DailyPlan> {
  const response = await fetch(`${API_BASE_URL}/plans/today/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      capacity_minutes: capacityMinutes,
    }),
  });
  if (!response.ok) {
    throw await responseError(response, "Generating today's plan");
  }
  return response.json() as Promise<DailyPlan>;
}

export async function confirmTodayPlan(
  taskIds?: string[],
): Promise<DailyPlan> {
  const response = await fetch(`${API_BASE_URL}/plans/today/confirm`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ task_ids: taskIds }),
  });
  if (!response.ok) {
    throw await responseError(response, "Confirming today's plan");
  }
  return response.json() as Promise<DailyPlan>;
}

export async function resetTodayPlan(): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/plans/today`, {
    method: "DELETE",
  });
  if (!response.ok) {
    throw await responseError(response, "Resetting today's plan");
  }
}

export async function getWeeklyReview(
  signal?: AbortSignal,
): Promise<WeeklyReview | null> {
  const response = await fetch(`${API_BASE_URL}/reviews/weekly`, {
    cache: "no-store",
    signal,
  });
  if (!response.ok) {
    throw await responseError(response, "Loading weekly review");
  }
  return response.json() as Promise<WeeklyReview | null>;
}

export async function generateWeeklyReview(): Promise<WeeklyReview> {
  const response = await fetch(`${API_BASE_URL}/reviews/weekly/generate`, {
    method: "POST",
  });
  if (!response.ok) {
    throw await responseError(response, "Generating weekly review");
  }
  return response.json() as Promise<WeeklyReview>;
}

export async function updateWeeklyReview(
  reviewId: string,
  payload: { user_note?: string | null; status?: WeeklyReview["status"] },
): Promise<WeeklyReview> {
  const response = await fetch(
    `${API_BASE_URL}/reviews/weekly/${reviewId}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
  if (!response.ok) {
    throw await responseError(response, "Updating weekly review");
  }
  return response.json() as Promise<WeeklyReview>;
}

export async function getEnglishOverview(
  signal?: AbortSignal,
): Promise<EnglishOverview> {
  const response = await fetch(`${API_BASE_URL}/english/overview`, {
    cache: "no-store",
    signal,
  });
  if (!response.ok) {
    throw await responseError(response, "Loading English overview");
  }
  return response.json() as Promise<EnglishOverview>;
}

export async function listEnglishSessions(
  signal?: AbortSignal,
): Promise<EnglishSession[]> {
  const response = await fetch(`${API_BASE_URL}/english/sessions`, {
    cache: "no-store",
    signal,
  });
  if (!response.ok) {
    throw await responseError(response, "Loading English sessions");
  }
  return response.json() as Promise<EnglishSession[]>;
}

export async function getEnglishSession(
  sessionId: string,
  signal?: AbortSignal,
): Promise<EnglishSessionDetail> {
  const response = await fetch(
    `${API_BASE_URL}/english/sessions/${sessionId}`,
    { cache: "no-store", signal },
  );
  if (!response.ok) {
    throw await responseError(response, "Loading English session");
  }
  return response.json() as Promise<EnglishSessionDetail>;
}

export async function createEnglishSession(payload: {
  session_type: EnglishSessionType;
  topic?: string;
  correction_mode: EnglishCorrectionMode;
  level: EnglishLevel;
  processing_mode: EnglishProcessingMode;
}): Promise<EnglishSessionDetail> {
  const response = await fetch(`${API_BASE_URL}/english/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw await responseError(response, "Starting English session");
  }
  return response.json() as Promise<EnglishSessionDetail>;
}

export async function deleteEnglishSession(sessionId: string): Promise<void> {
  const response = await fetch(
    `${API_BASE_URL}/english/sessions/${sessionId}`,
    { method: "DELETE" },
  );
  if (!response.ok) {
    throw await responseError(response, "Deleting English session");
  }
}

export async function sendEnglishMessage(
  sessionId: string,
  payload: {
    content: string;
    input_mode: "text" | "voice_transcript";
  },
): Promise<EnglishSendResponse> {
  const response = await fetch(
    `${API_BASE_URL}/english/sessions/${sessionId}/messages`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
  if (!response.ok) {
    throw await responseError(response, "Sending English message");
  }
  return response.json() as Promise<EnglishSendResponse>;
}

export async function editEnglishTranscript(
  messageId: string,
  content: string,
): Promise<EnglishMessage> {
  const response = await fetch(
    `${API_BASE_URL}/english/messages/${messageId}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content }),
    },
  );
  if (!response.ok) {
    throw await responseError(response, "Editing English transcript");
  }
  return response.json() as Promise<EnglishMessage>;
}

export async function completeEnglishSession(
  sessionId: string,
): Promise<EnglishSessionCompleteResponse> {
  const response = await fetch(
    `${API_BASE_URL}/english/sessions/${sessionId}/complete`,
    { method: "POST" },
  );
  if (!response.ok) {
    throw await responseError(response, "Completing English session");
  }
  return response.json() as Promise<EnglishSessionCompleteResponse>;
}

export async function listEnglishMistakes(
  options: {
    query?: string;
    status?: EnglishMistakeStatus | "all";
    signal?: AbortSignal;
  } = {},
): Promise<EnglishMistake[]> {
  const url = new URL(`${API_BASE_URL}/english/mistakes`);
  if (options.query?.trim()) url.searchParams.set("q", options.query.trim());
  if (options.status && options.status !== "all") {
    url.searchParams.set("status", options.status);
  }
  const response = await fetch(url, {
    cache: "no-store",
    signal: options.signal,
  });
  if (!response.ok) {
    throw await responseError(response, "Loading English mistakes");
  }
  return response.json() as Promise<EnglishMistake[]>;
}

export async function updateEnglishMistake(
  mistakeId: string,
  payload: Partial<{
    corrected_text: string;
    category: string;
    explanation: string;
    cefr: EnglishLevel;
  }>,
): Promise<EnglishMistake> {
  const response = await fetch(
    `${API_BASE_URL}/english/mistakes/${mistakeId}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
  if (!response.ok) {
    throw await responseError(response, "Updating English mistake");
  }
  return response.json() as Promise<EnglishMistake>;
}

async function englishMistakeAction(
  mistakeId: string,
  action: "reject" | "master" | "dispute",
): Promise<EnglishMistake> {
  const response = await fetch(
    `${API_BASE_URL}/english/mistakes/${mistakeId}/${action}`,
    { method: "POST" },
  );
  if (!response.ok) {
    throw await responseError(response, `${action} English mistake`);
  }
  return response.json() as Promise<EnglishMistake>;
}

export async function confirmEnglishMistake(
  mistakeId: string,
  reviewAt?: string,
): Promise<EnglishMistake> {
  const response = await fetch(
    `${API_BASE_URL}/english/mistakes/${mistakeId}/confirm`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ review_at: reviewAt }),
    },
  );
  if (!response.ok) {
    throw await responseError(response, "Confirming English mistake");
  }
  return response.json() as Promise<EnglishMistake>;
}

export function rejectEnglishMistake(
  mistakeId: string,
): Promise<EnglishMistake> {
  return englishMistakeAction(mistakeId, "reject");
}

export function masterEnglishMistake(
  mistakeId: string,
): Promise<EnglishMistake> {
  return englishMistakeAction(mistakeId, "master");
}

export function disputeEnglishMistake(
  mistakeId: string,
): Promise<EnglishMistake> {
  return englishMistakeAction(mistakeId, "dispute");
}

export async function deleteEnglishMistake(mistakeId: string): Promise<void> {
  const response = await fetch(
    `${API_BASE_URL}/english/mistakes/${mistakeId}`,
    { method: "DELETE" },
  );
  if (!response.ok) {
    throw await responseError(response, "Deleting English mistake");
  }
}

export async function listDueEnglishReviews(
  signal?: AbortSignal,
): Promise<EnglishReview[]> {
  const response = await fetch(`${API_BASE_URL}/english/reviews/due`, {
    cache: "no-store",
    signal,
  });
  if (!response.ok) {
    throw await responseError(response, "Loading due English reviews");
  }
  return response.json() as Promise<EnglishReview[]>;
}

export async function listUpcomingEnglishReviews(
  signal?: AbortSignal,
): Promise<EnglishReview[]> {
  const response = await fetch(`${API_BASE_URL}/english/reviews/upcoming`, {
    cache: "no-store",
    signal,
  });
  if (!response.ok) {
    throw await responseError(response, "Loading upcoming English reviews");
  }
  return response.json() as Promise<EnglishReview[]>;
}

export async function submitEnglishReview(
  reviewId: string,
  payload: {
    submitted_answer?: string;
    result: EnglishReviewResult;
  },
): Promise<EnglishReview> {
  const response = await fetch(
    `${API_BASE_URL}/english/reviews/${reviewId}/result`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
  if (!response.ok) {
    throw await responseError(response, "Saving English review");
  }
  return response.json() as Promise<EnglishReview>;
}

export async function getIntelligenceOverview(
  signal?: AbortSignal,
): Promise<IntelligenceOverview> {
  const response = await fetch(`${API_BASE_URL}/intelligence/overview`, {
    cache: "no-store",
    signal,
  });
  if (!response.ok) {
    throw await responseError(response, "Loading intelligence overview");
  }
  return response.json() as Promise<IntelligenceOverview>;
}

export async function getTodayIntelligenceBrief(
  signal?: AbortSignal,
): Promise<DailyBrief | null> {
  const response = await fetch(
    `${API_BASE_URL}/intelligence/briefs/today`,
    { cache: "no-store", signal },
  );
  if (!response.ok) {
    throw await responseError(response, "Loading today's intelligence");
  }
  return response.json() as Promise<DailyBrief | null>;
}

export async function generateIntelligenceBrief(payload: {
  processing_mode: "standard" | "local";
  refresh_sources: boolean;
  notify: boolean;
  use_ai?: boolean;
}): Promise<DailyBrief> {
  const response = await fetch(
    `${API_BASE_URL}/intelligence/briefs/generate`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
  if (!response.ok) {
    throw await responseError(response, "Generating intelligence brief");
  }
  return response.json() as Promise<DailyBrief>;
}

export async function listNewsItems(
  options: {
    query?: string;
    category?: NewsCategory | "all";
    status?: NewsItem["status"] | "all";
    signal?: AbortSignal;
  } = {},
): Promise<NewsItem[]> {
  const url = new URL(`${API_BASE_URL}/intelligence/items`);
  if (options.query?.trim()) url.searchParams.set("q", options.query.trim());
  if (options.category && options.category !== "all") {
    url.searchParams.set("category", options.category);
  }
  if (options.status && options.status !== "all") {
    url.searchParams.set("status", options.status);
  }
  const response = await fetch(url, {
    cache: "no-store",
    signal: options.signal,
  });
  if (!response.ok) {
    throw await responseError(response, "Loading intelligence items");
  }
  return response.json() as Promise<NewsItem[]>;
}

export async function listNewsSources(
  signal?: AbortSignal,
): Promise<NewsSource[]> {
  const response = await fetch(`${API_BASE_URL}/intelligence/sources`, {
    cache: "no-store",
    signal,
  });
  if (!response.ok) {
    throw await responseError(response, "Loading intelligence sources");
  }
  return response.json() as Promise<NewsSource[]>;
}

export async function createNewsSource(payload: {
  name: string;
  feed_url: string;
  site_url?: string;
  default_category: NewsCategory;
  language: string;
  trust_score: number;
  refresh_interval_minutes: number;
}): Promise<NewsSource> {
  const response = await fetch(`${API_BASE_URL}/intelligence/sources`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw await responseError(response, "Adding RSS source");
  }
  return response.json() as Promise<NewsSource>;
}

export async function updateNewsSource(
  sourceId: string,
  payload: Partial<{
    name: string;
    feed_url: string;
    site_url: string | null;
    default_category: NewsCategory;
    language: string;
    trust_score: number;
    enabled: boolean;
    refresh_interval_minutes: number;
  }>,
): Promise<NewsSource> {
  const response = await fetch(
    `${API_BASE_URL}/intelligence/sources/${sourceId}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
  if (!response.ok) {
    throw await responseError(response, "Updating RSS source");
  }
  return response.json() as Promise<NewsSource>;
}

export async function deleteNewsSource(sourceId: string): Promise<void> {
  const response = await fetch(
    `${API_BASE_URL}/intelligence/sources/${sourceId}`,
    { method: "DELETE" },
  );
  if (!response.ok) {
    throw await responseError(response, "Deleting RSS source");
  }
}

export async function refreshNewsSource(
  sourceId: string,
): Promise<SourceRefresh> {
  const response = await fetch(
    `${API_BASE_URL}/intelligence/sources/${sourceId}/refresh`,
    { method: "POST" },
  );
  if (!response.ok) {
    throw await responseError(response, "Refreshing RSS source");
  }
  return response.json() as Promise<SourceRefresh>;
}

export async function refreshAllNewsSources(): Promise<RefreshAllSources> {
  const response = await fetch(`${API_BASE_URL}/intelligence/refresh`, {
    method: "POST",
  });
  if (!response.ok) {
    throw await responseError(response, "Refreshing RSS sources");
  }
  return response.json() as Promise<RefreshAllSources>;
}

export async function createManualNewsItem(payload: {
  title: string;
  url: string;
  source_name: string;
  source_excerpt: string;
  category: NewsCategory;
  published_at?: string;
  language?: string;
}): Promise<NewsItem> {
  const response = await fetch(`${API_BASE_URL}/intelligence/items/manual`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw await responseError(response, "Adding a manual intelligence item");
  }
  return response.json() as Promise<NewsItem>;
}

export async function updateIntelligencePreferences(
  payload: Partial<IntelligencePreferences>,
): Promise<IntelligencePreferences> {
  const response = await fetch(`${API_BASE_URL}/intelligence/preferences`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw await responseError(response, "Saving intelligence interests");
  }
  return response.json() as Promise<IntelligencePreferences>;
}

export async function newsItemAction(
  itemId: string,
  action: "read" | "save" | "ignore",
): Promise<{
  item: NewsItem;
  interest_weights: IntelligencePreferences;
}> {
  const response = await fetch(
    `${API_BASE_URL}/intelligence/items/${itemId}/${action}`,
    { method: "POST" },
  );
  if (!response.ok) {
    throw await responseError(response, `${action} intelligence item`);
  }
  return response.json() as Promise<{
    item: NewsItem;
    interest_weights: IntelligencePreferences;
  }>;
}

export async function convertNewsItemToTask(
  itemId: string,
  payload: {
    title?: string;
    priority?: number;
    estimated_minutes?: number;
  } = {},
): Promise<{ item: NewsItem; task_id: string; task_title: string }> {
  const response = await fetch(
    `${API_BASE_URL}/intelligence/items/${itemId}/task`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
  if (!response.ok) {
    throw await responseError(response, "Converting intelligence to task");
  }
  return response.json() as Promise<{
    item: NewsItem;
    task_id: string;
    task_title: string;
  }>;
}

export async function getInvestmentOverview(
  signal?: AbortSignal,
): Promise<InvestmentOverview> {
  const response = await fetch(`${API_BASE_URL}/investment/overview`, {
    cache: "no-store",
    signal,
  });
  if (!response.ok) {
    throw await responseError(response, "Loading investment overview");
  }
  return response.json() as Promise<InvestmentOverview>;
}

export async function getMonitoringOverview(
  signal?: AbortSignal,
): Promise<MonitoringOverview> {
  const response = await fetch(`${API_BASE_URL}/monitoring/overview`, {
    cache: "no-store",
    signal,
  });
  if (!response.ok) {
    throw await responseError(response, "Loading monitoring overview");
  }
  return response.json() as Promise<MonitoringOverview>;
}

export async function listMonitorRules(
  signal?: AbortSignal,
): Promise<MonitorRule[]> {
  const response = await fetch(`${API_BASE_URL}/monitoring/rules`, {
    cache: "no-store",
    signal,
  });
  if (!response.ok) {
    throw await responseError(response, "Loading monitor rules");
  }
  return response.json() as Promise<MonitorRule[]>;
}

export async function createMonitorRule(payload: {
  name: string;
  monitor_type: MonitorType;
  asset_id?: string;
  thesis_id?: string;
  keywords: string[];
  regions: string[];
  risk_channels: string[];
  min_severity: number;
  cooldown_minutes: number;
  notify_enabled: boolean;
  cloud_allowed?: boolean;
}): Promise<MonitorRule> {
  const response = await fetch(`${API_BASE_URL}/monitoring/rules`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw await responseError(response, "Creating monitor rule");
  }
  return response.json() as Promise<MonitorRule>;
}

export async function updateMonitorRule(
  ruleId: string,
  payload: Partial<
    Pick<
      MonitorRule,
      | "name"
      | "keywords"
      | "regions"
      | "risk_channels"
      | "min_severity"
      | "cooldown_minutes"
      | "notify_enabled"
      | "enabled"
      | "cloud_allowed"
    >
  >,
): Promise<MonitorRule> {
  const response = await fetch(`${API_BASE_URL}/monitoring/rules/${ruleId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw await responseError(response, "Updating monitor rule");
  }
  return response.json() as Promise<MonitorRule>;
}

export async function deleteMonitorRule(ruleId: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/monitoring/rules/${ruleId}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    throw await responseError(response, "Deleting monitor rule");
  }
}

export async function listMonitorEvents(
  options: {
    status?: MonitorEvent["status"] | "all";
    minSeverity?: number;
    signal?: AbortSignal;
  } = {},
): Promise<MonitorEvent[]> {
  const url = new URL(`${API_BASE_URL}/monitoring/events`);
  url.searchParams.set("status", options.status ?? "new");
  url.searchParams.set("min_severity", String(options.minSeverity ?? 1));
  const response = await fetch(url, { cache: "no-store", signal: options.signal });
  if (!response.ok) {
    throw await responseError(response, "Loading monitor events");
  }
  return response.json() as Promise<MonitorEvent[]>;
}

export async function scanMonitoring(payload: {
  lookback_hours?: number;
  notify?: boolean;
} = {}): Promise<MonitoringScanResult> {
  const response = await fetch(`${API_BASE_URL}/monitoring/scan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ lookback_hours: 72, notify: true, ...payload }),
  });
  if (!response.ok) {
    throw await responseError(response, "Scanning monitored events");
  }
  return response.json() as Promise<MonitoringScanResult>;
}

export async function updateMonitorEvent(
  eventId: string,
  action: "acknowledge" | "dismiss",
): Promise<MonitorEvent> {
  const response = await fetch(
    `${API_BASE_URL}/monitoring/events/${eventId}/action`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action }),
    },
  );
  if (!response.ok) {
    throw await responseError(response, "Updating monitor event");
  }
  return response.json() as Promise<MonitorEvent>;
}

export async function listInvestmentAssets(
  signal?: AbortSignal,
): Promise<InvestmentAsset[]> {
  const response = await fetch(`${API_BASE_URL}/investment/assets`, {
    cache: "no-store",
    signal,
  });
  if (!response.ok) {
    throw await responseError(response, "Loading investment assets");
  }
  return response.json() as Promise<InvestmentAsset[]>;
}

export async function createInvestmentAsset(payload: {
  name: string;
  symbol: string;
  market: string;
  asset_type: InvestmentAssetType;
  currency: string;
  latest_price?: number;
  latest_price_date?: string;
  notes?: string;
}): Promise<InvestmentAsset> {
  const response = await fetch(`${API_BASE_URL}/investment/assets`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw await responseError(response, "Creating investment asset");
  }
  return response.json() as Promise<InvestmentAsset>;
}

export async function updateInvestmentAsset(
  assetId: string,
  payload: Partial<{
    name: string;
    symbol: string;
    market: string;
    asset_type: InvestmentAssetType;
    currency: string;
    latest_price: number | null;
    latest_price_date: string | null;
    notes: string | null;
  }>,
): Promise<InvestmentAsset> {
  const response = await fetch(
    `${API_BASE_URL}/investment/assets/${assetId}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
  if (!response.ok) {
    throw await responseError(response, "Updating investment asset");
  }
  return response.json() as Promise<InvestmentAsset>;
}

export async function deleteInvestmentAsset(assetId: string): Promise<void> {
  const response = await fetch(
    `${API_BASE_URL}/investment/assets/${assetId}`,
    { method: "DELETE" },
  );
  if (!response.ok) {
    throw await responseError(response, "Deleting investment asset");
  }
}

export async function createInitialPosition(payload: {
  asset_id: string;
  quantity: number;
  average_cost: number;
  fees: number;
  transaction_date: string;
  reason: string;
  target_allocation?: number;
  risk_level: InvestmentRisk;
}): Promise<PortfolioPosition> {
  const response = await fetch(`${API_BASE_URL}/investment/positions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw await responseError(response, "Creating initial position");
  }
  return response.json() as Promise<PortfolioPosition>;
}

export async function updatePortfolioPosition(
  positionId: string,
  payload: Partial<{
    target_allocation: number | null;
    risk_level: InvestmentRisk;
  }>,
): Promise<PortfolioPosition> {
  const response = await fetch(
    `${API_BASE_URL}/investment/positions/${positionId}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
  if (!response.ok) {
    throw await responseError(response, "Updating portfolio position");
  }
  return response.json() as Promise<PortfolioPosition>;
}

export async function listInvestmentTransactions(
  signal?: AbortSignal,
): Promise<InvestmentTransaction[]> {
  const response = await fetch(`${API_BASE_URL}/investment/transactions`, {
    cache: "no-store",
    signal,
  });
  if (!response.ok) {
    throw await responseError(response, "Loading investment transactions");
  }
  return response.json() as Promise<InvestmentTransaction[]>;
}

export async function createInvestmentTransaction(payload: {
  asset_id: string;
  transaction_type: InvestmentTransactionType;
  transaction_date: string;
  quantity?: number;
  unit_price?: number;
  cash_amount?: number;
  fees: number;
  reason?: string;
  notes?: string;
}): Promise<InvestmentTransaction> {
  const response = await fetch(`${API_BASE_URL}/investment/transactions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw await responseError(response, "Creating investment transaction");
  }
  return response.json() as Promise<InvestmentTransaction>;
}

export async function updateInvestmentTransaction(
  transactionId: string,
  payload: Partial<{
    transaction_type: InvestmentTransactionType;
    transaction_date: string;
    quantity: number | null;
    unit_price: number | null;
    cash_amount: number | null;
    fees: number;
    reason: string | null;
    notes: string | null;
  }>,
): Promise<InvestmentTransaction> {
  const response = await fetch(
    `${API_BASE_URL}/investment/transactions/${transactionId}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
  if (!response.ok) {
    throw await responseError(response, "Updating investment transaction");
  }
  return response.json() as Promise<InvestmentTransaction>;
}

export async function deleteInvestmentTransaction(
  transactionId: string,
): Promise<void> {
  const response = await fetch(
    `${API_BASE_URL}/investment/transactions/${transactionId}`,
    { method: "DELETE" },
  );
  if (!response.ok) {
    throw await responseError(response, "Deleting investment transaction");
  }
}

export async function listInvestmentTheses(
  signal?: AbortSignal,
): Promise<InvestmentThesis[]> {
  const response = await fetch(`${API_BASE_URL}/investment/theses`, {
    cache: "no-store",
    signal,
  });
  if (!response.ok) {
    throw await responseError(response, "Loading investment theses");
  }
  return response.json() as Promise<InvestmentThesis[]>;
}

export async function createInvestmentThesis(payload: {
  asset_id: string;
  title: string;
  original_reason: string;
  current_view?: string;
  key_assumptions: string[];
  watch_events: string[];
  invalidation_conditions: string[];
  risk_level: InvestmentRisk;
  cloud_allowed: boolean;
}): Promise<InvestmentThesis> {
  const response = await fetch(`${API_BASE_URL}/investment/theses`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw await responseError(response, "Creating investment thesis");
  }
  return response.json() as Promise<InvestmentThesis>;
}

export async function updateInvestmentThesis(
  thesisId: string,
  payload: Partial<{
    title: string;
    current_view: string | null;
    key_assumptions: string[];
    watch_events: string[];
    invalidation_conditions: string[];
    risk_level: InvestmentRisk;
    status: InvestmentThesis["status"];
    cloud_allowed: boolean;
  }>,
): Promise<InvestmentThesis> {
  const response = await fetch(
    `${API_BASE_URL}/investment/theses/${thesisId}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
  if (!response.ok) {
    throw await responseError(response, "Updating investment thesis");
  }
  return response.json() as Promise<InvestmentThesis>;
}

export async function listInvestmentReviews(
  signal?: AbortSignal,
): Promise<InvestmentReview[]> {
  const response = await fetch(`${API_BASE_URL}/investment/reviews`, {
    cache: "no-store",
    signal,
  });
  if (!response.ok) {
    throw await responseError(response, "Loading investment reviews");
  }
  return response.json() as Promise<InvestmentReview[]>;
}

export async function generateInvestmentReview(payload: {
  asset_id: string;
  review_type: InvestmentReview["review_type"];
}): Promise<InvestmentReview> {
  const response = await fetch(
    `${API_BASE_URL}/investment/reviews/generate`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
  if (!response.ok) {
    throw await responseError(response, "Generating investment review");
  }
  return response.json() as Promise<InvestmentReview>;
}

export async function updateInvestmentReview(
  reviewId: string,
  payload: Partial<{
    thesis_assessment: InvestmentReview["thesis_assessment"];
    summary: string;
    risks: string[];
    questions: string[];
    user_note: string | null;
    status: InvestmentReview["status"];
  }>,
): Promise<InvestmentReview> {
  const response = await fetch(
    `${API_BASE_URL}/investment/reviews/${reviewId}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
  if (!response.ok) {
    throw await responseError(response, "Updating investment review");
  }
  return response.json() as Promise<InvestmentReview>;
}

export async function listAssetNews(
  assetId: string,
  candidates: boolean,
  signal?: AbortSignal,
): Promise<RelatedInvestmentNews[]> {
  const url = new URL(`${API_BASE_URL}/investment/assets/${assetId}/news`);
  if (candidates) url.searchParams.set("candidates", "true");
  const response = await fetch(url, { cache: "no-store", signal });
  if (!response.ok) {
    throw await responseError(response, "Loading related investment news");
  }
  return response.json() as Promise<RelatedInvestmentNews[]>;
}

export async function linkAssetNews(
  assetId: string,
  newsItemId: string,
  relationshipNote?: string,
): Promise<RelatedInvestmentNews> {
  const response = await fetch(
    `${API_BASE_URL}/investment/assets/${assetId}/news/${newsItemId}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ relationship_note: relationshipNote || null }),
    },
  );
  if (!response.ok) {
    throw await responseError(response, "Linking investment news");
  }
  return response.json() as Promise<RelatedInvestmentNews>;
}

export async function unlinkAssetNews(
  assetId: string,
  newsItemId: string,
): Promise<void> {
  const response = await fetch(
    `${API_BASE_URL}/investment/assets/${assetId}/news/${newsItemId}`,
    { method: "DELETE" },
  );
  if (!response.ok) {
    throw await responseError(response, "Unlinking investment news");
  }
}

export type CareerProviderStatus = {
  enabled: boolean;
  configured: boolean;
  status: string;
  loopback_only: boolean;
  signed_requests: boolean;
  read_only: boolean;
  isolated_context: boolean;
  persistent_profile: boolean;
  credentials_configured: boolean;
  uploads_enabled: boolean;
  downloads_enabled: boolean;
  submissions_enabled: boolean;
  detail?: string | null;
};

export type CareerSource = {
  id: string;
  name: string;
  company_name: string;
  start_url: string;
  allowed_hosts: string[];
  source_kind: "official" | "sandbox";
  enabled: boolean;
  read_only_confirmed: boolean;
  last_checked_at?: string | null;
  last_error?: string | null;
  created_at: string;
  updated_at: string;
};

export type CareerResearchRun = {
  id: string;
  source_id: string;
  tool_execution_id?: string | null;
  status: "created" | "running" | "completed" | "failed";
  query: string;
  max_pages: number;
  pages_visited: number;
  opportunities_found: number;
  injection_signal_count: number;
  started_at?: string | null;
  completed_at?: string | null;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
};

export type CareerEvidencePage = {
  id: string;
  run_id: string;
  source_id: string;
  url: string;
  title: string;
  fetched_at: string;
  http_status: number;
  rendered: false;
  content_sha256: string;
  text_excerpt: string;
  injection_signals: string[];
  screenshot_sha256: string;
  screenshot_available: boolean;
  created_at: string;
};

export type CareerOpportunity = {
  id: string;
  source_id: string;
  last_run_id: string;
  company: string;
  title: string;
  location: string;
  employment_type: string;
  description: string;
  requirements: string;
  skills: string[];
  published_at?: string | null;
  valid_until?: string | null;
  apply_url?: string | null;
  source_url: string;
  source_fingerprint: string;
  content_sha256: string;
  match_score: number;
  match_level: "unknown" | "low" | "medium" | "high";
  match_reasons: string[];
  missing_skills: string[];
  first_seen_at: string;
  last_seen_at: string;
  created_at: string;
  updated_at: string;
};

export type CareerOverview = {
  provider: CareerProviderStatus;
  sources: CareerSource[];
  runs: CareerResearchRun[];
  opportunities: CareerOpportunity[];
  evidence: CareerEvidencePage[];
};

export async function getCareerOverview(
  signal?: AbortSignal,
): Promise<CareerOverview> {
  const response = await fetch(`${API_BASE_URL}/career/overview`, {
    cache: "no-store",
    signal,
  });
  if (!response.ok) {
    throw await responseError(response, "读取求职雷达");
  }
  return response.json() as Promise<CareerOverview>;
}

export async function createCareerSandbox(): Promise<CareerSource> {
  const response = await fetch(`${API_BASE_URL}/career/sources/sandbox`, {
    method: "POST",
  });
  if (!response.ok) {
    throw await responseError(response, "建立安全演练来源");
  }
  return response.json() as Promise<CareerSource>;
}

export async function createCareerSource(payload: {
  name: string;
  company_name: string;
  start_url: string;
  allowed_hosts: string[];
  confirmed_read_only_scope: true;
}): Promise<CareerSource> {
  const response = await fetch(`${API_BASE_URL}/career/sources`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw await responseError(response, "添加招聘来源");
  }
  return response.json() as Promise<CareerSource>;
}

export async function runCareerResearch(
  sourceId: string,
  payload: { query: string; max_pages: number },
): Promise<CareerResearchRun> {
  const response = await fetch(
    `${API_BASE_URL}/career/sources/${sourceId}/research`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
  if (!response.ok) {
    throw await responseError(response, "运行只读岗位研究");
  }
  return response.json() as Promise<CareerResearchRun>;
}

export function careerEvidenceScreenshotUrl(evidenceId: string) {
  return `${API_BASE_URL}/career/evidence/${evidenceId}/screenshot`;
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
  const response = await fetch(`${API_BASE_URL}/observatory/overview`, {
    cache: "no-store",
    signal,
  });
  if (!response.ok) {
    throw await responseError(response, "读取运行观测台");
  }
  return response.json() as Promise<ObservatoryOverview>;
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
  const response = await fetch(url, { cache: "no-store", signal: options.signal });
  if (!response.ok) {
    throw await responseError(response, "读取 Agent 运行记录");
  }
  return response.json() as Promise<ObservatoryRunSummary[]>;
}

export async function getObservatoryRun(
  runId: string,
  signal?: AbortSignal,
): Promise<ObservatoryRunDetail> {
  const response = await fetch(`${API_BASE_URL}/observatory/runs/${runId}`, {
    cache: "no-store",
    signal,
  });
  if (!response.ok) {
    throw await responseError(response, "读取运行详情");
  }
  return response.json() as Promise<ObservatoryRunDetail>;
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
  const response = await fetch(url, { cache: "no-store", signal: options.signal });
  if (!response.ok) {
    throw await responseError(response, "读取工具执行记录");
  }
  return response.json() as Promise<ObservatoryToolExecution[]>;
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
  const response = await fetch(url, { cache: "no-store", signal: options.signal });
  if (!response.ok) {
    throw await responseError(response, "读取审批观测记录");
  }
  return response.json() as Promise<ObservatoryApproval[]>;
}

export async function listObservatoryErrors(
  options: {
    limit?: number;
    signal?: AbortSignal;
  } = {},
): Promise<ObservatoryError[]> {
  const url = new URL(`${API_BASE_URL}/observatory/errors`);
  url.searchParams.set("limit", String(options.limit ?? 50));
  const response = await fetch(url, { cache: "no-store", signal: options.signal });
  if (!response.ok) {
    throw await responseError(response, "读取运行错误记录");
  }
  return response.json() as Promise<ObservatoryError[]>;
}

export type CostPriceRule = {
  provider: string;
  model_pattern: string;
  input_per_million: number;
  output_per_million: number;
  currency: string;
  is_estimate: boolean;
  note: string;
};

export type CostProviderSummary = {
  provider: string;
  calls: number;
  successful_calls: number;
  confirmed_calls: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  avg_latency_ms?: number | null;
  avg_tokens_per_second?: number | null;
  estimated_cost: number;
  cost_note: string;
};

export type CostDailyPoint = {
  date: string;
  calls: number;
  total_tokens: number;
  deepseek_estimated_cost: number;
};

export type OllamaModelMetric = {
  name: string;
  size_bytes: number;
  size_vram_bytes: number;
  processor: string;
};

export type OllamaResourceStatus = {
  status: "ready" | "offline";
  process_cpu_percent?: number | null;
  process_memory_mb?: number | null;
  loaded_models: OllamaModelMetric[];
  detail?: string | null;
};

export type CostOverview = {
  generated_at: string;
  days: number;
  currency: string;
  disclaimer: string;
  price_rules: CostPriceRule[];
  total_calls: number;
  total_successful_calls: number;
  total_tokens: number;
  deepseek_estimated_total: number;
  deepseek_confirmed_estimated_total: number;
  providers: CostProviderSummary[];
  daily: CostDailyPoint[];
  local: OllamaResourceStatus;
};

export type CostCallItem = {
  id: string;
  source: "chat" | "workflow";
  provider_used: string;
  model_used: string;
  success: boolean;
  prompt_tokens?: number | null;
  completion_tokens?: number | null;
  total_tokens?: number | null;
  latency_ms?: number | null;
  tokens_per_second?: number | null;
  user_confirmed: boolean;
  estimated_cost: number;
  created_at: string;
};

export async function getCostOverview(
  days = 30,
  signal?: AbortSignal,
): Promise<CostOverview> {
  const url = new URL(`${API_BASE_URL}/cost/overview`);
  url.searchParams.set("days", String(days));
  const response = await fetch(url, { cache: "no-store", signal });
  if (!response.ok) {
    throw await responseError(response, "读取费用统计");
  }
  return response.json() as Promise<CostOverview>;
}

export async function listCostCalls(
  limit = 50,
  signal?: AbortSignal,
): Promise<CostCallItem[]> {
  const url = new URL(`${API_BASE_URL}/cost/calls`);
  url.searchParams.set("limit", String(limit));
  const response = await fetch(url, { cache: "no-store", signal });
  if (!response.ok) {
    throw await responseError(response, "读取模型调用明细");
  }
  return response.json() as Promise<CostCallItem[]>;
}

export type ContextBudgetInfo = {
  agent_id: string;
  budget_chars: number;
  sections: Record<string, number>;
};

export type ContextSectionStat = {
  key: string;
  chars: number;
  count: number;
};

export type ContextAssemblyItem = {
  id: string;
  agent_id: string;
  provider_used: string;
  budget_chars: number;
  total_chars: number;
  estimated_tokens: number;
  trimmed_chars: number;
  sections: ContextSectionStat[];
  created_at: string;
};

export type ContextOverview = {
  generated_at: string;
  enabled: boolean;
  estimate_chars_per_token: number;
  budgets: ContextBudgetInfo[];
  assemblies_total: number;
  assemblies_today: number;
  avg_total_chars?: number | null;
  avg_estimated_tokens?: number | null;
  total_trimmed_today: number;
  disclaimer: string;
};

export type ContextAssemblyInfo = {
  assembly_id?: string | null;
  agent_id: string;
  budget_chars: number;
  total_chars: number;
  estimated_tokens: number;
  trimmed_chars: number;
  sections: ContextSectionStat[];
};

export async function getContextOverview(
  signal?: AbortSignal,
): Promise<ContextOverview> {
  const response = await fetch(`${API_BASE_URL}/context/overview`, {
    cache: "no-store",
    signal,
  });
  if (!response.ok) {
    throw await responseError(response, "读取上下文预算");
  }
  return response.json() as Promise<ContextOverview>;
}

export async function listContextAssemblies(
  limit = 50,
  signal?: AbortSignal,
): Promise<ContextAssemblyItem[]> {
  const url = new URL(`${API_BASE_URL}/context/assemblies`);
  url.searchParams.set("limit", String(limit));
  const response = await fetch(url, { cache: "no-store", signal });
  if (!response.ok) {
    throw await responseError(response, "读取上下文装配记录");
  }
  return response.json() as Promise<ContextAssemblyItem[]>;
}

export type PersonalitySettings = {
  nickname: string;
  tone: "balanced" | "casual" | "formal";
  emoji: boolean;
  extra_rules: string[];
};

export type PersonalityOverview = {
  name: string;
  tones: string[];
  settings: PersonalitySettings;
  prompts: Record<string, string>;
  boundaries: string[];
  disclaimer: string;
};

export async function getPersonalityOverview(
  signal?: AbortSignal,
): Promise<PersonalityOverview> {
  const response = await fetch(`${API_BASE_URL}/personality/overview`, {
    cache: "no-store",
    signal,
  });
  if (!response.ok) {
    throw await responseError(response, "读取 Jarvis 人格");
  }
  return response.json() as Promise<PersonalityOverview>;
}

export async function updatePersonalitySettings(
  payload: PersonalitySettings,
): Promise<PersonalityOverview> {
  const response = await fetch(`${API_BASE_URL}/personality/settings`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw await responseError(response, "保存人格设置");
  }
  return response.json() as Promise<PersonalityOverview>;
}

export async function previewPersonality(
  language: "zh" | "en",
  settings?: PersonalitySettings,
): Promise<{ prompt: string }> {
  const response = await fetch(`${API_BASE_URL}/personality/preview`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ language, settings: settings ?? undefined }),
  });
  if (!response.ok) {
    throw await responseError(response, "生成人格预览");
  }
  return response.json() as Promise<{ prompt: string }>;
}

export type ProactiveSuggestionItem = {
  id: string;
  source_type: string;
  source_id: string;
  suggestion_type: string;
  title: string;
  rationale: string;
  priority: number;
  status: string;
  suggested_at: string;
  dismissed_at?: string | null;
  accepted_at?: string | null;
  created_at: string;
};

export type ProactiveScanResult = {
  scanned_at: string;
  created: number;
  skipped: string[];
  today_created: number;
  daily_cap: number;
  quiet_active: boolean;
};

export type ProactiveOverview = {
  generated_at: string;
  enabled: boolean;
  pending_count: number;
  today_created: number;
  daily_cap: number;
  cooldown_hours: number;
  quiet_enabled: boolean;
  quiet_window: string;
  quiet_active: boolean;
  model_note: string;
};

export async function getProactiveOverview(
  signal?: AbortSignal,
): Promise<ProactiveOverview> {
  const response = await fetch(`${API_BASE_URL}/proactive/overview`, {
    cache: "no-store",
    signal,
  });
  if (!response.ok) {
    throw await responseError(response, "读取主动建议引擎");
  }
  return response.json() as Promise<ProactiveOverview>;
}

export async function listProactiveSuggestions(
  options: {
    status?: string;
    sourceType?: string;
    limit?: number;
    signal?: AbortSignal;
  } = {},
): Promise<ProactiveSuggestionItem[]> {
  const url = new URL(`${API_BASE_URL}/proactive/suggestions`);
  if (options.status) url.searchParams.set("status", options.status);
  if (options.sourceType) url.searchParams.set("source_type", options.sourceType);
  url.searchParams.set("limit", String(options.limit ?? 50));
  const response = await fetch(url, { cache: "no-store", signal: options.signal });
  if (!response.ok) {
    throw await responseError(response, "读取主动建议");
  }
  return response.json() as Promise<ProactiveSuggestionItem[]>;
}

export async function runProactiveScan(): Promise<ProactiveScanResult> {
  const response = await fetch(`${API_BASE_URL}/proactive/scan`, {
    method: "POST",
  });
  if (!response.ok) {
    throw await responseError(response, "扫描主动建议");
  }
  return response.json() as Promise<ProactiveScanResult>;
}

export async function dismissProactiveSuggestion(
  suggestionId: string,
): Promise<ProactiveSuggestionItem> {
  const response = await fetch(
    `${API_BASE_URL}/proactive/suggestions/${suggestionId}/dismiss`,
    { method: "POST" },
  );
  if (!response.ok) {
    throw await responseError(response, "忽略建议");
  }
  return response.json() as Promise<ProactiveSuggestionItem>;
}

export async function acceptProactiveSuggestion(
  suggestionId: string,
): Promise<ProactiveSuggestionItem> {
  const response = await fetch(
    `${API_BASE_URL}/proactive/suggestions/${suggestionId}/accept`,
    { method: "POST" },
  );
  if (!response.ok) {
    throw await responseError(response, "接受建议");
  }
  return response.json() as Promise<ProactiveSuggestionItem>;
}

export type ComputerStageInfo = {
  stage: number;
  label: string;
  allowed: string[];
  enabled: boolean;
};

export type ComputerUseStatus = {
  stage: number;
  ladder: ComputerStageInfo[];
  sandbox_root: string;
  permanent_blocks: string[];
  tools: Record<string, boolean>;
};

export type ComputerPlanStep = {
  tool_id: string;
  action: string;
  risk_level: string;
  requires_approval: boolean;
  target: string;
  preview_hint: string;
  blocked_by_stage?: boolean;
};

export type ComputerPlanResult = {
  instruction: string;
  generated_at: string;
  stage: number;
  steps: ComputerPlanStep[];
  note: string;
};

export async function getComputerUseStatus(
  signal?: AbortSignal,
): Promise<ComputerUseStatus> {
  const response = await fetch(`${API_BASE_URL}/computer-use/status`, {
    cache: "no-store",
    signal,
  });
  if (!response.ok) {
    throw await responseError(response, "读取受控电脑操作状态");
  }
  return response.json() as Promise<ComputerUseStatus>;
}

export async function generateComputerPlan(
  instruction: string,
  signal?: AbortSignal,
): Promise<ComputerPlanResult> {
  const response = await fetch(`${API_BASE_URL}/computer-use/plan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ instruction }),
    signal,
  });
  if (!response.ok) {
    throw await responseError(response, "生成操作计划");
  }
  return response.json() as Promise<ComputerPlanResult>;
}
