"use client";

import {
  AlertTriangle,
  Check,
  Eye,
  Fingerprint,
  Languages,
  LockKeyhole,
  RefreshCw,
  Save,
  ShieldCheck,
  Sparkles,
  UserRound,
  Wand2,
  X,
} from "lucide-react";
import { FormEvent, useCallback, useEffect, useState } from "react";

import {
  getPersonalityOverview,
  PersonalityOverview,
  PersonalitySettings,
  previewPersonality,
  updatePersonalitySettings,
} from "@/lib/api";

const toneLabels: Record<string, string> = {
  balanced: "自然平和",
  casual: "轻松自然",
  formal: "正式克制",
};

const toneDescriptions: Record<string, string> = {
  balanced: "像可靠的伙伴，不过度亲昵也不生硬",
  casual: "简短直接，像熟悉的朋友",
  formal: "用词准确，条理清晰",
};

const boundaryIcons = [
  <Fingerprint key="facts" />,
  <LockKeyhole key="safety" />,
  <ShieldCheck key="latest" />,
  <Eye key="reasoning" />,
];

function errorText(error: unknown) {
  return error instanceof Error ? error.message : "Jarvis 暂时无法读取人格设置";
}

export function PersonalityLayer() {
  const [overview, setOverview] = useState<PersonalityOverview | null>(null);
  const [settings, setSettings] = useState<PersonalitySettings>({
    nickname: "",
    tone: "balanced",
    emoji: false,
    extra_rules: [],
  });
  const [language, setLanguage] = useState<"zh" | "en">("zh");
  const [previewText, setPreviewText] = useState<string | null>(null);
  const [rulesText, setRulesText] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await getPersonalityOverview();
      setOverview(data);
      setSettings(data.settings);
      setRulesText(data.settings.extra_rules.join("\n"));
      setPreviewText(data.prompts[language]);
      setError(null);
    } catch (loadError) {
      setError(errorText(loadError));
    }
  }, [language]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  function draftSettings(): PersonalitySettings {
    return {
      ...settings,
      extra_rules: rulesText
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean)
        .slice(0, 8),
    };
  }

  async function handleSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setMessage(null);
    setError(null);
    try {
      const data = await updatePersonalitySettings(draftSettings());
      setOverview(data);
      setSettings(data.settings);
      setRulesText(data.settings.extra_rules.join("\n"));
      setPreviewText(data.prompts[language]);
      setMessage("人格设置已保存，下次对话立即生效。");
    } catch (saveError) {
      setError(errorText(saveError));
    } finally {
      setBusy(false);
    }
  }

  async function handlePreview() {
    setBusy(true);
    setMessage(null);
    setError(null);
    try {
      const result = await previewPersonality(language, draftSettings());
      setPreviewText(result.prompt);
      setMessage("预览已生成，尚未保存。");
    } catch (previewError) {
      setError(errorText(previewError));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="personality-shell">
      <div className="personality-banner">
        <Sparkles />
        <div>
          <strong>{overview?.disclaimer ?? "人格只影响表达方式，不改变事实判断、安全边界和你的最新要求。"}</strong>
          <p>中英文人格保持一致；任何冲突都以事实、安全规则和你的最新要求为准。</p>
        </div>
        <button aria-label="刷新人格设置" disabled={busy} onClick={() => void load()} type="button">
          <RefreshCw className={busy ? "is-spinning" : ""} />
        </button>
      </div>

      {(message || error) && (
        <div className={`personality-notice ${error ? "is-error" : "is-success"}`}>
          {error ? <AlertTriangle /> : <Check />}
          <span>{error ?? message}</span>
          <button onClick={() => { setMessage(null); setError(null); }} type="button"><X /></button>
        </div>
      )}

      <div className="personality-grid">
        <form className="personality-form" onSubmit={(event) => void handleSave(event)}>
          <div className="personality-panel-heading">
            <div><small>IDENTITY & TONE</small><h2>人格设置</h2></div>
            <UserRound />
          </div>

          <label className="personality-field">
            <span>称呼</span>
            <input
              maxLength={32}
              onChange={(event) => setSettings((current) => ({ ...current, nickname: event.target.value }))}
              placeholder="例如：小贾（留空则用「你」）"
              value={settings.nickname}
            />
          </label>

          <div className="personality-field">
            <span>语气</span>
            <div className="personality-tone-row">
              {(["balanced", "casual", "formal"] as const).map((tone) => (
                <button
                  className={settings.tone === tone ? "is-active" : ""}
                  key={tone}
                  onClick={() => setSettings((current) => ({ ...current, tone }))}
                  type="button"
                >
                  <strong>{toneLabels[tone]}</strong>
                  <small>{toneDescriptions[tone]}</small>
                </button>
              ))}
            </div>
          </div>

          <label className="personality-check">
            <input
              checked={settings.emoji}
              onChange={(event) => setSettings((current) => ({ ...current, emoji: event.target.checked }))}
              type="checkbox"
            />
            <span>允许使用少量表情符号</span>
          </label>

          <label className="personality-field">
            <span>额外表达规则（每行一条，最多 8 条）</span>
            <textarea
              onChange={(event) => setRulesText(event.target.value)}
              placeholder={"每次回答先给结论\n不要使用敬语"}
              rows={5}
              value={rulesText}
            />
          </label>

          <div className="personality-actions">
            <button className="personality-button preview" disabled={busy} onClick={() => void handlePreview()} type="button">
              <Eye />预览
            </button>
            <button className="personality-button save" disabled={busy} type="submit">
              <Save />保存
            </button>
          </div>
        </form>

        <div className="personality-preview-panel">
          <div className="personality-panel-heading">
            <div><small>SYSTEM PROMPT</small><h2>提示词预览</h2></div>
            <Wand2 />
          </div>
          <div className="personality-lang-tabs">
            {(["zh", "en"] as const).map((lang) => (
              <button className={language === lang ? "is-active" : ""} key={lang} onClick={() => setLanguage(lang)} type="button">
                <Languages />{lang === "zh" ? "中文" : "English"}
              </button>
            ))}
          </div>
          <pre className="personality-prompt">
            {previewText ?? "正在生成预览…"}
          </pre>
        </div>
      </div>

      <div className="personality-boundaries-panel">
        <div className="personality-panel-heading">
          <div><small>NEVER OVERRIDDEN</small><h2>人格不能覆盖的边界</h2></div>
          <LockKeyhole />
        </div>
        <div className="personality-boundary-grid">
          {overview?.boundaries.map((boundary, index) => (
            <div className="personality-boundary-card" key={boundary}>
              <span>{boundaryIcons[index % boundaryIcons.length]}</span>
              <p>{boundary}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
