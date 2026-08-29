#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod autostart_fuse;
mod config_store;
mod data_maintenance;
mod file_handoff;
mod reliability_ledger;
mod runtime;
mod update;
mod windows_integration;

use config_store::{DesktopConfigStatus, DesktopConfigStore, MigrationPreview, MigrationResult};
use data_maintenance::{DataExportReceipt, PendingDataDeletion};
use file_handoff::{FileHandoffContent, FileHandoffPreview, FileHandoffStore};
use reliability_ledger::{
    ReliabilityEventInput, ReliabilityEventKind, ReliabilityLedger, ReliabilityOutcome,
    ReliabilityStage,
};
use update::{run_update_watchdog, UpdateCoordinator, UpdateSnapshot};
use runtime::{
    BundledRuntimeAdapter, DiagnosticBundleRef, RuntimeAdapter, RuntimeConnection,
    RuntimeDiagnostics, RuntimeFailure, RuntimeSnapshot, RuntimeSupervisor, SourceRuntimeAdapter,
    UnavailableAdapter,
};
use windows_integration::{
    autostart_enabled, open_with_enabled, quick_shortcut_options, register_protocol_handler,
    set_autostart, set_open_with_enabled, unregister_desktop_integrations,
    voice_shortcut_options, QuickShortcutController,
};
use config_store::user_data_root;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{mpsc, Arc, Mutex};
use std::time::{Duration, Instant};
use tauri::menu::{CheckMenuItem, Menu, MenuItem};
use tauri::tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent};
use tauri::webview::NewWindowResponse;
use tauri::{
    DragDropEvent, Emitter, Manager, PhysicalPosition, PhysicalSize, WebviewUrl,
    WebviewWindowBuilder, WindowEvent,
};
use tauri_plugin_opener::OpenerExt;
use tauri_plugin_window_state::StateFlags;

#[cfg(windows)]
use webview2_com::{
    Microsoft::Web::WebView2::Win32::{
        COREWEBVIEW2_PERMISSION_KIND, COREWEBVIEW2_PERMISSION_KIND_MICROPHONE,
        COREWEBVIEW2_PERMISSION_STATE_DEFAULT, COREWEBVIEW2_PERMISSION_STATE_DENY,
    },
    PermissionRequestedEventHandler,
};

type DesktopSupervisor = RuntimeSupervisor<Box<dyn RuntimeAdapter>>;

struct DesktopState {
    supervisor: Arc<DesktopSupervisor>,
    config_store: Option<Arc<DesktopConfigStore>>,
    quitting: Arc<AtomicBool>,
    pending_activation: Mutex<Option<serde_json::Value>>,
    quick_shortcut: QuickShortcutController,
    file_handoff: FileHandoffStore,
    updater: Arc<UpdateCoordinator>,
    pending_data_deletion: Mutex<Option<PendingDataDeletion>>,
    reliability: Arc<ReliabilityLedger>,
}

#[tauri::command]
fn desktop_record_reliability_event(
    input: ReliabilityEventInput,
    state: tauri::State<'_, DesktopState>,
) -> Result<(), String> {
    state.reliability.record(input)
}

fn record_reliability(
    ledger: &ReliabilityLedger,
    kind: ReliabilityEventKind,
    outcome: ReliabilityOutcome,
    duration_ms: Option<u64>,
    stage: Option<ReliabilityStage>,
) {
    let _ = ledger.record(ReliabilityEventInput {
        kind,
        outcome,
        duration_ms,
        stage,
    });
}

#[tauri::command]
async fn desktop_export_user_data(
    state: tauri::State<'_, DesktopState>,
) -> Result<DataExportReceipt, String> {
    let supervisor = Arc::clone(&state.supervisor);
    let data_root = user_data_root()?;
    let result = tauri::async_runtime::spawn_blocking(move || {
        let database_manifest = supervisor
            .prepare_update_backup()
            .map_err(|error| error.message)?;
        data_maintenance::export_verified_user_data(&data_root, &database_manifest)
    })
    .await
    .map_err(|error| format!("数据导出任务失败：{error}"))??;
    let (receipt, pending) = result;
    *state
        .pending_data_deletion
        .lock()
        .map_err(|_| "数据删除凭据状态不可用。".to_owned())? = Some(pending);
    Ok(receipt)
}

#[tauri::command]
async fn desktop_delete_user_data(
    ticket: String,
    confirmation: String,
    app: tauri::AppHandle,
    state: tauri::State<'_, DesktopState>,
) -> Result<(), String> {
    if let Some(connection) = state.supervisor.connection() {
        if let Some(reason) = core_update_activity_blocker(&connection)? {
            return Err(format!("仍有活动任务，不能删除本地数据：{reason}"));
        }
    }
    let pending = state
        .pending_data_deletion
        .lock()
        .map_err(|_| "数据删除凭据状态不可用。".to_owned())?
        .as_ref()
        .cloned()
        .ok_or_else(|| "请先执行导出与验证。".to_owned())?;
    let data_root = user_data_root()?;
    let supervisor = Arc::clone(&state.supervisor);
    let result = tauri::async_runtime::spawn_blocking(move || {
        let stopped = supervisor.stop(|_| {});
        if !matches!(stopped.state, runtime::RuntimeState::Stopped) {
            return Err("Jarvis 自有运行时未能完全停止，未执行数据删除。".to_owned());
        }
        data_maintenance::stage_cleanup(&pending, &ticket, &confirmation, &data_root)
    })
    .await
    .map_err(|error| format!("数据删除准备任务失败：{error}"))?;
    let cleanup_ticket = match result {
        Ok(path) => path,
        Err(error) => {
            let _ = state.supervisor.start(|_| {});
            return Err(error);
        }
    };
    let executable = std::env::current_exe().map_err(|error| error.to_string())?;
    if let Err(error) = std::process::Command::new(executable)
        .args(["--data-cleanup", &cleanup_ticket.display().to_string()])
        .spawn()
    {
        let _ = state.supervisor.start(|_| {});
        return Err(format!("无法启动独立数据清理进程：{error}"));
    }
    *state
        .pending_data_deletion
        .lock()
        .map_err(|_| "数据删除凭据状态不可用。".to_owned())? = None;
    state.quitting.store(true, Ordering::SeqCst);
    app.exit(0);
    Ok(())
}

struct AutostartTrayItem(CheckMenuItem<tauri::Wry>);

#[tauri::command]
fn desktop_update_status(state: tauri::State<'_, DesktopState>) -> UpdateSnapshot {
    state.updater.status()
}

#[tauri::command]
fn desktop_update_set_channel(
    channel: String,
    state: tauri::State<'_, DesktopState>,
) -> Result<UpdateSnapshot, String> {
    let snapshot = state.updater.set_channel(&channel)?;
    if let Some(store) = state.config_store.as_ref() {
        store.set_preference_string("DESKTOP_UPDATE_CHANNEL", &snapshot.channel)?;
    }
    Ok(snapshot)
}

#[tauri::command]
fn desktop_update_set_activity(
    busy: bool,
    state: tauri::State<'_, DesktopState>,
) -> UpdateSnapshot {
    state.updater.set_activity_busy(busy)
}

#[tauri::command]
async fn desktop_update_check(
    state: tauri::State<'_, DesktopState>,
) -> Result<UpdateSnapshot, String> {
    let started = Instant::now();
    let updater = Arc::clone(&state.updater);
    let worker = Arc::clone(&updater);
    let result = tauri::async_runtime::spawn_blocking(move || worker.check())
        .await
        .map_err(|error| format!("更新检查任务失败：{error}"))?;
    if let Err(error) = &result {
        updater.mark_failed(error.clone());
    }
    record_reliability(
        &state.reliability,
        ReliabilityEventKind::UpdateCheck,
        if result.is_ok() {
            ReliabilityOutcome::Succeeded
        } else {
            ReliabilityOutcome::Failed
        },
        Some(started.elapsed().as_millis() as u64),
        None,
    );
    result
}

#[tauri::command]
async fn desktop_update_download(
    state: tauri::State<'_, DesktopState>,
) -> Result<UpdateSnapshot, String> {
    let started = Instant::now();
    let updater = Arc::clone(&state.updater);
    let worker = Arc::clone(&updater);
    let result = tauri::async_runtime::spawn_blocking(move || worker.download())
        .await
        .map_err(|error| format!("更新下载任务失败：{error}"))?;
    if let Err(error) = &result {
        updater.mark_failed(error.clone());
    }
    record_reliability(
        &state.reliability,
        ReliabilityEventKind::UpdateDownload,
        if result.is_ok() {
            ReliabilityOutcome::Succeeded
        } else {
            ReliabilityOutcome::Failed
        },
        Some(started.elapsed().as_millis() as u64),
        None,
    );
    result
}

