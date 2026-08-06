/**
 * Growth API client: workflows, goals, tasks, plans, reviews, research workflows.
 */

import { API_BASE_URL, request, requestVoid } from "./client";
import type { NewsCategory } from "./intelligence";

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
  return request<GrowthProgressResponse>(
    `${API_BASE_URL}/growth/progress`,
    {
      cache: "no-store",
      signal,
      errorMessage: (status) => `Growth progress failed with ${status}`,
    },
  );
}

export async function listGrowthWorkflows(
  signal?: AbortSignal,
): Promise<GrowthWorkflowRun[]> {
  return request<GrowthWorkflowRun[]>(
    `${API_BASE_URL}/growth/workflows`,
    {
      cache: "no-store",
      signal,
      action: "Loading growth planning workflows",
    },
  );
}

export async function startGrowthWorkflow(payload: {
  objective: string;
  constraints?: string;
  target_date?: string;
  weekly_hours?: number;
  model_preference: GrowthModelPreference;
  cloud_allowed: boolean;
}): Promise<GrowthWorkflowRun> {
  return request<GrowthWorkflowRun>(
    `${API_BASE_URL}/growth/workflows`,
    {
      method: "POST",
      body: payload,
      action: "Starting growth planning workflow",
    },
  );
}

export async function supplementGrowthWorkflow(
  runId: string,
  payload: {
    constraints?: string;
    target_date?: string;
    weekly_hours?: number;
  },
): Promise<GrowthWorkflowRun> {
  return request<GrowthWorkflowRun>(
    `${API_BASE_URL}/growth/workflows/${runId}/supplement`,
    {
      method: "POST",
      body: payload,
      action: "Supplementing growth planning workflow",
    },
  );
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
  return request<GrowthWorkflowRun>(
    `${API_BASE_URL}/growth/workflows/${runId}/resume`,
    {
      method: "POST",
      body: { action },
      action: "Resuming growth planning workflow",
    },
  );
}

export async function updateGrowthWorkflowDraft(
  runId: string,
  payload: Pick<
    GrowthPlanDraft,
    "title" | "summary" | "milestones" | "tasks"
  >,
): Promise<GrowthWorkflowRun> {
  return request<GrowthWorkflowRun>(
    `${API_BASE_URL}/growth/workflows/${runId}/draft`,
    {
      method: "PATCH",
      body: payload,
      action: "Updating growth plan draft",
    },
  );
}

export async function cancelGrowthWorkflow(
  runId: string,
): Promise<GrowthWorkflowRun> {
  return request<GrowthWorkflowRun>(
    `${API_BASE_URL}/growth/workflows/${runId}/cancel`,
    {
      method: "POST",
      action: "Cancelling growth planning workflow",
    },
  );
}

export async function listResearchWorkflows(
  signal?: AbortSignal,
): Promise<ResearchWorkflowRun[]> {
  return request<ResearchWorkflowRun[]>(
    `${API_BASE_URL}/research/workflows`,
    {
      cache: "no-store",
      signal,
      action: "读取研究工作流",
    },
  );
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
  return request<ResearchWorkflowRun>(
    `${API_BASE_URL}/research/workflows`,
    {
      method: "POST",
      body: payload,
      action: "启动多来源研究",
    },
  );
}

export async function addResearchIntelligenceSource(
  runId: string,
  itemId: string,
): Promise<ResearchWorkflowRun> {
  return request<ResearchWorkflowRun>(
    `${API_BASE_URL}/research/workflows/${runId}/sources/items/${itemId}`,
    {
      method: "POST",
      action: "添加情报来源",
    },
  );
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
  return request<ResearchWorkflowRun>(
    `${API_BASE_URL}/research/workflows/${runId}/sources`,
    {
      method: "POST",
      body: payload,
      action: "添加公开研究来源",
    },
  );
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
  return request<ResearchWorkflowRun>(
    `${API_BASE_URL}/research/workflows/${runId}/resume`,
    {
      method: "POST",
      body: { action },
      action: "继续研究工作流",
    },
  );
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
  return request<ResearchWorkflowRun>(
    `${API_BASE_URL}/research/workflows/${runId}/report`,
    {
      method: "PATCH",
      body: payload,
      action: "保存研究报告草稿",
    },
  );
}

export async function cancelResearchWorkflow(
  runId: string,
): Promise<ResearchWorkflowRun> {
  return request<ResearchWorkflowRun>(
    `${API_BASE_URL}/research/workflows/${runId}/cancel`,
    {
      method: "POST",
      action: "取消研究工作流",
    },
  );
}

export async function getGrowthOverview(
  signal?: AbortSignal,
): Promise<GrowthOverview> {
  return request<GrowthOverview>(
    `${API_BASE_URL}/growth/overview`,
    {
      cache: "no-store",
      signal,
      action: "Loading growth overview",
    },
  );
}

