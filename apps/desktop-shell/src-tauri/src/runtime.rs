use serde::{Deserialize, Serialize};
use rand::RngCore;
use crate::config_store::{load_bundled_environment, user_data_root};
use std::collections::HashMap;
use std::env;
use std::fs::{self, File, OpenOptions};
use std::io::{Read, Write};
use std::net::{IpAddr, Ipv4Addr, SocketAddr, TcpListener, TcpStream};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

#[cfg(windows)]
use std::os::windows::process::CommandExt;

const CREATE_NO_WINDOW: u32 = 0x0800_0000;

fn run_update_backup_gate(
    backup_root: &Path,
    backup_script: &Path,
    verify_script: &Path,
    wrapper: &Path,
    working_directory: &Path,
) -> Result<PathBuf, RuntimeFailure> {
    for path in [backup_script, verify_script, wrapper] {
        if !path.is_file() {
            return Err(RuntimeFailure::new(
                "update",
                "UPDATE_BACKUP_SCRIPT_MISSING",
                format!("更新备份门禁缺少受控脚本：{}", path.display()),
            ));
        }
    }
    fs::create_dir_all(backup_root).map_err(|error| {
        RuntimeFailure::new(
            "update",
            "UPDATE_BACKUP_DIRECTORY_FAILED",
            format!("无法创建更新备份目录：{error}"),
        )
    })?;
    let mut command = Command::new("powershell.exe");
    command
        .args(["-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File"])
        .arg(wrapper)
        .arg("-BackupDirectory")
        .arg(backup_root)
        .arg("-BackupScript")
        .arg(backup_script)
        .arg("-VerifyScript")
        .arg(verify_script)
        .current_dir(working_directory)
        .stdin(Stdio::null())
        .stderr(Stdio::piped())
        .stdout(Stdio::piped());
    #[cfg(windows)]
    command.creation_flags(CREATE_NO_WINDOW);
    let output = command.output().map_err(|error| {
        RuntimeFailure::new(
            "update",
            "UPDATE_BACKUP_START_FAILED",
            format!("无法启动数据库备份与恢复验证：{error}"),
        )
    })?;
    if !output.status.success() {
        return Err(RuntimeFailure::new(
            "update",
            "UPDATE_BACKUP_VERIFY_FAILED",
            format!(
                "更新前数据库恢复验证失败（{}）。详细错误只保留在受控备份流程中。",
                output.status
            ),
        ));
    }
    let manifest = String::from_utf8_lossy(&output.stdout)
        .lines()
        .map(str::trim)
        .filter(|line| line.to_ascii_lowercase().ends_with(".manifest.json"))
        .last()
        .map(PathBuf::from)
        .ok_or_else(|| {
            RuntimeFailure::new(
                "update",
                "UPDATE_BACKUP_EVIDENCE_MISSING",
                "更新备份已返回成功，但没有恢复验证清单。",
            )
        })?;
    let canonical_root = backup_root.canonicalize().map_err(|error| {
        RuntimeFailure::new("update", "UPDATE_BACKUP_ROOT_INVALID", error.to_string())
    })?;
    let canonical_manifest = manifest.canonicalize().map_err(|error| {
        RuntimeFailure::new("update", "UPDATE_BACKUP_MANIFEST_INVALID", error.to_string())
    })?;
    if !canonical_manifest.starts_with(&canonical_root) {
        return Err(RuntimeFailure::new(
            "update",
            "UPDATE_BACKUP_PATH_ESCAPE",
            "更新备份证据路径越出受控目录。",
        ));
    }
    Ok(canonical_manifest)
}

#[cfg(windows)]
use windows::Win32::{
    Foundation::{CloseHandle, HANDLE},
    System::JobObjects::{
        AssignProcessToJobObject, CreateJobObjectW, JobObjectExtendedLimitInformation,
        SetInformationJobObject, JOBOBJECT_EXTENDED_LIMIT_INFORMATION,
        JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
    },
};

#[derive(Clone, Debug, PartialEq, Deserialize, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum RuntimeState {
    Idle,
    Starting,
    Ready,
    #[allow(dead_code)]
    Degraded,
    Blocked,
    Stopping,
    Stopped,
}

#[derive(Clone, Debug, PartialEq, Deserialize, Serialize)]
pub struct RuntimeSnapshot {
    pub state: RuntimeState,
    pub stage: String,
    pub title: String,
    pub message: String,
    pub error_code: Option<String>,
    pub changed_at_ms: u128,
}

#[derive(Clone, Debug, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct RuntimeConnection {
    pub api_base_url: String,
    pub session_token: Option<String>,
    pub runtime_mode: String,
    pub app_version: String,
}

#[derive(Clone, Debug, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ComponentState {
    Ready,
    Degraded,
    Blocked,
    #[allow(dead_code)]
    Stopped,
    NotConfigured,
}

#[derive(Clone, Debug, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ComponentRequirement {
    Required,
    Optional,
}

#[derive(Clone, Debug, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ComponentOwnership {
    App,
    External,
}

#[derive(Clone, Debug, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct RuntimeComponent {
    pub id: String,
    pub name: String,
    pub state: ComponentState,
    pub requirement: ComponentRequirement,
    pub ownership: ComponentOwnership,
    pub version: Option<String>,
    pub detail: String,
    pub recovery: Option<String>,
    pub checked_at_ms: u128,
}

#[derive(Clone, Debug, PartialEq, Deserialize)]
struct VoiceReadiness {
    enabled: bool,
    stt_ready: bool,
    tts_ready: bool,
    reason: Option<String>,
}

#[derive(Clone, Debug, Default, PartialEq, Deserialize, Serialize)]
#[serde(rename_all = "snake_case")]
pub struct ReleaseInfo {
    pub app_version: String,
    pub git_sha: String,
    pub core_version: String,
    pub companion_version: String,
    pub schema_revision: String,
    pub build_time_utc: String,
    pub channel: String,
}

#[derive(Clone, Debug, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct DiagnosticLogFile {
    pub name: String,
    pub size_bytes: u64,
    pub modified_at_ms: u128,
}

#[derive(Clone, Debug, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct RuntimeDiagnostics {
    pub overall: RuntimeSnapshot,
    pub runtime_mode: String,
    pub app_version: String,
    pub generated_at_ms: u128,
    pub components: Vec<RuntimeComponent>,
    pub log_directory: String,
    pub data_directory: String,
    pub release: Option<ReleaseInfo>,
    pub log_files: Vec<DiagnosticLogFile>,
}

#[derive(Clone, Debug, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct DiagnosticBundleRef {
    pub path: String,
    pub generated_at_ms: u128,
    pub redacted: bool,
    pub entries: Vec<String>,
}

impl RuntimeSnapshot {
    fn new(state: RuntimeState, stage: &str, title: &str, message: &str) -> Self {
        Self {
            state,
            stage: stage.to_owned(),
            title: title.to_owned(),
            message: message.to_owned(),
            error_code: None,
            changed_at_ms: now_ms(),
        }
    }

    pub(crate) fn blocked(stage: &str, message: impl Into<String>, code: &str) -> Self {
        Self {
            state: RuntimeState::Blocked,
            stage: stage.to_owned(),
            title: "Jarvis 暂时无法启动".to_owned(),
            message: message.into(),
            error_code: Some(code.to_owned()),
            changed_at_ms: now_ms(),
        }
    }

}

fn converged_snapshot(
    diagnostics: RuntimeDiagnostics,
    ready: RuntimeSnapshot,
) -> RuntimeSnapshot {
    if diagnostics.components.iter().any(|item| {
        item.requirement == ComponentRequirement::Optional
            && matches!(item.state, ComponentState::Degraded | ComponentState::Blocked)
    }) {
        RuntimeSnapshot::new(
            RuntimeState::Degraded,
            "interface",
            "Jarvis 已启动，部分可选能力降级",
            "核心工作台可用；可在运行状态中查看降级原因。",
        )
    } else {
        ready
    }
}

pub trait RuntimeAdapter: Send + Sync + 'static {
    fn start(&self, publish: &mut dyn FnMut(RuntimeSnapshot)) -> Result<(), RuntimeFailure>;
    fn stop(&self) -> Result<(), RuntimeFailure>;
    fn is_ready(&self) -> bool;
    fn connection(&self) -> Option<RuntimeConnection>;
    fn diagnostics(&self, overall: RuntimeSnapshot) -> RuntimeDiagnostics;
    fn restart_core(
        &self,
        publish: &mut dyn FnMut(RuntimeSnapshot),
    ) -> Result<(), RuntimeFailure>;
    fn prepare_update_backup(&self) -> Result<PathBuf, RuntimeFailure> {
        Err(RuntimeFailure::new(
            "update",
            "UPDATE_BACKUP_UNAVAILABLE",
            "当前运行适配器不能执行更新前恢复验证。",
        ))
    }
    fn record_event(&self, _snapshot: &RuntimeSnapshot) {}
    fn health_failure(&self) -> Option<RuntimeFailure> {
        (!self.is_ready()).then(|| {
            RuntimeFailure::new(
                "core",
                "CORE_HEALTH_LOST",
                "Jarvis Core 在运行期间失去健康响应。",
            )
        })
    }
}

impl<T: RuntimeAdapter + ?Sized> RuntimeAdapter for Box<T> {
    fn start(&self, publish: &mut dyn FnMut(RuntimeSnapshot)) -> Result<(), RuntimeFailure> {
        (**self).start(publish)
    }

    fn stop(&self) -> Result<(), RuntimeFailure> {
        (**self).stop()
    }

    fn is_ready(&self) -> bool {
        (**self).is_ready()
    }

    fn connection(&self) -> Option<RuntimeConnection> {
        (**self).connection()
    }

    fn diagnostics(&self, overall: RuntimeSnapshot) -> RuntimeDiagnostics {
        (**self).diagnostics(overall)
    }

    fn restart_core(
        &self,
        publish: &mut dyn FnMut(RuntimeSnapshot),
    ) -> Result<(), RuntimeFailure> {
        (**self).restart_core(publish)
    }