#[tauri::command]
async fn desktop_update_install(
    app: tauri::AppHandle,
    state: tauri::State<'_, DesktopState>,
) -> Result<UpdateSnapshot, String> {
    let started = Instant::now();
    record_reliability(
        &state.reliability,
        ReliabilityEventKind::UpdateInstall,
        ReliabilityOutcome::Attempted,
        None,
        None,
    );
    let updater = Arc::clone(&state.updater);
    let supervisor = Arc::clone(&state.supervisor);
    let quitting = Arc::clone(&state.quitting);
    let (manifest, installer) = updater.installation_inputs()?;
    if let Some(connection) = supervisor.connection() {
        if let Some(reason) = core_update_activity_blocker(&connection)? {
            updater.mark_blocked(reason.clone());
            return Err(reason);
        }
    }
    let worker_updater = Arc::clone(&updater);
    let worker_supervisor = Arc::clone(&supervisor);
    let result = tauri::async_runtime::spawn_blocking(move || {
        let stopped = worker_supervisor.stop(|_| {});
        if !matches!(stopped.state, runtime::RuntimeState::Stopped) {
            return Err("Sidecar 未能完全停止，更新已取消。".to_owned());
        }
        let backup = match worker_supervisor.prepare_update_backup() {
            Ok(backup) => backup,
            Err(error) => {
                let _ = worker_supervisor.start(|_| {});
                return Err(error.message);
            }
        };
        worker_updater.set_backup_evidence(&backup);
        let (helper, transaction) = match worker_updater.stage_install_transaction(&manifest, &installer) {
            Ok(transaction) => transaction,
            Err(error) => {
                let _ = worker_supervisor.start(|_| {});
                return Err(error);
            }
        };
        let transaction_argument = transaction.display().to_string();
        std::process::Command::new(helper)
            .args(["--update-watchdog", &transaction_argument])
            .spawn()
            .map_err(|error| format!("无法启动独立更新监护进程：{error}"))?;
        quitting.store(true, Ordering::SeqCst);
        Ok(worker_updater.mark_installing("备份与校验已通过，Jarvis 将退出并由更新监护进程完成安装。"))
    })
    .await
    .map_err(|error| format!("更新安装准备任务失败：{error}"))?;
    let result = match result {
        Ok(snapshot) => snapshot,
        Err(error) => {
            updater.mark_blocked(error.clone());
            record_reliability(
                &state.reliability,
                ReliabilityEventKind::UpdateInstall,
                ReliabilityOutcome::Failed,
                Some(started.elapsed().as_millis() as u64),
                None,
            );
            return Err(error);
        }
    };
    record_reliability(
        &state.reliability,
        ReliabilityEventKind::UpdateInstall,
        ReliabilityOutcome::Succeeded,
        Some(started.elapsed().as_millis() as u64),
        None,
    );
    app.exit(0);
    Ok(result)
}

fn core_update_activity_blocker(connection: &RuntimeConnection) -> Result<Option<String>, String> {
    let overview = authenticated_core_json(connection, "/observatory/overview")?;
    let active_runs = overview
        .pointer("/runs/active")
        .and_then(serde_json::Value::as_u64)
        .unwrap_or(0);
    let pending_approvals = overview
        .pointer("/approvals/pending")
        .and_then(serde_json::Value::as_u64)
        .unwrap_or(0);
    let tool_executions = authenticated_core_json(connection, "/tool-gateway/executions?limit=200")?;
    let active_tools = tool_executions
        .as_array()
        .map(|items| {
            items
                .iter()
                .filter(|item| {
                    item.get("status")
                        .and_then(serde_json::Value::as_str)
                        .is_some_and(|status| matches!(status, "created" | "running" | "pending_approval" | "approved"))
                })
                .count()
        })
        .unwrap_or(0);
    if active_runs > 0 || pending_approvals > 0 || active_tools > 0 {
        return Ok(Some(format!(
            "当前仍有 {active_runs} 个运行任务、{pending_approvals} 个待审批项、{active_tools} 个未结束工具执行；更新不会强制重启。"
        )));
    }
    Ok(None)
}

fn authenticated_core_json(
    connection: &RuntimeConnection,
    path: &str,
) -> Result<serde_json::Value, String> {
    authenticated_core_request(connection, "GET", path, None)
}

fn authenticated_core_request(
    connection: &RuntimeConnection,
    method: &str,
    path: &str,
    body: Option<&str>,
) -> Result<serde_json::Value, String> {
    use std::io::{Read, Write};
    use std::net::TcpStream;

    let url = tauri::Url::parse(&connection.api_base_url)
        .map_err(|_| "桌面 Runtime Connection 地址无效。".to_owned())?;
    let host = url.host_str().unwrap_or_default();
    if host != "127.0.0.1" {
        return Err("更新活动检查只允许访问本次桌面会话的回环 Core。".to_owned());
    }
    let port = url.port().ok_or_else(|| "桌面 Core 端口不可用。".to_owned())?;
    let token = connection
        .session_token
        .as_deref()
        .ok_or_else(|| "桌面会话凭证不可用，不能确认更新空闲状态。".to_owned())?;
    let mut stream = TcpStream::connect_timeout(
        &format!("127.0.0.1:{port}").parse().map_err(|_| "Core 地址无效。")?,
        Duration::from_secs(3),
    )
    .map_err(|error| format!("无法确认 Core 更新空闲状态：{error}"))?;
    stream
        .set_read_timeout(Some(Duration::from_secs(5)))
        .map_err(|error| error.to_string())?;
    if !matches!(method, "GET" | "PATCH") {
        return Err("桌面 Core 请求方法不在允许列表中。".to_owned());
    }
    let payload = body.unwrap_or_default();
    let content_headers = if body.is_some() {
        format!(
            "Content-Type: application/json\r\nContent-Length: {}\r\n",
            payload.len()
        )
    } else {
        String::new()
    };
    let request = format!(
        "{method} /api/v1{path} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nX-Jarvis-Desktop-Session: {token}\r\n{content_headers}Connection: close\r\n\r\n{payload}"
    );
    stream.write_all(request.as_bytes()).map_err(|error| error.to_string())?;
    let mut response = Vec::new();
    stream
        .take(2 * 1024 * 1024)
        .read_to_end(&mut response)
        .map_err(|error| format!("读取更新空闲状态失败：{error}"))?;
    let separator = response
        .windows(4)
        .position(|window| window == b"\r\n\r\n")
        .ok_or_else(|| "Core 更新空闲状态响应无效。".to_owned())?;
    let header = String::from_utf8_lossy(&response[..separator]);
    let status = header.lines().next().unwrap_or_default();
    if !status.contains(" 200 ") {
        return Err(format!("Core 拒绝更新空闲状态检查：{status}"));
    }
    serde_json::from_slice(&response[separator + 4..])
        .map_err(|error| format!("Core 更新空闲状态格式无效：{error}"))
}

fn set_reminder_pause(app: tauri::AppHandle, paused: bool) {
    std::thread::spawn(move || {
        let result = app
            .state::<DesktopState>()
            .supervisor
            .connection()
            .ok_or_else(|| "Jarvis Core 尚未就绪，无法更新提醒状态。".to_owned())
            .and_then(|connection| {
                let paused_until = if paused {
                    (std::time::SystemTime::now() + Duration::from_secs(60 * 60))
                        .duration_since(std::time::UNIX_EPOCH)
                        .unwrap_or_default()
                        .as_secs()
                        .to_string()
                } else {
                    "null".to_owned()
                };
                authenticated_core_request(
                    &connection,
                    "PATCH",
                    "/notifications/preferences",
                    Some(&format!("{{\"paused_until\":{paused_until}}}")),
                )
            });
        let message = match result {
            Ok(_) if paused => "提醒已暂停 1 小时。",
            Ok(_) => "提醒已恢复。",
            Err(error) => {
                eprintln!("Jarvis reminder preference update failed: {error}");
                "无法更新提醒状态，请打开通知中心重试。"
            }
        };
        if let Some(window) = app.get_webview_window("main") {
            if let Ok(message) = serde_json::to_string(message) {
                let _ = window.eval(format!(
                    "window.dispatchEvent(new CustomEvent('jarvis:tray-feedback', {{ detail: {message} }}));"
                ));
            }
        }
    });
}

#[derive(Clone, serde::Serialize)]
#[serde(rename_all = "camelCase")]
struct DesktopPreferenceStatus {
    autostart_enabled: bool,
    quick_shortcut: String,
    quick_shortcut_options: Vec<String>,
    quick_shortcut_enabled: bool,
    voice_shortcut: String,
    voice_shortcut_options: Vec<String>,
    voice_shortcut_enabled: bool,
    close_behavior: String,
    close_behavior_options: Vec<String>,
    open_with_enabled: bool,
}

#[tauri::command]
fn desktop_preferences(app: tauri::AppHandle) -> Result<DesktopPreferenceStatus, String> {
    let state = app.state::<DesktopState>();
    let configured_shortcut = state
        .config_store
        .as_ref()
        .map(|store| store.preference_bool("DESKTOP_QUICK_SHORTCUT_ENABLED", true))
        .transpose()?
        .unwrap_or(true);
    let configured_voice = state
        .config_store
        .as_ref()
        .map(|store| store.preference_bool("DESKTOP_VOICE_SHORTCUT_ENABLED", false))
        .transpose()?
        .unwrap_or(false);
    let close_behavior = state
        .config_store
        .as_ref()
        .map(|store| store.preference_string("DESKTOP_CLOSE_BEHAVIOR", "hide"))
        .transpose()?
        .unwrap_or_else(|| "hide".to_owned());
    Ok(DesktopPreferenceStatus {
        autostart_enabled: autostart_enabled()?,
        quick_shortcut: state.quick_shortcut.quick_label(),
        quick_shortcut_options: quick_shortcut_options(),
        quick_shortcut_enabled: configured_shortcut && state.quick_shortcut.is_quick_registered(),
        voice_shortcut: state.quick_shortcut.voice_label(),
        voice_shortcut_options: voice_shortcut_options(),
        voice_shortcut_enabled: configured_voice && state.quick_shortcut.is_voice_registered(),
        close_behavior,
        close_behavior_options: vec!["hide".to_owned(), "quit".to_owned()],
        open_with_enabled: open_with_enabled()?,
    })
}

