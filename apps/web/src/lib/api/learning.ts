import { apiUrl, responseError, runtimeRequestHeaders } from "./client";

export type LearningGrade = "green" | "yellow" | "red";

export type LearningMasterySummary = {
  mastery_percent: number;
  confidence: number;
  evidence_count: number;
  low_confidence: boolean;
  method: string;
};

export type LearningReadiness = {
  enabled: boolean;
  reason?: string | null;
};

export type LearningModuleSummary = {
  id: string;
  name: string;
  slug: string;
  description: string;
  status: string;
  parent_id: string | null;
  core_concepts: string[];
  mastery: LearningMasterySummary;
};

export type LearningObservationView = {
  source: string;
  grade: LearningGrade;
  score: number | null;
  created_at: string;
};

export type LearningModuleDetail = LearningModuleSummary & {
  due_review_count: number;
  recent_observations: LearningObservationView[];
};

export type LearningVerificationItemView = {
  id: string;
  level: number;
  prompt: string;
  expected_points: string[];
  answer: string | null;
  grade: LearningGrade | null;
  grader: string | null;
  grade_score: number | null;
  feedback: string | null;
  answered_at: string | null;
};

export type LearningVerificationView = {
  id: string;
  module_id: string;
  status: string;
  mode: string;
  item_count: number;
  completed_at: string | null;
  items: LearningVerificationItemView[];
};

export type LearningAnswerResult = {
  verification_id: string;
  item: LearningVerificationItemView;
  verification_status: string;
  mastery: LearningMasterySummary;
  review_card_created: boolean;
};

export type LearningReviewCardView = {
  id: string;
  module_id: string;
  question: string;
  answer_hints: string[];
  state: string;
  due_at: string;
  retrievability: number | null;
  reps: number;
  lapses: number;
};

export type LearningReviewQueue = {
  cards: LearningReviewCardView[];
};

export type LearningGraderShadowView = {
  id: string;
  verification_item_id: string;
  module_id: string;
  rule_grade: LearningGrade;
  llm_grade: LearningGrade | null;
  llm_score: number | null;
  llm_feedback: string | null;
  agreement: boolean | null;
  model_used: string | null;
  prompt_version: string;
  latency_ms: number;
  success: boolean;
  error_message: string | null;
  created_at: string;
};

export type LearningGraderShadowSummary = {
  total: number;
  agreed: number;
  disagreed: number;
  failed: number;
  agreement_rate: number | null;
};

async function learningRequest<T>(
  path: string,
  init: RequestInit & { okMessage: string },
): Promise<T> {
  const hasBody = init.body !== undefined;
  const response = await fetch(apiUrl(path), {
    cache: "no-store",
    ...init,
    headers: {
      ...runtimeRequestHeaders(),
      ...(hasBody ? { "Content-Type": "application/json" } : {}),
      ...(init.headers ?? {}),
    },
  });
  if (!response.ok) throw await responseError(response, init.okMessage);
  return response.json() as Promise<T>;
}

export async function getLearningReadiness(
  signal?: AbortSignal,
): Promise<LearningReadiness> {
  return learningRequest<LearningReadiness>("/learning/readiness", {
    okMessage: "检查学习教练可用性",
    signal,
  });
}

export async function listLearningModules(
  signal?: AbortSignal,
): Promise<LearningModuleSummary[]> {
  return learningRequest<LearningModuleSummary[]>("/learning/modules", {
    okMessage: "加载知识模块",
    signal,
  });
}

export async function createLearningModule(payload: {
  name: string;
  description?: string;
  core_concepts: string[];
}): Promise<LearningModuleSummary> {
  return learningRequest<LearningModuleSummary>("/learning/modules", {
    method: "POST",
    body: JSON.stringify(payload),
    okMessage: "创建知识模块",
  });
}

export async function getLearningModuleDetail(
  moduleId: string,
  signal?: AbortSignal,
): Promise<LearningModuleDetail> {
  return learningRequest<LearningModuleDetail>(
    `/learning/modules/${moduleId}`,
    { okMessage: "加载模块详情", signal },
  );
}

export async function startLearningVerification(
  moduleId: string,
  levels?: number[],
): Promise<LearningVerificationView> {
  return learningRequest<LearningVerificationView>("/learning/verifications", {
    method: "POST",
    body: JSON.stringify({ module_id: moduleId, ...(levels ? { levels } : {}) }),
    okMessage: "开始验收",
  });
}

