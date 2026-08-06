/**
 * Personality API client.
 */

import { API_BASE_URL, request } from "./client";

export type PersonalitySettings = {
  nickname: string;
  tone: "balanced" | "casual" | "formal";
  emoji: boolean;
  extra_rules: string[];
};

export type PersonalityOverview = {
  name: string;
  tones: string[];
  settings: PersonalitySettings;
  prompts: Record<string, string>;
  boundaries: string[];
  disclaimer: string;
};

export async function getPersonalityOverview(
  signal?: AbortSignal,
): Promise<PersonalityOverview> {
  return request<PersonalityOverview>(
    `${API_BASE_URL}/personality/overview`,
    {
      cache: "no-store",
      signal,
      action: "读取 Jarvis 人格",
    },
  );
}

export async function updatePersonalitySettings(
  payload: PersonalitySettings,
): Promise<PersonalityOverview> {
  return request<PersonalityOverview>(
    `${API_BASE_URL}/personality/settings`,
    {
      method: "PUT",
      body: payload,
      action: "保存人格设置",
    },
  );
}

export async function previewPersonality(
  language: "zh" | "en",
  settings?: PersonalitySettings,
): Promise<{ prompt: string }> {
  return request<{ prompt: string }>(
    `${API_BASE_URL}/personality/preview`,
    {
      method: "POST",
      body: { language, settings: settings ?? undefined },
      action: "生成人格预览",
    },
  );
}