#[tauri::command]
fn desktop_set_autostart(
    enabled: bool,
    app: tauri::AppHandle,
) -> Result<DesktopPreferenceStatus, String> {
    if enabled {
        autostart_fuse::clear(&user_data_root()?)?;
    }
    set_autostart(enabled)?;
    if let Some(menu_item) = app.try_state::<AutostartTrayItem>() {
        menu_item
            .0
            .set_checked(enabled)
            .map_err(|error| format!("无法同步托盘开机启动状态：{error}"))?;
    }
    desktop_preferences(app)
}

#[tauri::command]
fn desktop_set_quick_shortcut(
    enabled: bool,
    app: tauri::AppHandle,
) -> Result<DesktopPreferenceStatus, String> {
    let state = app.state::<DesktopState>();
    state.quick_shortcut.set_quick_enabled(enabled)?;
    if let Some(store) = state.config_store.as_ref() {
        store.set_preference_bool("DESKTOP_QUICK_SHORTCUT_ENABLED", enabled)?;
    }
    desktop_preferences(app)
}

#[tauri::command]
fn desktop_set_voice_shortcut(
    enabled: bool,
    app: tauri::AppHandle,
) -> Result<DesktopPreferenceStatus, String> {
    let state = app.state::<DesktopState>();
    state.quick_shortcut.set_voice_enabled(enabled)?;
    if let Some(store) = state.config_store.as_ref() {
        store.set_preference_bool("DESKTOP_VOICE_SHORTCUT_ENABLED", enabled)?;
    }
    desktop_preferences(app)
}

#[tauri::command]
fn desktop_set_close_behavior(
    behavior: String,
    app: tauri::AppHandle,
) -> Result<DesktopPreferenceStatus, String> {
    if !matches!(behavior.as_str(), "hide" | "quit") {
        return Err("关闭主窗口行为不受支持。".to_owned());
    }
    let state = app.state::<DesktopState>();
    let store = state
        .config_store
        .as_ref()
        .ok_or_else(|| "安装态桌面配置尚未就绪。".to_owned())?;
    store.set_preference_string("DESKTOP_CLOSE_BEHAVIOR", &behavior)?;
    desktop_preferences(app)
}

#[tauri::command]
fn desktop_set_open_with(
    enabled: bool,
    app: tauri::AppHandle,
) -> Result<DesktopPreferenceStatus, String> {
    let previous = open_with_enabled()?;
    set_open_with_enabled(enabled)?;
    if let Some(store) = app.state::<DesktopState>().config_store.as_ref() {
        if let Err(error) = store.set_preference_bool("DESKTOP_OPEN_WITH_ENABLED", enabled) {
            let _ = set_open_with_enabled(previous);
            return Err(error);
        }
    }
    desktop_preferences(app)
}

#[tauri::command]
fn desktop_set_shortcut_binding(
    kind: String,
    binding: String,
    app: tauri::AppHandle,
) -> Result<DesktopPreferenceStatus, String> {
    let state = app.state::<DesktopState>();
    let voice = match kind.as_str() {
        "quick" => false,
        "voice" => true,
        _ => return Err("快捷键类型不受支持。".to_owned()),
    };
    let old = if voice { state.quick_shortcut.voice_label() } else { state.quick_shortcut.quick_label() };
    state.quick_shortcut.set_binding(&binding, voice)?;
    if let Some(store) = state.config_store.as_ref() {
        let key = if voice { "DESKTOP_VOICE_SHORTCUT" } else { "DESKTOP_QUICK_SHORTCUT" };
        if let Err(error) = store.set_preference_string(key, &binding) {
            let _ = state.quick_shortcut.set_binding(&old, voice);
            return Err(error);
        }
    }
    desktop_preferences(app)
}

#[tauri::command]
fn desktop_open_microphone_settings() -> Result<(), String> {
    #[cfg(windows)]
    {
        std::process::Command::new("explorer.exe")
            .arg("ms-settings:privacy-microphone")
            .spawn()
            .map(|_| ())
            .map_err(|error| format!("无法打开 Windows 麦克风隐私设置：{error}"))
    }
    #[cfg(not(windows))]
    {
        Err("麦克风隐私设置入口仅适用于 Windows。".to_owned())
    }
}

#[tauri::command]
fn quick_hide(app: tauri::AppHandle) {
    if let Some(window) = app.get_webview_window("quick") {
        let _ = window.hide();
    }
}

#[tauri::command]
fn desktop_file_read(
    token: String,
    state: tauri::State<'_, DesktopState>,
) -> Result<FileHandoffContent, String> {
    let result = state.file_handoff.read_confirmed(&token);
    record_reliability(
        &state.reliability,
        ReliabilityEventKind::FileConfirm,
        if result.is_ok() {
            ReliabilityOutcome::Succeeded
        } else {
            ReliabilityOutcome::Failed
        },
        None,
        None,
    );
    result
}

#[tauri::command]
fn desktop_file_cancel(
    token: String,
    state: tauri::State<'_, DesktopState>,
) -> Result<(), String> {
    let result = state.file_handoff.cancel(&token);
    record_reliability(
        &state.reliability,
        ReliabilityEventKind::FileReject,
        if result.is_ok() {
            ReliabilityOutcome::Succeeded
        } else {
            ReliabilityOutcome::Failed
        },
        None,
        None,
    );
    result
}

#[tauri::command]
fn quick_continue_in_main(
    conversation_id: Option<String>,
    draft: Option<String>,
    app: tauri::AppHandle,
    state: tauri::State<'_, DesktopState>,
) -> Result<(), String> {
    let started = Instant::now();
    if conversation_id
        .as_deref()
        .is_some_and(|value| !is_valid_object_id(value))
    {
        return Err("对话引用格式无效。".to_owned());
    }
    if draft.as_deref().is_some_and(|value| value.len() > 20_000) {
        return Err("草稿超过 20,000 字符，无法转入主窗口。".to_owned());
    }
    let connection = state
        .supervisor
        .connection()
        .ok_or_else(|| "Jarvis Core 尚未就绪。".to_owned())?;
    show_main_window(&app, connection).map_err(|error| {
        record_reliability(
            &state.reliability,
            ReliabilityEventKind::QuickContinue,
            ReliabilityOutcome::Failed,
            Some(started.elapsed().as_millis() as u64),
            None,
        );
        error.message
    })?;
    let detail = serde_json::to_string(&serde_json::json!({
        "conversationId": conversation_id,
        "draft": draft,
    }))
    .map_err(|error| error.to_string())?;
    if let Some(window) = app.get_webview_window("main") {
        window
            .eval(format!(
                "window.__JARVIS_DESKTOP_OPEN__ = {detail}; window.dispatchEvent(new CustomEvent('jarvis:open-conversation', {{ detail: {detail} }}));"
            ))
            .map_err(|error| error.to_string())?;
    }
    if let Some(window) = app.get_webview_window("quick") {
        let _ = window.hide();
    }
    record_reliability(
        &state.reliability,
        ReliabilityEventKind::QuickContinue,
        ReliabilityOutcome::Succeeded,
        Some(started.elapsed().as_millis() as u64),
        None,
    );
    Ok(())
}

fn is_valid_object_id(value: &str) -> bool {
    value.len() == 36
        && value.chars().enumerate().all(|(index, character)| {
            if matches!(index, 8 | 13 | 18 | 23) {
                character == '-'
            } else {
                character.is_ascii_hexdigit()
            }
        })
}

fn activation_detail(value: &str) -> Result<serde_json::Value, String> {
    let url = tauri::Url::parse(value).map_err(|_| "Jarvis 激活链接格式无效。".to_owned())?;
    if url.scheme() != "jarvis" {
        return Err("Jarvis 只接受已注册的 jarvis:// 激活链接。".to_owned());
    }
    let segments = url
        .path_segments()
        .map(|items| items.collect::<Vec<_>>())
        .unwrap_or_default();
    let host = url.host_str().unwrap_or_default();
    if host == "notification" && segments.len() == 1 && is_valid_object_id(segments[0]) {
        if url.query().is_some() {
            return Err("打开提醒的激活链接不接受额外参数。".to_owned());
        }
        return Ok(serde_json::json!({
            "kind": "notification",
            "id": segments[0],
        }));
    }
    if host == "notification"
        && segments.len() == 3
        && is_valid_object_id(segments[0])
        && segments[1] == "snooze"
        && segments[2] == "10"
    {
        let parameters = url.query_pairs().collect::<Vec<_>>();
        if parameters.len() != 1
            || parameters[0].0 != "action"
            || !is_valid_object_id(parameters[0].1.as_ref())
        {
            return Err("稍后提醒动作缺少有效的幂等引用。".to_owned());
        }
        return Ok(serde_json::json!({
            "kind": "notification_snooze",
            "id": segments[0],
            "minutes": 10,
            "actionId": parameters[0].1,
        }));
    }
    Err("激活链接引用无效或不受支持。".to_owned())
}

fn handle_activation_uri(app: &tauri::AppHandle, value: &str) -> Result<(), String> {
    let detail = activation_detail(value)?;
    let kind = match detail.get("kind").and_then(serde_json::Value::as_str) {
        Some("notification") => Some(ReliabilityEventKind::NotificationOpen),
        Some("notification_snooze") => Some(ReliabilityEventKind::NotificationSnooze),
        _ => None,
    };
    let result = deliver_desktop_activation(app, detail);
    if let Some(kind) = kind {
        let outcome = if matches!(kind, ReliabilityEventKind::NotificationSnooze) {
            ReliabilityOutcome::Attempted
        } else if result.is_ok() {
            ReliabilityOutcome::Succeeded
        } else {
            ReliabilityOutcome::Failed
        };
        record_reliability(
            &app.state::<DesktopState>().reliability,
            kind,
            outcome,
            None,
            None,
        );
    }
    result
}