    fn prepare_update_backup(&self) -> Result<PathBuf, RuntimeFailure> {
        (**self).prepare_update_backup()
    }

    fn record_event(&self, snapshot: &RuntimeSnapshot) {
        (**self).record_event(snapshot)
    }


    fn health_failure(&self) -> Option<RuntimeFailure> {
        (**self).health_failure()
    }
}

#[derive(Debug)]
pub struct RuntimeFailure {
    pub stage: &'static str,
    pub code: &'static str,
    pub message: String,
}

impl RuntimeFailure {
    pub fn new(stage: &'static str, code: &'static str, message: impl Into<String>) -> Self {
        Self {
            stage,
            code,
            message: message.into(),
        }
    }
}

pub struct RuntimeSupervisor<A: RuntimeAdapter> {
    adapter: Arc<A>,
    snapshot: Arc<Mutex<RuntimeSnapshot>>,
    transition_in_flight: Arc<AtomicBool>,
    recovery_attempts: Arc<Mutex<Vec<Instant>>>,
}

impl<A: RuntimeAdapter> Clone for RuntimeSupervisor<A> {
    fn clone(&self) -> Self {
        Self {
            adapter: Arc::clone(&self.adapter),
            snapshot: Arc::clone(&self.snapshot),
            transition_in_flight: Arc::clone(&self.transition_in_flight),
            recovery_attempts: Arc::clone(&self.recovery_attempts),
        }
    }
}

impl<A: RuntimeAdapter> RuntimeSupervisor<A> {
    pub fn new(adapter: A) -> Self {
        Self {
            adapter: Arc::new(adapter),
            snapshot: Arc::new(Mutex::new(RuntimeSnapshot::new(
                RuntimeState::Idle,
                "preflight",
                "等待启动",
                "Jarvis 桌面运行时尚未启动。",
            ))),
            transition_in_flight: Arc::new(AtomicBool::new(false)),
            recovery_attempts: Arc::new(Mutex::new(Vec::new())),
        }
    }

    pub fn status(&self) -> RuntimeSnapshot {
        let mut snapshot = self.snapshot.lock().expect("runtime snapshot poisoned");
        if !self.transition_in_flight.load(Ordering::SeqCst)
            && matches!(snapshot.state, RuntimeState::Ready | RuntimeState::Degraded)
            && !self.adapter.is_ready()
        {
            let failure = self.adapter.health_failure().unwrap_or_else(|| {
                RuntimeFailure::new(
                    "core",
                    "RUNTIME_HEALTH_LOST",
                    "运行记录仍在，但 Core 或 Companion 已不可用。",
                )
            });
            *snapshot = RuntimeSnapshot::blocked(failure.stage, failure.message, failure.code);
        }
        snapshot.clone()
    }

    pub fn prepare_update_backup(&self) -> Result<PathBuf, RuntimeFailure> {
        self.adapter.prepare_update_backup()
    }

    pub fn connection(&self) -> Option<RuntimeConnection> {
        self.adapter.connection()
    }

    pub fn diagnostics(&self) -> RuntimeDiagnostics {
        self.adapter.diagnostics(self.status())
    }

    pub fn export_diagnostics(&self) -> Result<DiagnosticBundleRef, RuntimeFailure> {
        export_diagnostic_bundle(&self.diagnostics(), self.adapter.connection().as_ref())
    }

    pub fn start<F>(&self, mut publish: F) -> RuntimeSnapshot
    where
        F: FnMut(RuntimeSnapshot),
    {
        if self
            .transition_in_flight
            .compare_exchange(false, true, Ordering::SeqCst, Ordering::SeqCst)
            .is_err()
        {
            return self.status();
        }

        self.set_and_publish(
            RuntimeSnapshot::new(
                RuntimeState::Starting,
                "preflight",
                "正在检查运行环境",
                "确认仓库、PowerShell 与现有 Jarvis 启动入口。",
            ),
            &mut publish,
        );

        let result = self.adapter.start(&mut |snapshot| {
            self.set_and_publish(snapshot, &mut publish);
        });

        let final_snapshot = match result {
            Ok(()) if self.adapter.is_ready() => {
                let ready = RuntimeSnapshot::new(
                    RuntimeState::Ready,
                    "interface",
                    "Jarvis 已准备完成",
                    "正在打开对话双翼工作台。",
                );
                converged_snapshot(self.adapter.diagnostics(ready.clone()), ready)
            }
            Ok(()) => RuntimeSnapshot::blocked(
                "interface",
                "启动脚本已退出，但 Core 或对话工作台仍不可访问。",
                "RUNTIME_NOT_READY",
            ),
            Err(error) => RuntimeSnapshot::blocked(error.stage, error.message, error.code),
        };
        self.set_and_publish(final_snapshot.clone(), &mut publish);
        self.transition_in_flight.store(false, Ordering::SeqCst);
        final_snapshot
    }

    pub fn restart_core<F>(&self, mut publish: F) -> RuntimeSnapshot
    where
        F: FnMut(RuntimeSnapshot),
    {
        if self
            .transition_in_flight
            .compare_exchange(false, true, Ordering::SeqCst, Ordering::SeqCst)
            .is_err()
        {
            return self.status();
        }
        let starting = RuntimeSnapshot::new(
            RuntimeState::Starting,
            "core",
            "正在重启 Jarvis Core",
            "Supervisor 只会重启已验证归属的 Jarvis 进程。",
        );
        self.set_and_publish(starting, &mut publish);
        let result = self.adapter.restart_core(&mut |snapshot| {
            self.set_and_publish(snapshot, &mut publish);
        });
        let final_snapshot = match result {
            Ok(()) if self.adapter.is_ready() => {
                let ready = RuntimeSnapshot::new(
                    RuntimeState::Ready,
                    "interface",
                    "Jarvis Core 已恢复",
                    "健康检查通过，对话工作台可继续使用。",
                );
                converged_snapshot(self.adapter.diagnostics(ready.clone()), ready)
            }
            Ok(()) => RuntimeSnapshot::blocked(
                "core",
                "Core 重启完成，但就绪检查未通过。",
                "CORE_RESTART_NOT_READY",
            ),
            Err(error) => RuntimeSnapshot::blocked(error.stage, error.message, error.code),
        };
        self.set_and_publish(final_snapshot.clone(), &mut publish);
        self.transition_in_flight.store(false, Ordering::SeqCst);
        final_snapshot
    }

    pub fn recover_if_needed<F>(&self, mut publish: F) -> RuntimeSnapshot
    where
        F: FnMut(RuntimeSnapshot),
    {
        let snapshot = self.status();
        if !matches!(snapshot.state, RuntimeState::Ready | RuntimeState::Degraded | RuntimeState::Blocked) {
            return snapshot;
        }
        let Some(failure) = self.adapter.health_failure() else {
            return snapshot;
        };
        let failure_snapshot = RuntimeSnapshot::blocked(failure.stage, failure.message, failure.code);
        self.set_and_publish(failure_snapshot, &mut publish);
        let attempt = {
            let mut attempts = self.recovery_attempts.lock().expect("recovery attempts poisoned");
            attempts.retain(|item| item.elapsed() < Duration::from_secs(300));
            if attempts.len() >= 3 {
                let limited = RuntimeSnapshot::blocked(
                    "core",
                    "Jarvis Core 在 5 分钟内已连续恢复 3 次，Supervisor 已停止自动重启。",
                    "CORE_RESTART_LIMIT_REACHED",
                );
                self.set_and_publish(limited.clone(), &mut publish);
                return limited;
            }
            attempts.push(Instant::now());
            attempts.len()
        };
        std::thread::sleep(Duration::from_millis(250 * (1_u64 << (attempt - 1))));
        self.restart_core(publish)
    }

    pub fn stop<F>(&self, mut publish: F) -> RuntimeSnapshot
    where
        F: FnMut(RuntimeSnapshot),
    {
        if self
            .transition_in_flight
            .compare_exchange(false, true, Ordering::SeqCst, Ordering::SeqCst)
            .is_err()
        {
            return self.status();
        }
        self.set_and_publish(
            RuntimeSnapshot::new(
                RuntimeState::Stopping,
                "interface",
                "正在完全退出",
                "只停止 Jarvis 记录并验证归属的源码运行时。",
            ),
            &mut publish,
        );
        let final_snapshot = match self.adapter.stop() {
            Ok(()) => RuntimeSnapshot::new(
                RuntimeState::Stopped,
                "preflight",
                "Jarvis 已完全退出",
                "数据库、Docker Desktop 和 Ollama 保持原有状态。",
            ),
            Err(error) => RuntimeSnapshot::blocked(error.stage, error.message, error.code),
        };
        self.set_and_publish(final_snapshot.clone(), &mut publish);
        self.transition_in_flight.store(false, Ordering::SeqCst);
        final_snapshot
    }

    pub fn record_failure<F>(&self, error: RuntimeFailure, mut publish: F) -> RuntimeSnapshot
    where
        F: FnMut(RuntimeSnapshot),
    {
        let snapshot = RuntimeSnapshot::blocked(error.stage, error.message, error.code);
        self.set_and_publish(snapshot.clone(), &mut publish);
        snapshot
    }

    fn set_and_publish<F>(&self, snapshot: RuntimeSnapshot, publish: &mut F)
    where
        F: FnMut(RuntimeSnapshot),
    {
        *self.snapshot.lock().expect("runtime snapshot poisoned") = snapshot.clone();
        self.adapter.record_event(&snapshot);
        publish(snapshot);
    }
}

pub struct SourceRuntimeAdapter {
    project_root: PathBuf,
    timeout: Duration,
}

