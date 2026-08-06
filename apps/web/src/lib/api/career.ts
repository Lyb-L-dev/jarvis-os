/**
 * Career radar API client.
 */

import { API_BASE_URL, request } from "./client";

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
  return request<CareerOverview>(
    `${API_BASE_URL}/career/overview`,
    {
      cache: "no-store",
      signal,
      action: "读取求职雷达",
    },
  );
}

export async function createCareerSandbox(): Promise<CareerSource> {
  return request<CareerSource>(
    `${API_BASE_URL}/career/sources/sandbox`,
    {
      method: "POST",
      action: "建立安全演练来源",
    },
  );
}

export async function createCareerSource(payload: {
  name: string;
  company_name: string;
  start_url: string;
  allowed_hosts: string[];
  confirmed_read_only_scope: true;
}): Promise<CareerSource> {
  return request<CareerSource>(
    `${API_BASE_URL}/career/sources`,
    {
      method: "POST",
      body: payload,
      action: "添加招聘来源",
    },
  );
}

export async function runCareerResearch(
  sourceId: string,
  payload: { query: string; max_pages: number },
): Promise<CareerResearchRun> {
  return request<CareerResearchRun>(
    `${API_BASE_URL}/career/sources/${sourceId}/research`,
    {
      method: "POST",
      body: payload,
      action: "运行只读岗位研究",
    },
  );
}

export function careerEvidenceScreenshotUrl(evidenceId: string) {
  return `${API_BASE_URL}/career/evidence/${evidenceId}/screenshot`;
}