fn deliver_desktop_activation(
    app: &tauri::AppHandle,
    detail_value: serde_json::Value,
) -> Result<(), String> {
    let detail = serde_json::to_string(&detail_value).map_err(|error| error.to_string())?;
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.show();
        let _ = window.unminimize();
        let _ = window.set_focus();
        window
            .eval(format!(
                "window.__JARVIS_DESKTOP_ACTIVATION__ = {detail}; window.dispatchEvent(new CustomEvent('jarvis:desktop-activation', {{ detail: {detail} }}));"
            ))
            .map_err(|error| error.to_string())?;
        return Ok(());
    }
    *app
        .state::<DesktopState>()
        .pending_activation
        .lock()
        .map_err(|_| "Jarvis 激活状态暂时不可用。".to_owned())? = Some(detail_value);
    if let Some(connection) = app.state::<DesktopState>().supervisor.connection() {
        let handle = app.clone();
        std::thread::spawn(move || {
            let _ = show_main_window(&handle, connection);
        });
    } else {
        focus_existing(app);
    }
    Ok(())
}

fn queue_file_handoff(
    app: &tauri::AppHandle,
    path: &std::path::Path,
    source: &str,
) -> Result<(), String> {
    let preview: FileHandoffPreview = app
        .state::<DesktopState>()
        .file_handoff
        .preview(path, source)?;
    record_reliability(
        &app.state::<DesktopState>().reliability,
        ReliabilityEventKind::FilePreview,
        ReliabilityOutcome::Succeeded,
        None,
        None,
    );
    deliver_desktop_activation(
        app,
        serde_json::json!({
            "kind": "file",
            "preview": preview,
        }),
    )
}

fn deliver_file_error(app: &tauri::AppHandle, message: String) {
    record_reliability(
        &app.state::<DesktopState>().reliability,
        ReliabilityEventKind::FilePreview,
        ReliabilityOutcome::Failed,
        None,
        None,
    );
    let _ = deliver_desktop_activation(
        app,
        serde_json::json!({
            "kind": "file-error",
            "message": message,
        }),
    );
}

fn activation_file_argument(arguments: &[String]) -> Option<std::path::PathBuf> {
    arguments
        .iter()
        .skip(1)
        .find(|argument| {
            !argument.starts_with('-')
                && !argument.starts_with("jarvis://")
                && !argument.contains("://")
        })
        .map(std::path::PathBuf::from)
}

fn show_quick_window(app: &tauri::AppHandle) -> Result<(), RuntimeFailure> {
    let started = Instant::now();
    let state = app.state::<DesktopState>();
    record_reliability(
        &state.reliability,
        ReliabilityEventKind::QuickOpen,
        ReliabilityOutcome::Attempted,
        None,
        None,
    );
    let result = show_quick_window_inner(app);
    record_reliability(
        &state.reliability,
        ReliabilityEventKind::QuickOpen,
        if result.is_ok() {
            ReliabilityOutcome::Succeeded
        } else {
            ReliabilityOutcome::Failed
        },
        Some(started.elapsed().as_millis() as u64),
        None,
    );
    result
}

fn show_quick_window_inner(app: &tauri::AppHandle) -> Result<(), RuntimeFailure> {
    if let Some(window) = app.get_webview_window("quick") {
        let _ = window.unminimize();
        ensure_window_visible(&window)?;
        window.show().map_err(|error| {
            RuntimeFailure::new(
                "interface",
                "QUICK_WINDOW_SHOW_FAILED",
                format!("无法显示快速提问窗口：{error}"),
            )
        })?;
        window.set_focus().map_err(|error| {
            RuntimeFailure::new(
                "interface",
                "QUICK_WINDOW_FOCUS_FAILED",
                format!("无法聚焦快速提问窗口：{error}"),
            )
        })?;
        return Ok(());
    }
    let state = app.state::<DesktopState>();
    let connection = state.supervisor.connection().ok_or_else(|| {
        RuntimeFailure::new(
            "interface",
            "QUICK_RUNTIME_NOT_READY",
            "Jarvis Core 尚未就绪，暂时无法快速提问。",
        )
    })?;
    let connection_json = serde_json::to_string(&connection).map_err(|error| {
        RuntimeFailure::new(
            "interface",
            "RUNTIME_CONNECTION_SERIALIZE_FAILED",
            format!("无法准备快速提问连接：{error}"),
        )
    })?;
    let initialization_script = format!(
        "Object.defineProperty(window, '__JARVIS_RUNTIME__', {{ value: Object.freeze({connection_json}), configurable: false, writable: false }});"
    );
    let window = WebviewWindowBuilder::new(
        app,
        "quick",
        WebviewUrl::App("splash/quick/index.html".into()),
    )
    .initialization_script(initialization_script)
    .title("Jarvis OS · 快速提问")
    .inner_size(720.0, 640.0)
    .min_inner_size(600.0, 520.0)
    .center()
    .visible(true)
    .always_on_top(false)
    .build()
    .map_err(|error| {
        RuntimeFailure::new(
            "interface",
            "QUICK_WINDOW_CREATE_FAILED",
            format!("无法创建快速提问窗口：{error}"),
        )
    })?;
    configure_local_media_permissions_async(window.clone());
    ensure_window_visible(&window)?;
    let _ = window.set_focus();
    Ok(())
}

#[tauri::command]
fn desktop_config_status(
    state: tauri::State<'_, DesktopState>,
) -> Option<DesktopConfigStatus> {
    state.config_store.as_ref().map(|store| store.status())
}

#[tauri::command]
fn desktop_config_preview(
    source_name: String,
    contents: String,
    state: tauri::State<'_, DesktopState>,
) -> Result<MigrationPreview, String> {
    let store = state
        .config_store
        .as_ref()
        .ok_or_else(|| "源码运行模式不需要迁移安装态配置。".to_owned())?;
    store.preview_legacy(&source_name, &contents)
}

#[tauri::command]
fn desktop_config_apply(
    selected_names: Vec<String>,
    state: tauri::State<'_, DesktopState>,
) -> Result<MigrationResult, String> {
    let store = state
        .config_store
        .as_ref()
        .ok_or_else(|| "源码运行模式不需要迁移安装态配置。".to_owned())?;
    store.apply_pending(&selected_names)
}

#[tauri::command]
fn desktop_config_cancel(state: tauri::State<'_, DesktopState>) -> Result<(), String> {
    let store = state
        .config_store
        .as_ref()
        .ok_or_else(|| "源码运行模式不需要迁移安装态配置。".to_owned())?;
    store.cancel_pending()
}

#[tauri::command]
fn desktop_config_complete(
    state: tauri::State<'_, DesktopState>,
) -> Result<DesktopConfigStatus, String> {
    let store = state
        .config_store
        .as_ref()
        .ok_or_else(|| "源码运行模式不需要迁移安装态配置。".to_owned())?;
    store.complete_without_import()
}

#[tauri::command]
fn runtime_status(state: tauri::State<'_, DesktopState>) -> RuntimeSnapshot {
    state.supervisor.status()
}

#[tauri::command]
async fn runtime_start(
    app: tauri::AppHandle,
    state: tauri::State<'_, DesktopState>,
) -> Result<RuntimeSnapshot, String> {
    let supervisor = Arc::clone(&state.supervisor);
    let reliability = Arc::clone(&state.reliability);
    let snapshot = supervisor.status();
    if matches!(snapshot.state, runtime::RuntimeState::Starting) {
        return Ok(snapshot);
    }
    let result = tauri::async_runtime::spawn_blocking(move || {
        start_runtime(app, supervisor, reliability, true)
    })
        .await
        .map_err(|error| format!("runtime start task failed: {error}"))?;
    Ok(result)
}

#[tauri::command]
async fn runtime_stop(
    app: tauri::AppHandle,
    state: tauri::State<'_, DesktopState>,
) -> Result<RuntimeSnapshot, String> {
    let supervisor = Arc::clone(&state.supervisor);
    let result = tauri::async_runtime::spawn_blocking(move || {
        supervisor.stop(|snapshot| {
            let _ = app.emit("runtime://snapshot", snapshot);
        })
    })
    .await
    .map_err(|error| format!("runtime stop task failed: {error}"))?;
    Ok(result)
}

#[tauri::command]
fn runtime_diagnostics(state: tauri::State<'_, DesktopState>) -> RuntimeDiagnostics {
    state.supervisor.diagnostics()
}

#[tauri::command]
async fn runtime_restart_core(
    app: tauri::AppHandle,
    state: tauri::State<'_, DesktopState>,
) -> Result<RuntimeSnapshot, String> {
    let supervisor = Arc::clone(&state.supervisor);
    let reliability = Arc::clone(&state.reliability);
    record_reliability(
        &reliability,
        ReliabilityEventKind::SupervisorRestart,
        ReliabilityOutcome::Attempted,
        None,
        None,
    );
    let result = tauri::async_runtime::spawn_blocking(move || {
        supervisor.restart_core(|snapshot| {
            let _ = app.emit("runtime://snapshot", snapshot);
        })
    })
    .await
    .map_err(|error| format!("runtime restart task failed: {error}"))?;
    record_reliability(
        &state.reliability,
        ReliabilityEventKind::SupervisorRestart,
        runtime_outcome(&result.state),
        None,
        None,
    );
    Ok(result)
}

#[tauri::command]
fn runtime_open_logs(
    app: tauri::AppHandle,
    state: tauri::State<'_, DesktopState>,
) -> Result<String, String> {
    let path = state.supervisor.diagnostics().log_directory;
    if path.is_empty() {
        return Err("当前运行适配器没有可用日志目录。".to_owned());
    }
    app.opener()
        .open_path(path.clone(), None::<&str>)
        .map_err(|error| format!("无法打开日志目录：{error}"))?;
    Ok(path)
}

