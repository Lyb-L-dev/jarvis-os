"use client";

import { useEffect, useState } from "react";

type DesktopPreferences = {
  autostartEnabled: boolean;
  quickShortcut: string;
  quickShortcutOptions: string[];
  quickShortcutEnabled: boolean;
  voiceShortcut: string;
  voiceShortcutOptions: string[];
  voiceShortcutEnabled: boolean;
  closeBehavior: "hide" | "quit";
  closeBehaviorOptions: Array<"hide" | "quit">;
  openWithEnabled: boolean;
};

type TauriCore = {
  invoke: <T>(command: string, args?: Record<string, unknown>) => Promise<T>;
};

type UpdatePhase =
  | "idle"
  | "checking"
  | "available"
  | "current"
  | "downloading"
  | "staged"
  | "installing"
  | "blocked"
  | "failed";

type UpdateSnapshot = {
  phase: UpdatePhase;
  channel: "stable" | "beta";
  currentVersion: string;
  availableVersion: string | null;
  releaseNotes: string | null;
  requiresRestart: boolean;
  packageSizeBytes: number | null;
  stagedPath: string | null;
  busyReason: string | null;
  backupEvidence: string | null;
  rollbackResult: string | null;
  message: string;
};

type DataExportReceipt = {
  exportDirectory: string;
  manifestPath: string;
  fileCount: number;
  totalBytes: number;
  verifiedAtMs: number;
  ticket: string;
  confirmationPhrase: string;
};

function tauriCore(): TauriCore | null {
  return (window as typeof window & { __TAURI__?: { core?: TauriCore } }).__TAURI__?.core ?? null;
}

