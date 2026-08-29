use rand::RngCore;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::env;
use std::fs::{self, File};
use std::io::Read;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::time::{Duration, SystemTime, UNIX_EPOCH};

#[cfg(windows)]
use std::os::windows::process::CommandExt;

#[cfg(windows)]
const CREATE_NO_WINDOW: u32 = 0x0800_0000;

pub const DELETE_CONFIRMATION: &str = "删除 Jarvis 本地数据";
const EXPORT_MANIFEST_NAME: &str = "jarvis-export-manifest.json";
const CLEANUP_TICKET_NAME: &str = "jarvis-cleanup-ticket.json";
const CLEANUP_RESULT_NAME: &str = "jarvis-cleanup-result.json";
const EXPORT_SCHEMA_VERSION: u32 = 1;
const TICKET_TTL_MS: u128 = 30 * 60 * 1000;

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct DataExportReceipt {
    pub export_directory: String,
    pub manifest_path: String,
    pub file_count: usize,
    pub total_bytes: u64,
    pub verified_at_ms: u128,
    pub ticket: String,
    pub confirmation_phrase: String,
}

#[derive(Clone, Debug)]
pub struct PendingDataDeletion {
    receipt: DataExportReceipt,
    nonce: String,
}

#[derive(Debug, Deserialize, Serialize)]
struct ExportFile {
    path: String,
    size_bytes: u64,
    sha256: String,
}

#[derive(Debug, Deserialize, Serialize)]
struct ExportManifest {
    schema_version: u32,
    created_at_ms: u128,
    source_data_root: String,
    verified_database_manifest: String,
    files: Vec<ExportFile>,
}

#[derive(Debug, Deserialize, Serialize)]
struct CleanupTicket {
    schema_version: u32,
    created_at_ms: u128,
    expires_at_ms: u128,
    source_data_root: String,
    export_manifest: String,
    nonce: String,
    parent_pid: u32,
}

#[derive(Debug, Serialize)]
struct CleanupResult {
    schema_version: u32,
    completed_at_ms: u128,
    data_root_deleted: bool,
    database_volume_deleted: bool,
    message: String,
}

pub fn export_verified_user_data(
    data_root: &Path,
    verified_database_manifest: &Path,
) -> Result<(DataExportReceipt, PendingDataDeletion), String> {
    validate_verified_database_manifest(verified_database_manifest)?;
    let source_root = canonical(data_root, "Jarvis 数据目录不可用")?;
    let backup_root = canonical(
        verified_database_manifest
            .parent()
            .ok_or_else(|| "数据库备份清单没有父目录。".to_owned())?,
        "数据库备份目录不可用",
    )?;
    if !backup_root.starts_with(&source_root.join("backups")) {
        return Err("数据库备份不属于 Jarvis 受控备份目录。".to_owned());
    }

    let export_base = export_root()?;
    fs::create_dir_all(&export_base)
        .map_err(|error| format!("无法创建 Jarvis 导出目录：{error}"))?;
    let export_directory = export_base.join(format!("export-{}", now_ms()));
    if export_directory.starts_with(&source_root) {
        return Err("导出目录不能位于 Jarvis 数据目录内部。".to_owned());
    }
    fs::create_dir(&export_directory).map_err(|error| format!("无法创建本次导出目录：{error}"))?;

    copy_tree(&backup_root, &export_directory.join("database-backup"))?;
    for directory in ["config", "data"] {
        let source = source_root.join(directory);
        if source.is_dir() {
            copy_tree(&source, &export_directory.join(directory))?;
        }
    }

    let mut files = collect_export_files(&export_directory)?;
    files.sort_by(|left, right| left.path.cmp(&right.path));
    let total_bytes = files.iter().map(|file| file.size_bytes).sum();
    let copied_database_manifest = export_directory.join("database-backup").join(
        verified_database_manifest
            .file_name()
            .ok_or_else(|| "数据库备份清单文件名无效。".to_owned())?,
    );
    let manifest_path = export_directory.join(EXPORT_MANIFEST_NAME);
    let manifest = ExportManifest {
        schema_version: EXPORT_SCHEMA_VERSION,
        created_at_ms: now_ms(),
        source_data_root: source_root.display().to_string(),
        verified_database_manifest: copied_database_manifest.display().to_string(),
        files,
    };
    write_json_atomic(&manifest_path, &manifest)?;
    verify_export_manifest(&manifest_path, &source_root)?;

    let nonce = random_hex(32);
    let receipt = DataExportReceipt {
        export_directory: export_directory.display().to_string(),
        manifest_path: manifest_path.display().to_string(),
        file_count: manifest.files.len(),
        total_bytes,
        verified_at_ms: now_ms(),
        ticket: nonce.clone(),
        confirmation_phrase: DELETE_CONFIRMATION.to_owned(),
    };
    Ok((receipt.clone(), PendingDataDeletion { receipt, nonce }))
}