#[tauri::command]
fn runtime_export_diagnostics(
    app: tauri::AppHandle,
    state: tauri::State<'_, DesktopState>,
) -> Result<DiagnosticBundleRef, String> {
    let started = Instant::now();
    let exported = state
        .supervisor
        .export_diagnostics()
        .map_err(|error| {
            record_reliability(
                &state.reliability,
                ReliabilityEventKind::DiagnosticExport,
                ReliabilityOutcome::Failed,
                Some(started.elapsed().as_millis() as u64),
                None,
            );
            error.message
        })?;
    record_reliability(
        &state.reliability,
        ReliabilityEventKind::DiagnosticExport,
        ReliabilityOutcome::Succeeded,
        Some(started.elapsed().as_millis() as u64),
        None,
    );
    app.opener()
        .open_path(exported.path.clone(), None::<&str>)
        .map_err(|error| format!("诊断文件已生成，但无法打开：{error}"))?;
    Ok(exported)
}

fn start_runtime(
    app: tauri::AppHandle,
    supervisor: Arc<DesktopSupervisor>,
    reliability: Arc<ReliabilityLedger>,
    open_main: bool,
) -> RuntimeSnapshot {
    let started = Instant::now();
    record_reliability(
        &reliability,
        ReliabilityEventKind::Startup,
        ReliabilityOutcome::Attempted,
        None,
        None,
    );
    let mut result = supervisor.start(|snapshot| {
        if let Some(stage) = reliability_stage(&snapshot.stage) {
            record_reliability(
                &reliability,
                ReliabilityEventKind::StartupStage,
                ReliabilityOutcome::Attempted,
                Some(started.elapsed().as_millis() as u64),
                Some(stage),
            );
        }
        let _ = app.emit("runtime://snapshot", snapshot);
    });
    if open_main && matches!(
        result.state,
        runtime::RuntimeState::Ready | runtime::RuntimeState::Degraded
    ) {
        if let Some(connection) = supervisor.connection() {
            if let Err(error) = show_main_window(&app, connection) {
                result = supervisor.record_failure(error, |snapshot| {
                    let _ = app.emit("runtime://snapshot", snapshot);
                });
            }
        } else {
            let error = RuntimeFailure::new(
                "interface",
                "RUNTIME_CONNECTION_MISSING",
                "Jarvis Core 已启动，但没有可用的桌面连接信息。",
            );
            result = supervisor.record_failure(error, |snapshot| {
                let _ = app.emit("runtime://snapshot", snapshot);
            });
        }
    }
    if !open_main
        && matches!(
            result.state,
            runtime::RuntimeState::Ready | runtime::RuntimeState::Degraded
        )
    {
        if let Some(splash) = app.get_webview_window("splash") {
            let _ = splash.hide();
        }
    }
    record_reliability(
        &reliability,
        ReliabilityEventKind::Startup,
        runtime_outcome(&result.state),
        Some(started.elapsed().as_millis() as u64),
        None,
    );
    record_reliability(
        &reliability,
        ReliabilityEventKind::SupervisorState,
        runtime_outcome(&result.state),
        None,
        None,
    );
    result
}

fn reliability_stage(stage: &str) -> Option<ReliabilityStage> {
    match stage {
        "preflight" => Some(ReliabilityStage::Preflight),
        "database" => Some(ReliabilityStage::Database),
        "migration" => Some(ReliabilityStage::Migration),
        "core" => Some(ReliabilityStage::Core),
        "companion" => Some(ReliabilityStage::Companion),
        "interface" => Some(ReliabilityStage::Interface),
        _ => None,
    }
}

fn runtime_outcome(state: &runtime::RuntimeState) -> ReliabilityOutcome {
    match state {
        runtime::RuntimeState::Ready => ReliabilityOutcome::Succeeded,
        runtime::RuntimeState::Degraded => ReliabilityOutcome::Degraded,
        runtime::RuntimeState::Blocked => ReliabilityOutcome::Blocked,
        runtime::RuntimeState::Idle
        | runtime::RuntimeState::Starting
        | runtime::RuntimeState::Stopping
        | runtime::RuntimeState::Stopped => {
            ReliabilityOutcome::Cancelled
        }
    }
}

fn show_main_window(
    app: &tauri::AppHandle,
    connection: RuntimeConnection,
) -> Result<(), RuntimeFailure> {
    let (sender, receiver) = mpsc::sync_channel(1);
    let handle = app.clone();
    app.run_on_main_thread(move || {
        let _ = sender.send(show_main_window_on_main_thread(&handle, connection));
    })
    .map_err(|error| {
        RuntimeFailure::new(
            "interface",
            "MAIN_THREAD_DISPATCH_FAILED",
            format!("无法调度 Jarvis 主窗口：{error}"),
        )
    })?;
    receiver.recv_timeout(Duration::from_secs(15)).map_err(|error| {
        RuntimeFailure::new(
            "interface",
            "MAIN_THREAD_RESPONSE_TIMEOUT",
            format!("等待 Jarvis 主窗口响应超时：{error}"),
        )
    })?
}

fn show_main_window_on_main_thread(
    app: &tauri::AppHandle,
    connection: RuntimeConnection,
) -> Result<(), RuntimeFailure> {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.unminimize();
        ensure_window_visible(&window)?;
        window.show().map_err(|error| {
            RuntimeFailure::new(
                "interface",
                "MAIN_WINDOW_SHOW_FAILED",
                format!("无法显示 Jarvis 主窗口：{error}"),
            )
        })?;
        window.set_focus().map_err(|error| {
            RuntimeFailure::new(
                "interface",
                "MAIN_WINDOW_FOCUS_FAILED",
                format!("无法聚焦 Jarvis 主窗口：{error}"),
            )
        })?;
    } else {
        let navigation_app = app.clone();
        let popup_app = app.clone();
        let connection_json = serde_json::to_string(&connection).map_err(|error| {
            RuntimeFailure::new(
                "interface",
                "RUNTIME_CONNECTION_SERIALIZE_FAILED",
                format!("无法准备 Jarvis 桌面连接：{error}"),
            )
        })?;
        let initialization_script = format!(
            "Object.defineProperty(window, '__JARVIS_RUNTIME__', {{ value: Object.freeze({connection_json}), configurable: false, writable: false }});"
        );
        let window = WebviewWindowBuilder::new(
            app,
            "main",
            WebviewUrl::App("chat/index.html".into()),
        )
            .initialization_script(initialization_script)
            .title("Jarvis OS")
            .inner_size(1440.0, 900.0)
            .min_inner_size(1080.0, 700.0)
            .center()
            .visible(false)
            .on_navigation(move |target| {
                if is_allowed_app_url(target) {
                    true
                } else {
                    open_external_url(&navigation_app, target);
                    false
                }
            })
            .on_new_window(move |target, _features| {
                open_external_url(&popup_app, &target);
                NewWindowResponse::Deny
            })
            .build()
            .map_err(|error| {
                RuntimeFailure::new(
                    "interface",
                    "MAIN_WINDOW_CREATE_FAILED",
                    format!("无法创建 Jarvis 主窗口：{error}"),
                )
            })?;
        configure_local_media_permissions_async(window.clone());
        ensure_window_visible(&window)?;
        window.show().map_err(|error| {
            RuntimeFailure::new(
                "interface",
                "MAIN_WINDOW_SHOW_FAILED",
                format!("无法显示 Jarvis 主窗口：{error}"),
            )
        })?;
        window.set_focus().map_err(|error| {
            RuntimeFailure::new(
                "interface",
                "MAIN_WINDOW_FOCUS_FAILED",
                format!("无法聚焦 Jarvis 主窗口：{error}"),
            )
        })?;
        // 一进去即大屏：window-state 插件可能恢复上一次的小窗状态，
        // 显示后显式最大化，保证每次启动都以大屏工作台呈现。
        window.maximize().map_err(|error| {
            RuntimeFailure::new(
                "interface",
                "MAIN_WINDOW_MAXIMIZE_FAILED",
                format!("无法最大化 Jarvis 主窗口：{error}"),
            )
        })?;
    }
    if let Some(splash) = app.get_webview_window("splash") {
        let _ = splash.hide();
    }
    dispatch_pending_activation(app)?;
    Ok(())
}

fn dispatch_pending_activation(app: &tauri::AppHandle) -> Result<(), RuntimeFailure> {
    let detail_value = app
        .state::<DesktopState>()
        .pending_activation
        .lock()
        .map_err(|_| {
            RuntimeFailure::new(
                "interface",
                "ACTIVATION_STATE_UNAVAILABLE",
                "Jarvis 激活状态暂时不可用。",
            )
        })?
        .take();
    let Some(detail_value) = detail_value else {
        return Ok(());
    };
    let detail = serde_json::to_string(&detail_value).map_err(|error| {
        RuntimeFailure::new(
            "interface",
            "ACTIVATION_SERIALIZE_FAILED",
            format!("无法准备 Jarvis 激活信息：{error}"),
        )
    })?;
    if let Some(window) = app.get_webview_window("main") {
        window
            .eval(format!(
                "window.__JARVIS_DESKTOP_ACTIVATION__ = {detail}; window.dispatchEvent(new CustomEvent('jarvis:desktop-activation', {{ detail: {detail} }}));"
            ))
            .map_err(|error| {
                RuntimeFailure::new(
                    "interface",
                    "ACTIVATION_DELIVERY_FAILED",
                    format!("无法送达 Jarvis 激活信息：{error}"),
                )
            })?;
    }
    Ok(())
}

