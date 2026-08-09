/**
 * Proactive engine API client.
 */

import { API_BASE_URL, request } from "./client";

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
  expires_at?: string | null;
  expired_at?: string | null;
  decision_reason?: string | null;
  created_at: string;
};

export type ProactiveCategoryState = {
  category: string;
  enabled: boolean;
  pending_count: number;
  disabled_at?: string | null;
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
  return request<ProactiveOverview>(
    `${API_BASE_URL}/proactive/overview`,
    {
      cache: "no-store",
      signal,
      action: "读取主动建议引擎",
    },
  );
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
  return request<ProactiveSuggestionItem[]>(
    url,
    {
      cache: "no-store",
      signal: options.signal,
      action: "读取主动建议",
    },
  );
}

export async function runProactiveScan(): Promise<ProactiveScanResult> {
  return request<ProactiveScanResult>(
    `${API_BASE_URL}/proactive/scan`,
    {
      method: "POST",
      action: "扫描主动建议",
    },
  );
}

export async function dismissProactiveSuggestion(
  suggestionId: string,
): Promise<ProactiveSuggestionItem> {
  return request<ProactiveSuggestionItem>(
    `${API_BASE_URL}/proactive/suggestions/${suggestionId}/dismiss`,
    {
      method: "POST",
      action: "忽略建议",
    },
  );
}

export async function acceptProactiveSuggestion(
  suggestionId: string,
): Promise<ProactiveSuggestionItem> {
  return request<ProactiveSuggestionItem>(
    `${API_BASE_URL}/proactive/suggestions/${suggestionId}/accept`,
    {
      method: "POST",
      action: "接受建议",
    },
  );
}

export async function decideConversationProactiveSuggestion(
  suggestionId: string,
  action: "accept" | "dismiss",
): Promise<ProactiveSuggestionItem> {
  return request<ProactiveSuggestionItem>(
    `${API_BASE_URL}/proactive/conversation/suggestions/${suggestionId}/${action}`,
    {
      method: "POST",
      action: action === "accept" ? "接受对话建议" : "忽略对话建议",
    },
  );
}

export async function updateConversationProactiveCategory(
  category: string,
  enabled: boolean,
): Promise<ProactiveCategoryState> {
  return request<ProactiveCategoryState>(
    `${API_BASE_URL}/proactive/conversation/categories/${encodeURIComponent(category)}`,
    {
      method: "PUT",
      body: { enabled },
      action: enabled ? "开启对话建议分类" : "关闭对话建议分类",
    },
  );
}
