"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import {
  completeOnboardingSession,
  createOnboardingSession,
  getProfile,
  updateOnboardingSession,
  type ProfileResponse,
} from "@/lib/api";

type WizardForm = {
  name: string;
  major: string;
  careerGoals: string;
  currentSkills: string;
  weaknesses: string;
  dailyHours: number;
  aiAgentInterest: string;
  technologyInterest: string;
  investmentInterest: string;
  internationalInterest: string;
  voiceAutoPlay: boolean;
  wechat: boolean;
  autoMemory: boolean;
  investmentCloudAllowed: boolean;
};

const initialForm: WizardForm = {
  name: "",
  major: "",
  careerGoals: "",
  currentSkills: "",
  weaknesses: "",
  dailyHours: 4,
  aiAgentInterest: "high",
  technologyInterest: "medium_high",
  investmentInterest: "medium",
  internationalInterest: "medium",
  voiceAutoPlay: true,
  wechat: false,
  autoMemory: true,
  investmentCloudAllowed: false,
};

const steps = ["目标与能力", "信息兴趣", "提醒与隐私", "确认"];

function splitList(value: string): string[] {
  return value
    .split(/[,，]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

export function OnboardingWizard({
  initialProfile,
}: {
  initialProfile?: ProfileResponse | null;
}) {
  const [form, setForm] = useState<WizardForm>(initialForm);
  const [step, setStep] = useState(1);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [profile, setProfile] = useState<ProfileResponse | null>(
    initialProfile ?? null,
  );
  const [loading, setLoading] = useState(initialProfile === undefined);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [finished, setFinished] = useState(false);

  useEffect(() => {
    if (initialProfile !== undefined) {
      return;
    }

    let cancelled = false;

    getProfile()
      .then((result) => {
        if (cancelled) return;
        setProfile(result);
      })
      .catch((reason: unknown) => {
        if (!cancelled) {
          setError(reason instanceof Error ? reason.message : "读取档案失败");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [initialProfile]);

  const answers = useMemo(
    () => ({
      education_level: "本科",
      major: form.major,
      career_goals: splitList(form.careerGoals),
      current_skills: splitList(form.currentSkills),
      weaknesses: splitList(form.weaknesses),
      daily_available_minutes: form.dailyHours * 60,
      information_interests: {
        ai_agent: form.aiAgentInterest,
        technology: form.technologyInterest,
        careers: "high",
        investment: form.investmentInterest,
        international: form.internationalInterest,
      },
      notification_settings: {
        voice_auto_play: form.voiceAutoPlay,
        wechat: form.wechat,
        timezone: "Asia/Shanghai",
      },
      privacy_settings: {
        auto_memory: form.autoMemory,
        investment_cloud_allowed: form.investmentCloudAllowed,
      },
      model_preferences: {
        standard: "mimo",
        deep: "deepseek",
        local: "qwen3:4b-instruct-2507-q4_K_M",
      },
    }),
    [form],
  );

  function updateForm<K extends keyof WizardForm>(
    key: K,
    value: WizardForm[K],
  ) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  async function saveAndContinue() {
    setSaving(true);
    setError(null);

    try {
      let currentSessionId = sessionId;
      if (!currentSessionId) {
        const created = await createOnboardingSession({
          user_name: form.name,
          timezone: "Asia/Shanghai",
        });
        currentSessionId = created.id;
        setSessionId(created.id);
      }

      await updateOnboardingSession(currentSessionId, {
        current_step: Math.min(step + 1, steps.length),
        answers,
      });

      if (step === steps.length) {
        await completeOnboardingSession(currentSessionId);
        setFinished(true);
      } else {
        setStep((current) => current + 1);
      }
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "保存失败");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <main className="dashboard onboarding-page">
        <section className="onboarding-shell onboarding-loading">
          <div className="loader-orbit" />
          正在读取 Jarvis 档案…
        </section>
      </main>
    );
  }

  if (profile?.onboarding_completed || finished) {
    return (
      <main className="dashboard onboarding-page">
        <section className="onboarding-shell onboarding-complete">
          <div className="complete-mark">✓</div>
          <div className="eyebrow cyan-text">INITIALIZATION COMPLETE</div>
          <h1>Jarvis 已经认识你了。</h1>
          <p>
            个人档案、信息偏好、自动记忆、语音提醒和模型分工已经保存，第一周行动计划也已建立。
          </p>
          <div className="profile-summary">
            <div>
              <span>职业方向</span>
              <strong>
                {profile?.profile.career_goals?.join(" · ") ??
                  splitList(form.careerGoals).join(" · ")}
              </strong>
            </div>
            <div>
              <span>每日投入</span>
              <strong>
                {(profile?.profile.daily_available_minutes ?? form.dailyHours * 60) /
                  60}
                小时
              </strong>
            </div>
            <div>
              <span>默认模型</span>
              <strong>MiMo · DeepSeek 辅助</strong>
            </div>
          </div>
          <Link className="primary-button onboarding-finish-button" href="/">
            返回 Jarvis 总览
          </Link>
        </section>
      </main>
    );
  }

  return (
    <main className="dashboard onboarding-page">
      <header className="onboarding-header">
        <div>
          <div className="eyebrow cyan-text">JARVIS INITIALIZATION</div>
          <h1>建立你的个人操作系统</h1>
          <p>这些信息会保存在本地，并用于生成第一周行动计划。</p>
        </div>
        <Link className="ghost-button onboarding-exit" href="/">
          暂时退出
        </Link>
      </header>

      <div className="onboarding-progress">
        {steps.map((label, index) => (
          <div
            className={`onboarding-step ${
              step >= index + 1 ? "onboarding-step-active" : ""
            }`}
            key={label}
          >
            <span>{index + 1}</span>
            {label}
          </div>
        ))}
      </div>

      <section className="onboarding-shell">
        {step === 1 && (
          <div className="wizard-section">
            <div className="wizard-heading">
              <div className="wizard-index">01</div>
              <div>
                <h2>目标与当前能力</h2>
                <p>Jarvis 会据此判断什么值得关注，以及任务难度。</p>
              </div>
            </div>
            <div className="form-grid">
              <label>
                <span>你的称呼</span>
                <input
                  value={form.name}
                  onChange={(event) => updateForm("name", event.target.value)}
                />
              </label>
              <label>
                <span>本科专业</span>
                <input
                  value={form.major}
                  onChange={(event) => updateForm("major", event.target.value)}
                />
              </label>
              <label className="form-wide">
                <span>职业目标，用逗号分隔</span>
                <input
                  value={form.careerGoals}
                  onChange={(event) =>
                    updateForm("careerGoals", event.target.value)
                  }
                />
              </label>
              <label className="form-wide">
                <span>当前技能，用逗号分隔</span>
                <input
                  value={form.currentSkills}
                  onChange={(event) =>
                    updateForm("currentSkills", event.target.value)
                  }
                />
              </label>
              <label className="form-wide">
                <span>目前的困难，用逗号分隔</span>
                <input
                  value={form.weaknesses}
                  onChange={(event) =>
                    updateForm("weaknesses", event.target.value)
                  }
                />
              </label>
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="wizard-section">
            <div className="wizard-heading">
              <div className="wizard-index">02</div>
              <div>
                <h2>信息兴趣</h2>
                <p>权重越高，越容易进入每天 3～5 条情报。</p>
              </div>
            </div>
            <div className="interest-list">
              {[
                ["aiAgentInterest", "AI / Agent / LLM", form.aiAgentInterest],
                ["technologyInterest", "科技", form.technologyInterest],
                ["investmentInterest", "投资", form.investmentInterest],
                ["internationalInterest", "国际动态", form.internationalInterest],
              ].map(([key, label, value]) => (
                <label className="interest-row" key={key}>
                  <span>{label}</span>
                  <select
                    value={String(value)}
                    onChange={(event) =>
                      updateForm(
                        key as keyof WizardForm,
                        event.target.value as never,
                      )
                    }
                  >
                    <option value="high">高</option>
                    <option value="medium_high">中高</option>
                    <option value="medium">中</option>
                    <option value="low">低</option>
                  </select>
                </label>
              ))}
            </div>
          </div>
        )}

        {step === 3 && (
          <div className="wizard-section">
            <div className="wizard-heading">
              <div className="wizard-index">03</div>
              <div>
                <h2>提醒、时间与隐私</h2>
                <p>所有选项都可以稍后在设置中修改。</p>
              </div>
            </div>
            <div className="preference-list">
              <label className="hours-field">
                <span>每天预计投入</span>
                <div>
                  <input
                    max={12}
                    min={1}
                    type="number"
                    value={form.dailyHours}
                    onChange={(event) =>
                      updateForm("dailyHours", Number(event.target.value))
                    }
                  />
                  <span>小时</span>
                </div>
              </label>
              <ToggleRow
                checked={form.voiceAutoPlay}
                description="电脑处于唤醒状态时自动开口"
                label="自动语音提醒"
                onChange={(value) => updateForm("voiceAutoPlay", value)}
              />
              <ToggleRow
                checked={form.wechat}
                description="OpenClaw 安全隔离完成前不启用"
                disabled
                label="微信提醒（延期）"
                onChange={(value) => updateForm("wechat", value)}
              />
              <ToggleRow
                checked={form.autoMemory}
                description="自动保存有长期价值、非敏感的信息"
                label="自动长期记忆"
                onChange={(value) => updateForm("autoMemory", value)}
              />
              <ToggleRow
                checked={form.investmentCloudAllowed}
                description="默认关闭，持仓数据优先保留在本地"
                label="允许投资数据发送至云端模型"
                onChange={(value) =>
                  updateForm("investmentCloudAllowed", value)
                }
              />
            </div>
          </div>
        )}

        {step === 4 && (
          <div className="wizard-section">
            <div className="wizard-heading">
              <div className="wizard-index">04</div>
              <div>
                <h2>确认初始化</h2>
                <p>Jarvis 将以这些信息建立个人档案和默认策略。</p>
              </div>
            </div>
            <div className="review-grid">
              <ReviewItem label="职业目标" value={splitList(form.careerGoals).join(" · ")} />
              <ReviewItem label="当前技能" value={splitList(form.currentSkills).join(" · ")} />
              <ReviewItem label="每日投入" value={`${form.dailyHours} 小时`} />
              <ReviewItem label="默认模型" value="MiMo 主导 · DeepSeek 辅助" />
              <ReviewItem
                label="主动提醒"
                value={`${form.voiceAutoPlay ? "语音" : "无语音"} · ${
                  form.wechat ? "微信" : "微信延期"
                }`}
              />
              <ReviewItem
                label="自动记忆"
                value={form.autoMemory ? "已启用" : "已关闭"}
              />
            </div>
          </div>
        )}

        {error && <div className="wizard-error">{error}</div>}

        <div className="wizard-actions">
          <button
            className="ghost-button"
            disabled={step === 1 || saving}
            onClick={() => setStep((current) => Math.max(1, current - 1))}
            type="button"
          >
            上一步
          </button>
          <button
            className="primary-button"
            disabled={saving}
            onClick={saveAndContinue}
            type="button"
          >
            {saving
              ? "正在保存…"
              : step === steps.length
                ? "完成初始化"
                : "保存并继续"}
          </button>
        </div>
      </section>
    </main>
  );
}

function ToggleRow({
  checked,
  description,
  disabled = false,
  label,
  onChange,
}: {
  checked: boolean;
  description: string;
  disabled?: boolean;
  label: string;
  onChange: (value: boolean) => void;
}) {
  return (
    <label className="toggle-row">
      <div>
        <strong>{label}</strong>
        <span>{description}</span>
      </div>
      <input
        checked={checked}
        disabled={disabled}
        onChange={(event) => onChange(event.target.checked)}
        type="checkbox"
      />
    </label>
  );
}

function ReviewItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="review-item">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