pub fn stage_cleanup(
    pending: &PendingDataDeletion,
    supplied_ticket: &str,
    confirmation: &str,
    expected_data_root: &Path,
) -> Result<PathBuf, String> {
    if confirmation != DELETE_CONFIRMATION {
        return Err(format!("请输入完整确认短语“{DELETE_CONFIRMATION}”。"));
    }
    if supplied_ticket.is_empty() || supplied_ticket != pending.nonce {
        return Err("导出凭据无效，请重新执行导出与验证。".to_owned());
    }
    if now_ms().saturating_sub(pending.receipt.verified_at_ms) > TICKET_TTL_MS {
        return Err("导出凭据已超过 30 分钟，请重新执行导出与验证。".to_owned());
    }
    let source_root = canonical(expected_data_root, "Jarvis 数据目录不可用")?;
    let manifest_path = PathBuf::from(&pending.receipt.manifest_path);
    verify_export_manifest(&manifest_path, &source_root)?;
    let export_directory = canonical(
        manifest_path
            .parent()
            .ok_or_else(|| "导出清单没有父目录。".to_owned())?,
        "导出目录不可用",
    )?;
    if export_directory.starts_with(&source_root) {
        return Err("安全检查拒绝位于 Jarvis 数据目录内的导出包。".to_owned());
    }
    let ticket_path = export_directory.join(CLEANUP_TICKET_NAME);
    write_json_atomic(
        &ticket_path,
        &CleanupTicket {
            schema_version: EXPORT_SCHEMA_VERSION,
            created_at_ms: now_ms(),
            expires_at_ms: now_ms() + TICKET_TTL_MS,
            source_data_root: source_root.display().to_string(),
            export_manifest: manifest_path.display().to_string(),
            nonce: pending.nonce.clone(),
            parent_pid: std::process::id(),
        },
    )?;
    Ok(ticket_path)
}

