import type { FormEvent } from "react";

import type {
  EnglishCorrectionMode,
  EnglishLevel,
  EnglishProcessingMode,
  EnglishSessionType,
} from "@/lib/api";

import {
  correctionModes,
  sessionTypes,
} from "@/components/english/english-utils";

export function EnglishSessionSetup({
  sessionType,
  setSessionType,
  topic,
  setTopic,
  correctionMode,
  setCorrectionMode,
  level,
  setLevel,
  processingMode,
  setProcessingMode,
  busy,
  onSubmit,
}: {
  sessionType: EnglishSessionType;
  setSessionType: (value: EnglishSessionType) => void;
  topic: string;
  setTopic: (value: string) => void;
  correctionMode: EnglishCorrectionMode;
  setCorrectionMode: (value: EnglishCorrectionMode) => void;
  level: EnglishLevel;
  setLevel: (value: EnglishLevel) => void;
  processingMode: EnglishProcessingMode;
  setProcessingMode: (value: EnglishProcessingMode) => void;
  busy: string | null;
  onSubmit: (event: FormEvent) => void;
}) {
  return (
    <form className="english-setup" onSubmit={onSubmit}>
      <div className="english-setup-heading">
        <span>NEW SESSION</span>
        <h2>这次想怎么练？</h2>
        <p>先选场景和纠错节奏，随时可以结束并生成学习总结。</p>
      </div>

      <fieldset>
        <legend>练习场景</legend>
        <div className="english-option-grid">
          {sessionTypes.map((item) => (
            <label
              className={sessionType === item.value ? "option-selected" : ""}
              key={item.value}
            >
              <input
                checked={sessionType === item.value}
                name="session-type"
                onChange={() => setSessionType(item.value)}
                type="radio"
              />
              <strong>{item.label}</strong>
              <small>{item.description}</small>
            </label>
          ))}
        </div>
      </fieldset>

      <label className="english-field english-field-wide">
        <span>
          {sessionType === "topic"
            ? "练习主题（必填）"
            : "主题或方向（可选）"}
        </span>
        <input
          onChange={(event) => setTopic(event.target.value)}
          placeholder={
            sessionType === "interview"
              ? "例如：前端开发岗位"
              : sessionType === "technical"
                ? "例如：解释一个 API 设计"
                : "例如：My weekend plan"
          }
          value={topic}
        />
      </label>

      <fieldset>
        <legend>纠错节奏</legend>
        <div className="english-correction-options">
          {correctionModes.map((item) => (
            <label
              className={correctionMode === item.value ? "option-selected" : ""}
              key={item.value}
            >
              <input
                checked={correctionMode === item.value}
                name="correction-mode"
                onChange={() => setCorrectionMode(item.value)}
                type="radio"
              />
              <strong>{item.label}</strong>
              <small>{item.description}</small>
            </label>
          ))}
        </div>
      </fieldset>

      <div className="english-setup-row">
        <label className="english-field">
          <span>当前水平</span>
          <select
            onChange={(event) => setLevel(event.target.value as EnglishLevel)}
            value={level}
          >
            {["A1", "A2", "B1", "B2", "C1", "C2"].map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </label>
        <label className="english-field">
          <span>模型路线</span>
          <select
            onChange={(event) =>
              setProcessingMode(
                event.target.value as EnglishProcessingMode,
              )
            }
            value={processingMode}
          >
            <option value="standard">MiMo 优先 · 自动本地降级</option>
            <option value="local">只用本地 Qwen</option>
          </select>
        </label>
      </div>

      <div className="english-cost-note">
        <span>¥0</span>
        English Coach 不会自动调用 DeepSeek，整个页面没有付费升级入口。
      </div>
      <button
        className="primary-button english-start-button"
        disabled={busy === "start-session"}
        type="submit"
      >
        {busy === "start-session" ? "正在创建…" : "开始英语对话"}
      </button>
    </form>
  );
}