export async function answerLearningItem(
  verificationId: string,
  itemId: string,
  answer: string,
): Promise<LearningAnswerResult> {
  return learningRequest<LearningAnswerResult>(
    `/learning/verifications/${verificationId}/items/${itemId}/answer`,
    {
      method: "POST",
      body: JSON.stringify({ answer }),
      okMessage: "提交回答",
    },
  );
}

export async function getLearningReviewQueue(
  signal?: AbortSignal,
): Promise<LearningReviewQueue> {
  return learningRequest<LearningReviewQueue>("/learning/review/queue", {
    okMessage: "加载复习队列",
    signal,
  });
}

export async function reviewLearningCard(
  cardId: string,
  rating: number,
): Promise<{ card: LearningReviewCardView; mastery: LearningMasterySummary }> {
  return learningRequest(
    `/learning/review/cards/${cardId}/review`,
    {
      method: "POST",
      body: JSON.stringify({ rating }),
      okMessage: "提交复习评级",
    },
  );
}

export async function runLearningShadowGrading(
  verificationId: string,
  itemId: string,
): Promise<LearningGraderShadowView> {
  return learningRequest<LearningGraderShadowView>(
    `/learning/verifications/${verificationId}/items/${itemId}/shadow-grading`,
    { method: "POST", okMessage: "运行影子判分" },
  );
}

export async function getLearningShadowSummary(
  signal?: AbortSignal,
): Promise<LearningGraderShadowSummary> {
  return learningRequest<LearningGraderShadowSummary>(
    "/learning/grader-shadow/summary",
    { okMessage: "加载影子判分统计", signal },
  );
}

export type LearningScheduleBlockView = {
  id: string;
  weekday: number;
  start_minutes: number;
  end_minutes: number;
  kind: string;
  label: string;
  active: boolean;
};

export type LearningDayPlanItem = {
  kind: "study" | "practice" | "career";
  title: string;
  detail: string;
  module_id: string | null;
  estimated_minutes: number;
};

export type LearningDayPlanDraft = {
  plan_date: string;
  minimum_day: boolean;
  auto_minimum: boolean;
  items: LearningDayPlanItem[];
  generation_note: string;
};

export type LearningDayPlanCommitResult = {
  daily_plan_id: string;
  plan_date: string;
  mode: string;
  task_ids: string[];
  items: LearningDayPlanItem[];
  generation_note: string;
};

export type LearningDayTaskStatus = {
  id: string;
  title: string;
  status: string;
  estimated_minutes: number;
};

export type LearningDayStatusView = {
  plan_date: string;
  mode: string;
  total_count: number;
  completed_count: number;
  generation_note: string | null;
  tasks: LearningDayTaskStatus[];
};

export async function getLearningScheduleBlocks(
  signal?: AbortSignal,
): Promise<LearningScheduleBlockView[]> {
  return learningRequest<LearningScheduleBlockView[]>("/learning/schedule/blocks", {
    okMessage: "加载作息块",
    signal,
  });
}

export async function createLearningScheduleBlock(payload: {
  weekday: number;
  start_minutes: number;
  end_minutes: number;
  kind: "study" | "practice" | "career" | "routine";
  label: string;
}): Promise<LearningScheduleBlockView> {
  return learningRequest<LearningScheduleBlockView>("/learning/schedule/blocks", {
    method: "POST",
    body: JSON.stringify(payload),
    okMessage: "创建作息块",
  });
}

export async function deactivateLearningScheduleBlock(
  blockId: string,
): Promise<LearningScheduleBlockView> {
  return learningRequest<LearningScheduleBlockView>(
    `/learning/schedule/blocks/${blockId}/deactivate`,
    { method: "POST", okMessage: "停用作息块" },
  );
}

export async function previewLearningDayPlan(payload: {
  minimum_day: boolean;
}): Promise<LearningDayPlanDraft> {
  return learningRequest<LearningDayPlanDraft>("/learning/schedule/plan/preview", {
    method: "POST",
    body: JSON.stringify(payload),
    okMessage: "生成今日计划预览",
  });
}

export async function commitLearningDayPlan(payload: {
  minimum_day: boolean;
}): Promise<LearningDayPlanCommitResult> {
  return learningRequest<LearningDayPlanCommitResult>("/learning/schedule/plan/commit", {
    method: "POST",
    body: JSON.stringify(payload),
    okMessage: "提交今日计划",
  });
}

export async function getLearningDayStatus(
  signal?: AbortSignal,
): Promise<LearningDayStatusView> {
  return learningRequest<LearningDayStatusView>("/learning/schedule/day", {
    okMessage: "加载当日状态",
    signal,
  });
}