pub fn run_cleanup_helper(ticket_path: &Path, expected_data_root: &Path) -> Result<(), String> {
    let ticket_bytes =
        fs::read(ticket_path).map_err(|error| format!("无法读取数据清理凭据：{error}"))?;
    let ticket: CleanupTicket = serde_json::from_slice(&ticket_bytes)
        .map_err(|error| format!("数据清理凭据格式无效：{error}"))?;
    if ticket.schema_version != EXPORT_SCHEMA_VERSION || ticket.expires_at_ms < now_ms() {
        return Err("数据清理凭据已失效。".to_owned());
    }
    if ticket.nonce.len() != 64 || !ticket.nonce.bytes().all(|byte| byte.is_ascii_hexdigit()) {
        return Err("数据清理凭据随机标识无效。".to_owned());
    }
    let expected_root = canonical(expected_data_root, "Jarvis 数据目录不可用")?;
    let ticket_root = canonical(Path::new(&ticket.source_data_root), "清理目标不可用")?;
    if ticket_root != expected_root {
        return Err("安全检查拒绝了不匹配的清理目标。".to_owned());
    }
    let manifest_path = PathBuf::from(&ticket.export_manifest);
    verify_export_manifest(&manifest_path, &expected_root)?;
    let export_directory = canonical(
        manifest_path
            .parent()
            .ok_or_else(|| "导出目录无效。".to_owned())?,
        "导出目录不可用",
    )?;
    if export_directory.starts_with(&expected_root)
        || canonical(ticket_path, "清理凭据不可用")?.parent() != Some(export_directory.as_path())
    {
        return Err("安全检查拒绝了导出目录之外的清理凭据。".to_owned());
    }

    // The helper is launched by the desktop process immediately before exit.
    // Waiting briefly prevents racing open log/config handles without accepting a PID kill target.
    std::thread::sleep(Duration::from_secs(2));
    let staged_root = cleanup_staging_path(&expected_root, &ticket.nonce)?;
    fs::rename(&expected_root, &staged_root)
        .map_err(|error| format!("无法安全暂存 Jarvis 数据目录，未执行删除：{error}"))?;
    if let Err(error) = remove_bundled_database_volume() {
        return match fs::rename(&staged_root, &expected_root) {
            Ok(()) => Err(error),
            Err(restore_error) => Err(format!(
                "{error}；数据目录仍在 {}，但无法恢复原目录名：{restore_error}",
                staged_root.display()
            )),
        };
    }
    fs::remove_dir_all(&staged_root)
        .map_err(|error| format!("数据库卷已移除，但暂存数据目录清理失败：{error}"))?;
    write_json_atomic(
        &export_directory.join(CLEANUP_RESULT_NAME),
        &CleanupResult {
            schema_version: EXPORT_SCHEMA_VERSION,
            completed_at_ms: now_ms(),
            data_root_deleted: true,
            database_volume_deleted: true,
            message: "Jarvis 本地数据已删除；导出包已保留。".to_owned(),
        },
    )
}

pub fn record_cleanup_failure(ticket_path: &Path, message: &str) {
    let Some(directory) = ticket_path.parent() else {
        return;
    };
    let _ = write_json_atomic(
        &directory.join(CLEANUP_RESULT_NAME),
        &CleanupResult {
            schema_version: EXPORT_SCHEMA_VERSION,
            completed_at_ms: now_ms(),
            data_root_deleted: false,
            database_volume_deleted: false,
            message: message.to_owned(),
        },
    );
}

fn cleanup_staging_path(expected_root: &Path, nonce: &str) -> Result<PathBuf, String> {
    if nonce.len() != 64 || !nonce.bytes().all(|byte| byte.is_ascii_hexdigit()) {
        return Err("数据清理凭据随机标识无效。".to_owned());
    }
    let parent = expected_root
        .parent()
        .ok_or_else(|| "Jarvis 数据目录没有安全父目录。".to_owned())?;
    let staged = parent.join(format!(".Jarvis OS.pending-delete-{}", &nonce[..12]));
    if staged.exists() {
        return Err("检测到同名待删除目录，未执行清理。".to_owned());
    }
    Ok(staged)
}

fn remove_bundled_database_volume() -> Result<(), String> {
    let executable = env::current_exe().map_err(|error| error.to_string())?;
    let resources = env::var_os("JARVIS_BUNDLED_RESOURCES")
        .map(PathBuf::from)
        .unwrap_or_else(|| {
            executable
                .parent()
                .unwrap_or_else(|| Path::new("."))
                .join("resources")
        });
    let compose = env::var_os("JARVIS_BUNDLED_COMPOSE")
        .map(PathBuf::from)
        .unwrap_or_else(|| resources.join("infra").join("docker-compose.yml"));
    let compose_text = fs::read_to_string(&compose)
        .map_err(|error| format!("无法读取受控 PostgreSQL 清单：{error}"))?;
    if !compose_text.contains("name: jarvis-os")
        || !compose_text.contains("jarvis_postgres_data")
        || !compose_text.contains("container_name: jarvis-postgres")
    {
        return Err("PostgreSQL 清单身份校验失败，未执行数据删除。".to_owned());
    }
    let mut command = Command::new("docker");
    command
        .args(["compose", "-f"])
        .arg(&compose)
        .args(["down", "--volumes", "--remove-orphans"])
        .env("POSTGRES_PASSWORD", "jarvis-cleanup-placeholder")
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null());
    #[cfg(windows)]
    command.creation_flags(CREATE_NO_WINDOW);
    let status = command
        .status()
        .map_err(|error| format!("无法启动 Docker 数据清理：{error}"))?;
    if status.success() {
        Ok(())
    } else {
        Err(format!(
            "Docker 数据卷清理失败（{status}），未删除文件数据。"
        ))
    }
}

