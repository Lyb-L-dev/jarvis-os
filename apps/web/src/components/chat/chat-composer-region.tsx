import Link from "next/link";
import {
  BookOpenCheck,
  BrainCircuit,
  Layers3,
  LockKeyhole,
  Mic,
  Send,
  Square,
  X,
} from "lucide-react";
import type { KeyboardEvent, ReactNode } from "react";

import { modeOptions } from "@/components/chat/chat-utils";
import type { ModelMode, VoiceLoopState } from "@/lib/api";

type ComposerProps = {
  error: string | null;
  setError: (value: string | null) => void;
  memoryNotice: string | null;
  setMemoryNotice: (value: string | null) => void;
  taskNotice: string | null;
  setTaskNotice: (value: string | null) => void;
  captureNotice: string | null;
  setCaptureNotice: (value: string | null) => void;
  voiceState: VoiceLoopState;
  voiceAvailable: boolean;
  voiceReason: string | null;
  onToggleVoice: () => void;
  input: string;
  setInput: (value: string) => void;
  sending: boolean;
  onSend: () => void;
  onStop: () => void;
  mode: ModelMode;
  setMode: (value: ModelMode) => void;
  sensitive: boolean;
  setSensitive: (value: boolean) => void;
  useKnowledge: boolean;
  setUseKnowledge: (value: boolean) => void;
  onComposerKeyDown: (event: KeyboardEvent<HTMLTextAreaElement>) => void;
};

export function ChatComposerRegion({
  error,
  setError,
  memoryNotice,
  setMemoryNotice,
  taskNotice,
  setTaskNotice,
  captureNotice,
  setCaptureNotice,
  voiceState,
  voiceAvailable,
  voiceReason,
  onToggleVoice,
  input,
  setInput,
  sending,
  onSend,
  onStop,
  mode,
  setMode,
  sensitive,
  setSensitive,
  useKnowledge,
  setUseKnowledge,
  onComposerKeyDown,
}: ComposerProps) {
  return (
    <div className="workspace-composer-region">
      {error ? (
        <Notice text={error} error onClose={() => setError(null)} />
      ) : null}
      {memoryNotice ? (
        <Notice
          icon={<BrainCircuit aria-hidden="true" />}
          text={memoryNotice}
          link={{ href: "/memory", label: "检查记忆" }}
          onClose={() => setMemoryNotice(null)}
        />
      ) : null}
      {taskNotice ? (
        <Notice
          icon={<Layers3 aria-hidden="true" />}
          text={taskNotice}
          link={{ href: "/growth", label: "打开行动" }}
          onClose={() => setTaskNotice(null)}
        />
      ) : null}
      {captureNotice ? (
        <Notice
          icon={<BookOpenCheck aria-hidden="true" />}
          text={captureNotice}
          link={{ href: "/knowledge", label: "检查知识草稿" }}
          onClose={() => setCaptureNotice(null)}
        />
      ) : null}

      <div className="workspace-composer">
        <div className="workspace-composer-input">
          <button
            aria-label={voiceActionLabel(voiceState, voiceAvailable)}
            className={voiceState === "listening" ? "is-listening" : ""}
            disabled={!voiceAvailable && !sending}
            onClick={onToggleVoice}
            title={voiceTitle(voiceAvailable, voiceReason)}
            type="button"
          >
            <Mic aria-hidden="true" />
          </button>
          <textarea
            aria-label="发送给 Jarvis"
            disabled={sending}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={onComposerKeyDown}
            placeholder={composerPlaceholder(voiceState)}
            rows={2}
            value={input}
          />
          <button
            aria-label={sending ? "停止生成" : "发送"}
            className={`workspace-send ${sending ? "is-stopping" : ""}`}
            disabled={!sending && !input.trim()}
            onClick={() => (sending ? onStop() : onSend())}
            type="button"
          >
            {sending ? <Square aria-hidden="true" /> : <Send aria-hidden="true" />}
          </button>
        </div>

        <div className="workspace-composer-controls">
          <select
            aria-label="模型模式"
            disabled={sending}
            onChange={(event) => setMode(event.target.value as ModelMode)}
            value={mode}
          >
            {modeOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label} · {option.detail}
              </option>
            ))}
          </select>
          <label className={sensitive ? "is-active" : ""}>
            <input
              checked={sensitive}
              disabled={sending}
              onChange={(event) => setSensitive(event.target.checked)}
              type="checkbox"
            />
            <LockKeyhole aria-hidden="true" />
            隐私模式
          </label>
          <label
            className={useKnowledge ? "is-active" : ""}
            title="本地模式可使用所有已启用笔记；云端模型只使用明确允许的笔记"
          >
            <input
              checked={useKnowledge}
              disabled={sending}
              onChange={(event) => setUseKnowledge(event.target.checked)}
              type="checkbox"
            />
            <BookOpenCheck aria-hidden="true" />
            知识增强
          </label>
          <span aria-live="polite">
            {voiceStatusText(voiceState, sending, voiceAvailable)}
          </span>
        </div>
      </div>
    </div>
  );
}

function Notice({
  icon,
  text,
  link,
  error = false,
  onClose,
}: {
  icon?: ReactNode;
  text: string;
  link?: { href: string; label: string };
  error?: boolean;
  onClose: () => void;
}) {
  return (
    <div className={`workspace-notice ${error ? "workspace-notice-error" : ""}`}>
      {icon}
      <span>{text}</span>
      {link ? <Link href={link.href}>{link.label}</Link> : null}
      <button aria-label="关闭提示" onClick={onClose} type="button">
        <X aria-hidden="true" />
      </button>
    </div>
  );
}

function voiceActionLabel(state: VoiceLoopState, available: boolean): string {
  if (!available) return "本地语音不可用";
  if (state === "listening") return "停止录音并本地转写";
  if (state === "responding" || state === "speaking") return "打断并重新聆听";
  return "开始本地语音对话";
}

function voiceTitle(available: boolean, reason: string | null): string {
  if (available) return "本地语音：音频不会发送到云端";
  return reason === "feature_disabled"
    ? "本地语音功能尚未启用"
    : "本地语音模型尚未就绪";
}

function composerPlaceholder(state: VoiceLoopState): string {
  if (state === "listening") return "Jarvis 正在本地聆听…";
  if (state === "transcribing") return "正在本地转写…";
  return "告诉 Jarvis 你想理解、规划或完成什么…";
}

function voiceStatusText(
  state: VoiceLoopState,
  sending: boolean,
  available: boolean,
): string {
  if (state === "listening") return "正在聆听；再次点击麦克风即可发送";
  if (state === "transcribing") return "音频正在本机转写，不会上传云端";
  if (state === "responding") return "Jarvis 正在回答；点击麦克风可打断";
  if (state === "speaking") return "正在本地播放；点击麦克风可打断";
  if (sending) return "结果正在生成；点击停止会保留已有内容";
  if (!available) return "本地语音未启用，文本对话仍可正常使用";
  return "Enter 发送 · Shift+Enter 换行 · 麦克风仅在点击后工作";
}
