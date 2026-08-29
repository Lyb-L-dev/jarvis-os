/**
 * Chat API client: conversations, streaming, model calls, evaluation.
 */

import {
  API_BASE_URL,
  apiUrl,
  request,
  requestVoid,
  responseError,
  runtimeRequestHeaders,
} from "./client";
import type { ContextAssemblyInfo } from "./context";

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

export async function listConversations(
  signal?: AbortSignal,
  query?: string,
): Promise<ConversationSummary[]> {
  const search = query?.trim();
  const url = new URL(`${API_BASE_URL}/chat/conversations`);
  if (search) {
    url.searchParams.set("q", search);
  }
  return request<ConversationSummary[]>(
    url,
    {
      cache: "no-store",
      signal,
      action: "Loading conversations",
    },
  );
}

export async function renameConversation(
  conversationId: string,
  title: string,
): Promise<ConversationSummary> {
  return request<ConversationSummary>(
    `${API_BASE_URL}/chat/conversations/${conversationId}`,
    {
      method: "PATCH",
      body: { title },
      action: "Renaming conversation",
    },
  );
}

export async function previewAgentRouting(payload: {
  content: string;
  mode: ModelMode;
  sensitive: boolean;
  paid_call_confirmed: boolean;
}): Promise<AgentRouting | null> {
  return request<AgentRouting | null>(
    `${API_BASE_URL}/chat/routing/preview`,
    {
      method: "POST",
      body: payload,
      action: "Previewing Agent route",
    },
  );
}

export async function createConversation(payload: {
  title?: string;
  model_mode: ModelMode;
}): Promise<ConversationSummary> {
  return request<ConversationSummary>(
    `${API_BASE_URL}/chat/conversations`,
    {
      method: "POST",
      body: payload,
      action: "Creating conversation",
    },
  );
}

export async function getConversation(
  conversationId: string,
  signal?: AbortSignal,
): Promise<ConversationDetail> {
  return request<ConversationDetail>(
    `${API_BASE_URL}/chat/conversations/${conversationId}`,
    {
      cache: "no-store",
      signal,
      action: "Loading conversation",
    },
  );
}

export async function archiveConversation(
  conversationId: string,
): Promise<void> {
  await requestVoid(
    `${API_BASE_URL}/chat/conversations/${conversationId}/archive`,
    {
      method: "POST",
      action: "Archiving conversation",
    },
  );
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
  return request<ChatSendResponse>(
    `${API_BASE_URL}/chat/conversations/${conversationId}/messages`,
    {
      method: "POST",
      body: payload,
      action: "Sending message",
    },
  );
}

async function consumeChatStream(
  url: string,
  payload: unknown,
  handlers: ChatStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(url, {
    method: "POST",
    headers: {
      ...runtimeRequestHeaders(),
      "Content-Type": "application/json",
    },
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
    apiUrl(`/chat/conversations/${conversationId}/stream`),
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
    apiUrl(
      `/chat/conversations/${conversationId}/messages/${assistantMessageId}/regenerate/stream`,
    ),
    payload,
    handlers,
    signal,
  );
}

export async function cancelChatStream(requestId: string): Promise<void> {
  await requestVoid(
    `${API_BASE_URL}/chat/streams/${requestId}/cancel`,
    {
      method: "POST",
      action: "Stopping generation",
    },
  );
}

export async function getModelCalls(
  limit = 20,
  signal?: AbortSignal,
): Promise<ModelCallLog[]> {
  return request<ModelCallLog[]>(
    `${API_BASE_URL}/chat/model-calls?limit=${encodeURIComponent(limit)}`,
    {
      cache: "no-store",
      signal,
      action: "Loading model calls",
    },
  );
}

export async function updateModelCallFeedback(
  modelCallId: string,
  payload: {
    rating: "helpful" | "not_helpful";
    task_completed?: boolean | null;
  },
): Promise<ModelCallLog> {
  return request<ModelCallLog>(
    `${API_BASE_URL}/chat/model-calls/${modelCallId}/feedback`,
    {
      method: "PUT",
      body: payload,
      action: "Saving model feedback",
    },
  );
}

export async function getModelCallTrace(
  modelCallId: string,
  signal?: AbortSignal,
): Promise<ModelExecutionTrace> {
  return request<ModelExecutionTrace>(
    `${API_BASE_URL}/chat/model-calls/${modelCallId}/trace`,
    {
      cache: "no-store",
      signal,
      action: "Loading execution trace",
    },
  );
}

export async function getEvaluationCases(
  signal?: AbortSignal,
): Promise<EvaluationCase[]> {
  return request<EvaluationCase[]>(
    `${API_BASE_URL}/evaluation/cases`,
    {
      cache: "no-store",
      signal,
      action: "Loading evaluation cases",
    },
  );
}

export async function getEvaluationOverview(
  signal?: AbortSignal,
): Promise<EvaluationOverview> {
  return request<EvaluationOverview>(
    `${API_BASE_URL}/evaluation/overview`,
    {
      cache: "no-store",
      signal,
      action: "Loading evaluation overview",
    },
  );
}

export async function getEvaluationRuns(
  limit = 30,
  signal?: AbortSignal,
): Promise<EvaluationRun[]> {
  return request<EvaluationRun[]>(
    `${API_BASE_URL}/evaluation/runs?limit=${encodeURIComponent(limit)}`,
    {
      cache: "no-store",
      signal,
      action: "Loading evaluation runs",
    },
  );
}

export async function runEvaluation(payload: {
  case_id: string;
  provider: EvaluationProvider;
  paid_call_confirmed: boolean;
}): Promise<EvaluationRun> {
  return request<EvaluationRun>(
    `${API_BASE_URL}/evaluation/runs`,
    {
      method: "POST",
      body: payload,
      action: "Running evaluation",
    },
  );
}

export async function updateEvaluationFeedback(
  runId: string,
  rating: "helpful" | "not_helpful",
): Promise<EvaluationRun> {
  return request<EvaluationRun>(
    `${API_BASE_URL}/evaluation/runs/${runId}/feedback`,
    {
      method: "PUT",
      body: { rating },
      action: "Saving evaluation feedback",
    },
  );
}