fn validate_verified_database_manifest(path: &Path) -> Result<(), String> {
    let bytes = fs::read(path).map_err(|error| format!("无法读取数据库备份清单：{error}"))?;
    let value: serde_json::Value = serde_json::from_slice(&bytes)
        .map_err(|error| format!("数据库备份清单格式无效：{error}"))?;
    let verified = value
        .get("restore_verified_at")
        .and_then(serde_json::Value::as_str)
        .is_some_and(|value| !value.trim().is_empty());
    let table_count = value
        .get("verified_table_count")
        .and_then(serde_json::Value::as_u64)
        .unwrap_or_default();
    if !verified || table_count < 1 {
        return Err("数据库备份没有通过临时库恢复验证。".to_owned());
    }
    Ok(())
}

fn verify_export_manifest(path: &Path, expected_data_root: &Path) -> Result<(), String> {
    let manifest_bytes = fs::read(path).map_err(|error| format!("无法读取导出清单：{error}"))?;
    let manifest: ExportManifest = serde_json::from_slice(&manifest_bytes)
        .map_err(|error| format!("导出清单格式无效：{error}"))?;
    if manifest.schema_version != EXPORT_SCHEMA_VERSION {
        return Err("导出清单版本不受支持。".to_owned());
    }
    let source_root = canonical(Path::new(&manifest.source_data_root), "导出来源不可用")?;
    if source_root != canonical(expected_data_root, "Jarvis 数据目录不可用")? {
        return Err("导出清单与当前 Jarvis 数据目录不匹配。".to_owned());
    }
    let export_root = canonical(
        path.parent()
            .ok_or_else(|| "导出清单没有父目录。".to_owned())?,
        "导出目录不可用",
    )?;
    let database_manifest = canonical(
        Path::new(&manifest.verified_database_manifest),
        "导出的数据库备份清单不可用",
    )?;
    if !database_manifest.starts_with(&export_root.join("database-backup")) {
        return Err("导出的数据库备份清单不在受控目录内。".to_owned());
    }
    validate_verified_database_manifest(&database_manifest)?;
    for record in &manifest.files {
        let relative = safe_relative_path(&record.path)?;
        let candidate = export_root.join(relative);
        let metadata = fs::symlink_metadata(&candidate)
            .map_err(|error| format!("导出文件缺失 {}：{error}", record.path))?;
        if metadata.file_type().is_symlink() || !metadata.is_file() {
            return Err(format!("导出文件类型不安全：{}", record.path));
        }
        if metadata.len() != record.size_bytes || sha256_file(&candidate)? != record.sha256 {
            return Err(format!("导出文件校验失败：{}", record.path));
        }
    }
    Ok(())
}