export function DesktopSettings() {
  const [preferences, setPreferences] = useState<DesktopPreferences | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [updateState, setUpdateState] = useState<UpdateSnapshot | null>(null);
  const [updateBusy, setUpdateBusy] = useState(false);
  const [dataBusy, setDataBusy] = useState(false);
  const [dataExport, setDataExport] = useState<DataExportReceipt | null>(null);
  const [deleteConfirmation, setDeleteConfirmation] = useState("");

  useEffect(() => {
    const core = tauriCore();
    if (!core) return;
    void core.invoke<DesktopPreferences>("desktop_preferences")
      .then(setPreferences)
      .catch((error: unknown) => setNotice(String(error)));
    void core.invoke<UpdateSnapshot>("desktop_update_status")
      .then(setUpdateState)
      .catch((error: unknown) => setNotice(String(error)));
  }, []);

  if (!preferences) return null;

  async function update(command: string, enabled: boolean) {
    const core = tauriCore();
    if (!core) return;
    setBusy(true);
    setNotice(null);
    try {
      setPreferences(await core.invoke<DesktopPreferences>(command, { enabled }));
      setNotice("Windows 桌面偏好已更新，可随时撤销。");
    } catch (error) {
      setNotice(String(error));
    } finally {
      setBusy(false);
    }
  }

  async function updateBinding(kind: "quick" | "voice", binding: string) {
    const core = tauriCore();
    if (!core) return;
    setBusy(true);
    setNotice(null);
    try {
      setPreferences(await core.invoke<DesktopPreferences>("desktop_set_shortcut_binding", { kind, binding }));
      setNotice("快捷键已更新。若组合被占用，Jarvis 会保留原设置。");
    } catch (error) {
      setNotice(String(error));
    } finally {
      setBusy(false);
    }
  }

  async function updateCloseBehavior(behavior: "hide" | "quit") {
    const core = tauriCore();
    if (!core) return;
    setBusy(true);
    setNotice(null);
    try {
      setPreferences(await core.invoke<DesktopPreferences>("desktop_set_close_behavior", { behavior }));
      setNotice("关闭主窗口行为已更新；最小化按钮仍只最小化窗口。");
    } catch (error) {
      setNotice(String(error));
    } finally {
      setBusy(false);
    }
  }

  async function updateAction(
    command: string,
    args?: Record<string, unknown>,
  ) {
    const core = tauriCore();
    if (!core) return;
    setUpdateBusy(true);
    setNotice(null);
    try {
      setUpdateState(await core.invoke<UpdateSnapshot>(command, args));
    } catch (error) {
      setNotice(String(error));
      setUpdateState(await core.invoke<UpdateSnapshot>("desktop_update_status"));
    } finally {
      setUpdateBusy(false);
    }
  }

  async function exportUserData() {
    const core = tauriCore();
    if (!core) return;
    setDataBusy(true);
    setNotice(null);
    setDataExport(null);
    setDeleteConfirmation("");
    try {
      const receipt = await core.invoke<DataExportReceipt>("desktop_export_user_data");
      setDataExport(receipt);
      setNotice("导出与数据库恢复验证已完成。导出包位于 Jarvis 数据目录之外。");
    } catch (error) {
      setNotice(String(error));
    } finally {
      setDataBusy(false);
    }
  }

  async function deleteUserData() {
    const core = tauriCore();
    if (!core || !dataExport) return;
    if (!window.confirm("这会删除本机 Jarvis 数据和 PostgreSQL 数据卷，并完全退出应用。已验证的导出包会保留。是否继续？")) {
      return;
    }
    setDataBusy(true);
    setNotice(null);
    try {
      await core.invoke<void>("desktop_delete_user_data", {
        ticket: dataExport.ticket,
        confirmation: deleteConfirmation,
      });
    } catch (error) {
      setNotice(String(error));
      setDataBusy(false);
    }
  }

  const updatePrimary = updateState?.phase === "available"
    ? { label: "下载并校验", command: "desktop_update_download" }
    : updateState?.phase === "staged"
      ? { label: "备份并安装", command: "desktop_update_install" }
      : { label: "检查更新", command: "desktop_update_check" };

  return (
    <section className="panel settings-panel desktop-settings-panel">
      <div className="section-heading">
        <div>
          <div className="eyebrow">WINDOWS INTEGRATION</div>
          <h3>桌面唤醒</h3>
        </div>
        <span className="settings-safe-label">均可关闭</span>
      </div>
      <label className="toggle-row desktop-setting-row">
        <div>
          <strong>全局快速提问</strong>
          <span>{preferences.quickShortcut} · 冲突时不会覆盖其他应用</span>
        </div>
        <input
          aria-label="启用全局快速提问快捷键"
          checked={preferences.quickShortcutEnabled}
          disabled={busy}
          onChange={(event) => void update("desktop_set_quick_shortcut", event.target.checked)}
          type="checkbox"
        />
      </label>
      <label className="desktop-shortcut-binding">
        <span>关闭主窗口时</span>
        <select
          aria-label="关闭主窗口行为"
          disabled={busy}
          onChange={(event) => void updateCloseBehavior(event.target.value as "hide" | "quit")}
          value={preferences.closeBehavior}
        >
          <option value="hide">隐藏到托盘</option>
          <option value="quit">完全退出 Jarvis</option>
        </select>
        <small>最小化、关闭和完全退出保持不同语义；完全退出只停止 Jarvis 自有进程。</small>
      </label>
      <label className="toggle-row desktop-setting-row">
        <div>
          <strong>“使用 Jarvis 打开”</strong>
          <span>在资源管理器为 .md/.txt 提供受控预览入口，不改变默认编辑器</span>
        </div>
        <input
          aria-label="启用使用 Jarvis 打开"
          checked={preferences.openWithEnabled}
          disabled={busy}
          onChange={(event) => void update("desktop_set_open_with", event.target.checked)}
          type="checkbox"
        />
      </label>
      <label className="desktop-shortcut-binding">
        <span>快速提问组合键</span>
        <select
          aria-label="快速提问组合键"
          disabled={busy || preferences.quickShortcutEnabled}
          onChange={(event) => void updateBinding("quick", event.target.value)}
          value={preferences.quickShortcut}
        >
          {preferences.quickShortcutOptions.map((option) => <option key={option}>{option}</option>)}
        </select>
        <small>更改前先关闭快速提问；重新启用时会检查与其他应用的冲突。</small>
      </label>
      <label className="toggle-row desktop-setting-row">
        <div>
          <strong>全局按住说话</strong>
          <span>{preferences.voiceShortcut} · 默认关闭；按住主键录音，释放后本地转写</span>
        </div>
        <input
          aria-label="启用全局按住说话快捷键"
          checked={preferences.voiceShortcutEnabled}
          disabled={busy}
          onChange={(event) => void update("desktop_set_voice_shortcut", event.target.checked)}
          type="checkbox"
        />
      </label>
      <label className="desktop-shortcut-binding">
        <span>按住说话组合键</span>
        <select
          aria-label="按住说话组合键"
          disabled={busy || preferences.voiceShortcutEnabled}
          onChange={(event) => void updateBinding("voice", event.target.value)}
          value={preferences.voiceShortcut}
        >
          {preferences.voiceShortcutOptions.map((option) => <option key={option}>{option}</option>)}
        </select>
        <small>只提供审核过的组合，不占用普通输入字符，也不会覆盖已占用组合。</small>
      </label>
      <label className="toggle-row desktop-setting-row">
        <div>
          <strong>开机启动</strong>
          <span>默认关闭；启用后登录 Windows 时在后台启动 Jarvis</span>
        </div>
        <input
          aria-label="启用开机启动"
          checked={preferences.autostartEnabled}
          disabled={busy}
          onChange={(event) => void update("desktop_set_autostart", event.target.checked)}
          type="checkbox"
        />
      </label>
      <p className="settings-note" role="status" aria-live="polite">
        {notice ?? "快速窗口和主窗口使用同一对话事实源；关闭能力后不会遗留监听。"}
      </p>
      {updateState ? (
        <div className="desktop-update-panel">
          <div className="desktop-update-heading">
            <div>
              <div className="eyebrow">SIGNED UPDATE</div>
              <h4>桌面更新</h4>
            </div>
            <span className={`desktop-update-state is-${updateState.phase}`}>
              {updateState.phase}
            </span>
          </div>
          <div className="desktop-update-meta">
            <span>当前 {updateState.currentVersion}</span>
            <span>{updateState.availableVersion ? `可用 ${updateState.availableVersion}` : "尚无候选版本"}</span>
            <span>{updateState.requiresRestart ? "需要重启" : "未声明重启"}</span>
          </div>
          <p>{updateState.message}</p>
          {updateState.releaseNotes ? (
            <details className="desktop-update-notes">
              <summary>查看版本影响与更新说明</summary>
              <p>{updateState.releaseNotes}</p>
            </details>
          ) : null}
          {updateState.busyReason ? <p className="desktop-update-warning">{updateState.busyReason}</p> : null}
          {updateState.rollbackResult ? <p className="desktop-update-result">上次更新：{updateState.rollbackResult}</p> : null}
          <div className="desktop-update-actions">
            <label>
              更新通道
              <select
                aria-label="桌面更新通道"
                disabled={updateBusy}
                value={updateState.channel}
                onChange={(event) => void updateAction("desktop_update_set_channel", { channel: event.target.value })}
              >
                <option value="stable">Stable</option>
                <option value="beta">Beta</option>
              </select>
            </label>
            <button
              className="primary-button"
              disabled={
                updateBusy ||
                updateState.phase === "checking" ||
                updateState.phase === "downloading" ||
                updateState.phase === "installing" ||
                Boolean(updateState.busyReason && updateState.phase === "staged")
              }
              onClick={() => void updateAction(updatePrimary.command)}
              type="button"
            >
              {updateBusy ? "处理中…" : updatePrimary.label}
            </button>
          </div>
          <small>清单先验签；安装包再校验 SHA-256 与 Authenticode。安装前停止 Sidecar，并将备份恢复到临时库验收。</small>
        </div>
      ) : null}
      <div className="desktop-data-panel">
        <div className="desktop-update-heading">
          <div>
            <div className="eyebrow">DATA CONTROL</div>
            <h4>本地数据维护</h4>
          </div>
          <span className="settings-safe-label">先导出，后删除</span>
        </div>
        <p>
          卸载 Jarvis 默认保留数据。如需彻底清理，必须先生成独立导出包，并通过数据库恢复与文件哈希校验。
        </p>
        <button
          className="secondary-button"
          disabled={dataBusy}
          onClick={() => void exportUserData()}
          type="button"
        >
          {dataBusy && !dataExport ? "正在导出并验证…" : "导出并验证本地数据"}
        </button>
        {dataExport ? (
          <div className="desktop-data-receipt" role="status" aria-live="polite">
            <strong>导出已验证</strong>
            <span>{dataExport.fileCount} 个文件 · {(dataExport.totalBytes / 1024 / 1024).toFixed(1)} MB</span>
            <code>{dataExport.exportDirectory}</code>
            <label>
              如要继续删除，请输入：<b>{dataExport.confirmationPhrase}</b>
              <input
                autoComplete="off"
                disabled={dataBusy}
                onChange={(event) => setDeleteConfirmation(event.target.value)}
                spellCheck={false}
                type="text"
                value={deleteConfirmation}
              />
            </label>
            <button
              className="desktop-data-delete"
              disabled={dataBusy || deleteConfirmation !== dataExport.confirmationPhrase}
              onClick={() => void deleteUserData()}
              type="button"
            >
              删除本机数据并退出
            </button>
          </div>
        ) : null}
        <small>删除入口不接受自定义目录；若 Docker 数据卷清理失败，文件数据不会继续删除。</small>
      </div>
    </section>
  );
}
