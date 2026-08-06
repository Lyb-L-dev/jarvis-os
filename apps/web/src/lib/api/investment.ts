/**
 * Investment API client: assets, positions, transactions, theses, reviews, monitoring.
 */

import { API_BASE_URL, request, requestVoid } from "./client";

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
  return request<InvestmentPerformanceResponse>(
    `${API_BASE_URL}/investment/performance`,
    {
      cache: "no-store",
      signal,
      errorMessage: (status) => `Investment performance failed with ${status}`,
    },
  );
}

export async function getInvestmentOverview(
  signal?: AbortSignal,
): Promise<InvestmentOverview> {
  return request<InvestmentOverview>(
    `${API_BASE_URL}/investment/overview`,
    {
      cache: "no-store",
      signal,
      action: "Loading investment overview",
    },
  );
}

export async function getMonitoringOverview(
  signal?: AbortSignal,
): Promise<MonitoringOverview> {
  return request<MonitoringOverview>(
    `${API_BASE_URL}/monitoring/overview`,
    {
      cache: "no-store",
      signal,
      action: "Loading monitoring overview",
    },
  );
}

export async function listMonitorRules(
  signal?: AbortSignal,
): Promise<MonitorRule[]> {
  return request<MonitorRule[]>(
    `${API_BASE_URL}/monitoring/rules`,
    {
      cache: "no-store",
      signal,
      action: "Loading monitor rules",
    },
  );
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
  return request<MonitorRule>(
    `${API_BASE_URL}/monitoring/rules`,
    {
      method: "POST",
      body: payload,
      action: "Creating monitor rule",
    },
  );
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
  return request<MonitorRule>(
    `${API_BASE_URL}/monitoring/rules/${ruleId}`,
    {
      method: "PATCH",
      body: payload,
      action: "Updating monitor rule",
    },
  );
}

export async function deleteMonitorRule(ruleId: string): Promise<void> {
  await requestVoid(
    `${API_BASE_URL}/monitoring/rules/${ruleId}`,
    {
      method: "DELETE",
      action: "Deleting monitor rule",
    },
  );
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
  return request<MonitorEvent[]>(
    url,
    {
      cache: "no-store",
      signal: options.signal,
      action: "Loading monitor events",
    },
  );
}

export async function scanMonitoring(payload: {
  lookback_hours?: number;
  notify?: boolean;
} = {}): Promise<MonitoringScanResult> {
  return request<MonitoringScanResult>(
    `${API_BASE_URL}/monitoring/scan`,
    {
      method: "POST",
      body: { lookback_hours: 72, notify: true, ...payload },
      action: "Scanning monitored events",
    },
  );
}

export async function updateMonitorEvent(
  eventId: string,
  action: "acknowledge" | "dismiss",
): Promise<MonitorEvent> {
  return request<MonitorEvent>(
    `${API_BASE_URL}/monitoring/events/${eventId}/action`,
    {
      method: "POST",
      body: { action },
      action: "Updating monitor event",
    },
  );
}

export async function listInvestmentAssets(
  signal?: AbortSignal,
): Promise<InvestmentAsset[]> {
  return request<InvestmentAsset[]>(
    `${API_BASE_URL}/investment/assets`,
    {
      cache: "no-store",
      signal,
      action: "Loading investment assets",
    },
  );
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
  return request<InvestmentAsset>(
    `${API_BASE_URL}/investment/assets`,
    {
      method: "POST",
      body: payload,
      action: "Creating investment asset",
    },
  );
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
  return request<InvestmentAsset>(
    `${API_BASE_URL}/investment/assets/${assetId}`,
    {
      method: "PATCH",
      body: payload,
      action: "Updating investment asset",
    },
  );
}

export async function deleteInvestmentAsset(assetId: string): Promise<void> {
  await requestVoid(
    `${API_BASE_URL}/investment/assets/${assetId}`,
    {
      method: "DELETE",
      action: "Deleting investment asset",
    },
  );
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
  return request<PortfolioPosition>(
    `${API_BASE_URL}/investment/positions`,
    {
      method: "POST",
      body: payload,
      action: "Creating initial position",
    },
  );
}