impl SourceRuntimeAdapter {
    pub fn discover() -> Result<Self, RuntimeFailure> {
        let project_root = env::var_os("JARVIS_PROJECT_ROOT")
            .map(PathBuf::from)
            .or_else(|| discover_project_root(env::current_dir().ok()?.as_path()))
            .ok_or_else(|| {
                RuntimeFailure::new(
                    "preflight",
                    "PROJECT_ROOT_NOT_FOUND",
                    "找不到 Jarvis 仓库。请设置 JARVIS_PROJECT_ROOT 后重试。",
                )
            })?;
        let timeout_seconds = env::var("JARVIS_DESKTOP_START_TIMEOUT_SECONDS")
            .ok()
            .and_then(|value| value.parse::<u64>().ok())
            .filter(|value| (30..=900).contains(value))
            .unwrap_or(240);
        Ok(Self {
            project_root,
            timeout: Duration::from_secs(timeout_seconds),
        })
    }

    fn script(&self, name: &str) -> PathBuf {
        self.project_root.join("scripts").join(name)
    }

    fn run_script(&self, script: &Path, arguments: &[&str]) -> Result<(), RuntimeFailure> {
        if !script.is_file() {
            return Err(RuntimeFailure::new(
                "preflight",
                "RUNTIME_SCRIPT_MISSING",
                format!("缺少受控启动脚本：{}", script.display()),
            ));
        }

        let log_path = self
            .project_root
            .join(".runtime")
            .join("desktop-source-adapter.log");
        let _ = fs::create_dir_all(log_path.parent().unwrap_or(&self.project_root));
        let stdout = OpenOptions::new()
            .create(true)
            .append(true)
            .open(&log_path)
            .map(Stdio::from)
            .unwrap_or_else(|_| Stdio::null());
        let stderr = OpenOptions::new()
            .create(true)
            .append(true)
            .open(&log_path)
            .map(Stdio::from)
            .unwrap_or_else(|_| Stdio::null());
        let mut command = Command::new("powershell.exe");
        command
            .args(["-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File"])
            .arg(script)
            .args(arguments)
            .current_dir(&self.project_root)
            .stdin(Stdio::null())
            .stdout(stdout)
            .stderr(stderr);
        if script.file_name().and_then(|name| name.to_str()) == Some("start.ps1") {
            command.env("JARVIS_DESKTOP_SHELL", "1");
            command.env("JARVIS_DESKTOP_STATIC_UI", "1");
        }
        #[cfg(windows)]
        command.creation_flags(CREATE_NO_WINDOW);

        let mut child = command.spawn().map_err(|error| {
            RuntimeFailure::new(
                "preflight",
                "POWERSHELL_START_FAILED",
                format!("无法启动受控 PowerShell Adapter：{error}"),
            )
        })?;
        let deadline = std::time::Instant::now() + self.timeout;
        loop {
            if let Some(status) = child.try_wait().map_err(|error| {
                RuntimeFailure::new(
                    "dependencies",
                    "SOURCE_RUNTIME_WAIT_FAILED",
                    format!("无法读取启动脚本状态：{error}"),
                )
            })? {
                return if status.success() {
                    Ok(())
                } else {
                    Err(RuntimeFailure::new(
                        "dependencies",
                        "SOURCE_RUNTIME_START_FAILED",
                        format!(
                            "源码启动 Adapter 以状态 {status} 退出。请查看 .runtime 日志。"
                        ),
                    ))
                };
            }
            if std::time::Instant::now() >= deadline {
                let _ = child.kill();
                return Err(RuntimeFailure::new(
                    "dependencies",
                    "SOURCE_RUNTIME_TIMEOUT",
                    format!("Jarvis 在 {} 秒内未完成启动。", self.timeout.as_secs()),
                ));
            }
            std::thread::sleep(Duration::from_millis(250));
        }
    }

    fn run_update_backup_gate(
        &self,
        backup_root: &Path,
        backup_script: &Path,
        verify_script: &Path,
        wrapper: &Path,
    ) -> Result<PathBuf, RuntimeFailure> {
        run_update_backup_gate(backup_root, backup_script, verify_script, wrapper, &self.project_root)
    }
}

impl RuntimeAdapter for SourceRuntimeAdapter {
    fn start(&self, publish: &mut dyn FnMut(RuntimeSnapshot)) -> Result<(), RuntimeFailure> {
        publish(RuntimeSnapshot::new(
            RuntimeState::Starting,
            "dependencies",
            "正在启动依赖与数据库",
            "复用现有受控源码启动入口；Docker 较慢时会继续等待。",
        ));
        self.run_script(&self.script("start.ps1"), &["-NoBrowser"])?;
        publish(RuntimeSnapshot::new(
            RuntimeState::Starting,
            "core",
            "正在确认 Jarvis Core",
            "检查本地 Core 与运行记录是否一致。",
        ));
        if !port_open(8000) {
            return Err(RuntimeFailure::new(
                "core",
                "CORE_NOT_LISTENING",
                "启动脚本完成，但 Jarvis Core 未监听受控本地端口。",
            ));
        }
        publish(RuntimeSnapshot::new(
            RuntimeState::Starting,
            "interface",
            "正在加载对话工作台",
            "确认 V3-4b 桌面资源与 Jarvis Core 已准备完成。",
        ));
        if !self
            .project_root
            .join("apps")
            .join("desktop-shell")
            .join("dist-ui")
            .join("chat")
            .join("index.html")
            .is_file()
        {
            return Err(RuntimeFailure::new(
                "interface",
                "STATIC_INTERFACE_MISSING",
                "Jarvis 桌面静态界面资源缺失，请重新构建桌面程序。",
            ));
        }
        Ok(())
    }

    fn stop(&self) -> Result<(), RuntimeFailure> {
        self.run_script(&self.script("stop.ps1"), &[])
    }

    fn is_ready(&self) -> bool {
        port_open(8000) && source_process_record(&self.project_root, "api_pid").is_some()
    }

    fn health_failure(&self) -> Option<RuntimeFailure> {
        if !self.project_root.join(".runtime").join("services.json").is_file() {
            return Some(RuntimeFailure::new(
                "core",
                "SOURCE_RUNTIME_RECORD_LOST",
                "源码运行记录已丢失，无法验证 Core 进程归属。",
            ));
        }
        if source_process_record(&self.project_root, "api_pid").is_none() {
            return Some(RuntimeFailure::new(
                "core",
                "CORE_PROCESS_OWNERSHIP_LOST",
                "8000 端口记录无法验证为 Jarvis Python Core，Supervisor 不会结束该进程。",
            ));
        }
        (!port_open(8000)).then(|| {
            RuntimeFailure::new(
                "core",
                "CORE_HEALTH_LOST",
                "Jarvis Core 在运行期间失去健康响应。",
            )
        })
    }

    fn connection(&self) -> Option<RuntimeConnection> {
        Some(RuntimeConnection {
            api_base_url: "http://127.0.0.1:8000/api/v1".to_owned(),
            session_token: None,
            runtime_mode: "source".to_owned(),
            app_version: env!("CARGO_PKG_VERSION").to_owned(),
        })
    }

    fn diagnostics(&self, overall: RuntimeSnapshot) -> RuntimeDiagnostics {
        let checked_at_ms = now_ms();
        let core_ready = port_open(8000);
        let postgres_ready = port_open(5433);
        let companion_ready = source_process_record(&self.project_root, "companion_pid").is_some();
        let ollama_ready = port_open(11434);
        let connection = self.connection().expect("source connection");
        let voice = probe_voice_readiness(&connection);
        let runtime_dir = self.project_root.join(".runtime");
        RuntimeDiagnostics {
            overall,
            runtime_mode: "source".to_owned(),
            app_version: env!("CARGO_PKG_VERSION").to_owned(),
            generated_at_ms: checked_at_ms,
            components: vec![
                app_component(checked_at_ms),
                component(
                    "postgres",
                    "PostgreSQL",
                    required_state(postgres_ready),
                    ComponentRequirement::Required,
                    ComponentOwnership::External,
                    None,
                    if postgres_ready { "数据库端口可达。" } else { "数据库端口不可达。" },
                    (!postgres_ready).then(|| "启动 Docker Desktop，再重新检查。".to_owned()),
                    checked_at_ms,
                ),
                component(
                    "core",
                    "Jarvis Core",
                    required_state(core_ready),
                    ComponentRequirement::Required,
                    ComponentOwnership::App,
                    Some("0.1.0".to_owned()),
                    if core_ready { "Core 就绪端口可达。" } else { "Core 就绪端口不可达。" },
                    (!core_ready).then(|| "从状态中心重启 Jarvis Core。".to_owned()),
                    checked_at_ms,
                ),
                component(
                    "companion",
                    "Companion",
                    required_state(companion_ready),
                    ComponentRequirement::Required,
                    ComponentOwnership::App,
                    Some("0.1.0".to_owned()),
                    if companion_ready { "受控 Companion 进程已记录。" } else { "未找到可验证的 Companion 进程记录。" },
                    (!companion_ready).then(|| "重启 Jarvis Core 运行组。".to_owned()),
                    checked_at_ms,
                ),
                component(
                    "ollama",
                    "Ollama",
                    optional_state(ollama_ready),
                    ComponentRequirement::Optional,
                    ComponentOwnership::External,
                    None,
                    if ollama_ready { "本地模型服务可达。" } else { "Ollama 未启动；云模型和其他能力仍可用。" },
                    (!ollama_ready).then(|| "需要本地模型时手动启动 Ollama。".to_owned()),
                    checked_at_ms,
                ),
                voice_component(voice, checked_at_ms),
                optional_worker_component(
                    "browser_worker",
                    "Browser Worker",
                    source_process_record(&self.project_root, "browser_worker_pid").is_some(),
                    checked_at_ms,
                ),
            ],
            log_directory: runtime_dir.display().to_string(),
            data_directory: self.project_root.display().to_string(),
            release: load_release_info(
                &self
                    .project_root
                    .join("apps")
                    .join("desktop-shell")
                    .join("resources")
                    .join("release-manifest.json"),
            ),
            log_files: list_log_metadata(&runtime_dir),
        }
    }

