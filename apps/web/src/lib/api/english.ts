/**
 * English coach API client.
 */

import { API_BASE_URL, request, requestVoid } from "./client";

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

export type EnglishSessionCompleteResponse = {
  session: EnglishSession;
  mistakes: EnglishMistake[];
};

export async function getEnglishOverview(
  signal?: AbortSignal,
): Promise<EnglishOverview> {
  return request<EnglishOverview>(
    `${API_BASE_URL}/english/overview`,
    {
      cache: "no-store",
      signal,
      action: "Loading English overview",
    },
  );
}

export async function listEnglishSessions(
  signal?: AbortSignal,
): Promise<EnglishSession[]> {
  return request<EnglishSession[]>(
    `${API_BASE_URL}/english/sessions`,
    {
      cache: "no-store",
      signal,
      action: "Loading English sessions",
    },
  );
}

export async function getEnglishSession(
  sessionId: string,
  signal?: AbortSignal,
): Promise<EnglishSessionDetail> {
  return request<EnglishSessionDetail>(
    `${API_BASE_URL}/english/sessions/${sessionId}`,
    {
      cache: "no-store",
      signal,
      action: "Loading English session",
    },
  );
}

export async function createEnglishSession(payload: {
  session_type: EnglishSessionType;
  topic?: string;
  correction_mode: EnglishCorrectionMode;
  level: EnglishLevel;
  processing_mode: EnglishProcessingMode;
}): Promise<EnglishSessionDetail> {
  return request<EnglishSessionDetail>(
    `${API_BASE_URL}/english/sessions`,
    {
      method: "POST",
      body: payload,
      action: "Starting English session",
    },
  );
}

export async function deleteEnglishSession(sessionId: string): Promise<void> {
  await requestVoid(
    `${API_BASE_URL}/english/sessions/${sessionId}`,
    {
      method: "DELETE",
      action: "Deleting English session",
    },
  );
}

export async function sendEnglishMessage(
  sessionId: string,
  payload: {
    content: string;
    input_mode: "text" | "voice_transcript";
  },
): Promise<EnglishSendResponse> {
  return request<EnglishSendResponse>(
    `${API_BASE_URL}/english/sessions/${sessionId}/messages`,
    {
      method: "POST",
      body: payload,
      action: "Sending English message",
    },
  );
}

export async function editEnglishTranscript(
  messageId: string,
  content: string,
): Promise<EnglishMessage> {
  return request<EnglishMessage>(
    `${API_BASE_URL}/english/messages/${messageId}`,
    {
      method: "PATCH",
      body: { content },
      action: "Editing English transcript",
    },
  );
}

export async function completeEnglishSession(
  sessionId: string,
): Promise<EnglishSessionCompleteResponse> {
  return request<EnglishSessionCompleteResponse>(
    `${API_BASE_URL}/english/sessions/${sessionId}/complete`,
    {
      method: "POST",
      action: "Completing English session",
    },
  );
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
  return request<EnglishMistake[]>(
    url,
    {
      cache: "no-store",
      signal: options.signal,
      action: "Loading English mistakes",
    },
  );
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
  return request<EnglishMistake>(
    `${API_BASE_URL}/english/mistakes/${mistakeId}`,
    {
      method: "PATCH",
      body: payload,
      action: "Updating English mistake",
    },
  );
}

async function englishMistakeAction(
  mistakeId: string,
  action: "reject" | "master" | "dispute",
): Promise<EnglishMistake> {
  return request<EnglishMistake>(
    `${API_BASE_URL}/english/mistakes/${mistakeId}/${action}`,
    {
      method: "POST",
      action: `${action} English mistake`,
    },
  );
}

export async function confirmEnglishMistake(
  mistakeId: string,
  reviewAt?: string,
): Promise<EnglishMistake> {
  return request<EnglishMistake>(
    `${API_BASE_URL}/english/mistakes/${mistakeId}/confirm`,
    {
      method: "POST",
      body: { review_at: reviewAt },
      action: "Confirming English mistake",
    },
  );
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
  await requestVoid(
    `${API_BASE_URL}/english/mistakes/${mistakeId}`,
    {
      method: "DELETE",
      action: "Deleting English mistake",
    },
  );
}

export async function listDueEnglishReviews(
  signal?: AbortSignal,
): Promise<EnglishReview[]> {
  return request<EnglishReview[]>(
    `${API_BASE_URL}/english/reviews/due`,
    {
      cache: "no-store",
      signal,
      action: "Loading due English reviews",
    },
  );
}

export async function listUpcomingEnglishReviews(
  signal?: AbortSignal,
): Promise<EnglishReview[]> {
  return request<EnglishReview[]>(
    `${API_BASE_URL}/english/reviews/upcoming`,
    {
      cache: "no-store",
      signal,
      action: "Loading upcoming English reviews",
    },
  );
}

export async function submitEnglishReview(
  reviewId: string,
  payload: {
    submitted_answer?: string;
    result: EnglishReviewResult;
  },
): Promise<EnglishReview> {
  return request<EnglishReview>(
    `${API_BASE_URL}/english/reviews/${reviewId}/result`,
    {
      method: "POST",
      body: payload,
      action: "Saving English review",
    },
  );
}