fn open_external_url(app: &tauri::AppHandle, url: &tauri::Url) {
    if matches!(url.scheme(), "http" | "https" | "mailto") {
        let _ = app.opener().open_url(url.as_str(), None::<&str>);
    }
}

#[cfg(windows)]
fn configure_local_media_permissions_async(window: tauri::WebviewWindow) {
    std::thread::spawn(move || {
        if let Err(error) = configure_local_media_permissions(&window) {
            eprintln!("Jarvis media permission policy failed closed: {}", error.message);
            let _ = window.close();
        }
    });
}

#[cfg(not(windows))]
fn configure_local_media_permissions_async(_window: tauri::WebviewWindow) {}

#[cfg(windows)]
fn configure_local_media_permissions(
    window: &tauri::WebviewWindow,
) -> Result<(), RuntimeFailure> {
    window
        .with_webview(|platform_webview| unsafe {
            let core = match platform_webview.controller().CoreWebView2() {
                Ok(core) => core,
                Err(_) => return,
            };
            let mut token = 0;
            let _ = core.add_PermissionRequested(
                &PermissionRequestedEventHandler::create(Box::new(|_, args| {
                    let Some(args) = args else {
                        return Ok(());
                    };
                    let mut kind = COREWEBVIEW2_PERMISSION_KIND::default();
                    args.PermissionKind(&mut kind)?;
                    let mut uri = windows_core::PWSTR::null();
                    args.Uri(&mut uri)?;
                    let uri = webview2_com::take_pwstr(uri);
                    let trusted_origin = uri.starts_with("http://tauri.localhost/")
                        || uri.starts_with("tauri://localhost/");
                    let state = if kind == COREWEBVIEW2_PERMISSION_KIND_MICROPHONE
                        && trusted_origin
                    {
                        COREWEBVIEW2_PERMISSION_STATE_DEFAULT
                    } else {
                        COREWEBVIEW2_PERMISSION_STATE_DENY
                    };
                    args.SetState(state)?;
                    Ok(())
                })),
                &mut token,
            );
        })
        .map_err(|error| {
            RuntimeFailure::new(
                "interface",
                "MEDIA_PERMISSION_POLICY_FAILED",
                format!("无法安装 Jarvis 麦克风权限策略：{error}"),
            )
        })?;
    Ok(())
}

#[cfg(not(windows))]
fn configure_local_media_permissions(
    _window: &tauri::WebviewWindow,
) -> Result<(), RuntimeFailure> {
    Ok(())
}

fn is_allowed_app_url(url: &tauri::Url) -> bool {
    (url.scheme() == "http" && url.host_str() == Some("tauri.localhost"))
        || (url.scheme() == "tauri" && url.host_str() == Some("localhost"))
}

fn focus_existing(app: &tauri::AppHandle) {
    let target = app
        .get_webview_window("main")
        .or_else(|| app.get_webview_window("splash"));
    if let Some(window) = target {
        let _ = window.unminimize();
        let _ = ensure_window_visible(&window);
        let _ = window.show();
        let _ = window.set_focus();
    }
}

fn show_status_window(app: &tauri::AppHandle) -> Result<(), RuntimeFailure> {
    if let Some(window) = app.get_webview_window("status") {
        let _ = window.unminimize();
        ensure_window_visible(&window)?;
        window.show().map_err(|error| {
            RuntimeFailure::new(
                "interface",
                "STATUS_WINDOW_SHOW_FAILED",
                format!("无法显示运行状态中心：{error}"),
            )
        })?;
        window.set_focus().map_err(|error| {
            RuntimeFailure::new(
                "interface",
                "STATUS_WINDOW_FOCUS_FAILED",
                format!("无法聚焦运行状态中心：{error}"),
            )
        })?;
        return Ok(());
    }
    let window = WebviewWindowBuilder::new(
        app,
        "status",
        WebviewUrl::App("splash/status/index.html".into()),
    )
    .title("Jarvis OS · 运行状态中心")
    .inner_size(1120.0, 760.0)
    .min_inner_size(880.0, 620.0)
    .center()
    .visible(true)
    .build()
    .map_err(|error| {
        RuntimeFailure::new(
            "interface",
            "STATUS_WINDOW_CREATE_FAILED",
            format!("无法创建运行状态中心：{error}"),
        )
    })?;
    ensure_window_visible(&window)?;
    Ok(())
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
struct PhysicalRect {
    x: i32,
    y: i32,
    width: u32,
    height: u32,
}

fn ensure_window_visible(window: &tauri::WebviewWindow) -> Result<(), RuntimeFailure> {
    if window.is_maximized().unwrap_or(false) || window.is_fullscreen().unwrap_or(false) {
        return Ok(());
    }
    let position = window.outer_position().map_err(|error| {
        RuntimeFailure::new(
            "interface",
            "WINDOW_POSITION_UNAVAILABLE",
            format!("无法读取窗口位置：{error}"),
        )
    })?;
    let size = window.outer_size().map_err(|error| {
        RuntimeFailure::new(
            "interface",
            "WINDOW_SIZE_UNAVAILABLE",
            format!("无法读取窗口大小：{error}"),
        )
    })?;
    let mut monitors = Vec::new();
    if let Ok(Some(monitor)) = window.primary_monitor() {
        monitors.push(PhysicalRect {
            x: monitor.position().x,
            y: monitor.position().y,
            width: monitor.size().width,
            height: monitor.size().height,
        });
    }
    for monitor in window.available_monitors().unwrap_or_default() {
        let candidate = PhysicalRect {
            x: monitor.position().x,
            y: monitor.position().y,
            width: monitor.size().width,
            height: monitor.size().height,
        };
        if !monitors.contains(&candidate) {
            monitors.push(candidate);
        }
    }
    let Some(adjusted) = constrain_to_visible_monitor(
        PhysicalRect {
            x: position.x,
            y: position.y,
            width: size.width,
            height: size.height,
        },
        &monitors,
    ) else {
        return Ok(());
    };
    if adjusted.width != size.width || adjusted.height != size.height {
        window
            .set_size(PhysicalSize::new(adjusted.width, adjusted.height))
            .map_err(|error| {
                RuntimeFailure::new(
                    "interface",
                    "WINDOW_VISIBLE_SIZE_FAILED",
                    format!("无法将窗口大小恢复到可见显示器：{error}"),
                )
            })?;
    }
    if adjusted.x != position.x || adjusted.y != position.y {
        window
            .set_position(PhysicalPosition::new(adjusted.x, adjusted.y))
            .map_err(|error| {
                RuntimeFailure::new(
                    "interface",
                    "WINDOW_VISIBLE_POSITION_FAILED",
                    format!("无法将窗口位置恢复到可见显示器：{error}"),
                )
            })?;
    }
    Ok(())
}

fn constrain_to_visible_monitor(
    window: PhysicalRect,
    monitors: &[PhysicalRect],
) -> Option<PhysicalRect> {
    if monitors.is_empty() {
        return None;
    }
    if monitors.iter().any(|monitor| contains_rect(*monitor, window)) {
        return Some(window);
    }
    let target = monitors
        .iter()
        .copied()
        .max_by_key(|monitor| intersection_area(*monitor, window))
        .unwrap_or(monitors[0]);
    let width = window.width.min(target.width.saturating_sub(32).max(1));
    let height = window.height.min(target.height.saturating_sub(64).max(1));
    let maximum_x = i64::from(target.x) + i64::from(target.width) - i64::from(width);
    let maximum_y = i64::from(target.y) + i64::from(target.height) - i64::from(height);
    let intersects = intersection_area(target, window) > 0;
    let x = if intersects {
        i64::from(window.x).clamp(i64::from(target.x), maximum_x)
    } else {
        i64::from(target.x) + (i64::from(target.width) - i64::from(width)) / 2
    };
    let y = if intersects {
        i64::from(window.y).clamp(i64::from(target.y), maximum_y)
    } else {
        i64::from(target.y) + (i64::from(target.height) - i64::from(height)) / 2
    };
    Some(PhysicalRect {
        x: x as i32,
        y: y as i32,
        width,
        height,
    })
}

fn contains_rect(container: PhysicalRect, candidate: PhysicalRect) -> bool {
    i64::from(candidate.x) >= i64::from(container.x)
        && i64::from(candidate.y) >= i64::from(container.y)
        && i64::from(candidate.x) + i64::from(candidate.width)
            <= i64::from(container.x) + i64::from(container.width)
        && i64::from(candidate.y) + i64::from(candidate.height)
            <= i64::from(container.y) + i64::from(container.height)
}

fn intersection_area(left: PhysicalRect, right: PhysicalRect) -> u64 {
    let x_overlap = (i64::from(left.x) + i64::from(left.width))
        .min(i64::from(right.x) + i64::from(right.width))
        - i64::from(left.x).max(i64::from(right.x));
    let y_overlap = (i64::from(left.y) + i64::from(left.height))
        .min(i64::from(right.y) + i64::from(right.height))
        - i64::from(left.y).max(i64::from(right.y));
    x_overlap.max(0) as u64 * y_overlap.max(0) as u64
}

fn hide_main_window(app: &tauri::AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.hide();
    }
}

fn request_full_exit(app: tauri::AppHandle) {
    let state = app.state::<DesktopState>();
    if state.quitting.swap(true, Ordering::SeqCst) {
        return;
    }
    let supervisor = Arc::clone(&state.supervisor);
    std::thread::spawn(move || {
        let result = supervisor.stop(|snapshot| {
            let _ = app.emit("runtime://snapshot", snapshot);
        });
        let exit_code = if matches!(result.state, runtime::RuntimeState::Stopped) {
            0
        } else {
            1
        };
        app.exit(exit_code);
    });
}