    fn restart_core(
        &self,
        publish: &mut dyn FnMut(RuntimeSnapshot),
    ) -> Result<(), RuntimeFailure> {
        publish(RuntimeSnapshot::new(
            RuntimeState::Starting,
            "core",
            "正在重启源码运行组",
            "源码适配器通过已审查的 stop.ps1 / start.ps1 收敛状态。",
        ));
        self.run_script(&self.script("stop.ps1"), &[])?;
        self.run_script(&self.script("start.ps1"), &["-NoBrowser"])
    }

    fn record_event(&self, snapshot: &RuntimeSnapshot) {
        append_structured_event(
            &self.project_root.join(".runtime").join("desktop-supervisor.jsonl"),
            snapshot,
        );
    }


    fn prepare_update_backup(&self) -> Result<PathBuf, RuntimeFailure> {
        let backup_root = user_data_root()
            .map_err(|message| RuntimeFailure::new("update", "UPDATE_DATA_ROOT_UNAVAILABLE", message))?
            .join("backups")
            .join(format!("update-{}", now_ms()));
        let wrapper = self
            .project_root
            .join("apps")
            .join("desktop-shell")
            .join("scripts")
            .join("desktop-update-backup.ps1");
        self.run_update_backup_gate(
            &backup_root,
            &self.project_root.join("scripts").join("backup.ps1"),
            &self.project_root.join("scripts").join("verify-backup.ps1"),
            &wrapper,
        )
    }
}

struct ManagedChild {
    role: String,
    child: Child,
}

pub struct BundledRuntimeAdapter {
    sidecar: PathBuf,
    compose_file: PathBuf,
    data_root: PathBuf,
    children: Mutex<Vec<ManagedChild>>,
    connection: Mutex<Option<RuntimeConnection>>,
    job: ManagedJob,
}

impl BundledRuntimeAdapter {
    pub fn discover() -> Result<Self, RuntimeFailure> {
        let executable = env::current_exe().map_err(|error| {
            RuntimeFailure::new(
                "preflight",
                "EXECUTABLE_PATH_UNAVAILABLE",
                format!("无法读取 Jarvis 安装路径：{error}"),
            )
        })?;
        let resources = env::var_os("JARVIS_BUNDLED_RESOURCES")
            .map(PathBuf::from)
            .unwrap_or_else(|| {
                executable
                    .parent()
                    .unwrap_or_else(|| Path::new("."))
                    .join("resources")
            });
        let sidecar = env::var_os("JARVIS_BUNDLED_SIDECAR")
            .map(PathBuf::from)
            .unwrap_or_else(|| resources.join("sidecar").join("jarvis-sidecar.exe"));
        let compose_file = env::var_os("JARVIS_BUNDLED_COMPOSE")
            .map(PathBuf::from)
            .unwrap_or_else(|| resources.join("infra").join("docker-compose.yml"));
        if !sidecar.is_file() {
            return Err(RuntimeFailure::new(
                "preflight",
                "BUNDLED_SIDECAR_MISSING",
                format!("安装包缺少 Jarvis Sidecar：{}", sidecar.display()),
            ));
        }
        if !compose_file.is_file() {
            return Err(RuntimeFailure::new(
                "preflight",
                "BUNDLED_COMPOSE_MISSING",
                format!("安装包缺少 PostgreSQL 清单：{}", compose_file.display()),
            ));
        }
        let data_root = user_data_root().map_err(|message| {
            RuntimeFailure::new("preflight", "LOCAL_APP_DATA_UNAVAILABLE", message)
        })?;
        for directory in ["config", "data", "runtime", "logs", "backups"] {
            fs::create_dir_all(data_root.join(directory)).map_err(|error| {
                RuntimeFailure::new(
                    "preflight",
                    "USER_DATA_DIRECTORY_FAILED",
                    format!("无法准备 Jarvis 用户目录 {directory}：{error}"),
                )
            })?;
        }
        Ok(Self {
            sidecar,
            compose_file,
            data_root,
            children: Mutex::new(Vec::new()),
            connection: Mutex::new(None),
            job: ManagedJob::new()?,
        })
    }

    pub fn should_use() -> bool {
        env::var("JARVIS_RUNTIME_MODE").ok().as_deref() == Some("bundled")
            || (!cfg!(debug_assertions) && env::var_os("JARVIS_PROJECT_ROOT").is_none())
    }

    fn environment(&self) -> Result<HashMap<String, String>, RuntimeFailure> {
        let mut environment = load_bundled_environment(&self.data_root).map_err(|message| {
            RuntimeFailure::new("preflight", "BUNDLED_CONFIG_READ_FAILED", message)
        })?;
        environment.insert(
            "WEB_ORIGINS".to_owned(),
            "http://tauri.localhost,https://tauri.localhost,tauri://localhost".to_owned(),
        );
        environment.insert("APP_ENV".to_owned(), "production".to_owned());
        environment.insert("PYTHONUTF8".to_owned(), "1".to_owned());
        Ok(environment)
    }

    fn command(&self, mode: &str, environment: &HashMap<String, String>) -> Command {
        let mut command = Command::new(&self.sidecar);
        command
            .arg(mode)
            .envs(environment)
            .current_dir(&self.data_root)
            .stdin(Stdio::null());
        #[cfg(windows)]
        command.creation_flags(CREATE_NO_WINDOW);
        command
    }

    fn run_migration(&self, environment: &HashMap<String, String>) -> Result<(), RuntimeFailure> {
        let log = self.log_file("migration.log")?;
        let error_log = self.log_file("migration-error.log")?;
        let status = self
            .command("migrate", environment)
            .stdout(Stdio::from(log))
            .stderr(Stdio::from(error_log))
            .status()
            .map_err(|error| {
                RuntimeFailure::new(
                    "migration",
                    "MIGRATION_PROCESS_FAILED",
                    format!("无法启动数据库迁移：{error}"),
                )
            })?;
        if status.success() {
            Ok(())
        } else {
            Err(RuntimeFailure::new(
                "migration",
                "MIGRATION_FAILED",
                format!(
                    "数据库迁移失败（{status}），已保留 {}。",
                    self.data_root.join("logs").join("migration-error.log").display()
                ),
            ))
        }
    }

    fn start_child(
        &self,
        mode: &str,
        arguments: &[&str],
        log_name: &str,
        environment: &HashMap<String, String>,
    ) -> Result<u32, RuntimeFailure> {
        let log = self.log_file(&format!("{log_name}.log"))?;
        let error_log = self.log_file(&format!("{log_name}-error.log"))?;
        let mut command = Command::new(&self.sidecar);
        command
            .arg(mode)
            .args(arguments)
            .envs(environment)
            .current_dir(&self.data_root)
            .stdin(Stdio::null())
            .stdout(Stdio::from(log))
            .stderr(Stdio::from(error_log));
        #[cfg(windows)]
        command.creation_flags(CREATE_NO_WINDOW);
        let child = command.spawn().map_err(|error| {
            RuntimeFailure::new(
                "core",
                "SIDECAR_START_FAILED",
                format!("无法启动 Jarvis {mode} Sidecar：{error}"),
            )
        })?;
        self.job.assign(child.id())?;
        let pid = child.id();
        self.children
            .lock()
            .expect("bundled children poisoned")
            .push(ManagedChild {
                role: mode.to_owned(),
                child,
            });
        Ok(pid)
    }

    fn log_file(&self, name: &str) -> Result<File, RuntimeFailure> {
        let path = self.data_root.join("logs").join(name);
        rotate_log_if_needed(&path, 5 * 1024 * 1024, 3);
        OpenOptions::new()
            .create(true)
            .append(true)
            .open(path)
            .map_err(|error| {
                RuntimeFailure::new(
                    "preflight",
                    "LOG_FILE_FAILED",
                    format!("无法打开 Jarvis 日志 {name}：{error}"),
                )
            })
    }

    fn ensure_database(&self, environment: &HashMap<String, String>) -> Result<(), RuntimeFailure> {
        let status = Command::new("docker.exe")
            .args(["compose", "-f"])
            .arg(&self.compose_file)
            .args(["up", "-d", "postgres"])
            .envs(environment)
            .creation_flags(CREATE_NO_WINDOW)
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status()
            .map_err(|error| {
                RuntimeFailure::new(
                    "dependencies",
                    "DOCKER_UNAVAILABLE",
                    format!("Docker Desktop 不可用：{error}"),
                )
            })?;
        if !status.success() {
            return Err(RuntimeFailure::new(
                "dependencies",
                "POSTGRES_START_FAILED",
                "无法启动 Jarvis PostgreSQL。请确认 Docker Desktop 已启动。",
            ));
        }
        wait_for_port(5433, Duration::from_secs(90)).map_err(|_| {
            RuntimeFailure::new(
                "dependencies",
                "POSTGRES_READY_TIMEOUT",
                "Jarvis PostgreSQL 在 90 秒内未准备完成。",
            )
        })
    }

    fn write_runtime_record(&self, api_pid: u32, companion_pid: u32, port: u16) -> Result<(), RuntimeFailure> {
        let record = serde_json::json!({
            "mode": "bundled",
            "api_pid": api_pid,
            "companion_pid": companion_pid,
            "api_port": port,
            "started_at_ms": now_ms(),
            "app_version": env!("CARGO_PKG_VERSION"),
        });
        let path = self.data_root.join("runtime").join("services.json");
        fs::write(path, serde_json::to_vec_pretty(&record).unwrap_or_default()).map_err(|error| {
            RuntimeFailure::new(
                "core",
                "RUNTIME_RECORD_FAILED",
                format!("无法写入安装态运行记录：{error}"),
            )
        })
    }
}

