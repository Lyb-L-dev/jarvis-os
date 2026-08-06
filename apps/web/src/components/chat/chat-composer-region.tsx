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
import type { KeyboardEvent } from "react";

import { modeOptions } from "@/components/chat/chat-utils";
import type { ModelMode } from "@/lib/api";

export function ChatComposerRegion({
  error,
  setError,
  memoryNotice,
  setMemoryNotice,
  taskNotice,
  setTaskNotice,
  captureNotice,
  setCaptureNotice,
  listening,
  onToggleDictation,
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
}: {
  error: string | null;
  setError: (value: string | null) => void;
  memoryNotice: string | null;
  setMemoryNotice: (value: string | null) => void;
  taskNotice: string | null;
  setTaskNotice: (value: string | null) => void;
  captureNotice: string | null;
  setCaptureNotice: (value: string | null) => void;
  listening: boolean;
  onToggleDictation: () => void;
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
}) {
  return (
    <div className="workspace-composer-region">
      {error ? (
        <div className="workspace-notice workspace-notice-error">
          <span>{error}</span>
          <button
            aria-label="关闭错误提示"
            onClick={() => setError(null)}
            type="button"
          >
            <X aria-hidden="true" />
          </button>
        </div>
      ) : null}
      {memoryNotice ? (
        <div className="workspace-notice">
          <BrainCircuit aria-hidden="true" />
          <span>{memoryNotice}</span>
          <Link href="/memory">检查记忆</Link>
          <button
            aria-label="关闭记忆提示"
            onClick={() => setMemoryNotice(null)}
            type="button"
          >
            <X aria-hidden="true" />
          </button>
        </div>
      ) : null}
      {taskNotice ? (
        <div className="workspace-notice">
          <Layers3 aria-hidden="true" />
          <span>{taskNotice}</span>
          <Link href="/growth">打开行动</Link>
          <button
            aria-label="关闭任务提示"
            onClick={() => setTaskNotice(null)}
            type="button"
          >
            <X aria-hidden="true" />
          </button>
        </div>
      ) : null}
      {captureNotice ? (
        <div className="workspace-notice">
          <BookOpenCheck aria-hidden="true" />
          <span>{captureNotice}</span>
          <Link href="/knowledge">检查知识草稿</Link>
          <button
            aria-label="关闭知识草稿提示"
            onClick={() => setCaptureNotice(null)}
            type="button"
          >
            <X aria-hidden="true" />
          </button>
        </div>
      ) : null}

      <div className="workspace-composer">
        <div className="workspace-composer-input">
          <button
            aria-label={listening ? "停止语音输入" : "开始语音输入"}
            className={listening ? "is-listening" : ""}
            disabled={sending}
            onClick={onToggleDictation}
            type="button"
          >
            <Mic aria-hidden="true" />
          </button>
          <textarea
            aria-label="发送给 Jarvis"
            disabled={sending}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={onComposerKeyDown}
            placeholder={
              listening
                ? "Jarvis 正在聆听…"
                : "告诉 Jarvis 你想理解、规划或完成什么…"
            }
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
            {sending ? (
              <Square aria-hidden="true" />
            ) : (
              <Send aria-hidden="true" />
            )}
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
          <span>
            {sending
              ? "结果正在生成，点击停止会自动保存已有内容"
              : "Enter 发送 · Shift+Enter 换行"}
          </span>
        </div>
      </div>
    </div>
  );
}