export async function listGoals(signal?: AbortSignal): Promise<Goal[]> {
  return request<Goal[]>(
    `${API_BASE_URL}/goals`,
    {
      cache: "no-store",
      signal,
      action: "Loading goals",
    },
  );
}

export async function createGoal(payload: {
  title: string;
  description?: string;
  area: GrowthArea;
  target_date?: string;
}): Promise<Goal> {
  return request<Goal>(
    `${API_BASE_URL}/goals`,
    {
      method: "POST",
      body: payload,
      action: "Creating goal",
    },
  );
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
  return request<Goal>(
    `${API_BASE_URL}/goals/${goalId}`,
    {
      method: "PATCH",
      body: payload,
      action: "Updating goal",
    },
  );
}

export async function deleteGoal(goalId: string): Promise<void> {
  await requestVoid(
    `${API_BASE_URL}/goals/${goalId}`,
    {
      method: "DELETE",
      action: "Deleting goal",
    },
  );
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
  return request<Milestone>(
    `${API_BASE_URL}/goals/${goalId}/milestones`,
    {
      method: "POST",
      body: payload,
      action: "Creating milestone",
    },
  );
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
  return request<Milestone>(
    `${API_BASE_URL}/milestones/${milestoneId}`,
    {
      method: "PATCH",
      body: payload,
      action: "Updating milestone",
    },
  );
}

export async function listGrowthTasks(
  signal?: AbortSignal,
): Promise<GrowthTask[]> {
  return request<GrowthTask[]>(
    `${API_BASE_URL}/tasks`,
    {
      cache: "no-store",
      signal,
      action: "Loading tasks",
    },
  );
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
  return request<GrowthTask>(
    `${API_BASE_URL}/tasks`,
    {
      method: "POST",
      body: payload,
      action: "Creating task",
    },
  );
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
  return request<GrowthTask>(
    `${API_BASE_URL}/tasks/${taskId}`,
    {
      method: "PATCH",
      body: payload,
      action: "Updating task",
    },
  );
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
  return request<GrowthTask>(
    `${API_BASE_URL}/tasks/${taskId}/${action}`,
    {
      method: "POST",
      body: payload,
      action: `${action} task`,
    },
  );
}

export async function logGrowthTaskTime(
  taskId: string,
  minutes: number,
  note?: string,
): Promise<GrowthTask> {
  return request<GrowthTask>(
    `${API_BASE_URL}/tasks/${taskId}/time`,
    {
      method: "POST",
      body: { minutes, note },
      action: "Logging task time",
    },
  );
}

export async function deleteGrowthTask(taskId: string): Promise<void> {
  await requestVoid(
    `${API_BASE_URL}/tasks/${taskId}`,
    {
      method: "DELETE",
      action: "Deleting task",
    },
  );
}

export async function getTodayPlan(
  signal?: AbortSignal,
): Promise<DailyPlan | null> {
  return request<DailyPlan | null>(
    `${API_BASE_URL}/plans/today`,
    {
      cache: "no-store",
      signal,
      action: "Loading today's plan",
    },
  );
}

export async function generateTodayPlan(
  capacityMinutes?: number,
): Promise<DailyPlan> {
  return request<DailyPlan>(
    `${API_BASE_URL}/plans/today/generate`,
    {
      method: "POST",
      body: { capacity_minutes: capacityMinutes, },
      action: "Generating today's plan",
    },
  );
}

export async function confirmTodayPlan(
  taskIds?: string[],
): Promise<DailyPlan> {
  return request<DailyPlan>(
    `${API_BASE_URL}/plans/today/confirm`,
    {
      method: "POST",
      body: { task_ids: taskIds },
      action: "Confirming today's plan",
    },
  );
}

export async function resetTodayPlan(): Promise<void> {
  await requestVoid(
    `${API_BASE_URL}/plans/today`,
    {
      method: "DELETE",
      action: "Resetting today's plan",
    },
  );
}

export async function getWeeklyReview(
  signal?: AbortSignal,
): Promise<WeeklyReview | null> {
  return request<WeeklyReview | null>(
    `${API_BASE_URL}/reviews/weekly`,
    {
      cache: "no-store",
      signal,
      action: "Loading weekly review",
    },
  );
}

export async function generateWeeklyReview(): Promise<WeeklyReview> {
  return request<WeeklyReview>(
    `${API_BASE_URL}/reviews/weekly/generate`,
    {
      method: "POST",
      action: "Generating weekly review",
    },
  );
}

export async function updateWeeklyReview(
  reviewId: string,
  payload: { user_note?: string | null; status?: WeeklyReview["status"] },
): Promise<WeeklyReview> {
  return request<WeeklyReview>(
    `${API_BASE_URL}/reviews/weekly/${reviewId}`,
    {
      method: "PATCH",
      body: payload,
      action: "Updating weekly review",
    },
  );
}