impl RuntimeAdapter for BundledRuntimeAdapter {
    fn start(&self, publish: &mut dyn FnMut(RuntimeSnapshot)) -> Result<(), RuntimeFailure> {
        if self.is_ready() {
            return Ok(());
        }
        let environment = self.environment()?;
        publish(RuntimeSnapshot::new(
            RuntimeState::Starting,
            "dependencies",
            "正在检查 PostgreSQL",
            "Docker Desktop 和 Jarvis PostgreSQL 是可见的外部依赖。",
        ));
        self.ensure_database(&environment)?;
        publish(RuntimeSnapshot::new(
            RuntimeState::Starting,
            "migration",
            "正在验证数据库版本",
            "迁移失败时不会进入主工作台。",
        ));
        self.run_migration(&environment)?;

        let port = reserve_loopback_port()?;
        let token = generate_session_token();
        let mut runtime_environment = environment;
        runtime_environment.insert("API_PORT".to_owned(), port.to_string());
        runtime_environment.insert("DESKTOP_SESSION_TOKEN".to_owned(), token.clone());
        let api_base_url = format!("http://127.0.0.1:{port}/api/v1");
        runtime_environment.insert("JARVIS_API_BASE_URL".to_owned(), api_base_url.clone());
        runtime_environment.insert("JARVIS_DASHBOARD_URL".to_owned(), "jarvis://notifications".to_owned());

        publish(RuntimeSnapshot::new(
            RuntimeState::Starting,
            "core",
            "正在启动 Jarvis Core",
            "Core 使用本次启动的受控端口与短会话凭证。",
        ));
        let api_pid = self.start_child("api", &[], "core", &runtime_environment)?;
        wait_for_http_health(port, &token, Duration::from_secs(45))?;
        let companion_pid = self.start_child(
            "companion",
            &["--no-tray"],
            "companion",
            &runtime_environment,
        )?;
        let connection = RuntimeConnection {
            api_base_url,
            session_token: Some(token),
            runtime_mode: "bundled".to_owned(),
            app_version: env!("CARGO_PKG_VERSION").to_owned(),
        };
        *self.connection.lock().expect("bundled connection poisoned") = Some(connection);
        self.write_runtime_record(api_pid, companion_pid, port)?;
        Ok(())
    }

    fn stop(&self) -> Result<(), RuntimeFailure> {
        let mut children = self.children.lock().expect("bundled children poisoned");
        for managed in children.iter_mut() {
            let _ = managed.child.kill();
            let _ = managed.child.wait();
        }
        children.clear();
        *self.connection.lock().expect("bundled connection poisoned") = None;
        let _ = fs::remove_file(self.data_root.join("runtime").join("services.json"));
        Ok(())
    }

    fn is_ready(&self) -> bool {
        let core_ready = self
            .connection()
            .as_ref()
            .and_then(connection_port)
            .is_some_and(port_open);
        let children_ready = self
            .children
            .lock()
            .expect("bundled children poisoned")
            .iter_mut()
            .filter(|managed| matches!(managed.role.as_str(), "api" | "companion"))
            .all(|managed| managed.child.try_wait().ok().flatten().is_none());
        core_ready && children_ready
    }

    fn health_failure(&self) -> Option<RuntimeFailure> {
        let connection = self.connection()?;
        let port = connection_port(&connection)?;
        if !port_open(port) {
            return Some(RuntimeFailure::new(
                "core",
                "CORE_HEALTH_LOST",
                "Jarvis Core 在运行期间失去健康响应。",
            ));
        }
        let companion_alive = self
            .children
            .lock()
            .expect("bundled children poisoned")
            .iter_mut()
            .find(|managed| managed.role == "companion")
            .is_some_and(|managed| managed.child.try_wait().ok().flatten().is_none());
        (!companion_alive).then(|| {
            RuntimeFailure::new(
                "core",
                "COMPANION_HEALTH_LOST",
                "Companion Worker 已退出，Supervisor 将恢复受控运行组。",
            )
        })
    }

    fn connection(&self) -> Option<RuntimeConnection> {
        self.connection.lock().expect("bundled connection poisoned").clone()
    }

    fn diagnostics(&self, overall: RuntimeSnapshot) -> RuntimeDiagnostics {
        let checked_at_ms = now_ms();
        let postgres_ready = port_open(5433);
        let ollama_ready = port_open(11434);
        let core_ready = self.is_ready();
        let voice = self
            .connection()
            .as_ref()
            .and_then(probe_voice_readiness);
        let process_states: HashMap<String, bool> = self
            .children
            .lock()
            .expect("bundled children poisoned")
            .iter_mut()
            .map(|managed| {
                let alive = managed.child.try_wait().ok().flatten().is_none();
                (managed.role.clone(), alive)
            })
            .collect();
        let release = load_release_info(&bundled_release_manifest_path(&self.sidecar));
        let core_version = release
            .as_ref()
            .map(|item| item.core_version.clone())
            .filter(|item| !item.is_empty());
        let companion_version = release
            .as_ref()
            .map(|item| item.companion_version.clone())
            .filter(|item| !item.is_empty());
        RuntimeDiagnostics {
            overall,
            runtime_mode: "bundled".to_owned(),
            app_version: env!("CARGO_PKG_VERSION").to_owned(),
            generated_at_ms: checked_at_ms,
            components: vec![
                app_component(checked_at_ms),
                component(
                    "postgres",
                    "PostgreSQL",
                    required_state(postgres_ready),
                    ComponentRequirement::Required,
                    ComponentOwnership::External,
                    None,
                    if postgres_ready { "Jarvis PostgreSQL 端口可达。" } else { "Jarvis PostgreSQL 端口不可达。" },
                    (!postgres_ready).then(|| "启动 Docker Desktop，再重新检查。".to_owned()),
                    checked_at_ms,
                ),
                voice_component(voice, checked_at_ms),
                component(
                    "core",
                    "Jarvis Core",
                    required_state(core_ready && process_states.get("api") == Some(&true)),
                    ComponentRequirement::Required,
                    ComponentOwnership::App,
                    core_version,
                    if core_ready { "带桌面会话凭证的就绪检查通过。" } else { "Core 进程或就绪端点不可用。" },
                    (!core_ready).then(|| "从状态中心重启 Jarvis Core。".to_owned()),
                    checked_at_ms,
                ),
                component(
                    "companion",
                    "Companion",
                    required_state(process_states.get("companion") == Some(&true)),
                    ComponentRequirement::Required,
                    ComponentOwnership::App,
                    companion_version,
                    if process_states.get("companion") == Some(&true) { "Companion Worker 由 Supervisor 持有。" } else { "Companion Worker 已退出或未启动。" },
                    (process_states.get("companion") != Some(&true)).then(|| "重启 Jarvis Core 运行组。".to_owned()),
                    checked_at_ms,
                ),
                component(
                    "ollama",
                    "Ollama",
                    optional_state(ollama_ready),
                    ComponentRequirement::Optional,
                    ComponentOwnership::External,
                    None,
                    if ollama_ready { "本地模型服务可达。" } else { "Ollama 未启动；不阻断核心工作台。" },
                    (!ollama_ready).then(|| "需要本地模型时手动启动 Ollama。".to_owned()),
                    checked_at_ms,
                ),
                component(
                    "browser_worker",
                    "Browser Worker",
                    ComponentState::NotConfigured,
                    ComponentRequirement::Optional,
                    ComponentOwnership::App,
                    None,
                    "安装态首发未启用 Browser Worker。".to_owned(),
                    None,
                    checked_at_ms,
                ),
            ],
            log_directory: self.data_root.join("logs").display().to_string(),
            data_directory: self.data_root.display().to_string(),
            release,
            log_files: list_log_metadata(&self.data_root.join("logs")),
        }
    }

    fn restart_core(
        &self,
        publish: &mut dyn FnMut(RuntimeSnapshot),
    ) -> Result<(), RuntimeFailure> {
        let existing_connection = self.connection();
        {
            let mut children = self.children.lock().expect("bundled children poisoned");
            for managed in children.iter_mut() {
                let _ = managed.child.kill();
                let _ = managed.child.wait();
            }
            children.clear();
        }
        *self.connection.lock().expect("bundled connection poisoned") = None;
        let _ = fs::remove_file(self.data_root.join("runtime").join("services.json"));
        publish(RuntimeSnapshot::new(
            RuntimeState::Starting,
            "core",
            "正在重建本次桌面会话",
            "将重新分配受控端口和短会话凭证。",
        ));
        let Some(connection) = existing_connection else {
            return self.start(publish);
        };
        let port = connection_port(&connection).ok_or_else(|| {
            RuntimeFailure::new(
                "core",
                "RUNTIME_CONNECTION_INVALID",
                "现有桌面连接不包含可恢复的本地端口。",
            )
        })?;
        let token = connection.session_token.clone().ok_or_else(|| {
            RuntimeFailure::new(
                "core",
                "RUNTIME_SESSION_MISSING",
                "安装态桌面连接缺少可恢复的短会话凭证。",
            )
        })?;
        let mut runtime_environment = self.environment()?;
        runtime_environment.insert("API_PORT".to_owned(), port.to_string());
        runtime_environment.insert("DESKTOP_SESSION_TOKEN".to_owned(), token.clone());
        runtime_environment.insert("JARVIS_API_BASE_URL".to_owned(), connection.api_base_url.clone());
        runtime_environment.insert("JARVIS_DASHBOARD_URL".to_owned(), "jarvis://notifications".to_owned());
        let api_pid = self.start_child("api", &[], "core", &runtime_environment)?;
        wait_for_http_health(port, &token, Duration::from_secs(45))?;
        let companion_pid = self.start_child(
            "companion",
            &["--no-tray"],
            "companion",
            &runtime_environment,
        )?;
        *self.connection.lock().expect("bundled connection poisoned") = Some(connection);
        self.write_runtime_record(api_pid, companion_pid, port)
    }

    fn record_event(&self, snapshot: &RuntimeSnapshot) {
        append_structured_event(
            &self.data_root.join("logs").join("desktop-supervisor.jsonl"),
            snapshot,
        );
    }


    fn prepare_update_backup(&self) -> Result<PathBuf, RuntimeFailure> {
        let executable = env::current_exe().map_err(|error| {
            RuntimeFailure::new("update", "UPDATE_EXECUTABLE_UNAVAILABLE", error.to_string())
        })?;
        let resources = env::var_os("JARVIS_BUNDLED_RESOURCES")
            .map(PathBuf::from)
            .unwrap_or_else(|| executable.parent().unwrap_or_else(|| Path::new(".")).join("resources"));
        let script_root = resources.join("scripts");
        let backup_root = self.data_root.join("backups").join(format!("update-{}", now_ms()));
        run_update_backup_gate(
            &backup_root,
            &script_root.join("backup.ps1"),
            &script_root.join("verify-backup.ps1"),
            &script_root.join("desktop-update-backup.ps1"),
            &self.data_root,
        )
    }
}

