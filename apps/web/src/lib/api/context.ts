/**
 * Context engineering API client.
 */

import { API_BASE_URL, request } from "./client";

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
  return request<ContextOverview>(
    `${API_BASE_URL}/context/overview`,
    {
      cache: "no-store",
      signal,
      action: "读取上下文预算",
    },
  );
}

export async function listContextAssemblies(
  limit = 50,
  signal?: AbortSignal,
): Promise<ContextAssemblyItem[]> {
  const url = new URL(`${API_BASE_URL}/context/assemblies`);
  url.searchParams.set("limit", String(limit));
  return request<ContextAssemblyItem[]>(
    url,
    {
      cache: "no-store",
      signal,
      action: "读取上下文装配记录",
    },
  );
}
