/**
 * Intelligence API client: news, briefs, sources, preferences.
 */

import { API_BASE_URL, request, requestVoid } from "./client";

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

export async function getIntelligenceOverview(
  signal?: AbortSignal,
): Promise<IntelligenceOverview> {
  return request<IntelligenceOverview>(
    `${API_BASE_URL}/intelligence/overview`,
    {
      cache: "no-store",
      signal,
      action: "Loading intelligence overview",
    },
  );
}

export async function getTodayIntelligenceBrief(
  signal?: AbortSignal,
): Promise<DailyBrief | null> {
  return request<DailyBrief | null>(
    `${API_BASE_URL}/intelligence/briefs/today`,
    {
      cache: "no-store",
      signal,
      action: "Loading today's intelligence",
    },
  );
}

export async function generateIntelligenceBrief(payload: {
  processing_mode: "standard" | "local";
  refresh_sources: boolean;
  notify: boolean;
  use_ai?: boolean;
}): Promise<DailyBrief> {
  return request<DailyBrief>(
    `${API_BASE_URL}/intelligence/briefs/generate`,
    {
      method: "POST",
      body: payload,
      action: "Generating intelligence brief",
    },
  );
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
  return request<NewsItem[]>(
    url,
    {
      cache: "no-store",
      signal: options.signal,
      action: "Loading intelligence items",
    },
  );
}

export async function listNewsSources(
  signal?: AbortSignal,
): Promise<NewsSource[]> {
  return request<NewsSource[]>(
    `${API_BASE_URL}/intelligence/sources`,
    {
      cache: "no-store",
      signal,
      action: "Loading intelligence sources",
    },
  );
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
  return request<NewsSource>(
    `${API_BASE_URL}/intelligence/sources`,
    {
      method: "POST",
      body: payload,
      action: "Adding RSS source",
    },
  );
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
  return request<NewsSource>(
    `${API_BASE_URL}/intelligence/sources/${sourceId}`,
    {
      method: "PATCH",
      body: payload,
      action: "Updating RSS source",
    },
  );
}

export async function deleteNewsSource(sourceId: string): Promise<void> {
  await requestVoid(
    `${API_BASE_URL}/intelligence/sources/${sourceId}`,
    {
      method: "DELETE",
      action: "Deleting RSS source",
    },
  );
}

export async function refreshNewsSource(
  sourceId: string,
): Promise<SourceRefresh> {
  return request<SourceRefresh>(
    `${API_BASE_URL}/intelligence/sources/${sourceId}/refresh`,
    {
      method: "POST",
      action: "Refreshing RSS source",
    },
  );
}

export async function refreshAllNewsSources(): Promise<RefreshAllSources> {
  return request<RefreshAllSources>(
    `${API_BASE_URL}/intelligence/refresh`,
    {
      method: "POST",
      action: "Refreshing RSS sources",
    },
  );
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
  return request<NewsItem>(
    `${API_BASE_URL}/intelligence/items/manual`,
    {
      method: "POST",
      body: payload,
      action: "Adding a manual intelligence item",
    },
  );
}

export async function updateIntelligencePreferences(
  payload: Partial<IntelligencePreferences>,
): Promise<IntelligencePreferences> {
  return request<IntelligencePreferences>(
    `${API_BASE_URL}/intelligence/preferences`,
    {
      method: "PATCH",
      body: payload,
      action: "Saving intelligence interests",
    },
  );
}

export async function newsItemAction(
  itemId: string,
  action: "read" | "save" | "ignore",
): Promise<{
  item: NewsItem;
  interest_weights: IntelligencePreferences;
}> {
  return request<{ item: NewsItem; interest_weights: IntelligencePreferences; }>(
    `${API_BASE_URL}/intelligence/items/${itemId}/${action}`,
    {
      method: "POST",
      action: `${action} intelligence item`,
    },
  );
}

export async function convertNewsItemToTask(
  itemId: string,
  payload: {
    title?: string;
    priority?: number;
    estimated_minutes?: number;
  } = {},
): Promise<{ item: NewsItem; task_id: string; task_title: string }> {
  return request<{ item: NewsItem; task_id: string; task_title: string; }>(
    `${API_BASE_URL}/intelligence/items/${itemId}/task`,
    {
      method: "POST",
      body: payload,
      action: "Converting intelligence to task",
    },
  );
}