#[derive(Clone)]
struct ManagedJob {
    #[cfg(windows)]
    handle: Arc<JobHandle>,
}

#[cfg(windows)]
struct JobHandle(HANDLE);

#[cfg(windows)]
unsafe impl Send for JobHandle {}
#[cfg(windows)]
unsafe impl Sync for JobHandle {}

#[cfg(windows)]
impl Drop for JobHandle {
    fn drop(&mut self) {
        unsafe { let _ = CloseHandle(self.0); }
    }
}

impl ManagedJob {
    fn new() -> Result<Self, RuntimeFailure> {
        #[cfg(windows)]
        unsafe {
            let handle = CreateJobObjectW(None, None).map_err(|error| {
                RuntimeFailure::new("preflight", "JOB_OBJECT_CREATE_FAILED", error.to_string())
            })?;
            let mut limits = JOBOBJECT_EXTENDED_LIMIT_INFORMATION::default();
            limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
            SetInformationJobObject(
                handle,
                JobObjectExtendedLimitInformation,
                &limits as *const _ as *const std::ffi::c_void,
                std::mem::size_of::<JOBOBJECT_EXTENDED_LIMIT_INFORMATION>() as u32,
            )
            .map_err(|error| RuntimeFailure::new("preflight", "JOB_OBJECT_CONFIG_FAILED", error.to_string()))?;
            Ok(Self { handle: Arc::new(JobHandle(handle)) })
        }
        #[cfg(not(windows))]
        Ok(Self {})
    }

    fn assign(&self, pid: u32) -> Result<(), RuntimeFailure> {
        #[cfg(windows)]
        unsafe {
            use windows::Win32::System::Threading::{OpenProcess, PROCESS_SET_QUOTA, PROCESS_TERMINATE};
            let process = OpenProcess(PROCESS_SET_QUOTA | PROCESS_TERMINATE, false, pid)
                .map_err(|error| RuntimeFailure::new("core", "JOB_PROCESS_OPEN_FAILED", error.to_string()))?;
            let result = AssignProcessToJobObject(self.handle.0, process);
            let _ = CloseHandle(process);
            result.map_err(|error| RuntimeFailure::new("core", "JOB_ASSIGN_FAILED", error.to_string()))?;
        }
        Ok(())
    }

}

pub struct UnavailableAdapter {
    message: String,
}

impl UnavailableAdapter {
    pub fn new(message: impl Into<String>) -> Self {
        Self {
            message: message.into(),
        }
    }
}

impl RuntimeAdapter for UnavailableAdapter {
    fn start(&self, _publish: &mut dyn FnMut(RuntimeSnapshot)) -> Result<(), RuntimeFailure> {
        Err(RuntimeFailure::new(
            "preflight",
            "SOURCE_ADAPTER_UNAVAILABLE",
            self.message.clone(),
        ))
    }

    fn stop(&self) -> Result<(), RuntimeFailure> {
        Ok(())
    }

    fn is_ready(&self) -> bool {
        false
    }

    fn connection(&self) -> Option<RuntimeConnection> {
        None
    }

    fn diagnostics(&self, overall: RuntimeSnapshot) -> RuntimeDiagnostics {
        let checked_at_ms = now_ms();
        let postgres_ready = port_open(5433);
        let ollama_ready = port_open(11434);
        RuntimeDiagnostics {
            overall,
            runtime_mode: "unavailable".to_owned(),
            app_version: env!("CARGO_PKG_VERSION").to_owned(),
            generated_at_ms: checked_at_ms,
            components: vec![
                app_component(checked_at_ms),
                component(
                    "core",
                    "Jarvis Core",
                    ComponentState::Blocked,
                    ComponentRequirement::Required,
                    ComponentOwnership::App,
                    None,
                    self.message.clone(),
                    Some("检查安装资源或 JARVIS_PROJECT_ROOT 配置。".to_owned()),
                    checked_at_ms,
                ),
                component(
                    "postgres",
                    "PostgreSQL",
                    required_state(postgres_ready),
                    ComponentRequirement::Required,
                    ComponentOwnership::External,
                    None,
                    if postgres_ready { "数据库端口可达。" } else { "数据库端口不可达。" },
                    (!postgres_ready).then(|| "启动 Docker Desktop，再重新检查。".to_owned()),
                    checked_at_ms,
                ),
                component(
                    "ollama",
                    "Ollama",
                    optional_state(ollama_ready),
                    ComponentRequirement::Optional,
                    ComponentOwnership::External,
                    None,
                    if ollama_ready { "本地模型服务可达。" } else { "Ollama 未启动；不阻断状态中心。" },
                    (!ollama_ready).then(|| "需要本地模型时手动启动 Ollama。".to_owned()),
                    checked_at_ms,
                ),
                component(
                    "companion",
                    "Companion",
                    ComponentState::Blocked,
                    ComponentRequirement::Required,
                    ComponentOwnership::App,
                    None,
                    "运行适配器不可用，Companion 未启动。",
                    Some("修复运行适配器后重新启动。".to_owned()),
                    checked_at_ms,
                ),
                voice_component(None, checked_at_ms),
                optional_worker_component(
                    "browser_worker",
                    "Browser Worker",
                    false,
                    checked_at_ms,
                ),
            ],
            log_directory: String::new(),
            data_directory: String::new(),
            release: None,
            log_files: Vec::new(),
        }
    }

    fn restart_core(
        &self,
        _publish: &mut dyn FnMut(RuntimeSnapshot),
    ) -> Result<(), RuntimeFailure> {
        Err(RuntimeFailure::new(
            "preflight",
            "RUNTIME_ADAPTER_UNAVAILABLE",
            self.message.clone(),
        ))
    }
}

fn component(
    id: &str,
    name: &str,
    state: ComponentState,
    requirement: ComponentRequirement,
    ownership: ComponentOwnership,
    version: Option<String>,
    detail: impl Into<String>,
    recovery: Option<String>,
    checked_at_ms: u128,
) -> RuntimeComponent {
    RuntimeComponent {
        id: id.to_owned(),
        name: name.to_owned(),
        state,
        requirement,
        ownership,
        version,
        detail: detail.into(),
        recovery,
        checked_at_ms,
    }
}

fn required_state(ready: bool) -> ComponentState {
    if ready {
        ComponentState::Ready
    } else {
        ComponentState::Blocked
    }
}

fn optional_state(ready: bool) -> ComponentState {
    if ready {
        ComponentState::Ready
    } else {
        ComponentState::Degraded
    }
}

fn optional_worker_component(
    id: &str,
    name: &str,
    running: bool,
    checked_at_ms: u128,
) -> RuntimeComponent {
    component(
        id,
        name,
        if running {
            ComponentState::Ready
        } else {
            ComponentState::NotConfigured
        },
        ComponentRequirement::Optional,
        ComponentOwnership::App,
        None,
        if running {
            "可选 Worker 正在运行。"
        } else {
            "当前 profile 未启用该 Worker。"
        },
        None,
        checked_at_ms,
    )
}

fn app_component(checked_at_ms: u128) -> RuntimeComponent {
    component(
        "app",
        "Jarvis App",
        ComponentState::Ready,
        ComponentRequirement::Required,
        ComponentOwnership::App,
        Some(env!("CARGO_PKG_VERSION").to_owned()),
        "桌面壳与状态中心正在运行。",
        None,
        checked_at_ms,
    )
}

fn voice_component(
    readiness: Option<VoiceReadiness>,
    checked_at_ms: u128,
) -> RuntimeComponent {
    match readiness {
        Some(item) if !item.enabled => component(
            "local_voice",
            "本地语音",
            ComponentState::NotConfigured,
            ComponentRequirement::Optional,
            ComponentOwnership::App,
            None,
            "本地语音功能未启用。",
            None,
            checked_at_ms,
        ),
        Some(item) if item.stt_ready && item.tts_ready => component(
            "local_voice",
            "本地语音",
            ComponentState::Ready,
            ComponentRequirement::Optional,
            ComponentOwnership::App,
            None,
            "本地 STT 与 TTS 模型均已就绪。",
            None,
            checked_at_ms,
        ),
        Some(item) => component(
            "local_voice",
            "本地语音",
            ComponentState::Degraded,
            ComponentRequirement::Optional,
            ComponentOwnership::App,
            None,
            format!(
                "本地语音模型不完整（STT={}，TTS={}，原因={}）。",
                item.stt_ready,
                item.tts_ready,
                item.reason.as_deref().unwrap_or("unknown")
            ),
            Some("在设置中检查本地语音模型目录后重新检查。".to_owned()),
            checked_at_ms,
        ),
        None => component(
            "local_voice",
            "本地语音",
            ComponentState::Degraded,
            ComponentRequirement::Optional,
            ComponentOwnership::App,
            None,
            "暂时无法读取本地语音就绪状态。",
            Some("确认 Jarvis Core 就绪后重新检查。".to_owned()),
            checked_at_ms,
        ),
    }
}

fn probe_voice_readiness(connection: &RuntimeConnection) -> Option<VoiceReadiness> {
    let port = connection_port(connection)?;
    let address = SocketAddr::new(IpAddr::V4(Ipv4Addr::LOCALHOST), port);
    let mut stream = TcpStream::connect_timeout(&address, Duration::from_millis(500)).ok()?;
    let token_header = connection
        .session_token
        .as_ref()
        .map(|token| format!("X-Jarvis-Desktop-Session: {token}\r\n"))
        .unwrap_or_default();
    let request = format!(
        "GET /api/v1/voice/readiness HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n{token_header}Connection: close\r\n\r\n"
    );
    stream.set_read_timeout(Some(Duration::from_secs(2))).ok()?;
    stream.write_all(request.as_bytes()).ok()?;
    let mut response = String::new();
    stream.read_to_string(&mut response).ok()?;
    if !response.starts_with("HTTP/1.1 200") {
        return None;
    }
    let (_, body) = response.split_once("\r\n\r\n")?;
    serde_json::from_str(body).ok()
}