fn request_integration_cleanup_and_exit(app: tauri::AppHandle) {
    if let Err(error) = unregister_desktop_integrations() {
        eprintln!("Jarvis desktop integration cleanup failed: {error}");
        app.exit(1);
        return;
    }
    app.exit(0);
}

fn install_tray(app: &tauri::App) -> tauri::Result<()> {
    let show = MenuItem::with_id(app, "show", "显示 Jarvis", true, None::<&str>)?;
    let quick = MenuItem::with_id(app, "quick", "快速提问", true, None::<&str>)?;
    let status = MenuItem::with_id(app, "status", "运行状态", true, None::<&str>)?;
    let pause_reminders =
        MenuItem::with_id(app, "pause_reminders", "暂停提醒 1 小时", true, None::<&str>)?;
    let resume_reminders =
        MenuItem::with_id(app, "resume_reminders", "恢复提醒", true, None::<&str>)?;
    let autostart = CheckMenuItem::with_id(
        app,
        "autostart",
        "开机启动",
        true,
        autostart_enabled().unwrap_or(false),
        None::<&str>,
    )?;
    let quit = MenuItem::with_id(app, "quit", "完全退出", true, None::<&str>)?;
    let menu = Menu::with_items(
        app,
        &[
            &show,
            &quick,
            &status,
            &pause_reminders,
            &resume_reminders,
            &autostart,
            &quit,
        ],
    )?;
    let autostart_menu = autostart.clone();
    let mut builder = TrayIconBuilder::with_id("jarvis-main")
        .menu(&menu)
        .show_menu_on_left_click(false)
        .tooltip("Jarvis OS")
        .on_menu_event(move |app, event| match event.id.as_ref() {
            "show" => focus_existing(app),
            "quick" => {
                let _ = show_quick_window(app);
            }
            "status" => {
                let _ = show_status_window(app);
            }
            "pause_reminders" => set_reminder_pause(app.clone(), true),
            "resume_reminders" => set_reminder_pause(app.clone(), false),
            "autostart" => {
                let enabled = autostart_menu.is_checked().unwrap_or(false);
                let result = set_autostart(enabled);
                if result.is_err() {
                    let _ = autostart_menu.set_checked(!enabled);
                }
            }
            "quit" => request_full_exit(app.clone()),
            _ => {}
        })
        .on_tray_icon_event(|tray, event| {
            if matches!(
                event,
                TrayIconEvent::Click {
                    button: MouseButton::Left,
                    button_state: MouseButtonState::Up,
                    ..
                }
            ) {
                focus_existing(tray.app_handle());
            }
        });
    if let Some(icon) = app.default_window_icon() {
        builder = builder.icon(icon.clone());
    }
    builder.build(app)?;
    app.manage(AutostartTrayItem(autostart));
    Ok(())
}

