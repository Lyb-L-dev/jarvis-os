use crate::config_store::user_data_root;
use base64::{engine::general_purpose::STANDARD as BASE64, Engine as _};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::env;
use std::fs::{self, File};
use std::io::Read;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Mutex;
use std::thread;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

#[cfg(windows)]
use std::os::windows::process::CommandExt;

#[cfg(windows)]
const CREATE_NO_WINDOW: u32 = 0x0800_0000;

const MANIFEST_LIMIT_BYTES: u64 = 1024 * 1024;
const INSTALLER_LIMIT_BYTES: u64 = 1024 * 1024 * 1024;
const EXPECTED_TARGET: &str = "x86_64-pc-windows-msvc";
const UPDATE_PUBLIC_KEY: &str = include_str!(env!("JARVIS_UPDATE_PUBLIC_KEY_PATH"));

#[derive(Clone, Debug, Deserialize)]
struct UpdatePublicKey {
    schema_version: u32,
    key_id: String,
    algorithm: String,
    modulus_base64: String,
    exponent_base64: String,
    development_key: bool,
}

#[derive(Clone, Debug, Deserialize)]
struct SignedEnvelope {
    schema_version: u32,
    key_id: String,
    payload_base64: String,
    signature_base64: String,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct UpdatePackage {
    pub url: String,
    pub file_name: String,
    pub size_bytes: u64,
    pub sha256: String,
    pub authenticode_required: bool,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct UpdateCompatibility {
    pub minimum_app_version: String,
    pub database_migration_strategy: String,
    pub binary_rollback_compatible: bool,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct UpdateManifest {
    pub manifest_version: u32,
    pub channel: String,
    pub app_version: String,
    pub target: String,
    pub published_at: String,
    pub release_notes: String,
    pub requires_restart: bool,
    pub package: UpdatePackage,
    pub compatibility: UpdateCompatibility,
}

#[derive(Clone, Debug)]
struct VerifiedManifest {
    payload: UpdateManifest,
    development_key: bool,
}

#[derive(Clone, Debug, Serialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum UpdatePhase {
    Idle,
    Checking,
    Available,
    Current,
    Downloading,
    Staged,
    Installing,
    Blocked,
    Failed,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct UpdateSnapshot {
    pub phase: UpdatePhase,
    pub channel: String,
    pub current_version: String,
    pub available_version: Option<String>,
    pub release_notes: Option<String>,
    pub requires_restart: bool,
    pub package_size_bytes: Option<u64>,
    pub staged_path: Option<String>,
    pub busy_reason: Option<String>,
    pub backup_evidence: Option<String>,
    pub rollback_result: Option<String>,
    pub message: String,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
struct UpdateTransaction {
    schema_version: u32,
    id: String,
    from_version: String,
    target_version: String,
    installer_path: String,
    installer_sha256: String,
    rollback_installer_path: String,
    rollback_installer_sha256: String,
    target_executable: String,
    success_marker: String,
    result_path: String,
    authenticode_required: bool,
    parent_process_id: u32,
}

struct UpdateState {
    snapshot: UpdateSnapshot,
    manifest: Option<VerifiedManifest>,
}

pub struct UpdateCoordinator {
    data_root: PathBuf,
    state: Mutex<UpdateState>,
    activity_busy: AtomicBool,
}

impl UpdateCoordinator {
    pub fn discover(channel: &str) -> Result<Self, String> {
        Self::open(user_data_root()?, channel)
    }

    pub fn open(data_root: PathBuf, channel: &str) -> Result<Self, String> {
        let channel = normalize_channel(channel)?;
        fs::create_dir_all(data_root.join("updates"))
            .map_err(|error| format!("无法准备更新目录：{error}"))?;
        let rollback_result = load_latest_update_result(&data_root);
        Ok(Self {
            data_root,
            state: Mutex::new(UpdateState {
                snapshot: UpdateSnapshot {
                    phase: UpdatePhase::Idle,
                    channel,
                    current_version: env!("CARGO_PKG_VERSION").to_owned(),
                    available_version: None,
                    release_notes: None,
                    requires_restart: false,
                    package_size_bytes: None,
                    staged_path: None,
                    busy_reason: None,
                    backup_evidence: None,
                    rollback_result,
                    message: "尚未检查更新。".to_owned(),
                },
                manifest: None,
            }),
            activity_busy: AtomicBool::new(false),
        })
    }

    pub fn status(&self) -> UpdateSnapshot {
        let mut snapshot = self.state.lock().expect("update state poisoned").snapshot.clone();
        if self.activity_busy.load(Ordering::SeqCst) {
            snapshot.busy_reason = Some("对话流、审批或工具任务仍在进行。".to_owned());
        }
        snapshot
    }

    pub fn set_activity_busy(&self, busy: bool) -> UpdateSnapshot {
        self.activity_busy.store(busy, Ordering::SeqCst);
        self.status()
    }

    pub fn set_channel(&self, channel: &str) -> Result<UpdateSnapshot, String> {
        let channel = normalize_channel(channel)?;
        let mut state = self.state.lock().map_err(|_| "更新状态不可用。")?;
        state.manifest = None;
        state.snapshot = UpdateSnapshot {
            phase: UpdatePhase::Idle,
            channel,
            current_version: env!("CARGO_PKG_VERSION").to_owned(),
            available_version: None,
            release_notes: None,
            requires_restart: false,
            package_size_bytes: None,
            staged_path: None,
            busy_reason: None,
            backup_evidence: None,
            rollback_result: load_latest_update_result(&self.data_root),
            message: "更新通道已切换，尚未检查。".to_owned(),
        };
        Ok(state.snapshot.clone())
    }

    pub fn check(&self) -> Result<UpdateSnapshot, String> {
        let channel = {
            let mut state = self.state.lock().map_err(|_| "更新状态不可用。")?;
            state.snapshot.phase = UpdatePhase::Checking;
            state.snapshot.message = format!("正在检查 {} 通道…", state.snapshot.channel);
            state.snapshot.channel.clone()
        };
        let bytes = self.fetch_manifest(&channel)?;
        let verified = verify_signed_manifest(&bytes, &channel)?;
        validate_manifest(&verified, env!("CARGO_PKG_VERSION"))?;
        let available = version_is_newer(&verified.payload.app_version, env!("CARGO_PKG_VERSION"))?;
        let mut state = self.state.lock().map_err(|_| "更新状态不可用。")?;
        state.snapshot.available_version = Some(verified.payload.app_version.clone());
        state.snapshot.release_notes = Some(verified.payload.release_notes.clone());
        state.snapshot.requires_restart = verified.payload.requires_restart;
        state.snapshot.package_size_bytes = Some(verified.payload.package.size_bytes);
        state.snapshot.staged_path = None;
        if available {
            state.snapshot.phase = UpdatePhase::Available;
            state.snapshot.message = format!(
                "发现 Jarvis OS {}，安装前会再次校验并完成数据库恢复验证。",
                verified.payload.app_version
            );
            state.manifest = Some(verified);
        } else {
            state.snapshot.phase = UpdatePhase::Current;
            state.snapshot.message = "当前已是此通道的最新版本。".to_owned();
            state.manifest = None;
        }
        Ok(state.snapshot.clone())
    }

    pub fn download(&self) -> Result<UpdateSnapshot, String> {
        let manifest = {
            let mut state = self.state.lock().map_err(|_| "更新状态不可用。")?;
            let manifest = state
                .manifest
                .clone()
                .ok_or_else(|| "请先检查并确认有可用更新。".to_owned())?;
            state.snapshot.phase = UpdatePhase::Downloading;
            state.snapshot.message = "正在下载更新包；下载完成后会验证哈希与发行签名。".to_owned();
            manifest
        };
        let directory = self
            .data_root
            .join("updates")
            .join(safe_version_segment(&manifest.payload.app_version)?);
        fs::create_dir_all(&directory).map_err(|error| format!("无法准备更新暂存目录：{error}"))?;
        let target = directory.join(safe_file_name(&manifest.payload.package.file_name)?);
        download_https(&manifest.payload.package.url, &target)?;
        verify_update_package(&target, &manifest)?;
        let mut state = self.state.lock().map_err(|_| "更新状态不可用。")?;
        state.snapshot.phase = UpdatePhase::Staged;
        state.snapshot.staged_path = Some(target.display().to_string());
        state.snapshot.message = "更新包已通过签名与哈希校验；等待你主动安装。".to_owned();
        Ok(state.snapshot.clone())
    }

    pub fn installation_inputs(&self) -> Result<(UpdateManifest, PathBuf), String> {
        if self.activity_busy.load(Ordering::SeqCst) {
            return Err("当前有对话流、审批或工具任务，不能开始安装。".to_owned());
        }
        let state = self.state.lock().map_err(|_| "更新状态不可用。")?;
        if state.snapshot.phase != UpdatePhase::Staged {
            return Err("更新包尚未完成校验与暂存。".to_owned());
        }
        let manifest = state
            .manifest
            .as_ref()
            .ok_or_else(|| "已验证的更新清单不可用。".to_owned())?
            .clone();
        let path = state
            .snapshot
            .staged_path
            .as_ref()
            .map(PathBuf::from)
            .ok_or_else(|| "更新包路径不可用。".to_owned())?;
        verify_update_package(&path, &manifest)?;
        Ok((manifest.payload, path))
    }

    pub fn mark_installing(&self, message: impl Into<String>) -> UpdateSnapshot {
        let mut state = self.state.lock().expect("update state poisoned");
        state.snapshot.phase = UpdatePhase::Installing;
        state.snapshot.message = message.into();
        state.snapshot.clone()
    }

    pub fn mark_failed(&self, message: impl Into<String>) -> UpdateSnapshot {
        let mut state = self.state.lock().expect("update state poisoned");
        state.snapshot.phase = UpdatePhase::Failed;
        state.snapshot.message = message.into();
        state.snapshot.clone()
    }

    pub fn mark_blocked(&self, message: impl Into<String>) -> UpdateSnapshot {
        let mut state = self.state.lock().expect("update state poisoned");
        state.snapshot.phase = UpdatePhase::Blocked;
        state.snapshot.message = message.into();
        state.snapshot.clone()
    }

    pub fn set_backup_evidence(&self, path: &Path) -> UpdateSnapshot {
        let mut state = self.state.lock().expect("update state poisoned");
        state.snapshot.backup_evidence = Some(path.display().to_string());
        state.snapshot.message = "数据库备份已完成真实恢复验证；正在移交安装器。".to_owned();
        state.snapshot.clone()
    }

    pub fn stage_install_transaction(
        &self,
        manifest: &UpdateManifest,
        installer: &Path,
    ) -> Result<(PathBuf, PathBuf), String> {
        let current_executable = env::current_exe()
            .map_err(|error| format!("无法定位当前 Jarvis 可执行文件：{error}"))?;
        let update_root = self.data_root.join("updates");
        let rollback_source = update_root.join("rollback").join("previous-installer.exe");
        if !rollback_source.is_file() {
            return Err(
                "尚未保存上一版签名安装包，不能保证失败回退；请先通过安装器建立回退入口。"
                    .to_owned(),
            );
        }
        if manifest.package.authenticode_required {
            verify_authenticode(&rollback_source)?;
        }
        let transaction_id = format!("{}-{}", safe_version_segment(&manifest.app_version)?, now_ms());
        let transaction_root = update_root.join("transactions").join(&transaction_id);
        fs::create_dir_all(&transaction_root)
            .map_err(|error| format!("无法准备更新事务目录：{error}"))?;
        let helper = transaction_root.join("jarvis-update-helper.exe");
        fs::copy(&current_executable, &helper)
            .map_err(|error| format!("无法建立独立更新监护进程：{error}"))?;
        let rollback_installer = transaction_root.join("rollback-installer.exe");
        fs::copy(&rollback_source, &rollback_installer)
            .map_err(|error| format!("无法冻结上一版回退安装包：{error}"))?;
        let rollback_hash = file_sha256(&rollback_installer)?;
        let success_marker = transaction_root.join("startup-success.json");
        let result_path = transaction_root.join("result.json");
        let transaction_path = transaction_root.join("transaction.json");
        let transaction = UpdateTransaction {
            schema_version: 1,
            id: transaction_id,
            from_version: env!("CARGO_PKG_VERSION").to_owned(),
            target_version: manifest.app_version.clone(),
            installer_path: installer.display().to_string(),
            installer_sha256: manifest.package.sha256.clone(),
            rollback_installer_path: rollback_installer.display().to_string(),
            rollback_installer_sha256: rollback_hash,
            target_executable: current_executable.display().to_string(),
            success_marker: success_marker.display().to_string(),
            result_path: result_path.display().to_string(),
            authenticode_required: manifest.package.authenticode_required,
            parent_process_id: std::process::id(),
        };
        atomic_write_json(&transaction_path, &transaction)?;
        Ok((helper, transaction_path))
    }

    pub fn mark_post_update_success(&self, transaction_path: &Path) -> Result<(), String> {
        let transaction = read_transaction(transaction_path)?;
        if transaction.target_version != env!("CARGO_PKG_VERSION") {
            return Err("更新事务目标版本与当前应用版本不一致。".to_owned());
        }
        atomic_write_json(
            Path::new(&transaction.success_marker),
            &serde_json::json!({
                "schema_version": 1,
                "transaction_id": transaction.id,
                "app_version": env!("CARGO_PKG_VERSION"),
                "ready_at_ms": now_ms(),
            }),
        )
    }

    fn fetch_manifest(&self, channel: &str) -> Result<Vec<u8>, String> {
        if cfg!(debug_assertions) {
            if let Some(path) = env::var_os("JARVIS_UPDATE_MANIFEST_FILE") {
                return read_limited_file(&PathBuf::from(path), MANIFEST_LIMIT_BYTES, "更新清单");
            }
        }
        let url = env::var(format!("JARVIS_{}_UPDATE_MANIFEST_URL", channel.to_ascii_uppercase()))
            .unwrap_or_else(|_| default_manifest_url(channel));
        validate_https_url(&url, ManifestUrlKind::Manifest)?;
        let path = self.data_root.join("updates").join(format!("{channel}-manifest.json.tmp"));
        download_https(&url, &path)?;
        read_limited_file(&path, MANIFEST_LIMIT_BYTES, "更新清单")
    }
}

pub fn run_update_watchdog(transaction_path: &Path) -> Result<(), String> {
    let transaction = read_transaction(transaction_path)?;
    wait_for_parent_exit(transaction.parent_process_id, Duration::from_secs(30))?;
    let installer = PathBuf::from(&transaction.installer_path);
    if file_sha256(&installer)? != transaction.installer_sha256 {
        return Err("监护进程检测到新版本安装包哈希变化，已中止更新。".to_owned());
    }
    if transaction.authenticode_required {
        verify_authenticode(&installer)?;
    }
    let rollback_installer = PathBuf::from(&transaction.rollback_installer_path);
    if file_sha256(&rollback_installer)? != transaction.rollback_installer_sha256 {
        return Err("上一版回退安装包哈希变化，已中止更新。".to_owned());
    }
    if transaction.authenticode_required {
        verify_authenticode(&rollback_installer)?;
    }

    let install_status = silent_installer(&installer)?;
    if !install_status.success() {
        write_update_result(&transaction, "install_failed", "新版本安装器返回失败，未进入启动验证。")?;
        return Err(format!("新版本安装失败：{install_status}"));
    }
    let transaction_argument = transaction_path.display().to_string();
    let mut candidate = Command::new(&transaction.target_executable)
        .args(["--post-update", &transaction_argument])
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .map_err(|error| format!("新版本安装完成，但无法启动健康验证：{error}"))?;
    if wait_for_file(Path::new(&transaction.success_marker), Duration::from_secs(120)) {
        write_update_result(&transaction, "updated", "新版本启动并进入 ready，更新完成。")?;
        return Ok(());
    }

    let _ = candidate.kill();
    let _ = candidate.wait();

    let rollback_status = silent_installer(&rollback_installer)?;
    if !rollback_status.success() {
        write_update_result(
            &transaction,
            "rollback_failed",
            "新版本未在 120 秒内就绪，上一版安装器回退也失败；数据未执行 downgrade。",
        )?;
        return Err(format!("新版本启动失败且二进制回退失败：{rollback_status}"));
    }
    Command::new(&transaction.target_executable)
        .arg("--rollback-recovery")
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .map_err(|error| format!("二进制已回退，但无法启动上一版本：{error}"))?;
    write_update_result(
        &transaction,
        "rolled_back",
        "新版本未在 120 秒内就绪，已恢复上一版二进制；数据库未做自动 downgrade。",
    )
}

fn default_manifest_url(channel: &str) -> String {
    format!(
        "https://github.com/Lyb-L-dev/jarvis-os/releases/download/desktop-{channel}/{channel}-update.json"
    )
}

fn read_transaction(path: &Path) -> Result<UpdateTransaction, String> {
    let bytes = read_limited_file(path, 128 * 1024, "更新事务")?;
    let transaction: UpdateTransaction = serde_json::from_slice(&bytes)
        .map_err(|error| format!("更新事务格式无效：{error}"))?;
    if transaction.schema_version != 1 {
        return Err("更新事务版本不受支持。".to_owned());
    }
    Ok(transaction)
}

fn atomic_write_json<T: Serialize>(path: &Path, value: &T) -> Result<(), String> {
    let parent = path.parent().ok_or_else(|| "更新证据路径没有父目录。".to_owned())?;
    fs::create_dir_all(parent).map_err(|error| format!("无法创建更新证据目录：{error}"))?;
    let temporary = path.with_extension("json.partial");
    let bytes = serde_json::to_vec_pretty(value).map_err(|error| format!("无法序列化更新证据：{error}"))?;
    fs::write(&temporary, bytes).map_err(|error| format!("无法写入更新证据：{error}"))?;
    fs::rename(&temporary, path).map_err(|error| format!("无法提交更新证据：{error}"))
}

fn silent_installer(path: &Path) -> Result<std::process::ExitStatus, String> {
    let mut command = Command::new(path);
    command.arg("/S").stdin(Stdio::null()).stdout(Stdio::null()).stderr(Stdio::null());
    #[cfg(windows)]
    command.creation_flags(CREATE_NO_WINDOW);
    command.status().map_err(|error| format!("无法启动受控安装器：{error}"))
}

fn wait_for_file(path: &Path, timeout: Duration) -> bool {
    let started = std::time::Instant::now();
    while started.elapsed() < timeout {
        if path.is_file() {
            return true;
        }
        thread::sleep(Duration::from_millis(500));
    }
    false
}

#[cfg(windows)]
fn wait_for_parent_exit(process_id: u32, timeout: Duration) -> Result<(), String> {
    use windows::Win32::Foundation::{CloseHandle, WAIT_OBJECT_0};
    use windows::Win32::System::Threading::{OpenProcess, WaitForSingleObject, PROCESS_SYNCHRONIZE};

    let handle = unsafe { OpenProcess(PROCESS_SYNCHRONIZE, false, process_id) }
        .map_err(|error| format!("更新监护进程无法观察 Jarvis 退出：{error}"))?;
    let milliseconds = timeout.as_millis().min(u32::MAX as u128) as u32;
    let result = unsafe { WaitForSingleObject(handle, milliseconds) };
    let _ = unsafe { CloseHandle(handle) };
    if result == WAIT_OBJECT_0 {
        Ok(())
    } else {
        Err("Jarvis 主进程未在 30 秒内退出，更新已取消。".to_owned())
    }
}

#[cfg(not(windows))]
fn wait_for_parent_exit(_process_id: u32, _timeout: Duration) -> Result<(), String> {
    Err("更新监护进程只支持 Windows。".to_owned())
}

fn write_update_result(transaction: &UpdateTransaction, status: &str, message: &str) -> Result<(), String> {
    atomic_write_json(
        Path::new(&transaction.result_path),
        &serde_json::json!({
            "schema_version": 1,
            "transaction_id": transaction.id,
            "from_version": transaction.from_version,
            "target_version": transaction.target_version,
            "status": status,
            "message": message,
            "finished_at_ms": now_ms(),
        }),
    )
}

fn load_latest_update_result(data_root: &Path) -> Option<String> {
    let transactions = data_root.join("updates").join("transactions");
    let latest = fs::read_dir(transactions)
        .ok()?
        .flatten()
        .filter_map(|entry| {
            let path = entry.path().join("result.json");
            let modified = fs::metadata(&path).ok()?.modified().ok()?;
            Some((modified, path))
        })
        .max_by_key(|(modified, _)| *modified)?
        .1;
    let value: serde_json::Value = serde_json::from_slice(&fs::read(latest).ok()?).ok()?;
    let status = value.get("status")?.as_str()?;
    let message = value.get("message")?.as_str()?;
    Some(format!("{status}: {message}"))
}

fn now_ms() -> u128 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis()
}

fn verify_signed_manifest(bytes: &[u8], expected_channel: &str) -> Result<VerifiedManifest, String> {
    if bytes.len() as u64 > MANIFEST_LIMIT_BYTES {
        return Err("更新清单超过 1 MiB 安全上限。".to_owned());
    }
    let key: UpdatePublicKey = serde_json::from_str(UPDATE_PUBLIC_KEY)
        .map_err(|error| format!("内置更新公钥无效：{error}"))?;
    let envelope: SignedEnvelope = serde_json::from_slice(bytes)
        .map_err(|error| format!("更新清单格式无效：{error}"))?;
    if key.schema_version != 1
        || envelope.schema_version != 1
        || key.algorithm != "rsa-pkcs1-sha256"
        || envelope.key_id != key.key_id
    {
        return Err("更新清单的签名版本或密钥标识不受信任。".to_owned());
    }
    let payload = BASE64
        .decode(envelope.payload_base64.as_bytes())
        .map_err(|_| "更新清单正文不是有效 Base64。".to_owned())?;
    let signature = BASE64
        .decode(envelope.signature_base64.as_bytes())
        .map_err(|_| "更新清单签名不是有效 Base64。".to_owned())?;
    verify_rsa_signature(&key, &payload, &signature)?;
    let manifest: UpdateManifest = serde_json::from_slice(&payload)
        .map_err(|error| format!("已签名更新正文格式无效：{error}"))?;
    if manifest.channel != expected_channel {
        return Err("更新清单通道与当前设置不一致。".to_owned());
    }
    Ok(VerifiedManifest {
        payload: manifest,
        development_key: key.development_key,
    })
}

fn validate_manifest(manifest: &VerifiedManifest, current_version: &str) -> Result<(), String> {
    let payload = &manifest.payload;
    if payload.manifest_version != 1 || payload.target != EXPECTED_TARGET {
        return Err("更新清单版本或目标平台不兼容。".to_owned());
    }
    parse_version(&payload.app_version)?;
    parse_version(&payload.compatibility.minimum_app_version)?;
    if version_is_newer(&payload.compatibility.minimum_app_version, current_version)? {
        return Err("当前版本低于此更新允许的最小版本，请先安装过渡版本。".to_owned());
    }
    if payload.compatibility.database_migration_strategy != "expand-migrate-contract"
        || !payload.compatibility.binary_rollback_compatible
    {
        return Err("此更新没有声明可验证的向前兼容迁移与二进制回退策略。".to_owned());
    }
    if payload.release_notes.trim().is_empty() || payload.release_notes.len() > 12_000 {
        return Err("更新说明为空或超过安全长度。".to_owned());
    }
    if payload.package.size_bytes == 0 || payload.package.size_bytes > INSTALLER_LIMIT_BYTES {
        return Err("更新包大小不在允许范围内。".to_owned());
    }
    if !is_sha256(&payload.package.sha256) {
        return Err("更新包 SHA-256 格式无效。".to_owned());
    }
    safe_file_name(&payload.package.file_name)?;
    validate_https_url(&payload.package.url, ManifestUrlKind::Package)?;
    if payload.channel == "stable" && (manifest.development_key || !payload.package.authenticode_required) {
        return Err("Stable 更新必须使用正式清单公钥并要求 Windows 代码签名。".to_owned());
    }
    Ok(())
}

fn verify_update_package(path: &Path, manifest: &VerifiedManifest) -> Result<(), String> {
    let metadata = fs::metadata(path).map_err(|error| format!("无法读取更新包：{error}"))?;
    if !metadata.is_file() || metadata.len() != manifest.payload.package.size_bytes {
        return Err("更新包大小与签名清单不一致，已拒绝安装。".to_owned());
    }
    let actual = file_sha256(path)?;
    if actual != manifest.payload.package.sha256.to_ascii_lowercase() {
        return Err("更新包 SHA-256 与签名清单不一致，已拒绝安装。".to_owned());
    }
    if manifest.payload.package.authenticode_required {
        verify_authenticode(path)?;
    } else if !manifest.development_key || manifest.payload.channel != "beta" {
        return Err("未签名安装包只允许用于明确的开发 Beta 清单。".to_owned());
    }
    Ok(())
}

fn file_sha256(path: &Path) -> Result<String, String> {
    let mut file = File::open(path).map_err(|error| format!("无法打开更新包：{error}"))?;
    let mut hash = Sha256::new();
    let mut buffer = [0u8; 128 * 1024];
    loop {
        let read = file.read(&mut buffer).map_err(|error| format!("无法校验更新包：{error}"))?;
        if read == 0 {
            break;
        }
        hash.update(&buffer[..read]);
    }
    Ok(hash.finalize().iter().map(|byte| format!("{byte:02x}")).collect())
}

fn read_limited_file(path: &Path, limit: u64, label: &str) -> Result<Vec<u8>, String> {
    let metadata = fs::metadata(path).map_err(|error| format!("无法读取{label}：{error}"))?;
    if !metadata.is_file() || metadata.len() > limit {
        return Err(format!("{label}不是普通文件或超过安全上限。"));
    }
    fs::read(path).map_err(|error| format!("无法读取{label}：{error}"))
}

fn normalize_channel(value: &str) -> Result<String, String> {
    match value.trim().to_ascii_lowercase().as_str() {
        "stable" => Ok("stable".to_owned()),
        "beta" => Ok("beta".to_owned()),
        _ => Err("更新通道只允许 stable 或 beta。".to_owned()),
    }
}

fn safe_version_segment(value: &str) -> Result<String, String> {
    if value.is_empty()
        || value.len() > 64
        || !value.chars().all(|character| character.is_ascii_alphanumeric() || matches!(character, '.' | '-' | '+'))
    {
        return Err("更新版本号不能安全用作暂存目录。".to_owned());
    }
    Ok(value.to_owned())
}

fn safe_file_name(value: &str) -> Result<String, String> {
    if value.is_empty()
        || value.len() > 160
        || !value.to_ascii_lowercase().ends_with(".exe")
        || value.contains(['/', '\\', ':'])
        || value == "."
        || value == ".."
    {
        return Err("更新包文件名不安全或不是 .exe 安装包。".to_owned());
    }
    Ok(value.to_owned())
}

fn is_sha256(value: &str) -> bool {
    value.len() == 64 && value.bytes().all(|byte| byte.is_ascii_hexdigit())
}

fn parse_version(value: &str) -> Result<Vec<u64>, String> {
    let core = value.split_once('-').map(|(core, _)| core).unwrap_or(value);
    let parts = core
        .split('.')
        .map(|part| part.parse::<u64>().map_err(|_| "版本号格式无效。".to_owned()))
        .collect::<Result<Vec<_>, _>>()?;
    if parts.len() != 3 {
        return Err("版本号必须包含 major.minor.patch。".to_owned());
    }
    Ok(parts)
}

fn version_is_newer(candidate: &str, current: &str) -> Result<bool, String> {
    let candidate_parts = parse_version(candidate)?;
    let current_parts = parse_version(current)?;
    if candidate_parts != current_parts {
        return Ok(candidate_parts > current_parts);
    }
    let candidate_pre = candidate.split_once('-').map(|(_, suffix)| suffix);
    let current_pre = current.split_once('-').map(|(_, suffix)| suffix);
    Ok(match (candidate_pre, current_pre) {
        (None, Some(_)) => true,
        (Some(candidate), Some(current)) => candidate > current,
        _ => false,
    })
}

enum ManifestUrlKind {
    Manifest,
    Package,
}

fn validate_https_url(value: &str, kind: ManifestUrlKind) -> Result<(), String> {
    let url = tauri::Url::parse(value).map_err(|_| "更新 URL 格式无效。".to_owned())?;
    if url.scheme() != "https" || url.username() != "" || url.password().is_some() || url.port().is_some() {
        return Err("更新 URL 必须是无凭据、无自定义端口的 HTTPS 地址。".to_owned());
    }
    let host = url.host_str().unwrap_or_default().to_ascii_lowercase();
    let allowed = match kind {
        ManifestUrlKind::Manifest => matches!(host.as_str(), "github.com" | "raw.githubusercontent.com"),
        ManifestUrlKind::Package => matches!(
            host.as_str(),
            "github.com" | "objects.githubusercontent.com" | "github-releases.githubusercontent.com"
        ),
    };
    if !allowed {
        return Err("更新地址不在 Jarvis OS 发行主机白名单中。".to_owned());
    }
    Ok(())
}

#[cfg(windows)]
fn download_https(url: &str, target: &Path) -> Result<(), String> {
    use windows::Win32::System::Com::Urlmon::URLDownloadToFileW;
    use windows_core::{HSTRING, IUnknown};

    validate_https_url(url, ManifestUrlKind::Package).or_else(|_| validate_https_url(url, ManifestUrlKind::Manifest))?;
    if let Some(parent) = target.parent() {
        fs::create_dir_all(parent).map_err(|error| format!("无法准备下载目录：{error}"))?;
    }
    let _ = fs::remove_file(target);
    let source = HSTRING::from(url);
    let destination = HSTRING::from(target.as_os_str().to_string_lossy().as_ref());
    unsafe {
        URLDownloadToFileW(
            None::<&IUnknown>,
            &source,
            &destination,
            0,
            None::<&windows::Win32::System::Com::IBindStatusCallback>,
        )
    }
    .map_err(|error| format!("下载更新发行物失败：{error}"))
}

#[cfg(not(windows))]
fn download_https(_url: &str, _target: &Path) -> Result<(), String> {
    Err("Jarvis OS 桌面更新只支持 Windows。".to_owned())
}

#[cfg(windows)]
fn verify_rsa_signature(key: &UpdatePublicKey, payload: &[u8], signature: &[u8]) -> Result<(), String> {
    use std::mem::size_of;
    use windows::Win32::Security::Cryptography::{
        BCryptCloseAlgorithmProvider, BCryptDestroyKey, BCryptImportKeyPair,
        BCryptOpenAlgorithmProvider, BCryptVerifySignature, BCRYPT_ALG_HANDLE,
        BCRYPT_KEY_HANDLE, BCRYPT_OPEN_ALGORITHM_PROVIDER_FLAGS, BCRYPT_PAD_PKCS1,
        BCRYPT_PKCS1_PADDING_INFO, BCRYPT_RSAPUBLIC_BLOB, BCRYPT_RSAPUBLIC_MAGIC,
        BCRYPT_RSAKEY_BLOB, BCRYPT_RSA_ALGORITHM, BCRYPT_SHA256_ALGORITHM,
    };

    let modulus = BASE64.decode(key.modulus_base64.as_bytes()).map_err(|_| "内置公钥模数无效。".to_owned())?;
    let exponent = BASE64.decode(key.exponent_base64.as_bytes()).map_err(|_| "内置公钥指数无效。".to_owned())?;
    if modulus.len() < 256 || exponent.is_empty() {
        return Err("内置更新公钥强度不足。".to_owned());
    }
    let header = BCRYPT_RSAKEY_BLOB {
        Magic: BCRYPT_RSAPUBLIC_MAGIC,
        BitLength: (modulus.len() * 8) as u32,
        cbPublicExp: exponent.len() as u32,
        cbModulus: modulus.len() as u32,
        cbPrime1: 0,
        cbPrime2: 0,
    };
    let mut blob = Vec::with_capacity(size_of::<BCRYPT_RSAKEY_BLOB>() + exponent.len() + modulus.len());
    let header_bytes = unsafe {
        std::slice::from_raw_parts((&header as *const BCRYPT_RSAKEY_BLOB).cast::<u8>(), size_of::<BCRYPT_RSAKEY_BLOB>())
    };
    blob.extend_from_slice(header_bytes);
    blob.extend_from_slice(&exponent);
    blob.extend_from_slice(&modulus);

    let mut algorithm = BCRYPT_ALG_HANDLE::default();
    let open = unsafe {
        BCryptOpenAlgorithmProvider(
            &mut algorithm,
            BCRYPT_RSA_ALGORITHM,
            None,
            BCRYPT_OPEN_ALGORITHM_PROVIDER_FLAGS(0),
        )
    };
    if open.is_err() {
        return Err(format!("Windows 无法打开 RSA 验证器：0x{:08x}", open.0 as u32));
    }
    let result = (|| {
        let mut public_key = BCRYPT_KEY_HANDLE::default();
        let imported = unsafe {
            BCryptImportKeyPair(
                algorithm,
                None,
                BCRYPT_RSAPUBLIC_BLOB,
                &mut public_key,
                &blob,
                0,
            )
        };
        if imported.is_err() {
            return Err(format!("Windows 无法导入更新公钥：0x{:08x}", imported.0 as u32));
        }
        let hash = Sha256::digest(payload);
        let padding = BCRYPT_PKCS1_PADDING_INFO { pszAlgId: BCRYPT_SHA256_ALGORITHM };
        let verified = unsafe {
            BCryptVerifySignature(
                public_key,
                Some((&padding as *const BCRYPT_PKCS1_PADDING_INFO).cast()),
                hash.as_slice(),
                signature,
                BCRYPT_PAD_PKCS1,
            )
        };
        let _ = unsafe { BCryptDestroyKey(public_key) };
        if verified.is_err() {
            return Err("更新清单签名无效或正文已被篡改。".to_owned());
        }
        Ok(())
    })();
    let _ = unsafe { BCryptCloseAlgorithmProvider(algorithm, 0) };
    result
}

#[cfg(not(windows))]
fn verify_rsa_signature(_key: &UpdatePublicKey, _payload: &[u8], _signature: &[u8]) -> Result<(), String> {
    Err("更新签名验证只支持 Windows。".to_owned())
}

#[cfg(windows)]
fn verify_authenticode(path: &Path) -> Result<(), String> {
    use std::ffi::c_void;
    use std::os::windows::ffi::OsStrExt;
    use windows::Win32::Foundation::{HANDLE, HWND};
    use windows::Win32::Security::WinTrust::{
        WinVerifyTrust, WINTRUST_ACTION_GENERIC_VERIFY_V2, WINTRUST_DATA,
        WINTRUST_DATA_0, WINTRUST_FILE_INFO, WTD_CHOICE_FILE, WTD_REVOKE_NONE,
        WTD_STATEACTION_CLOSE, WTD_STATEACTION_VERIFY, WTD_UI_NONE,
    };
    use windows_core::{GUID, PCWSTR, PWSTR};

    let wide = path.as_os_str().encode_wide().chain(Some(0)).collect::<Vec<_>>();
    let mut file_info = WINTRUST_FILE_INFO {
        cbStruct: std::mem::size_of::<WINTRUST_FILE_INFO>() as u32,
        pcwszFilePath: PCWSTR(wide.as_ptr()),
        hFile: HANDLE::default(),
        pgKnownSubject: std::ptr::null_mut(),
    };
    let mut data = WINTRUST_DATA {
        cbStruct: std::mem::size_of::<WINTRUST_DATA>() as u32,
        pPolicyCallbackData: std::ptr::null_mut(),
        pSIPClientData: std::ptr::null_mut(),
        dwUIChoice: WTD_UI_NONE,
        fdwRevocationChecks: WTD_REVOKE_NONE,
        dwUnionChoice: WTD_CHOICE_FILE,
        Anonymous: WINTRUST_DATA_0 { pFile: &mut file_info },
        dwStateAction: WTD_STATEACTION_VERIFY,
        hWVTStateData: HANDLE::default(),
        pwszURLReference: PWSTR::null(),
        dwProvFlags: Default::default(),
        dwUIContext: Default::default(),
        pSignatureSettings: std::ptr::null_mut(),
    };
    let mut action: GUID = WINTRUST_ACTION_GENERIC_VERIFY_V2;
    let status = unsafe { WinVerifyTrust(HWND::default(), &mut action, (&mut data as *mut WINTRUST_DATA).cast::<c_void>()) };
    data.dwStateAction = WTD_STATEACTION_CLOSE;
    let _ = unsafe { WinVerifyTrust(HWND::default(), &mut action, (&mut data as *mut WINTRUST_DATA).cast::<c_void>()) };
    if status == 0 {
        Ok(())
    } else {
        Err(format!("Windows Authenticode 校验失败（0x{:08x}），已拒绝安装。", status as u32))
    }
}

#[cfg(not(windows))]
fn verify_authenticode(_path: &Path) -> Result<(), String> {
    Err("Windows Authenticode 验证不可用。".to_owned())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn channels_and_file_names_are_closed_sets() {
        assert_eq!(normalize_channel("Stable").unwrap(), "stable");
        assert!(normalize_channel("nightly").is_err());
        assert!(safe_file_name("Jarvis-4.0.0.exe").is_ok());
        assert!(safe_file_name("..\\evil.exe").is_err());
        assert!(safe_file_name("update.zip").is_err());
    }

    #[test]
    fn version_comparison_handles_beta_to_stable() {
        assert!(version_is_newer("4.0.1", "4.0.0-beta.9").unwrap());
        assert!(version_is_newer("4.0.0", "4.0.0-beta.9").unwrap());
        assert!(!version_is_newer("4.0.0-beta.1", "4.0.0-beta.1").unwrap());
    }

    #[test]
    fn release_hosts_are_allowlisted() {
        assert!(validate_https_url(
            "https://github.com/Lyb-L-dev/jarvis-os/releases/download/v4/Jarvis.exe",
            ManifestUrlKind::Package,
        )
        .is_ok());
        assert!(validate_https_url("https://example.com/Jarvis.exe", ManifestUrlKind::Package).is_err());
        assert!(validate_https_url("http://github.com/Jarvis.exe", ManifestUrlKind::Package).is_err());
    }

    #[test]
    fn signed_manifest_accepts_original_and_rejects_tampering() {
        let path = match env::var_os("JARVIS_UPDATE_TEST_ENVELOPE") {
            Some(path) => PathBuf::from(path),
            None => return,
        };
        let bytes = fs::read(path).expect("signed fixture");
        let verified = verify_signed_manifest(&bytes, "beta").expect("original signature");
        validate_manifest(&verified, env!("CARGO_PKG_VERSION")).expect("valid manifest");

        let mut envelope: serde_json::Value = serde_json::from_slice(&bytes).expect("envelope json");
        let payload = envelope["payload_base64"].as_str().expect("payload");
        let mut decoded = BASE64.decode(payload).expect("payload base64");
        let middle = decoded.len() / 2;
        decoded[middle] ^= 1;
        envelope["payload_base64"] = serde_json::Value::String(BASE64.encode(decoded));
        let tampered = serde_json::to_vec(&envelope).expect("tampered envelope");
        assert!(verify_signed_manifest(&tampered, "beta").is_err());
    }

    #[test]
    fn downloaded_package_rejects_same_size_tampering() {
        let path = env::temp_dir().join(format!(
            "jarvis-update-package-test-{}-{}.exe",
            std::process::id(),
            now_ms()
        ));
        let original = b"jarvis signed beta package fixture";
        fs::write(&path, original).expect("write package fixture");
        let manifest = VerifiedManifest {
            development_key: true,
            payload: UpdateManifest {
                manifest_version: 1,
                channel: "beta".to_owned(),
                app_version: "4.0.1-beta.1".to_owned(),
                target: EXPECTED_TARGET.to_owned(),
                published_at: "2026-08-13T00:00:00Z".to_owned(),
                release_notes: "fixture".to_owned(),
                requires_restart: true,
                package: UpdatePackage {
                    url: "https://github.com/Lyb-L-dev/jarvis-os/releases/download/test/Jarvis.exe"
                        .to_owned(),
                    file_name: "Jarvis.exe".to_owned(),
                    size_bytes: original.len() as u64,
                    sha256: file_sha256(&path).expect("fixture sha256"),
                    authenticode_required: false,
                },
                compatibility: UpdateCompatibility {
                    minimum_app_version: "4.0.0-beta.1".to_owned(),
                    database_migration_strategy: "expand-migrate-contract".to_owned(),
                    binary_rollback_compatible: true,
                },
            },
        };
        verify_update_package(&path, &manifest).expect("original package");

        let mut tampered = original.to_vec();
        let middle = tampered.len() / 2;
        tampered[middle] ^= 1;
        fs::write(&path, tampered).expect("write tampered package");
        assert!(verify_update_package(&path, &manifest).is_err());
        let _ = fs::remove_file(path);
    }
}