export async function updatePortfolioPosition(
  positionId: string,
  payload: Partial<{
    target_allocation: number | null;
    risk_level: InvestmentRisk;
  }>,
): Promise<PortfolioPosition> {
  return request<PortfolioPosition>(
    `${API_BASE_URL}/investment/positions/${positionId}`,
    {
      method: "PATCH",
      body: payload,
      action: "Updating portfolio position",
    },
  );
}

export async function listInvestmentTransactions(
  signal?: AbortSignal,
): Promise<InvestmentTransaction[]> {
  return request<InvestmentTransaction[]>(
    `${API_BASE_URL}/investment/transactions`,
    {
      cache: "no-store",
      signal,
      action: "Loading investment transactions",
    },
  );
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
  return request<InvestmentTransaction>(
    `${API_BASE_URL}/investment/transactions`,
    {
      method: "POST",
      body: payload,
      action: "Creating investment transaction",
    },
  );
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
  return request<InvestmentTransaction>(
    `${API_BASE_URL}/investment/transactions/${transactionId}`,
    {
      method: "PATCH",
      body: payload,
      action: "Updating investment transaction",
    },
  );
}

export async function deleteInvestmentTransaction(
  transactionId: string,
): Promise<void> {
  await requestVoid(
    `${API_BASE_URL}/investment/transactions/${transactionId}`,
    {
      method: "DELETE",
      action: "Deleting investment transaction",
    },
  );
}

export async function listInvestmentTheses(
  signal?: AbortSignal,
): Promise<InvestmentThesis[]> {
  return request<InvestmentThesis[]>(
    `${API_BASE_URL}/investment/theses`,
    {
      cache: "no-store",
      signal,
      action: "Loading investment theses",
    },
  );
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
  return request<InvestmentThesis>(
    `${API_BASE_URL}/investment/theses`,
    {
      method: "POST",
      body: payload,
      action: "Creating investment thesis",
    },
  );
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
  return request<InvestmentThesis>(
    `${API_BASE_URL}/investment/theses/${thesisId}`,
    {
      method: "PATCH",
      body: payload,
      action: "Updating investment thesis",
    },
  );
}

export async function listInvestmentReviews(
  signal?: AbortSignal,
): Promise<InvestmentReview[]> {
  return request<InvestmentReview[]>(
    `${API_BASE_URL}/investment/reviews`,
    {
      cache: "no-store",
      signal,
      action: "Loading investment reviews",
    },
  );
}

export async function generateInvestmentReview(payload: {
  asset_id: string;
  review_type: InvestmentReview["review_type"];
}): Promise<InvestmentReview> {
  return request<InvestmentReview>(
    `${API_BASE_URL}/investment/reviews/generate`,
    {
      method: "POST",
      body: payload,
      action: "Generating investment review",
    },
  );
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
  return request<InvestmentReview>(
    `${API_BASE_URL}/investment/reviews/${reviewId}`,
    {
      method: "PATCH",
      body: payload,
      action: "Updating investment review",
    },
  );
}

export async function listAssetNews(
  assetId: string,
  candidates: boolean,
  signal?: AbortSignal,
): Promise<RelatedInvestmentNews[]> {
  const url = new URL(`${API_BASE_URL}/investment/assets/${assetId}/news`);
  if (candidates) url.searchParams.set("candidates", "true");
  return request<RelatedInvestmentNews[]>(
    url,
    {
      cache: "no-store",
      signal,
      action: "Loading related investment news",
    },
  );
}

export async function linkAssetNews(
  assetId: string,
  newsItemId: string,
  relationshipNote?: string,
): Promise<RelatedInvestmentNews> {
  return request<RelatedInvestmentNews>(
    `${API_BASE_URL}/investment/assets/${assetId}/news/${newsItemId}`,
    {
      method: "POST",
      body: { relationship_note: relationshipNote || null },
      action: "Linking investment news",
    },
  );
}

export async function unlinkAssetNews(
  assetId: string,
  newsItemId: string,
): Promise<void> {
  await requestVoid(
    `${API_BASE_URL}/investment/assets/${assetId}/news/${newsItemId}`,
    {
      method: "DELETE",
      action: "Unlinking investment news",
    },
  );
}
