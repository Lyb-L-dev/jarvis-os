/**
 * System API client: backups, health, models, profile, onboarding, UI bootstrap.
 */

import {
  API_BASE_URL,
  apiUrl,
  request,
  requestVoid,
  responseError,
  runtimeRequestHeaders,
} from "./client";

export type DependencyStatus = {
  name: string;
  status: "ready" | "not_configured" | "unavailable";
  detail?: string | null;
};

export type ReadinessResponse = {
  status: "ready" | "degraded";
  dependencies: DependencyStatus[];
};

export type BackupRecord = {
  id: string;
  created_at: string;
  file_name: string;
  size_bytes: number;
  sha256: string;
  archive_verified: boolean;
  restore_verified_at?: string | null;
  verified_table_count?: number | null;
  alembic_version?: string | null;
};

export type BackupStatus = {
  enabled: boolean;
  backup_directory: string;
  interval_hours: number;
  retention_count: number;
  backup_count: number;
  latest_backup?: BackupRecord | null;
  worker_error?: string | null;
};

export type BackupListResponse = {
  status: BackupStatus;
  backups: BackupRecord[];
};

export type BackupActionResponse = {
  status: "created" | "verified";
  message: string;
  backup: BackupRecord;
};

export async function listSystemBackups(
  signal?: AbortSignal,
): Promise<BackupListResponse> {
  return request<BackupListResponse>(
    `${API_BASE_URL}/system/backups`,
    {
      cache: "no-store",
      signal,
      action: "Loading local backups",
    },
  );
}

export async function createSystemBackup(): Promise<BackupActionResponse> {
  return request<BackupActionResponse>(
    `${API_BASE_URL}/system/backups`,
    {
      method: "POST",
      action: "Creating local backup",
    },
  );
}

export async function verifySystemBackup(
  backupId: string,
): Promise<BackupActionResponse> {
  return request<BackupActionResponse>(
    `${API_BASE_URL}/system/backups/${backupId}/verify`,
    {
      method: "POST",
      action: "Verifying local backup",
    },
  );
}

export async function downloadUserDataExport(): Promise<void> {
  const response = await fetch(apiUrl("/system/export"), {
    cache: "no-store",
    headers: runtimeRequestHeaders(),
  });
  if (!response.ok) {
    throw await responseError(response, "Exporting personal data");
  }

  const disposition = response.headers.get("Content-Disposition") ?? "";
  const fileName =
    disposition.match(/filename="([^"]+)"/)?.[1] ??
    "jarvis-user-data-export.json";
  const objectUrl = URL.createObjectURL(await response.blob());
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = fileName;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(objectUrl);
}

export type ModelProviderStatus = {
  provider: "mimo" | "deepseek" | "ollama";
  configured: boolean;
  base_url: string;
  model: string;
  role: string;
  configuration_issue?: string | null;
};

export type ModelStatusResponse = {
  default_provider: string;
  providers: ModelProviderStatus[];
};

export type ProfileResponse = {
  user_id: string;
  name: string;
  timezone: string;
  onboarding_completed: boolean;
  onboarding_completed_at?: string | null;
  profile: {
    education_level?: string | null;
    major?: string | null;
    career_goals: string[];
    current_skills: string[];
    weaknesses: string[];
    daily_available_minutes: number;
    extra: Record<string, unknown>;
  };
  preferences: {
    information_interests: Record<string, string>;
    notification_settings: Record<string, unknown>;
    privacy_settings: Record<string, unknown>;
    model_preferences: Record<string, string>;
  };
};

export type OnboardingSession = {
  id: string;
  user_id: string;
  status: string;
  current_step: number;
  answers: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export async function getReadiness(
  signal?: AbortSignal,
): Promise<ReadinessResponse> {
  return request<ReadinessResponse>(
    `${API_BASE_URL}/health/ready`,
    {
      cache: "no-store",
      signal,
      errorMessage: (status) => `Health request failed with ${status}`,
    },
  );
}

export type HeaderStatusResponse = {
  core: "ready" | "degraded" | "offline";
  model: {
    provider: string;
    model?: string | null;
    mode: string;
  };
  quiet_hours?: {
    enabled: boolean;
    start?: string | null;
    end?: string | null;
    active: boolean;
  } | null;
  unread_notifications: number;
  server_time: string;
};

export async function getHeaderStatus(
  signal?: AbortSignal,
): Promise<HeaderStatusResponse> {
  return request<HeaderStatusResponse>(
    `${API_BASE_URL}/ui/header-status`,
    {
      cache: "no-store",
      signal,
      errorMessage: (status) => `Header status failed with ${status}`,
    },
  );
}

export type TabletTodayTask = {
  id: string;
  title: string;
  status: string;
};

export type TabletBootstrapResponse = {
  core: "ready" | "degraded" | "offline";
  model: {
    provider: string;
    model?: string | null;
    mode: string;
  };
  quiet_hours?: {
    enabled: boolean;
    start?: string | null;
    end?: string | null;
    active: boolean;
  } | null;
  unread_notifications: number;
  profile_name?: string | null;
  configured_models: number;
  total_models: number;
  today_tasks: TabletTodayTask[];
  unread_intelligence: number;
  memory_active: number;
  server_time: string;
};

export async function getTabletBootstrap(
  signal?: AbortSignal,
): Promise<TabletBootstrapResponse> {
  return request<TabletBootstrapResponse>(
    `${API_BASE_URL}/ui/tablet-bootstrap`,
    {
      cache: "no-store",
      signal,
      errorMessage: (status) => `Tablet bootstrap failed with ${status}`,
    },
  );
}

export async function getModelStatus(
  signal?: AbortSignal,
): Promise<ModelStatusResponse> {
  return request<ModelStatusResponse>(
    `${API_BASE_URL}/models/status`,
    {
      cache: "no-store",
      signal,
      errorMessage: (status) => `Model status request failed with ${status}`,
    },
  );
}

export async function getProfile(
  signal?: AbortSignal,
): Promise<ProfileResponse | null> {
  const response = await fetch(apiUrl("/profile"), {
    cache: "no-store",
    headers: runtimeRequestHeaders(),
    signal,
  });

  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw new Error(`Profile request failed with ${response.status}`);
  }

  return response.json() as Promise<ProfileResponse>;
}

export async function createOnboardingSession(payload: {
  user_name: string;
  timezone: string;
}): Promise<OnboardingSession> {
  return request<OnboardingSession>(
    `${API_BASE_URL}/onboarding/sessions`,
    {
      method: "POST",
      body: payload,
      errorMessage: (status) => `Creating onboarding failed with ${status}`,
    },
  );
}

export async function updateOnboardingSession(
  sessionId: string,
  payload: {
    current_step: number;
    answers: Record<string, unknown>;
  },
): Promise<OnboardingSession> {
  return request<OnboardingSession>(
    `${API_BASE_URL}/onboarding/sessions/${sessionId}`,
    {
      method: "PATCH",
      body: payload,
      errorMessage: (status) => `Updating onboarding failed with ${status}`,
    },
  );
}

export async function completeOnboardingSession(
  sessionId: string,
): Promise<void> {
  await requestVoid(
    `${API_BASE_URL}/onboarding/sessions/${sessionId}/complete`,
    {
      method: "POST",
      errorMessage: (status) => `Completing onboarding failed with ${status}`,
    },
  );
}
