import type { KeyboardEvent, RefObject } from "react";

import type {
  EnglishMistake,
  EnglishSessionDetail,
} from "@/lib/api";

import {
  correctionModeLabel,
  providerLabel,
  sessionTitle,
  sessionTypes,
  statusLabels,
} from "@/components/english/english-utils";

export function EnglishConversation({
  selectedSession,
  busy,
  draft,
  setDraft,
  draftInputMode,
  setDraftInputMode,
  listening,
  onToggleSpeech,
  onSubmitMessage,
  onComposerKeyDown,
  onFinish,
  onSaveTranscript,
  editingMessageId,
  setEditingMessageId,
  editingTranscript,
  setEditingTranscript,
  messagesEnd,
  mistakeMap,
  onConfirmMistake,
  onChangeMistakeStatus,
  onOpenMistakes,
}: {
  selectedSession: EnglishSessionDetail;
  busy: string | null;
  draft: string;
  setDraft: (value: string) => void;
  draftInputMode: "text" | "voice_transcript";
  setDraftInputMode: (value: "text" | "voice_transcript") => void;
  listening: boolean;
  onToggleSpeech: () => void;
  onSubmitMessage: () => void;
  onComposerKeyDown: (event: KeyboardEvent<HTMLTextAreaElement>) => void;
  onFinish: () => void;
  onSaveTranscript: (messageId: string) => void;
  editingMessageId: string | null;
  setEditingMessageId: (value: string | null) => void;
  editingTranscript: string;
  setEditingTranscript: (value: string) => void;
  messagesEnd: RefObject<HTMLDivElement | null>;
  mistakeMap: Map<string, EnglishMistake>;
  onConfirmMistake: (mistake: EnglishMistake) => void;
  onChangeMistakeStatus: (
    mistake: EnglishMistake,
    action: "reject" | "master" | "dispute",
  ) => void;
  onOpenMistakes: () => void;
}) {
  return (
    <div className="english-conversation">
      <header className="english-conversation-head">
        <div>
          <span>
            {sessionTypes.find(
              (item) => item.value === selectedSession.session_type,
            )?.label || "英语对话"}{" "}
            · {selectedSession.level}
          </span>
          <h2>{sessionTitle(selectedSession)}</h2>
          <p>
            {correctionModeLabel(selectedSession.correction_mode)} ·{" "}
            {selectedSession.processing_mode === "standard"
              ? "MiMo 优先 / 本地兜底"
              : "只用本地 Qwen"}
          </p>
        </div>
        {selectedSession.status === "active" ? (
          <button
            className="english-finish-button"
            disabled={busy === "complete-session"}
            onClick={() => void onFinish()}
            type="button"
          >
            {busy === "complete-session" ? "正在总结…" : "结束并总结"}
          </button>
        ) : (
          <span className="english-complete-badge">已完成</span>
        )}
      </header>

      <div className="english-message-list">
        {selectedSession.messages.length === 0 && (
          <div className="english-welcome">
            <div>Aa</div>
            <h3>Ready when you are.</h3>
            <p>
              用英语说说你现在在做什么。可以打字，也可以点击麦克风说话。
            </p>
          </div>
        )}
        {selectedSession.messages.map((message) => {
          const corrections = message.correction_ids
            .map((id) => mistakeMap.get(id))
            .filter((item): item is EnglishMistake => Boolean(item));
          return (
            <div
              className={`english-message english-message-${message.role}`}
              key={message.id}
            >
              <div className="english-message-label">
                <span>
                  {message.role === "user" ? "YOU" : "JARVIS COACH"}
                </span>
                {providerLabel(message) && (
                  <small>{providerLabel(message)}</small>
                )}
              </div>
              {editingMessageId === message.id ? (
                <div className="english-transcript-editor">
                  <textarea
                    onChange={(event) =>
                      setEditingTranscript(event.target.value)
                    }
                    value={editingTranscript}
                  />
                  <div>
                    <button
                      onClick={() => setEditingMessageId(null)}
                      type="button"
                    >
                      取消
                    </button>
                    <button
                      disabled={busy === `edit-message-${message.id}`}
                      onClick={() => void onSaveTranscript(message.id)}
                      type="button"
                    >
                      保存转写
                    </button>
                  </div>
                </div>
              ) : (
                <p>{message.content}</p>
              )}
              {message.role === "user" && (
                <button
                  className="english-edit-transcript"
                  onClick={() => {
                    setEditingMessageId(message.id);
                    setEditingTranscript(message.content);
                  }}
                  type="button"
                >
                  {message.input_mode === "voice_transcript"
                    ? "修正语音转写"
                    : "编辑原句"}
                  {message.transcript_edited && " · 已修改"}
                </button>
              )}
              {corrections.map((mistake) => (
                <article
                  className="english-inline-correction"
                  key={mistake.id}
                >
                  <div>
                    <span>{mistake.category}</span>
                    <small>{statusLabels[mistake.status]}</small>
                  </div>
                  <del>{mistake.original_text}</del>
                  <strong>{mistake.corrected_text}</strong>
                  <p>{mistake.explanation}</p>
                  {mistake.status === "pending" && (
                    <div className="english-inline-actions">
                      <button
                        disabled={busy === `reject-${mistake.id}`}
                        onClick={() =>
                          void onChangeMistakeStatus(mistake, "reject")
                        }
                        type="button"
                      >
                        解释不对
                      </button>
                      <button
                        disabled={busy === `confirm-${mistake.id}`}
                        onClick={() => void onConfirmMistake(mistake)}
                        type="button"
                      >
                        确认并加入复习
                      </button>
                    </div>
                  )}
                </article>
              ))}
            </div>
          );
        })}
        {busy === "send-message" && (
          <div className="english-message english-message-assistant">
            <div className="english-message-label">
              <span>JARVIS COACH</span>
              <small>正在组织回答</small>
            </div>
            <div className="english-thinking">
              <i />
              <i />
              <i />
            </div>
          </div>
        )}
        {selectedSession.summary && (
          <article className="english-session-summary">
            <span>SESSION SUMMARY</span>
            <h3>本次学习小结</h3>
            <p>{selectedSession.summary}</p>
            <button onClick={onOpenMistakes} type="button">
              打开错题本核对纠错 →
            </button>
          </article>
        )}
        <div ref={messagesEnd} />
      </div>

      {selectedSession.status === "active" && (
        <div className="english-composer">
          <div className="english-composer-status">
            <span>
              {draftInputMode === "voice_transcript"
                ? "语音转写 · 发送前可自由修改"
                : "English only · Enter 发送，Shift + Enter 换行"}
            </span>
            <small>
              {selectedSession.correction_mode === "summary"
                ? "本轮不会打断纠错"
                : correctionModeLabel(selectedSession.correction_mode)}
            </small>
          </div>
          <div className="english-composer-row">
            <button
              aria-label={listening ? "停止录音" : "开始语音输入"}
              className={`english-mic-button ${
                listening ? "mic-listening" : ""
              }`}
              onClick={onToggleSpeech}
              type="button"
            >
              {listening ? "■" : "●"}
            </button>
            <textarea
              onChange={(event) => {
                setDraft(event.target.value);
                if (draftInputMode !== "voice_transcript") {
                  setDraftInputMode("text");
                }
              }}
              onKeyDown={onComposerKeyDown}
              placeholder="Write or speak in English…"
              value={draft}
            />
            <button
              className="english-send-button"
              disabled={!draft.trim() || busy === "send-message"}
              onClick={() => void onSubmitMessage()}
              type="button"
            >
              发送
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
