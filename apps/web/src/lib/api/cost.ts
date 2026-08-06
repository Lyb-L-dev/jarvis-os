/**
 * Cost API client.
 */

import { API_BASE_URL, request } from "./client";

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
  return request<CostOverview>(
    url,
    {
      cache: "no-store",
      signal,
      action: "读取费用统计",
    },
  );
}

export async function listCostCalls(
  limit = 50,
  signal?: AbortSignal,
): Promise<CostCallItem[]> {
  const url = new URL(`${API_BASE_URL}/cost/calls`);
  url.searchParams.set("limit", String(limit));
  return request<CostCallItem[]>(
    url,
    {
      cache: "no-store",
      signal,
      action: "读取模型调用明细",
    },
  );
}