fn copy_tree(source: &Path, destination: &Path) -> Result<(), String> {
    let metadata = fs::symlink_metadata(source)
        .map_err(|error| format!("无法读取导出源 {}：{error}", source.display()))?;
    if metadata.file_type().is_symlink() || !metadata.is_dir() {
        return Err(format!("导出源不是安全目录：{}", source.display()));
    }
    fs::create_dir_all(destination)
        .map_err(|error| format!("无法创建导出目录 {}：{error}", destination.display()))?;
    for entry in fs::read_dir(source).map_err(|error| error.to_string())? {
        let entry = entry.map_err(|error| error.to_string())?;
        let kind = entry.file_type().map_err(|error| error.to_string())?;
        let target = destination.join(entry.file_name());
        if kind.is_symlink() {
            return Err(format!(
                "导出源包含符号链接，已安全中止：{}",
                entry.path().display()
            ));
        }
        if kind.is_dir() {
            copy_tree(&entry.path(), &target)?;
        } else if kind.is_file() {
            fs::copy(entry.path(), &target)
                .map_err(|error| format!("复制导出文件失败：{error}"))?;
        }
    }
    Ok(())
}

fn collect_export_files(root: &Path) -> Result<Vec<ExportFile>, String> {
    let mut records = Vec::new();
    collect_export_files_into(root, root, &mut records)?;
    Ok(records)
}

fn collect_export_files_into(
    root: &Path,
    directory: &Path,
    records: &mut Vec<ExportFile>,
) -> Result<(), String> {
    for entry in fs::read_dir(directory).map_err(|error| error.to_string())? {
        let entry = entry.map_err(|error| error.to_string())?;
        let kind = entry.file_type().map_err(|error| error.to_string())?;
        if kind.is_symlink() {
            return Err(format!("导出目录包含符号链接：{}", entry.path().display()));
        }
        if kind.is_dir() {
            collect_export_files_into(root, &entry.path(), records)?;
        } else if kind.is_file() && entry.file_name() != EXPORT_MANIFEST_NAME {
            let relative = entry
                .path()
                .strip_prefix(root)
                .map_err(|error| error.to_string())?
                .to_string_lossy()
                .replace('\\', "/");
            let size_bytes = entry.metadata().map_err(|error| error.to_string())?.len();
            records.push(ExportFile {
                path: relative,
                size_bytes,
                sha256: sha256_file(&entry.path())?,
            });
        }
    }
    Ok(())
}

fn safe_relative_path(value: &str) -> Result<PathBuf, String> {
    let path = Path::new(value);
    if path.is_absolute()
        || path.components().any(|component| {
            matches!(
                component,
                std::path::Component::ParentDir
                    | std::path::Component::RootDir
                    | std::path::Component::Prefix(_)
            )
        })
    {
        return Err("导出清单包含不安全路径。".to_owned());
    }
    Ok(path.to_path_buf())
}

fn sha256_file(path: &Path) -> Result<String, String> {
    let mut file = File::open(path).map_err(|error| error.to_string())?;
    let mut digest = Sha256::new();
    let mut buffer = [0_u8; 64 * 1024];
    loop {
        let read = file.read(&mut buffer).map_err(|error| error.to_string())?;
        if read == 0 {
            break;
        }
        digest.update(&buffer[..read]);
    }
    Ok(format!("{:x}", digest.finalize()))
}

fn write_json_atomic<T: Serialize>(path: &Path, value: &T) -> Result<(), String> {
    let temporary = path.with_extension("tmp");
    let bytes = serde_json::to_vec_pretty(value).map_err(|error| error.to_string())?;
    fs::write(&temporary, bytes).map_err(|error| error.to_string())?;
    fs::rename(&temporary, path).map_err(|error| error.to_string())
}

fn export_root() -> Result<PathBuf, String> {
    if let Some(root) = env::var_os("JARVIS_EXPORT_ROOT") {
        return Ok(PathBuf::from(root));
    }
    env::var_os("USERPROFILE")
        .map(PathBuf::from)
        .map(|root| root.join("Documents").join("Jarvis OS Exports"))
        .ok_or_else(|| "Windows 用户目录不可用，无法创建独立导出包。".to_owned())
}

fn canonical(path: &Path, label: &str) -> Result<PathBuf, String> {
    path.canonicalize()
        .map_err(|error| format!("{label}（{}）：{error}", path.display()))
}