fn source_process_record(project_root: &Path, field: &str) -> Option<u64> {
    let bytes = fs::read(project_root.join(".runtime").join("services.json")).ok()?;
    let record: serde_json::Value = serde_json::from_slice(&bytes).ok()?;
    let pid = record.get(field)?.as_u64()?;
    process_identity_matches(pid as u32, "python").then_some(pid)
}

#[cfg(windows)]
fn process_identity_matches(pid: u32, expected_name: &str) -> bool {
    use windows::Win32::{
        Foundation::CloseHandle,
        System::{
            ProcessStatus::GetModuleBaseNameW,
            Threading::{OpenProcess, PROCESS_QUERY_INFORMATION, PROCESS_VM_READ},
        },
    };
    unsafe {
        let Ok(process) = OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, false, pid) else {
            return false;
        };
        let mut name = [0_u16; 260];
        let length = GetModuleBaseNameW(process, None, &mut name);
        let _ = CloseHandle(process);
        if length == 0 {
            return false;
        }
        let actual = String::from_utf16_lossy(&name[..length as usize]);
        actual.trim_end_matches(".exe").eq_ignore_ascii_case(expected_name)
    }
}

#[cfg(not(windows))]
fn process_identity_matches(_pid: u32, _expected_name: &str) -> bool {
    false
}

fn load_release_info(path: &Path) -> Option<ReleaseInfo> {
    let bytes = fs::read(path).ok()?;
    serde_json::from_slice(&bytes).ok()
}

fn bundled_release_manifest_path(sidecar: &Path) -> PathBuf {
    sidecar
        .parent()
        .and_then(Path::parent)
        .unwrap_or_else(|| Path::new("."))
        .join("release-manifest.json")
}

fn list_log_metadata(directory: &Path) -> Vec<DiagnosticLogFile> {
    let mut files = fs::read_dir(directory)
        .ok()
        .into_iter()
        .flatten()
        .filter_map(Result::ok)
        .filter_map(|entry| {
            let path = entry.path();
            if !path.is_file() {
                return None;
            }
            let metadata = entry.metadata().ok()?;
            let modified_at_ms = metadata
                .modified()
                .ok()
                .and_then(|value| value.duration_since(UNIX_EPOCH).ok())
                .map(|value| value.as_millis())
                .unwrap_or_default();
            Some(DiagnosticLogFile {
                name: entry.file_name().to_string_lossy().into_owned(),
                size_bytes: metadata.len(),
                modified_at_ms,
            })
        })
        .collect::<Vec<_>>();
    files.sort_by(|left, right| left.name.cmp(&right.name));
    files
}

fn export_diagnostic_bundle(
    diagnostics: &RuntimeDiagnostics,
    connection: Option<&RuntimeConnection>,
) -> Result<DiagnosticBundleRef, RuntimeFailure> {
    let root = if diagnostics.runtime_mode == "source" && !diagnostics.log_directory.is_empty() {
        PathBuf::from(&diagnostics.log_directory)
    } else if diagnostics.data_directory.is_empty() {
        env::temp_dir().join("Jarvis OS")
    } else {
        PathBuf::from(&diagnostics.data_directory)
    };
    let directory = root.join("diagnostics");
    fs::create_dir_all(&directory).map_err(|error| {
        RuntimeFailure::new(
            "diagnostics",
            "DIAGNOSTIC_DIRECTORY_FAILED",
            format!("无法创建诊断目录：{error}"),
        )
    })?;
    let generated_at_ms = now_ms();
    let path = directory.join(format!("jarvis-diagnostics-{generated_at_ms}.json"));
    let payload = serde_json::json!({
        "schema_version": 1,
        "generated_at_ms": generated_at_ms,
        "runtime": diagnostics,
        "connection": connection.map(|item| serde_json::json!({
            "api_origin": redact_api_base_url(&item.api_base_url),
            "runtime_mode": item.runtime_mode,
            "app_version": item.app_version,
            "session_token": "[REDACTED]",
        })),
        "privacy": {
            "includes_log_content": false,
            "includes_prompt_content": false,
            "includes_file_content": false,
            "includes_secrets": false,
        },
    });
    let bytes = serde_json::to_vec_pretty(&payload).map_err(|error| {
        RuntimeFailure::new(
            "diagnostics",
            "DIAGNOSTIC_SERIALIZE_FAILED",
            format!("无法生成脱敏诊断数据：{error}"),
        )
    })?;
    assert_diagnostic_bytes_are_redacted(&bytes)?;
    fs::write(&path, &bytes).map_err(|error| {
        RuntimeFailure::new(
            "diagnostics",
            "DIAGNOSTIC_WRITE_FAILED",
            format!("无法写入脱敏诊断数据：{error}"),
        )
    })?;
    let written = fs::read(&path).map_err(|error| {
        RuntimeFailure::new(
            "diagnostics",
            "DIAGNOSTIC_VERIFY_FAILED",
            format!("无法回读诊断数据：{error}"),
        )
    })?;
    assert_diagnostic_bytes_are_redacted(&written)?;
    Ok(DiagnosticBundleRef {
        path: path.display().to_string(),
        generated_at_ms,
        redacted: true,
        entries: vec!["runtime.json".to_owned(), "log-metadata.json".to_owned()],
    })
}

fn redact_api_base_url(value: &str) -> String {
    value
        .split("/api/")
        .next()
        .unwrap_or("http://127.0.0.1")
        .to_owned()
}

fn assert_diagnostic_bytes_are_redacted(bytes: &[u8]) -> Result<(), RuntimeFailure> {
    let text = String::from_utf8_lossy(bytes).to_ascii_lowercase();
    let forbidden = [
        "authorization: bearer",
        "x-jarvis-desktop-session:",
        "cookie:",
        "postgresql+asyncpg://",
        "\"prompt_text\"",
        "\"file_content\"",
    ];
    if let Some(pattern) = forbidden.iter().find(|pattern| text.contains(**pattern)) {
        return Err(RuntimeFailure::new(
            "diagnostics",
            "DIAGNOSTIC_REDACTION_FAILED",
            format!("诊断包在写入前检出受禁内容模式：{pattern}"),
        ));
    }
    Ok(())
}

fn port_open(port: u16) -> bool {
    let address = SocketAddr::new(IpAddr::V4(Ipv4Addr::LOCALHOST), port);
    TcpStream::connect_timeout(&address, Duration::from_millis(350)).is_ok()
}

fn connection_port(connection: &RuntimeConnection) -> Option<u16> {
    connection
        .api_base_url
        .split(':')
        .next_back()?
        .split('/')
        .next()?
        .parse()
        .ok()
}

fn append_structured_event(path: &Path, snapshot: &RuntimeSnapshot) {
    rotate_log_if_needed(path, 5 * 1024 * 1024, 3);
    if let Some(parent) = path.parent() {
        let _ = fs::create_dir_all(parent);
    }
    let event = serde_json::json!({
        "timestamp_ms": now_ms(),
        "event": "runtime_snapshot",
        "state": snapshot.state,
        "stage": snapshot.stage,
        "error_code": snapshot.error_code,
    });
    if let Ok(mut file) = OpenOptions::new().create(true).append(true).open(path) {
        if let Ok(mut bytes) = serde_json::to_vec(&event) {
            bytes.push(b'\n');
            let _ = file.write_all(&bytes);
        }
    }
}

fn rotate_log_if_needed(path: &Path, max_bytes: u64, backups: usize) {
    if path.metadata().map(|item| item.len()).unwrap_or_default() < max_bytes {
        return;
    }
    for index in (1..=backups).rev() {
        let source = if index == 1 {
            path.to_path_buf()
        } else {
            path.with_extension(format!("log.{}", index - 1))
        };
        let destination = path.with_extension(format!("log.{index}"));
        if source.is_file() {
            let _ = fs::rename(source, destination);
        }
    }
}

fn wait_for_port(port: u16, timeout: Duration) -> Result<(), ()> {
    let deadline = std::time::Instant::now() + timeout;
    while std::time::Instant::now() < deadline {
        if port_open(port) {
            return Ok(());
        }
        std::thread::sleep(Duration::from_millis(300));
    }
    Err(())
}

fn reserve_loopback_port() -> Result<u16, RuntimeFailure> {
    let listener = TcpListener::bind((Ipv4Addr::LOCALHOST, 0)).map_err(|error| {
        RuntimeFailure::new(
            "core",
            "API_PORT_RESERVATION_FAILED",
            format!("无法分配 Jarvis Core 本地端口：{error}"),
        )
    })?;
    listener.local_addr().map(|address| address.port()).map_err(|error| {
        RuntimeFailure::new(
            "core",
            "API_PORT_READ_FAILED",
            format!("无法读取 Jarvis Core 本地端口：{error}"),
        )
    })
}

fn generate_session_token() -> String {
    let mut bytes = [0_u8; 32];
    rand::rng().fill_bytes(&mut bytes);
    bytes.iter().map(|byte| format!("{byte:02x}")).collect()
}

fn wait_for_http_health(port: u16, token: &str, timeout: Duration) -> Result<(), RuntimeFailure> {
    let deadline = std::time::Instant::now() + timeout;
    while std::time::Instant::now() < deadline {
        if let Ok(mut stream) = TcpStream::connect_timeout(
            &SocketAddr::new(IpAddr::V4(Ipv4Addr::LOCALHOST), port),
            Duration::from_millis(500),
        ) {
            let request = format!(
                "GET /api/v1/health/ready HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nX-Jarvis-Desktop-Session: {token}\r\nConnection: close\r\n\r\n"
            );
            let _ = stream.set_read_timeout(Some(Duration::from_secs(2)));
            if stream.write_all(request.as_bytes()).is_ok() {
                let mut response = String::new();
                if stream.read_to_string(&mut response).is_ok()
                    && response.starts_with("HTTP/1.1 200")
                {
                    return Ok(());
                }
            }
        }
        std::thread::sleep(Duration::from_millis(400));
    }
    Err(RuntimeFailure::new(
        "core",
        "CORE_READY_TIMEOUT",
        format!("Jarvis Core 在 {} 秒内未通过带会话凭证的就绪检查。", timeout.as_secs()),
    ))
}