fn main() {
    let arguments = std::env::args().collect::<Vec<_>>();
    if let Some(index) = arguments.iter().position(|argument| argument == "--data-cleanup") {
        let result = arguments
            .get(index + 1)
            .ok_or_else(|| "数据清理进程缺少受控凭据路径。".to_owned())
            .and_then(|path| {
                let data_root = user_data_root()?;
                data_maintenance::run_cleanup_helper(std::path::Path::new(path), &data_root)
            });
        if let Err(error) = result {
            if let Some(path) = arguments.get(index + 1) {
                data_maintenance::record_cleanup_failure(std::path::Path::new(path), &error);
            }
            eprintln!("Jarvis data cleanup failed: {error}");
            std::process::exit(1);
        }
        return;
    }
    if let Some(index) = arguments.iter().position(|argument| argument == "--update-watchdog") {
        let result = arguments
            .get(index + 1)
            .ok_or_else(|| "更新监护进程缺少事务路径。".to_owned())
            .and_then(|path| run_update_watchdog(std::path::Path::new(path)));
        if let Err(error) = result {
            eprintln!("Jarvis update watchdog failed: {error}");
            std::process::exit(1);
        }
        return;
    }
    tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, args, _cwd| {
            if args.iter().any(|argument| argument == "--cleanup-integrations") {
                request_integration_cleanup_and_exit(app.clone());
            } else if args.iter().any(|argument| argument == "--quit") {
                request_full_exit(app.clone());
            } else if args.iter().any(|argument| argument == "--status") {
                let _ = show_status_window(app);
            } else if args.iter().any(|argument| argument == "--quick") {
                let _ = show_quick_window(app);
            } else if let Some(uri) = args.iter().find(|argument| argument.starts_with("jarvis://")) {
                let _ = handle_activation_uri(app, uri);
            } else if let Some(path) = activation_file_argument(&args) {
                if let Err(error) = queue_file_handoff(app, &path, "Windows 资源管理器") {
                    deliver_file_error(app, error);
                }
            } else {
                focus_existing(app);
            }
        }))
        .plugin(tauri_plugin_opener::init())
        .plugin(
            tauri_plugin_window_state::Builder::default()
                .with_denylist(&["splash"])
                .with_state_flags(
                    StateFlags::SIZE
                        | StateFlags::POSITION
                        | StateFlags::MAXIMIZED
                        | StateFlags::FULLSCREEN,
                )
                .build(),
        )
        .on_window_event(|window, event| {
            if window.label() == "main" {
                if let WindowEvent::DragDrop(DragDropEvent::Drop { paths, .. }) = event {
                    if paths.len() != 1 {
                        deliver_file_error(
                            window.app_handle(),
                            "一次只支持拖入一个 .md 或 .txt 文件。".to_owned(),
                        );
                    } else if let Err(error) =
                        queue_file_handoff(window.app_handle(), &paths[0], "拖入主窗口")
                    {
                        deliver_file_error(window.app_handle(), error);
                    }
                }
            }
            if matches!(window.label(), "main" | "status" | "quick") {
                if let WindowEvent::CloseRequested { api, .. } = event {
                    let quitting = window.state::<DesktopState>().quitting.load(Ordering::SeqCst);
                    if !quitting {
                        api.prevent_close();
                        if window.label() == "main" {
                            let should_quit = window
                                .state::<DesktopState>()
                                .config_store
                                .as_ref()
                                .and_then(|store| {
                                    store
                                        .preference_string("DESKTOP_CLOSE_BEHAVIOR", "hide")
                                        .ok()
                                })
                                .is_some_and(|behavior| behavior == "quit");
                            if should_quit {
                                request_full_exit(window.app_handle().clone());
                            } else {
                                let should_explain = window
                                    .state::<DesktopState>()
                                    .config_store
                                    .as_ref()
                                    .and_then(|store| {
                                        store
                                            .preference_bool("DESKTOP_CLOSE_HINT_SHOWN", false)
                                            .ok()
                                            .map(|shown| !shown)
                                    })
                                    .unwrap_or(false);
                                if should_explain {
                                    if let Some(store) =
                                        window.state::<DesktopState>().config_store.as_ref()
                                    {
                                        let _ = store.set_preference_bool(
                                            "DESKTOP_CLOSE_HINT_SHOWN",
                                            true,
                                        );
                                    }
                                    if let Some(webview) =
                                        window.app_handle().get_webview_window("main")
                                    {
                                        let _ = webview.eval(
                                            "window.dispatchEvent(new Event('jarvis:close-hint'));",
                                        );
                                    }
                                    let _ = window.show();
                                    let _ = window.set_focus();
                                } else {
                                    hide_main_window(window.app_handle());
                                }
                            }
                        } else {
                            let _ = window.hide();
                        }
                    }
                }
            }
        })
        .setup(|app| {
            if std::env::args().any(|argument| argument == "--cleanup-integrations") {
                request_integration_cleanup_and_exit(app.handle().clone());
                return Ok(());
            }
            // `--quit` is normally delivered to the existing single instance.
            // When no instance is running it must remain a no-op instead of
            // launching the full desktop runtime and blocking maintenance.
            if std::env::args().any(|argument| argument == "--quit") {
                app.handle().exit(0);
                return Ok(());
            }
            let autostart_launch = std::env::args().any(|argument| argument == "--autostart");
            if autostart_launch {
                if let Some(splash) = app.get_webview_window("splash") {
                    let _ = splash.hide();
                }
            }
            let bundled_mode = BundledRuntimeAdapter::should_use();
            let config_store = if bundled_mode {
                DesktopConfigStore::discover().ok().map(Arc::new)
            } else {
                None
            };
            let setup_required = config_store
                .as_ref()
                .is_some_and(|store| store.status().first_run);
            if autostart_launch && setup_required {
                let _ = set_autostart(false);
                if let Some(splash) = app.get_webview_window("splash") {
                    let _ = splash.show();
                    let _ = splash.set_focus();
                }
            }
            let adapter: Box<dyn RuntimeAdapter> = if bundled_mode {
                match BundledRuntimeAdapter::discover() {
                    Ok(adapter) => Box::new(adapter),
                    Err(error) => Box::new(UnavailableAdapter::new(error.message)),
                }
            } else {
                match SourceRuntimeAdapter::discover() {
                    Ok(adapter) => Box::new(adapter),
                    Err(error) => Box::new(UnavailableAdapter::new(error.message)),
                }
            };
            let supervisor = Arc::new(RuntimeSupervisor::new(adapter));
            let update_channel = config_store
                .as_ref()
                .and_then(|store| store.preference_string("DESKTOP_UPDATE_CHANNEL", "beta").ok())
                .unwrap_or_else(|| "beta".to_owned());
            let updater = Arc::new(UpdateCoordinator::discover(&update_channel)?);
            let reliability = Arc::new(ReliabilityLedger::new(&user_data_root()?));
            let quitting = Arc::new(AtomicBool::new(false));
            let quick_shortcut_label = config_store
                .as_ref()
                .and_then(|store| store.preference_string("DESKTOP_QUICK_SHORTCUT", "Ctrl+Alt+Space").ok())
                .unwrap_or_else(|| "Ctrl+Alt+Space".to_owned());
            let voice_shortcut_label = config_store
                .as_ref()
                .and_then(|store| store.preference_string("DESKTOP_VOICE_SHORTCUT", "Ctrl+Alt+V").ok())
                .unwrap_or_else(|| "Ctrl+Alt+V".to_owned());
            let quick_shortcut = QuickShortcutController::start(
                app.handle().clone(),
                &quick_shortcut_label,
                &voice_shortcut_label,
            )?;
            let reliability_for_start = Arc::clone(&reliability);
            app.manage(DesktopState {
                supervisor: Arc::clone(&supervisor),
                config_store,
                quitting: Arc::clone(&quitting),
                pending_activation: Mutex::new(None),
                quick_shortcut,
                file_handoff: FileHandoffStore::default(),
                updater: Arc::clone(&updater),
                pending_data_deletion: Mutex::new(None),
                reliability: Arc::clone(&reliability),
            });
            install_tray(app)?;
                if let Err(error) = register_protocol_handler() {
                    eprintln!("Jarvis protocol registration unavailable: {error}");
                }
                let open_with = app
                    .state::<DesktopState>()
                    .config_store
                    .as_ref()
                    .and_then(|store| store.preference_bool("DESKTOP_OPEN_WITH_ENABLED", true).ok())
                    .unwrap_or(true);
                if let Err(error) = set_open_with_enabled(open_with) {
                    eprintln!("Jarvis Open With integration unavailable: {error}");
                }
            let quick_shortcut_enabled = app
                .state::<DesktopState>()
                .config_store
                .as_ref()
                .and_then(|store| {
                    store
                        .preference_bool("DESKTOP_QUICK_SHORTCUT_ENABLED", true)
                        .ok()
                })
                .unwrap_or(true);
            if quick_shortcut_enabled {
                if let Err(error) = app
                    .state::<DesktopState>()
                    .quick_shortcut
                    .set_quick_enabled(true)
                {
                    eprintln!("Jarvis quick shortcut unavailable: {error}");
                }
            }
            let voice_shortcut_enabled = app
                .state::<DesktopState>()
                .config_store
                .as_ref()
                .and_then(|store| store.preference_bool("DESKTOP_VOICE_SHORTCUT_ENABLED", false).ok())
                .unwrap_or(false);
            if voice_shortcut_enabled {
                if let Err(error) = app.state::<DesktopState>().quick_shortcut.set_voice_enabled(true) {
                    eprintln!("Jarvis voice shortcut unavailable: {error}");
                }
            }
            let launch_arguments = std::env::args().collect::<Vec<_>>();
            if let Some(uri) = launch_arguments.iter().find(|argument| argument.starts_with("jarvis://")) {
                let _ = handle_activation_uri(app.handle(), &uri);
            } else if let Some(path) = activation_file_argument(&launch_arguments) {
                if let Err(error) = queue_file_handoff(app.handle(), &path, "Windows 资源管理器") {
                    deliver_file_error(app.handle(), error);
                }
            }
            let handle = app.handle().clone();
            let post_update_transaction = launch_arguments
                .iter()
                .position(|argument| argument == "--post-update")
                .and_then(|index| launch_arguments.get(index + 1))
                .map(std::path::PathBuf::from);
            std::thread::spawn(move || {
                if !setup_required {
                    let initial = start_runtime(
                        handle.clone(),
                        Arc::clone(&supervisor),
                        Arc::clone(&reliability_for_start),
                        !autostart_launch,
                    );
                    let runtime_ready = matches!(
                        initial.state,
                        runtime::RuntimeState::Ready | runtime::RuntimeState::Degraded
                    );
                    if runtime_ready {
                        if autostart_launch {
                            if let Ok(root) = user_data_root() {
                                let _ = autostart_fuse::clear(&root);
                            }
                        }
                        if let Some(transaction) = post_update_transaction.as_deref() {
                            if let Err(error) = updater.mark_post_update_success(transaction) {
                                eprintln!("Jarvis post-update marker failed: {error}");
                            }
                        }
                    } else if autostart_launch {
                        let fuse_result = user_data_root()
                            .and_then(|root| autostart_fuse::record_failure(&root))
                            .map(|outcome| outcome.newly_tripped);
                        if !matches!(fuse_result, Ok(false)) {
                            let _ = set_autostart(false);
                            if let Some(splash) = handle.get_webview_window("splash") {
                                let _ = splash.show();
                                let _ = splash.set_focus();
                            }
                            let (message, code) = match fuse_result {
                                Ok(true) => (
                                    "连续三次登录启动失败，Jarvis 已自动关闭开机启动。请修复依赖后在设置中重新启用。".to_owned(),
                                    "AUTOSTART_CIRCUIT_OPEN",
                                ),
                                Err(error) => (
                                    format!("开机启动安全记录不可用，Jarvis 已按安全策略关闭开机启动：{error}"),
                                    "AUTOSTART_FUSE_INVALID",
                                ),
                                Ok(false) => unreachable!(),
                            };
                            let _ = handle.emit(
                                "runtime://snapshot",
                                RuntimeSnapshot::blocked(
                                    "preflight",
                                    message,
                                    code,
                                ),
                            );
                        }
                    }
                }
                while !quitting.load(Ordering::SeqCst) {
                    std::thread::sleep(Duration::from_secs(5));
                    if quitting.load(Ordering::SeqCst) {
                        break;
                    }
                    let mut recovery_published = false;
                    let recovery = supervisor.recover_if_needed(|snapshot| {
                        recovery_published = true;
                        let _ = handle.emit("runtime://snapshot", snapshot);
                    });
                    if recovery_published {
                        record_reliability(
                            &reliability_for_start,
                            ReliabilityEventKind::SupervisorState,
                            runtime_outcome(&recovery.state),
                            None,
                            None,
                        );
                    }
                }
            });
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            desktop_config_status,
            desktop_config_preview,
            desktop_config_apply,
            desktop_config_cancel,
            desktop_config_complete,
            desktop_preferences,
            desktop_set_autostart,
            desktop_set_quick_shortcut,
            desktop_set_voice_shortcut,
            desktop_set_close_behavior,
            desktop_set_open_with,
            desktop_set_shortcut_binding,
            desktop_open_microphone_settings,
            desktop_update_status,
            desktop_update_set_channel,
            desktop_update_set_activity,
            desktop_update_check,
            desktop_update_download,
            desktop_update_install,
            desktop_export_user_data,
            desktop_delete_user_data,
            desktop_record_reliability_event,
            desktop_file_read,
            desktop_file_cancel,
            quick_hide,
            quick_continue_in_main,
            runtime_status,
            runtime_start,
            runtime_stop,
            runtime_diagnostics,
            runtime_restart_core,
            runtime_open_logs,
            runtime_export_diagnostics
        ])
        .run(tauri::generate_context!())
        .expect("failed to run Jarvis OS desktop shell");
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn desktop_url_is_restricted_to_bundled_app_origin() {
        assert!(is_allowed_app_url(
            &"http://tauri.localhost/chat/".parse().unwrap()
        ));
        assert!(is_allowed_app_url(
            &"tauri://localhost/chat/".parse().unwrap()
        ));
        assert!(!is_allowed_app_url(
            &"https://example.com/chat".parse().unwrap()
        ));
        assert!(!is_allowed_app_url(
            &"http://127.0.0.1:3000/chat".parse().unwrap()
        ));
    }

    #[test]
    fn notification_activation_accepts_only_closed_routes() {
        let notification_id = "7a04664f-3780-4c6a-8e31-0d5fd19acbd4";
        let action_id = "390862ab-06cb-4a10-978b-577910213d79";
        assert_eq!(
            activation_detail(&format!("jarvis://notification/{notification_id}"))
                .unwrap()["kind"],
            "notification"
        );
        assert_eq!(
            activation_detail(&format!(
                "jarvis://notification/{notification_id}/snooze/10?action={action_id}"
            ))
            .unwrap()["actionId"],
            action_id
        );
        assert!(activation_detail("https://example.com/private").is_err());
        assert!(activation_detail(&format!(
            "jarvis://notification/{notification_id}?next=https://example.com"
        ))
        .is_err());
        assert!(activation_detail(&format!(
            "jarvis://notification/{notification_id}/snooze/20?action={action_id}"
        ))
        .is_err());
        assert!(activation_detail(&format!(
            "jarvis://notification/{notification_id}/snooze/10?action={action_id}&extra=1"
        ))
        .is_err());
    }

    #[test]
    fn window_bounds_remain_fully_visible_after_monitor_changes() {
        let primary = PhysicalRect {
            x: 0,
            y: 0,
            width: 1920,
            height: 1080,
        };
        let removed_monitor_position = PhysicalRect {
            x: 2400,
            y: 200,
            width: 1440,
            height: 900,
        };
        assert_eq!(
            constrain_to_visible_monitor(removed_monitor_position, &[primary]),
            Some(PhysicalRect {
                x: 240,
                y: 90,
                width: 1440,
                height: 900,
            })
        );
        let partially_visible = PhysicalRect {
            x: 1800,
            y: 900,
            width: 800,
            height: 600,
        };
        assert_eq!(
            constrain_to_visible_monitor(partially_visible, &[primary]),
            Some(PhysicalRect {
                x: 1120,
                y: 480,
                width: 800,
                height: 600,
            })
        );
        assert_eq!(
            constrain_to_visible_monitor(primary, &[primary]),
            Some(primary)
        );
    }
}
