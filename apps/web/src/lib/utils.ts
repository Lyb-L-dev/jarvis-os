import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export const providerDisplayNames: Record<string, string> = {
  mimo: "MiMo",
  deepseek: "DeepSeek",
  ollama: "本地 Qwen",
};

export const providerPlainLabels: Record<string, string> = {
  mimo: "MiMo",
  deepseek: "DeepSeek",
  ollama: "Ollama",
};

export function providerLabel(
  provider?: string | null,
  options?: { fallback?: string },
): string {
  if (!provider) return options?.fallback ?? "Jarvis Router";
  return providerDisplayNames[provider] ?? provider;
}

export function providerBadge(provider?: string | null): string {
  if (provider === "ollama") return "LOCAL · QWEN";
  if (provider === "deepseek") return "DEEPSEEK";
  if (provider === "mimo") return "MIMO";
  return "JARVIS";
}

export function providerTitle(provider?: string | null): string {
  if (provider === "mimo") return "MiMo";
  if (provider === "deepseek") return "DeepSeek";
  if (provider === "ollama") return "Local Qwen";
  return "Jarvis Router";
}

export type SpeechResultEvent = {
  results: ArrayLike<{
    0: { transcript: string };
    isFinal?: boolean;
  }>;
};

export type SpeechRecognitionLike = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onresult: ((event: SpeechResultEvent) => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
};

export type SpeechRecognitionConstructor = new () => SpeechRecognitionLike;

export function today(): string {
  return new Date().toISOString().slice(0, 10);
}

export function localDateString(): string {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function formatDate(
  value?: string | null,
  fallback = "未设置",
): string {
  if (!value) return fallback;
  return new Date(`${value.slice(0, 10)}T00:00:00`).toLocaleDateString(
    "zh-CN",
    {
      month: "numeric",
      day: "numeric",
    },
  );
}

export function formatDateTime(
  value?: string | null,
  fallback = "尚未刷新",
): string {
  if (!value) return fallback;
  return new Date(value).toLocaleString("zh-CN", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatDateTimeMedium(
  value?: string | null,
  fallback = "尚未验证",
): string {
  if (!value) return fallback;
  return new Intl.DateTimeFormat("zh-CN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function formatNumber(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
  return String(value);
}

export function splitLines(value: string): string[] {
  return value
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}
