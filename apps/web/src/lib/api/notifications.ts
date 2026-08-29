/**
 * Notifications API client: preferences, notifications, reminders, companion devices.
 */

import { API_BASE_URL, request, requestVoid } from "./client";

export type NotificationChannel = "desktop" | "voice";

export type VoiceEngine = "auto" | "local_neural" | "windows";

export type VoicePersona = "calm" | "concise" | "plain";

export type NotificationPreference = {
  desktop_enabled: boolean;
  voice_enabled: boolean;
  quiet_enabled: boolean;
  quiet_start: string;
  quiet_end: string;
  max_daily_notifications: number;
  max_hourly_voice: number;
  default_snooze_minutes: number;
  voice_rate: number;
  voice_volume: number;
  voice_engine: VoiceEngine;
  voice_persona: VoicePersona;
  sensitive_voice_enabled: boolean;
  paused_until?: string | null;
  updated_at: string;
};

export type DeliveryAttempt = {
  channel: NotificationChannel;
  device_id: string;
  success: boolean;
  error_message?: string | null;
  created_at: string;
};

export type JarvisNotification = {
  id: string;
  scheduled_job_id?: string | null;
  task_id?: string | null;
  title: string;
  message: string;
  category: string;
  priority: number;
  status:
    | "pending"
    | "claimed"
    | "snoozed"
    | "delivered"
    | "dismissed"
    | "cancelled"
    | "failed";
  requested_channels: NotificationChannel[];
  claimed_channels: NotificationChannel[];
  sensitive: boolean;
  available_at: string;
  claimed_at?: string | null;
  delivered_at?: string | null;
  read_at?: string | null;
  dismissed_at?: string | null;
  snooze_count: number;
  attempt_count: number;
  error_message?: string | null;
  attempts: DeliveryAttempt[];
  created_at: string;
  updated_at: string;
};

export type CompanionDevice = {
  device_id: string;
  display_name: string;
  platform: string;
  capabilities: NotificationChannel[];
  last_seen_at: string;
  online: boolean;
  last_error?: string | null;
  voice_status?: {
    local_neural_ready: boolean;
    chinese_neural_ready: boolean;
    english_neural_ready: boolean;
    bilingual_neural_ready: boolean;
    windows_voice_ready: boolean;
    selected_engine: string;
    local_model_name?: string | null;
    english_model_name?: string | null;
    windows_voice_name?: string | null;
    fallback_reason?: string | null;
  } | null;
};

export async function getNotificationPreferences(
  signal?: AbortSignal,
): Promise<NotificationPreference> {
  return request<NotificationPreference>(
    `${API_BASE_URL}/notifications/preferences`,
    {
      cache: "no-store",
      signal,
      action: "Loading reminder settings",
    },
  );
}

export async function updateNotificationPreferences(
  payload: Partial<
    Omit<NotificationPreference, "updated_at">
  >,
): Promise<NotificationPreference> {
  return request<NotificationPreference>(
    `${API_BASE_URL}/notifications/preferences`,
    {
      method: "PATCH",
      body: payload,
      action: "Saving reminder settings",
    },
  );
}

export async function listNotifications(
  signal?: AbortSignal,
): Promise<JarvisNotification[]> {
  return request<JarvisNotification[]>(
    `${API_BASE_URL}/notifications`,
    {
      cache: "no-store",
      signal,
      action: "Loading reminders",
    },
  );
}

export async function listCompanionDevices(
  signal?: AbortSignal,
): Promise<CompanionDevice[]> {
  return request<CompanionDevice[]>(
    `${API_BASE_URL}/notifications/devices/status`,
    {
      cache: "no-store",
      signal,
      action: "Loading Windows Companion",
    },
  );
}

export async function createReminder(payload: {
  title: string;
  message: string;
  scheduled_for: string;
  task_id?: string;
  channels: NotificationChannel[];
  priority?: number;
  sensitive?: boolean;
}): Promise<JarvisNotification> {
  return request<JarvisNotification>(
    `${API_BASE_URL}/notifications`,
    {
      method: "POST",
      body: payload,
      action: "Creating reminder",
    },
  );
}

export async function snoozeReminder(
  notificationId: string,
  minutes: number,
  actionId?: string,
): Promise<JarvisNotification> {
  return request<JarvisNotification>(
    `${API_BASE_URL}/notifications/${notificationId}/snooze`,
    {
      method: "POST",
      body: { minutes, action_id: actionId },
      action: "Snoozing reminder",
    },
  );
}

export async function dismissReminder(
  notificationId: string,
): Promise<JarvisNotification> {
  return request<JarvisNotification>(
    `${API_BASE_URL}/notifications/${notificationId}/dismiss`,
    {
      method: "POST",
      action: "Dismissing reminder",
    },
  );
}

export async function retryReminder(
  notificationId: string,
): Promise<JarvisNotification> {
  return request<JarvisNotification>(
    `${API_BASE_URL}/notifications/${notificationId}/retry`,
    {
      method: "POST",
      action: "Retrying reminder",
    },
  );
}

export async function deleteReminder(notificationId: string): Promise<void> {
  await requestVoid(
    `${API_BASE_URL}/notifications/${notificationId}`,
    {
      method: "DELETE",
      action: "Deleting reminder history",
    },
  );
}
