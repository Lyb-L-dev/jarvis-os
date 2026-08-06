import type { EnglishSession, EnglishSessionDetail } from "@/lib/api";

import {
  correctionModeLabel,
  sessionTitle,
} from "@/components/english/english-utils";

export function EnglishSessionRail({
  sessions,
  selectedSession,
  showSetup,
  busy,
  onOpen,
  onDelete,
  onNew,
}: {
  sessions: EnglishSession[];
  selectedSession: EnglishSessionDetail | null;
  showSetup: boolean;
  busy: string | null;
  onOpen: (session: EnglishSession) => void;
  onDelete: (session: EnglishSession) => void;
  onNew: () => void;
}) {
  return (
    <aside className="english-session-rail">
      <div className="english-section-head">
        <div>
          <span>HISTORY</span>
          <h2>练习记录</h2>
        </div>
        <button aria-label="开始新练习" onClick={onNew} type="button">
          ＋
        </button>
      </div>
      <div className="english-session-list">
        {sessions.map((session) => (
          <div
            className={`english-session-item ${
              selectedSession?.id === session.id && !showSetup
                ? "session-selected"
                : ""
            }`}
            key={session.id}
          >
            <button
              className="session-open"
              onClick={() => onOpen(session)}
              type="button"
            >
              <span>
                {session.status === "active" ? "进行中" : "已完成"} ·{" "}
                {session.level}
              </span>
              <strong>{sessionTitle(session)}</strong>
              <small>
                {correctionModeLabel(session.correction_mode)} ·{" "}
                {Math.floor(session.message_count / 2)} 轮
              </small>
            </button>
            <button
              aria-label="删除会话"
              className="session-delete"
              disabled={busy === `delete-session-${session.id}`}
              onClick={() => onDelete(session)}
              type="button"
            >
              ×
            </button>
          </div>
        ))}
        {sessions.length === 0 && (
          <div className="english-inline-empty">
            还没有练习记录
            <small>从右侧选择一个场景开始</small>
          </div>
        )}
      </div>
    </aside>
  );
}
