"use client";

import {
  createReminder,
  deleteReminder,
  dismissReminder,
  getNotificationPreferences,
  listCompanionDevices,
  listNotifications,
  retryReminder,
  snoozeReminder,
  updateNotificationPreferences,
  type CompanionDevice,
  type JarvisNotification,
  type NotificationPreference,
} from "@/lib/api";
import { useCallback, useEffect, useMemo, useState } from "react";

const statusLabels: Record<JarvisNotification["status"], string> = {
  pending: "等待中",
  claimed: "正在投递",
  snoozed: "已延迟",
  delivered: "已送达",
  dismissed: "已忽略",
  cancelled: "已取消",
  failed: "投递失败",
};

function defaultReminderTime() {
  const value = new Date(Date.now() + 10 * 60 * 1000);
  const offset = value.getTimezoneOffset() * 60_000;
  return new Date(value.getTime() - offset).toISOString().slice(0, 16);
}

function formatTime(value?: string | null) {
  if (!value) return "—";
  return new Date(value).toLocaleString("zh-CN", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function channelLabel(notification: JarvisNotification) {
  return notification.requested_channels
    .map((channel) => (channel === "desktop" ? "桌面" : "语音"))
    .join(" + ");
}

export function NotificationCenter() {
  const [preferences, setPreferences] =
    useState<NotificationPreference | null>(null);
  const [notifications, setNotifications] = useState<JarvisNotification[]>([]);
  const [devices, setDevices] = useState<CompanionDevice[]>([]);
  const [loading, setLoading] = useState(true);
  const [now, setNow] = useState(() => Date.now());
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [message, setMessage] = useState("");
  const [scheduledFor, setScheduledFor] = useState("");
  const [voice, setVoice] = useState(true);
  const [sensitive, setSensitive] = useState(false);

  const refresh = useCallback(async (signal?: AbortSignal) => {
    try {
      const [nextPreferences, nextNotifications, nextDevices] =
        await Promise.all([
          getNotificationPreferences(signal),
          listNotifications(signal),
          listCompanionDevices(signal),
        ]);
      setPreferences(nextPreferences);
      setNotifications(nextNotifications);
      setDevices(nextDevices);
      setNow(Date.now());
      setError(null);
    } catch (loadError) {
      if (
        loadError instanceof DOMException &&
        loadError.name === "AbortError"
      ) {
        return;
      }
      setError(
        loadError instanceof Error
          ? loadError.message
          : "读取提醒数据失败。",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    const initial = window.setTimeout(
      () => {
        setScheduledFor(defaultReminderTime());
        void refresh(controller.signal);
      },
      0,
    );
    const timer = window.setInterval(() => void refresh(), 10_000);
    return () => {
      controller.abort();
      window.clearTimeout(initial);
      window.clearInterval(timer);
    };
  }, [refresh]);

  useEffect(() => {
    const focusId = new URLSearchParams(window.location.search).get("focus");
    if (!focusId || loading) return;
    const target = document.querySelector<HTMLElement>(`[data-notification-id="${CSS.escape(focusId)}"]`);
    if (target) {
      target.scrollIntoView({ block: "center", behavior: "smooth" });
      target.focus({ preventScroll: true });
    } else {
      const timer = window.setTimeout(
        () => setNotice("该提醒已过期、被删除，或不属于当前用户。"),
        0,
      );
      return () => window.clearTimeout(timer);
    }
  }, [loading, notifications]);

  const upcoming = useMemo(
    () =>
      notifications
        .filter((item) =>
          ["pending", "claimed", "snoozed"].includes(item.status),
        )
        .sort(
          (left, right) =>
            new Date(left.available_at).getTime() -
            new Date(right.available_at).getTime(),
        ),
    [notifications],
  );
  const history = useMemo(
    () =>
      notifications.filter(
        (item) => !["pending", "claimed", "snoozed"].includes(item.status),
      ),
    [notifications],
  );
  const onlineDevice = devices.find((device) => device.online);
  const voiceStatus = onlineDevice?.voice_status;
  const paused =
    preferences?.paused_until &&
    new Date(preferences.paused_until).getTime() > now;

  async function runAction(
    key: string,
    action: () => Promise<unknown>,
    success: string,
  ) {
    setBusy(key);
    setError(null);
    setNotice(null);
    try {
      await action();
      setNotice(success);
      await refresh();
    } catch (actionError) {
      setError(
        actionError instanceof Error ? actionError.message : "操作失败。",
      );
    } finally {
      setBusy(null);
    }
  }

  async function savePreferences() {
    if (!preferences) return;
    await runAction(
      "save-preferences",
      () =>
        updateNotificationPreferences({
          desktop_enabled: preferences.desktop_enabled,
          voice_enabled: preferences.voice_enabled,
          quiet_enabled: preferences.quiet_enabled,
          quiet_start: preferences.quiet_start,
          quiet_end: preferences.quiet_end,
          max_daily_notifications: preferences.max_daily_notifications,
          max_hourly_voice: preferences.max_hourly_voice,
          default_snooze_minutes: preferences.default_snooze_minutes,
          voice_rate: preferences.voice_rate,
          voice_volume: preferences.voice_volume,
          voice_engine: preferences.voice_engine,
          voice_persona: preferences.voice_persona,
          sensitive_voice_enabled: preferences.sensitive_voice_enabled,
        }),
      "提醒设置已保存。",
    );
  }

  async function addReminder() {
    const cleanTitle = title.trim();
    const cleanMessage = message.trim();
    if (!cleanTitle || !cleanMessage || !scheduledFor) return;
    await runAction(
      "create-reminder",
      () =>
        createReminder({
          title: cleanTitle,
          message: cleanMessage,
          scheduled_for: new Date(scheduledFor).toISOString(),
          channels: voice ? ["desktop", "voice"] : ["desktop"],
          sensitive,
        }),
      "提醒已安排，关闭浏览器后仍会生效。",
    );
    setTitle("");
    setMessage("");
    setScheduledFor(defaultReminderTime());
    setSensitive(false);
  }

  async function sendTest(channel: "desktop" | "voice") {
    if (
      channel === "voice" &&
      !window.confirm("Jarvis 将通过当前扬声器开口播报，确认试听吗？")
    ) {
      return;
    }
    await runAction(
      `test-${channel}`,
      () =>
        createReminder({
          title: channel === "voice" ? "Jarvis 语音测试" : "Jarvis 桌面测试",
          message:
            channel === "voice"
              ? "主动语音提醒已经可以工作。"
              : "Windows 后台提醒已经可以工作。",
          scheduled_for: new Date().toISOString(),
          channels: [channel],
        }),
      channel === "voice"
        ? "语音测试已提交；免打扰时段会延后播报。"
        : "桌面测试已提交。",
    );
  }

  function updatePreference<K extends keyof NotificationPreference>(
    key: K,
    value: NotificationPreference[K],
  ) {
    setPreferences((current) =>
      current ? { ...current, [key]: value } : current,
    );
  }

  return (
    <main className="notification-page">
      <header className="notification-header">
        <div>
          <div className="eyebrow">ACTIVE REMINDERS</div>
          <h1>主动提醒</h1>
          <p>持久化调度、Windows 通知和自动语音播报。</p>
        </div>
        <div
          className={`companion-state ${
            onlineDevice ? "companion-online" : ""
          }`}
        >
          <i />
          <div>
            <strong>
              {onlineDevice ? "Windows 后台在线" : "Windows 后台未连接"}
            </strong>
            <span>
              {onlineDevice
                ? `${onlineDevice.display_name} · 刚刚心跳`
                : "启动 Jarvis 后将自动连接"}
            </span>
          </div>
        </div>
      </header>

      {error ? <div className="notification-feedback notification-error">{error}</div> : null}
      {notice ? <div className="notification-feedback">{notice}</div> : null}

      {loading || !preferences ? (
        <div className="notification-loading">正在读取提醒设置…</div>
      ) : (
        <>
          <section className="notification-summary">
            <article>
              <span>待提醒</span>
              <strong>{upcoming.length}</strong>
            </article>
            <article>
              <span>今日已送达</span>
              <strong>
                {
                  notifications.filter(
                    (item) =>
                      item.status === "delivered" &&
                      new Date(item.delivered_at ?? 0).toDateString() ===
                        new Date().toDateString(),
                  ).length
                }
              </strong>
            </article>
            <article>
              <span>自动语音</span>
              <strong>{preferences.voice_enabled ? "开启" : "关闭"}</strong>
            </article>
            <article>
              <span>当前状态</span>
              <strong>{paused ? "已暂停" : "运行中"}</strong>
            </article>
          </section>

          <div className="notification-layout">
            <div className="notification-main">
              <section className="panel reminder-create-card">
                <div className="notification-section-head">
                  <div>
                    <div className="eyebrow">NEW REMINDER</div>
                    <h2>安排一个提醒</h2>
                  </div>
                  <span>时间到后由 Windows 后台接管</span>
                </div>
                <div className="reminder-form">
                  <label className="reminder-form-wide">
                    标题
                    <input
                      maxLength={200}
                      onChange={(event) => setTitle(event.target.value)}
                      placeholder="例如：开始今天的英语训练"
                      value={title}
                    />
                  </label>
                  <label className="reminder-form-wide">
                    播报内容
                    <textarea
                      maxLength={4000}
                      onChange={(event) => setMessage(event.target.value)}
                      placeholder="提醒时要显示和朗读的内容"
                      rows={3}
                      value={message}
                    />
                  </label>
                  <label>
                    提醒时间
                    <input
                      onChange={(event) => setScheduledFor(event.target.value)}
                      type="datetime-local"
                      value={scheduledFor}
                    />
                  </label>
                  <label className="reminder-check">
                    <input
                      checked={voice}
                      onChange={(event) => setVoice(event.target.checked)}
                      type="checkbox"
                    />
                    自动语音播报
                  </label>
                  <label className="reminder-check">
                    <input
                      checked={sensitive}
                      onChange={(event) => setSensitive(event.target.checked)}
                      type="checkbox"
                    />
                    内容敏感（默认不朗读）
                  </label>
                  <button
                    className="primary-button"
                    disabled={
                      !title.trim() ||
                      !message.trim() ||
                      !scheduledFor ||
                      busy === "create-reminder"
                    }
                    onClick={() => void addReminder()}
                    type="button"
                  >
                    {busy === "create-reminder" ? "安排中…" : "安排提醒"}
                  </button>
                </div>
              </section>

              <section className="panel reminder-list-card">
                <div className="notification-section-head">
                  <div>
                    <div className="eyebrow">UPCOMING</div>
                    <h2>即将提醒</h2>
                  </div>
                  <span>{upcoming.length} 项</span>
                </div>
                <div className="reminder-list">
                  {upcoming.length ? (
                    upcoming.map((item) => (
                      <article className="reminder-item" data-notification-id={item.id} key={item.id} tabIndex={-1}>
                        <div className="reminder-time">
                          {formatTime(item.available_at)}
                        </div>
                        <div className="reminder-body">
                          <div>
                            <strong>{item.title}</strong>
                            <span className={`reminder-status status-${item.status}`}>
                              {statusLabels[item.status]}
                            </span>
                          </div>
                          <p>{item.message}</p>
                          <small>
                            {channelLabel(item)}
                            {item.sensitive ? " · 敏感内容不自动朗读" : ""}
                          </small>
                        </div>
                        <div className="reminder-actions">
                          {[10, 30, 60].map((minutes) => (
                            <button
                              disabled={busy === item.id}
                              key={minutes}
                              onClick={() =>
                                void runAction(
                                  item.id,
                                  () => snoozeReminder(item.id, minutes),
                                  `已延迟 ${minutes} 分钟。`,
                                )
                              }
                              type="button"
                            >
                              +{minutes}m
                            </button>
                          ))}
                          <button
                            className="reminder-dismiss"
                            disabled={busy === item.id}
                            onClick={() =>
                              void runAction(
                                item.id,
                                () => dismissReminder(item.id),
                                "提醒已忽略。",
                              )
                            }
                            type="button"
                          >
                            忽略
                          </button>
                        </div>
                      </article>
                    ))
                  ) : (
                    <div className="notification-empty">
                      <strong>目前没有待提醒事项</strong>
                      <span>新建提醒或给成长任务设置提醒时间。</span>
                    </div>
                  )}
                </div>
              </section>

              <section className="panel reminder-list-card">
                <div className="notification-section-head">
                  <div>
                    <div className="eyebrow">HISTORY</div>
                    <h2>投递历史</h2>
                  </div>
                  <span>保留成功、失败和忽略记录</span>
                </div>
                <div className="reminder-list reminder-history">
                  {history.length ? (
                    history.slice(0, 30).map((item) => (
                      <article className="reminder-item" data-notification-id={item.id} key={item.id} tabIndex={-1}>
                        <div className="reminder-time">
                          {formatTime(item.delivered_at ?? item.available_at)}
                        </div>
                        <div className="reminder-body">
                          <div>
                            <strong>{item.title}</strong>
                            <span className={`reminder-status status-${item.status}`}>
                              {statusLabels[item.status]}
                            </span>
                          </div>
                          <p>{item.message}</p>
                          <small>
                            {item.attempts.length
                              ? item.attempts
                                  .map(
                                    (attempt) =>
                                      `${
                                        attempt.channel === "desktop"
                                          ? "桌面"
                                          : "语音"
                                      }${attempt.success ? "成功" : "失败"}`,
                                  )
                                  .join(" · ")
                              : channelLabel(item)}
                          </small>
                          {item.error_message ? (
                            <em>{item.error_message}</em>
                          ) : null}
                        </div>
                        <div className="reminder-actions">
                          {item.status === "failed" ? (
                            <button
                              disabled={busy === item.id}
                              onClick={() =>
                                void runAction(
                                  item.id,
                                  () => retryReminder(item.id),
                                  "失败提醒已重新加入队列。",
                                )
                              }
                              type="button"
                            >
                              重试
                            </button>
                          ) : null}
                          <button
                            className="reminder-dismiss"
                            disabled={busy === item.id}
                            onClick={() =>
                              void runAction(
                                item.id,
                                () => deleteReminder(item.id),
                                "提醒记录已删除。",
                              )
                            }
                            type="button"
                          >
                            删除记录
                          </button>
                        </div>
                      </article>
                    ))
                  ) : (
                    <div className="notification-empty">
                      <strong>还没有投递记录</strong>
                      <span>完成第一次测试后，这里会显示各渠道结果。</span>
                    </div>
                  )}
                </div>
              </section>
            </div>

            <aside className="notification-settings">
              <section className="panel notification-settings-card">
                <div className="notification-section-head">
                  <div>
                    <div className="eyebrow">DELIVERY</div>
                    <h2>提醒方式</h2>
                  </div>
                </div>
                <div
                  className={`voice-runtime-card ${
                    voiceStatus?.bilingual_neural_ready
                      ? "voice-runtime-neural"
                      : ""
                  }`}
                >
                  <div>
                    <span className="voice-runtime-pulse" />
                    <strong>
                      {voiceStatus?.bilingual_neural_ready
                        ? "原创中英双男声已就绪"
                        : voiceStatus?.chinese_neural_ready
                          ? "中文男声可用，英语男声待安装"
                          : "当前使用 Windows 系统声音"}
                    </strong>
                  </div>
                  <small>
                    {voiceStatus?.bilingual_neural_ready
                      ? `${voiceStatus.local_model_name} · ${voiceStatus.english_model_name}`
                      : voiceStatus?.fallback_reason ||
                      "等待 Windows Companion 上报声音状态"}
                  </small>
                </div>
                <label className="notification-toggle">
                  <div>
                    <strong>Windows 桌面通知</strong>
                    <span>即使浏览器关闭也会显示</span>
                  </div>
                  <input
                    checked={preferences.desktop_enabled}
                    onChange={(event) =>
                      updatePreference("desktop_enabled", event.target.checked)
                    }
                    type="checkbox"
                  />
                </label>
                <label className="notification-toggle">
                  <div>
                    <strong>自动语音播报</strong>
                    <span>到时间后通过当前扬声器开口</span>
                  </div>
                  <input
                    checked={preferences.voice_enabled}
                    onChange={(event) =>
                      updatePreference("voice_enabled", event.target.checked)
                    }
                    type="checkbox"
                  />
                </label>
                <label className="notification-toggle">
                  <div>
                    <strong>免打扰</strong>
                    <span>这段时间只保留文字通知</span>
                  </div>
                  <input
                    checked={preferences.quiet_enabled}
                    onChange={(event) =>
                      updatePreference("quiet_enabled", event.target.checked)
                    }
                    type="checkbox"
                  />
                </label>
                <div className="quiet-hours">
                  <label>
                    开始
                    <input
                      disabled={!preferences.quiet_enabled}
                      onChange={(event) =>
                        updatePreference("quiet_start", event.target.value)
                      }
                      type="time"
                      value={preferences.quiet_start}
                    />
                  </label>
                  <span>至</span>
                  <label>
                    结束
                    <input
                      disabled={!preferences.quiet_enabled}
                      onChange={(event) =>
                        updatePreference("quiet_end", event.target.value)
                      }
                      type="time"
                      value={preferences.quiet_end}
                    />
                  </label>
                </div>
                <label className="settings-number">
                  <span>每天最多提醒</span>
                  <input
                    max={100}
                    min={1}
                    onChange={(event) =>
                      updatePreference(
                        "max_daily_notifications",
                        Number(event.target.value),
                      )
                    }
                    type="number"
                    value={preferences.max_daily_notifications}
                  />
                </label>
                <label className="settings-number">
                  <span>每小时最多语音</span>
                  <input
                    max={20}
                    min={1}
                    onChange={(event) =>
                      updatePreference(
                        "max_hourly_voice",
                        Number(event.target.value),
                      )
                    }
                    type="number"
                    value={preferences.max_hourly_voice}
                  />
                </label>
                <label className="voice-setting-select">
                  <span>语音引擎</span>
                  <select
                    onChange={(event) =>
                      updatePreference(
                        "voice_engine",
                        event.target.value as NotificationPreference["voice_engine"],
                      )
                    }
                    value={preferences.voice_engine}
                  >
                    <option value="auto">自动 · 离线男声优先</option>
                    <option value="local_neural">原创离线中文男声</option>
                    <option value="windows">Windows 中文声音</option>
                  </select>
                </label>
                <label className="voice-setting-select">
                  <span>声音人格</span>
                  <select
                    onChange={(event) =>
                      updatePreference(
                        "voice_persona",
                        event.target.value as NotificationPreference["voice_persona"],
                      )
                    }
                    value={preferences.voice_persona}
                  >
                    <option value="calm">沉稳指挥 · 推荐</option>
                    <option value="concise">简洁提醒</option>
                    <option value="plain">原文播报</option>
                  </select>
                </label>
                <label className="settings-number">
                  <span>语速</span>
                  <input
                    max={10}
                    min={-10}
                    onChange={(event) =>
                      updatePreference(
                        "voice_rate",
                        Number(event.target.value),
                      )
                    }
                    type="number"
                    value={preferences.voice_rate}
                  />
                </label>
                <label className="settings-number">
                  <span>语音音量</span>
                  <input
                    max={100}
                    min={0}
                    onChange={(event) =>
                      updatePreference(
                        "voice_volume",
                        Number(event.target.value),
                      )
                    }
                    type="number"
                    value={preferences.voice_volume}
                  />
                </label>
                <button
                  className="primary-button settings-save"
                  disabled={busy === "save-preferences"}
                  onClick={() => void savePreferences()}
                  type="button"
                >
                  {busy === "save-preferences" ? "保存中…" : "保存设置"}
                </button>
              </section>

              <section className="panel notification-test-card">
                <div className="notification-section-head">
                  <div>
                    <div className="eyebrow">CHECK</div>
                    <h2>测试后台</h2>
                  </div>
                </div>
                <p>
                  桌面测试会立即显示通知；语音测试会先要求确认，并遵守免打扰设置。
                </p>
                <button
                  disabled={busy === "test-desktop"}
                  onClick={() => void sendTest("desktop")}
                  type="button"
                >
                  测试桌面通知
                </button>
                <button
                  disabled={busy === "test-voice"}
                  onClick={() => void sendTest("voice")}
                  type="button"
                >
                  试听语音
                </button>
              </section>

              <section className="panel notification-pause-card">
                <strong>{paused ? "提醒已暂停" : "需要临时安静？"}</strong>
                <p>
                  {paused
                    ? `将在 ${formatTime(preferences.paused_until)} 自动恢复。`
                    : "暂停后队列会保留，恢复时继续投递。"}
                </p>
                <button
                  onClick={() =>
                    void runAction(
                      "pause",
                      () =>
                        updateNotificationPreferences({
                          paused_until: paused
                            ? null
                            : new Date(
                                Date.now() + 60 * 60 * 1000,
                              ).toISOString(),
                        }),
                      paused ? "主动提醒已恢复。" : "提醒已暂停 1 小时。",
                    )
                  }
                  type="button"
                >
                  {paused ? "立即恢复" : "暂停 1 小时"}
                </button>
              </section>
            </aside>
          </div>
        </>
      )}
    </main>
  );
}