fn discover_project_root(from: &Path) -> Option<PathBuf> {
    from.ancestors()
        .find(|candidate| {
            candidate.join("scripts").join("start.ps1").is_file()
                && candidate.join("apps").join("web").is_dir()
        })
        .map(Path::to_path_buf)
}

fn now_ms() -> u128 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis()
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::AtomicUsize;

    struct FakeAdapter {
        ready: bool,
        starts: Arc<AtomicUsize>,
        optional_degraded: bool,
        health_fails: bool,
    }

    impl RuntimeAdapter for FakeAdapter {
        fn start(&self, publish: &mut dyn FnMut(RuntimeSnapshot)) -> Result<(), RuntimeFailure> {
            self.starts.fetch_add(1, Ordering::SeqCst);
            publish(RuntimeSnapshot::new(
                RuntimeState::Starting,
                "core",
                "Core",
                "Starting",
            ));
            Ok(())
        }

        fn stop(&self) -> Result<(), RuntimeFailure> {
            Ok(())
        }

        fn is_ready(&self) -> bool {
            self.ready
        }

        fn connection(&self) -> Option<RuntimeConnection> {
            None
        }

        fn diagnostics(&self, overall: RuntimeSnapshot) -> RuntimeDiagnostics {
            RuntimeDiagnostics {
                overall,
                runtime_mode: "test".to_owned(),
                app_version: "test".to_owned(),
                generated_at_ms: now_ms(),
                components: if self.optional_degraded {
                    vec![component(
                        "optional",
                        "Optional",
                        ComponentState::Degraded,
                        ComponentRequirement::Optional,
                        ComponentOwnership::External,
                        None,
                        "Unavailable",
                        None,
                        now_ms(),
                    )]
                } else {
                    Vec::new()
                },
                log_directory: String::new(),
                data_directory: String::new(),
                release: None,
                log_files: Vec::new(),
            }
        }

        fn restart_core(
            &self,
            publish: &mut dyn FnMut(RuntimeSnapshot),
        ) -> Result<(), RuntimeFailure> {
            self.start(publish)
        }

        fn health_failure(&self) -> Option<RuntimeFailure> {
            self.health_fails.then(|| {
                RuntimeFailure::new("core", "CORE_HEALTH_LOST", "Core health lost")
            })
        }
    }

    #[test]
    fn supervisor_converges_to_ready_through_one_interface() {
        let starts = Arc::new(AtomicUsize::new(0));
        let supervisor = RuntimeSupervisor::new(FakeAdapter {
            ready: true,
            starts: Arc::clone(&starts),
            optional_degraded: false,
            health_fails: false,
        });
        let mut snapshots = Vec::new();
        let result = supervisor.start(|snapshot| snapshots.push(snapshot));
        assert_eq!(result.state, RuntimeState::Ready);
        assert_eq!(starts.load(Ordering::SeqCst), 1);
        assert!(snapshots.iter().any(|item| item.stage == "core"));
    }

    #[test]
    fn successful_adapter_without_health_is_blocked() {
        let supervisor = RuntimeSupervisor::new(FakeAdapter {
            ready: false,
            starts: Arc::new(AtomicUsize::new(0)),
            optional_degraded: false,
            health_fails: false,
        });
        let result = supervisor.start(|_| {});
        assert_eq!(result.state, RuntimeState::Blocked);
        assert_eq!(result.error_code.as_deref(), Some("RUNTIME_NOT_READY"));
    }


    #[test]
    fn supervisor_records_window_failure_as_current_status() {
        let supervisor = RuntimeSupervisor::new(FakeAdapter {
            ready: true,
            starts: Arc::new(AtomicUsize::new(0)),
            optional_degraded: false,
            health_fails: false,
        });
        let snapshot = supervisor.record_failure(
            RuntimeFailure::new(
                "interface",
                "MAIN_WINDOW_CREATE_FAILED",
                "The main window could not be created.",
            ),
            |_| {},
        );
        assert_eq!(snapshot.state, RuntimeState::Blocked);
        assert_eq!(supervisor.status(), snapshot);
    }

    #[test]
    fn project_root_discovery_uses_reviewed_start_script() {
        let fixture = Path::new(env!("CARGO_MANIFEST_DIR"));
        let root = discover_project_root(fixture).expect("repository root");
        assert!(root.join("scripts").join("start.ps1").is_file());
    }

    #[test]
    fn optional_dependency_failure_converges_to_degraded_not_blocked() {
        let supervisor = RuntimeSupervisor::new(FakeAdapter {
            ready: true,
            starts: Arc::new(AtomicUsize::new(0)),
            optional_degraded: true,
            health_fails: false,
        });
        let result = supervisor.start(|_| {});
        assert_eq!(result.state, RuntimeState::Degraded);
        assert_eq!(result.stage, "interface");
    }

    #[test]
    fn voice_diagnostics_distinguish_disabled_ready_and_missing_models() {
        let disabled = voice_component(
            Some(VoiceReadiness {
                enabled: false,
                stt_ready: false,
                tts_ready: false,
                reason: Some("feature_disabled".to_owned()),
            }),
            1,
        );
        let ready = voice_component(
            Some(VoiceReadiness {
                enabled: true,
                stt_ready: true,
                tts_ready: true,
                reason: None,
            }),
            1,
        );
        let incomplete = voice_component(
            Some(VoiceReadiness {
                enabled: true,
                stt_ready: true,
                tts_ready: false,
                reason: Some("local_models_missing".to_owned()),
            }),
            1,
        );

        assert_eq!(disabled.state, ComponentState::NotConfigured);
        assert_eq!(ready.state, ComponentState::Ready);
        assert_eq!(incomplete.state, ComponentState::Degraded);
        assert_eq!(incomplete.requirement, ComponentRequirement::Optional);
    }

    #[test]
    fn app_diagnostics_report_running_shell_version() {
        let app = app_component(42);

        assert_eq!(app.id, "app");
        assert_eq!(app.state, ComponentState::Ready);
        assert_eq!(app.version.as_deref(), Some(env!("CARGO_PKG_VERSION")));
        assert_eq!(app.checked_at_ms, 42);
    }

    #[test]
    fn unavailable_runtime_still_reports_the_full_status_center_contract() {
        let diagnostics = UnavailableAdapter::new("missing adapter")
            .diagnostics(RuntimeSnapshot::blocked(
                "preflight",
                "missing adapter",
                "RUNTIME_ADAPTER_UNAVAILABLE",
            ));
        let ids = diagnostics
            .components
            .iter()
            .map(|item| item.id.as_str())
            .collect::<Vec<_>>();

        assert_eq!(
            ids,
            vec![
                "app",
                "core",
                "postgres",
                "ollama",
                "companion",
                "local_voice",
                "browser_worker",
            ]
        );
    }

    #[test]
    fn diagnostic_export_replaces_session_token_and_omits_private_content() {
        let fixture = env::temp_dir().join(format!("jarvis-diagnostic-test-{}", now_ms()));
        fs::create_dir_all(&fixture).expect("diagnostic fixture");
        let diagnostics = RuntimeDiagnostics {
            overall: RuntimeSnapshot::new(RuntimeState::Ready, "interface", "Ready", "Ready"),
            runtime_mode: "bundled".to_owned(),
            app_version: "4.0.0-test".to_owned(),
            generated_at_ms: now_ms(),
            components: Vec::new(),
            log_directory: fixture.join("logs").display().to_string(),
            data_directory: fixture.display().to_string(),
            release: None,
            log_files: Vec::new(),
        };
        let secret = "secret-session-value";
        let connection = RuntimeConnection {
            api_base_url: "http://127.0.0.1:53123/api/v1".to_owned(),
            session_token: Some(secret.to_owned()),
            runtime_mode: "bundled".to_owned(),
            app_version: "4.0.0-test".to_owned(),
        };
        let exported = export_diagnostic_bundle(&diagnostics, Some(&connection)).expect("export");
        let text = fs::read_to_string(&exported.path).expect("diagnostic text");
        assert!(!text.contains(secret));
        assert!(text.contains("[REDACTED]"));
        assert!(text.contains("\"includes_log_content\": false"));
        assert!(!text.contains("prompt_text"));
        let _ = fs::remove_dir_all(fixture);
    }

    #[test]
    fn redaction_gate_rejects_known_secret_and_private_content_patterns() {
        assert!(assert_diagnostic_bytes_are_redacted(
            b"Authorization: Bearer do-not-export"
        )
        .is_err());
        assert!(assert_diagnostic_bytes_are_redacted(b"{\"prompt_text\":\"private\"}").is_err());
        assert!(assert_diagnostic_bytes_are_redacted(b"safe metadata only").is_ok());
    }

    #[test]
    fn automatic_recovery_stops_after_three_attempts_in_window() {
        let starts = Arc::new(AtomicUsize::new(0));
        let supervisor = RuntimeSupervisor::new(FakeAdapter {
            ready: true,
            starts: Arc::clone(&starts),
            optional_degraded: false,
            health_fails: true,
        });
        supervisor.start(|_| {});
        for _ in 0..3 {
            supervisor.recover_if_needed(|_| {});
        }
        let limited = supervisor.recover_if_needed(|_| {});
        assert_eq!(limited.state, RuntimeState::Blocked);
        assert_eq!(limited.error_code.as_deref(), Some("CORE_RESTART_LIMIT_REACHED"));
        assert_eq!(starts.load(Ordering::SeqCst), 4);
    }
}