fn random_hex(bytes: usize) -> String {
    let mut value = vec![0_u8; bytes];
    rand::rng().fill_bytes(&mut value);
    value.iter().map(|byte| format!("{byte:02x}")).collect()
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

    fn temp_root(name: &str) -> PathBuf {
        env::temp_dir().join(format!("jarvis-data-maintenance-{name}-{}", random_hex(8)))
    }

    fn fixture() -> (PathBuf, PathBuf, PathBuf) {
        let root = temp_root("fixture");
        let data_root = root.join("Jarvis OS");
        let export_root = root.join("exports").join("export-1");
        fs::create_dir_all(export_root.join("database-backup")).unwrap();
        fs::create_dir_all(data_root.join("backups")).unwrap();
        let database_manifest = export_root.join("database-backup").join("db.manifest.json");
        fs::write(
            &database_manifest,
            r#"{"restore_verified_at":"2026-08-14T00:00:00Z","verified_table_count":1}"#,
        )
        .unwrap();
        let database_record = ExportFile {
            path: "database-backup/db.manifest.json".to_owned(),
            size_bytes: fs::metadata(&database_manifest).unwrap().len(),
            sha256: sha256_file(&database_manifest).unwrap(),
        };
        let export_manifest = export_root.join(EXPORT_MANIFEST_NAME);
        write_json_atomic(
            &export_manifest,
            &ExportManifest {
                schema_version: EXPORT_SCHEMA_VERSION,
                created_at_ms: now_ms(),
                source_data_root: data_root.display().to_string(),
                verified_database_manifest: database_manifest.display().to_string(),
                files: vec![database_record],
            },
        )
        .unwrap();
        (root, data_root, export_manifest)
    }

    #[test]
    fn verified_export_rejects_path_traversal() {
        assert!(safe_relative_path("../secrets.dpapi").is_err());
        assert!(safe_relative_path("config/secrets.dpapi").is_ok());
    }

    #[test]
    fn cleanup_requires_exact_phrase_and_matching_ticket() {
        let (root, data_root, manifest) = fixture();
        let pending = PendingDataDeletion {
            receipt: DataExportReceipt {
                export_directory: manifest.parent().unwrap().display().to_string(),
                manifest_path: manifest.display().to_string(),
                file_count: 1,
                total_bytes: 1,
                verified_at_ms: now_ms(),
                ticket: "ticket".to_owned(),
                confirmation_phrase: DELETE_CONFIRMATION.to_owned(),
            },
            nonce: "ticket".to_owned(),
        };
        assert!(stage_cleanup(&pending, "ticket", "删除", &data_root).is_err());
        assert!(stage_cleanup(&pending, "wrong", DELETE_CONFIRMATION, &data_root).is_err());
        let ticket = stage_cleanup(&pending, "ticket", DELETE_CONFIRMATION, &data_root).unwrap();
        assert_eq!(
            ticket.parent().unwrap().canonicalize().unwrap(),
            manifest.parent().unwrap().canonicalize().unwrap()
        );
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn export_manifest_detects_tampering() {
        let (root, data_root, manifest) = fixture();
        assert!(verify_export_manifest(&manifest, &data_root).is_ok());
        fs::write(
            manifest
                .parent()
                .unwrap()
                .join("database-backup/db.manifest.json"),
            "tampered",
        )
        .unwrap();
        assert!(verify_export_manifest(&manifest, &data_root).is_err());
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn cleanup_staging_path_is_fixed_beside_data_root() {
        let data_root = PathBuf::from(r"C:\Users\test\AppData\Local\Jarvis OS");
        let nonce = "ab".repeat(32);
        assert_eq!(
            cleanup_staging_path(&data_root, &nonce).unwrap(),
            PathBuf::from(r"C:\Users\test\AppData\Local\.Jarvis OS.pending-delete-abababababab")
        );
        assert!(cleanup_staging_path(&data_root, "../../escape").is_err());
    }
}
