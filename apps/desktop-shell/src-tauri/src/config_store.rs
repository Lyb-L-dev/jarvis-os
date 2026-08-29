use rand::RngCore;
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet, HashMap};
use std::env;
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::Mutex;
use std::time::{SystemTime, UNIX_EPOCH};

#[cfg(windows)]
use windows::Win32::{
    Foundation::{LocalFree, HLOCAL},
    Security::Cryptography::{
        CryptProtectData, CryptUnprotectData, CRYPTPROTECT_UI_FORBIDDEN,
        CRYPT_INTEGER_BLOB,
    },
    Storage::FileSystem::{
        MoveFileExW, ReplaceFileW, MOVEFILE_WRITE_THROUGH, REPLACEFILE_WRITE_THROUGH,
    },
};
#[cfg(windows)]
use windows_core::PCWSTR;

const MAX_LEGACY_CONFIG_BYTES: usize = 1024 * 1024;
const CONFIG_FILE_NAME: &str = "jarvis.env";
const PROTECTED_FILE_NAME: &str = "secrets.dpapi";
const SETUP_MARKER_NAME: &str = "setup-complete.json";
const DEFAULT_DATABASE_PASSWORD: &str = "jarvis_dev_only";

#[derive(Clone, Debug, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct DesktopConfigStatus {
    pub first_run: bool,
    pub configured: bool,
    pub protected_store_ready: bool,
    pub data_directory: String,
    pub config_directory: String,
}

#[derive(Clone, Debug, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct MigrationField {
    pub name: String,
    pub destination: String,
    pub display_value: String,
    pub sensitive: bool,
    pub selected_by_default: bool,
    pub replaces_existing: bool,
}

#[derive(Clone, Debug, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct MigrationPreview {
    pub source_name: String,
    pub fields: Vec<MigrationField>,
    pub ignored_fields: Vec<String>,
    pub source_bytes: usize,
}

#[derive(Clone, Debug, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct MigrationResult {
    pub imported_fields: usize,
    pub protected_fields: usize,
    pub ordinary_fields: usize,
    pub source_unchanged: bool,
    pub restart_required: bool,
}

#[derive(Debug)]
struct PendingMigration {
    values: BTreeMap<String, String>,
}

#[derive(Debug, Deserialize, Serialize)]
struct ProtectedPayload {
    schema_version: u8,
    values: BTreeMap<String, String>,
}

#[derive(Debug)]
pub struct DesktopConfigStore {
    data_root: PathBuf,
    pending: Mutex<Option<PendingMigration>>,
}

impl DesktopConfigStore {
    pub fn discover() -> Result<Self, String> {
        let data_root = user_data_root()?;
        Self::open(data_root)
    }

    pub fn open(data_root: PathBuf) -> Result<Self, String> {
        for directory in ["config", "data", "runtime", "logs", "backups"] {
            fs::create_dir_all(data_root.join(directory)).map_err(|error| {
                format!("无法准备 Jarvis 用户目录 {directory}：{error}")
            })?;
        }
        let store = Self {
            data_root,
            pending: Mutex::new(None),
        };
        store.ensure_protected_defaults()?;
        Ok(store)
    }

    pub fn status(&self) -> DesktopConfigStatus {
        let config_directory = self.config_directory();
        DesktopConfigStatus {
            first_run: !self.setup_marker_path().is_file(),
            configured: self.config_path().is_file() || self.protected_path().is_file(),
            protected_store_ready: self.protected_path().is_file(),
            data_directory: self.data_root.display().to_string(),
            config_directory: config_directory.display().to_string(),
        }
    }

    pub fn preview_legacy(
        &self,
        source_name: &str,
        contents: &str,
    ) -> Result<MigrationPreview, String> {
        if !source_name.to_ascii_lowercase().ends_with(".env") {
            return Err("只允许预览 .env 配置文件。".to_owned());
        }
        if contents.len() > MAX_LEGACY_CONFIG_BYTES {
            return Err("配置文件超过 1 MiB，已拒绝读取。".to_owned());
        }
        let parsed = parse_environment(contents);
        let current = self.load_all_values()?;
        let mut accepted = BTreeMap::new();
        let mut ignored_fields = Vec::new();
        for (name, value) in parsed {
            if is_desktop_managed_key(&name) {
                ignored_fields.push(name);
            } else {
                accepted.insert(name, value);
            }
        }
        let fields = accepted
            .iter()
            .map(|(name, value)| {
                let sensitive = is_sensitive_key(name);
                MigrationField {
                    name: name.clone(),
                    destination: if sensitive {
                        "Windows DPAPI 受保护存储".to_owned()
                    } else {
                        "用户配置目录".to_owned()
                    },
                    display_value: if sensitive {
                        masked_value(value)
                    } else {
                        value.clone()
                    },
                    sensitive,
                    selected_by_default: true,
                    replaces_existing: current.contains_key(name),
                }
            })
            .collect();
        *self.pending.lock().map_err(|_| "配置迁移状态不可用。")? =
            Some(PendingMigration { values: accepted });
        Ok(MigrationPreview {
            source_name: sanitize_source_name(source_name),
            fields,
            ignored_fields,
            source_bytes: contents.len(),
        })
    }

    pub fn apply_pending(&self, selected_names: &[String]) -> Result<MigrationResult, String> {
        let selected = selected_names.iter().cloned().collect::<BTreeSet<_>>();
        let pending = self
            .pending
            .lock()
            .map_err(|_| "配置迁移状态不可用。")?
            .take()
            .ok_or_else(|| "没有等待导入的配置预览。".to_owned())?;
        let mut ordinary = read_environment_file(&self.config_path())?;
        let mut protected = self.read_protected_values()?;
        let mut ordinary_fields = 0;
        let mut protected_fields = 0;
        for (name, value) in pending.values {
            if !selected.contains(&name) {
                continue;
            }
            if is_sensitive_key(&name) {
                protected.insert(name.clone(), value.clone());
                protected_fields += 1;
                if name == "DATABASE_URL" {
                    if let Some(password) = database_password_from_url(&value) {
                        protected.insert("POSTGRES_PASSWORD".to_owned(), password);
                    }
                }
            } else {
                ordinary.insert(name, value);
                ordinary_fields += 1;
            }
        }
        self.backup_existing_config()?;
        write_environment_file(&self.config_path(), &ordinary)?;
        self.write_protected_values(&protected)?;
        self.mark_setup_complete("legacy_import")?;
        Ok(MigrationResult {
            imported_fields: ordinary_fields + protected_fields,
            protected_fields,
            ordinary_fields,
            source_unchanged: true,
            restart_required: false,
        })
    }

    pub fn cancel_pending(&self) -> Result<(), String> {
        *self.pending.lock().map_err(|_| "配置迁移状态不可用。")? = None;
        Ok(())
    }

    pub fn complete_without_import(&self) -> Result<DesktopConfigStatus, String> {
        self.cancel_pending()?;
        self.mark_setup_complete("fresh_install")?;
        Ok(self.status())
    }

    pub fn preference_bool(&self, name: &str, default: bool) -> Result<bool, String> {
        if !is_desktop_preference_key(name) {
            return Err("桌面偏好名称不受支持。".to_owned());
        }
        Ok(read_environment_file(&self.config_path())?
            .get(name)
            .map(|value| value.eq_ignore_ascii_case("true"))
            .unwrap_or(default))
    }

    pub fn set_preference_bool(&self, name: &str, value: bool) -> Result<(), String> {
        if !is_desktop_preference_key(name) {
            return Err("桌面偏好名称不受支持。".to_owned());
        }
        let mut ordinary = read_environment_file(&self.config_path())?;
        ordinary.insert(name.to_owned(), value.to_string());
        write_environment_file(&self.config_path(), &ordinary)
    }

    pub fn preference_string(&self, name: &str, default: &str) -> Result<String, String> {
        if !is_desktop_preference_key(name) {
            return Err("桌面偏好名称不受支持。".to_owned());
        }
        Ok(read_environment_file(&self.config_path())?
            .get(name)
            .cloned()
            .unwrap_or_else(|| default.to_owned()))
    }

    pub fn set_preference_string(&self, name: &str, value: &str) -> Result<(), String> {
        if !is_desktop_preference_key(name) {
            return Err("桌面偏好名称不受支持。".to_owned());
        }
        let mut ordinary = read_environment_file(&self.config_path())?;
        ordinary.insert(name.to_owned(), value.to_owned());
        write_environment_file(&self.config_path(), &ordinary)
    }

    pub fn load_environment(&self) -> Result<HashMap<String, String>, String> {
        let mut values = read_environment_file(&self.config_path())?
            .into_iter()
            .collect::<HashMap<_, _>>();
        values.extend(self.read_protected_values()?);
        let password = values
            .get("POSTGRES_PASSWORD")
            .cloned()
            .or_else(|| values.get("DATABASE_URL").and_then(|url| database_password_from_url(url)))
            .unwrap_or_else(|| DEFAULT_DATABASE_PASSWORD.to_owned());
        values.insert("POSTGRES_PASSWORD".to_owned(), password.clone());
        values.entry("DATABASE_URL".to_owned()).or_insert_with(|| {
            format!(
                "postgresql+asyncpg://jarvis:{password}@127.0.0.1:5433/jarvis"
            )
        });
        Ok(values)
    }

    fn config_directory(&self) -> PathBuf {
        self.data_root.join("config")
    }

    fn config_path(&self) -> PathBuf {
        env::var_os("JARVIS_BUNDLED_CONFIG")
            .map(PathBuf::from)
            .unwrap_or_else(|| self.config_directory().join(CONFIG_FILE_NAME))
    }

    fn protected_path(&self) -> PathBuf {
        self.config_directory().join(PROTECTED_FILE_NAME)
    }

    fn setup_marker_path(&self) -> PathBuf {
        self.config_directory().join(SETUP_MARKER_NAME)
    }

    fn load_all_values(&self) -> Result<BTreeMap<String, String>, String> {
        let mut values = read_environment_file(&self.config_path())?;
        values.extend(self.read_protected_values()?);
        Ok(values)
    }

    fn ensure_protected_defaults(&self) -> Result<(), String> {
        let mut values = self.read_protected_values()?;
        if values.contains_key("POSTGRES_PASSWORD") {
            return Ok(());
        }
        values.insert(
            "POSTGRES_PASSWORD".to_owned(),
            DEFAULT_DATABASE_PASSWORD.to_owned(),
        );
        self.write_protected_values(&values)
    }

    fn read_protected_values(&self) -> Result<BTreeMap<String, String>, String> {
        let path = self.protected_path();
        if !path.is_file() {
            return Ok(BTreeMap::new());
        }
        let encrypted = fs::read(&path)
            .map_err(|error| format!("无法读取 Windows 受保护配置：{error}"))?;
        let plaintext = unprotect_bytes(&encrypted)?;
        let payload: ProtectedPayload = serde_json::from_slice(&plaintext)
            .map_err(|error| format!("受保护配置格式无效：{error}"))?;
        if payload.schema_version != 1 {
            return Err("受保护配置版本不受支持。".to_owned());
        }
        Ok(payload.values)
    }

    fn write_protected_values(&self, values: &BTreeMap<String, String>) -> Result<(), String> {
        let payload = ProtectedPayload {
            schema_version: 1,
            values: values.clone(),
        };
        let plaintext = serde_json::to_vec(&payload)
            .map_err(|error| format!("无法序列化受保护配置：{error}"))?;
        let encrypted = protect_bytes(&plaintext)?;
        atomic_write(&self.protected_path(), &encrypted)
    }

    fn backup_existing_config(&self) -> Result<(), String> {
        let existing = [self.config_path(), self.protected_path()]
            .into_iter()
            .filter(|path| path.is_file())
            .collect::<Vec<_>>();
        if existing.is_empty() {
            return Ok(());
        }
        let directory = self
            .data_root
            .join("backups")
            .join(format!("config-{}", now_ms()));
        fs::create_dir_all(&directory)
            .map_err(|error| format!("无法创建配置备份目录：{error}"))?;
        for path in existing {
            if let Some(name) = path.file_name() {
                fs::copy(&path, directory.join(name))
                    .map_err(|error| format!("无法备份现有配置：{error}"))?;
            }
        }
        Ok(())
    }

    fn mark_setup_complete(&self, mode: &str) -> Result<(), String> {
        let marker = serde_json::json!({
            "schema_version": 1,
            "completed_at_ms": now_ms(),
            "mode": mode,
        });
        let bytes = serde_json::to_vec_pretty(&marker)
            .map_err(|error| format!("无法生成首次运行标记：{error}"))?;
        atomic_write(&self.setup_marker_path(), &bytes)
    }
}

pub fn load_bundled_environment(data_root: &Path) -> Result<HashMap<String, String>, String> {
    DesktopConfigStore::open(data_root.to_path_buf())?.load_environment()
}

fn read_environment_file(path: &Path) -> Result<BTreeMap<String, String>, String> {
    if !path.is_file() {
        return Ok(BTreeMap::new());
    }
    let text = fs::read_to_string(path)
        .map_err(|error| format!("无法读取安装态配置 {}：{error}", path.display()))?;
    Ok(parse_environment(&text))
}

fn parse_environment(text: &str) -> BTreeMap<String, String> {
    text.lines()
        .filter_map(|raw_line| {
            let line = raw_line.trim();
            if line.is_empty() || line.starts_with('#') {
                return None;
            }
            let (name, value) = line.split_once('=')?;
            let name = name.trim();
            if !is_valid_environment_name(name) {
                return None;
            }
            Some((
                name.to_owned(),
                value.trim().trim_matches('"').trim_matches('\'').to_owned(),
            ))
        })
        .collect()
}

fn write_environment_file(path: &Path, values: &BTreeMap<String, String>) -> Result<(), String> {
    let mut text = String::from("# Jarvis OS desktop configuration. Secrets are stored separately with Windows DPAPI.\n");
    for (name, value) in values {
        if !is_sensitive_key(name) && !is_desktop_managed_key(name) {
            text.push_str(name);
            text.push('=');
            text.push_str(&quote_environment_value(value));
            text.push('\n');
        }
    }
    atomic_write(path, text.as_bytes())
}

fn quote_environment_value(value: &str) -> String {
    if value.chars().all(|character| {
        character.is_ascii_alphanumeric() || "-._/:,\\".contains(character)
    }) {
        value.to_owned()
    } else {
        format!("\"{}\"", value.replace('"', "\\\""))
    }
}

fn is_valid_environment_name(name: &str) -> bool {
    !name.is_empty()
        && name
            .chars()
            .all(|character| character == '_' || character.is_ascii_alphanumeric())
        && name
            .chars()
            .next()
            .is_some_and(|character| character == '_' || character.is_ascii_alphabetic())
}

fn is_sensitive_key(name: &str) -> bool {
    let upper = name.to_ascii_uppercase();
    upper == "DATABASE_URL"
        || upper.contains("API_KEY")
        || upper.contains("PASSWORD")
        || upper.contains("SECRET")
        || upper.contains("TOKEN")
        || upper.ends_with("_CREDENTIAL")
}

fn is_desktop_managed_key(name: &str) -> bool {
    matches!(
        name.to_ascii_uppercase().as_str(),
        "API_HOST"
            | "API_PORT"
            | "APP_ENV"
            | "DESKTOP_SESSION_TOKEN"
            | "JARVIS_API_BASE_URL"
            | "NEXT_PUBLIC_API_BASE_URL"
            | "PYTHONUTF8"
            | "WEB_ORIGINS"
    )
}

fn is_desktop_preference_key(name: &str) -> bool {
    matches!(
        name,
        "DESKTOP_QUICK_SHORTCUT_ENABLED"
            | "DESKTOP_QUICK_SHORTCUT"
            | "DESKTOP_VOICE_SHORTCUT_ENABLED"
            | "DESKTOP_VOICE_SHORTCUT"
            | "DESKTOP_CLOSE_BEHAVIOR"
            | "DESKTOP_CLOSE_HINT_SHOWN"
            | "DESKTOP_OPEN_WITH_ENABLED"
            | "DESKTOP_UPDATE_CHANNEL"
    )
}

fn masked_value(value: &str) -> String {
    if value.is_empty() {
        return "未配置".to_owned();
    }
    let suffix = value.chars().rev().take(4).collect::<Vec<_>>();
    let suffix = suffix.into_iter().rev().collect::<String>();
    format!("••••••••{suffix}")
}

fn sanitize_source_name(value: &str) -> String {
    Path::new(value)
        .file_name()
        .and_then(|name| name.to_str())
        .unwrap_or(".env")
        .to_owned()
}

fn database_password_from_url(value: &str) -> Option<String> {
    let authority = value.split_once("://")?.1.split('@').next()?;
    authority.split_once(':').map(|(_, password)| password.to_owned())
}

fn atomic_write(path: &Path, bytes: &[u8]) -> Result<(), String> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)
            .map_err(|error| format!("无法创建配置目录：{error}"))?;
    }
    let mut random = [0_u8; 8];
    rand::rng().fill_bytes(&mut random);
    let temporary = path.with_extension(format!(
        "tmp-{}",
        random.iter().map(|byte| format!("{byte:02x}")).collect::<String>()
    ));
    fs::write(&temporary, bytes).map_err(|error| format!("无法写入临时配置：{error}"))?;
    replace_file(&temporary, path).inspect_err(|_| {
        let _ = fs::remove_file(&temporary);
    })
}

#[cfg(windows)]
fn replace_file(source: &Path, destination: &Path) -> Result<(), String> {
    let source_wide = wide_path(source);
    let destination_wide = wide_path(destination);
    let result = if destination.is_file() {
        unsafe {
            ReplaceFileW(
                PCWSTR(destination_wide.as_ptr()),
                PCWSTR(source_wide.as_ptr()),
                PCWSTR::null(),
                REPLACEFILE_WRITE_THROUGH,
                None,
                None,
            )
        }
    } else {
        unsafe {
            MoveFileExW(
                PCWSTR(source_wide.as_ptr()),
                PCWSTR(destination_wide.as_ptr()),
                MOVEFILE_WRITE_THROUGH,
            )
        }
    };
    result
    .map_err(|error| format!("无法原子替换配置：{error}"))
}

#[cfg(not(windows))]
fn replace_file(source: &Path, destination: &Path) -> Result<(), String> {
    if destination.exists() {
        fs::remove_file(destination).map_err(|error| format!("无法替换配置：{error}"))?;
    }
    fs::rename(source, destination).map_err(|error| format!("无法替换配置：{error}"))
}

#[cfg(windows)]
fn wide_path(path: &Path) -> Vec<u16> {
    use std::os::windows::ffi::OsStrExt;
    path.as_os_str().encode_wide().chain(Some(0)).collect()
}

#[cfg(windows)]
fn protect_bytes(bytes: &[u8]) -> Result<Vec<u8>, String> {
    let input = CRYPT_INTEGER_BLOB {
        cbData: bytes.len() as u32,
        pbData: bytes.as_ptr() as *mut u8,
    };
    let mut output = CRYPT_INTEGER_BLOB::default();
    unsafe {
        CryptProtectData(
            &input,
            windows_core::w!("Jarvis OS desktop secrets"),
            None,
            None,
            None,
            CRYPTPROTECT_UI_FORBIDDEN,
            &mut output,
        )
    }
    .map_err(|error| format!("Windows DPAPI 无法保护配置：{error}"))?;
    copy_and_free_blob(output)
}

#[cfg(windows)]
fn unprotect_bytes(bytes: &[u8]) -> Result<Vec<u8>, String> {
    let input = CRYPT_INTEGER_BLOB {
        cbData: bytes.len() as u32,
        pbData: bytes.as_ptr() as *mut u8,
    };
    let mut output = CRYPT_INTEGER_BLOB::default();
    unsafe {
        CryptUnprotectData(&input, None, None, None, None, CRYPTPROTECT_UI_FORBIDDEN, &mut output)
    }
    .map_err(|error| format!("Windows DPAPI 无法解锁配置：{error}"))?;
    copy_and_free_blob(output)
}

#[cfg(windows)]
fn copy_and_free_blob(blob: CRYPT_INTEGER_BLOB) -> Result<Vec<u8>, String> {
    if blob.pbData.is_null() {
        return Err("Windows DPAPI 返回了空配置。".to_owned());
    }
    let result = unsafe { std::slice::from_raw_parts(blob.pbData, blob.cbData as usize) }.to_vec();
    unsafe {
        let _ = LocalFree(Some(HLOCAL(blob.pbData.cast())));
    }
    Ok(result)
}

#[cfg(not(windows))]
fn protect_bytes(_bytes: &[u8]) -> Result<Vec<u8>, String> {
    Err("受保护配置只在 Windows 桌面版可用。".to_owned())
}

#[cfg(not(windows))]
fn unprotect_bytes(_bytes: &[u8]) -> Result<Vec<u8>, String> {
    Err("受保护配置只在 Windows 桌面版可用。".to_owned())
}

pub fn user_data_root() -> Result<PathBuf, String> {
    if let Some(root) = env::var_os("JARVIS_DATA_ROOT") {
        return Ok(PathBuf::from(root));
    }
    env::var_os("LOCALAPPDATA")
        .map(PathBuf::from)
        .map(|path| path.join("Jarvis OS"))
        .ok_or_else(|| "Windows LOCALAPPDATA 用户目录不可用。".to_owned())
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

    fn fixture() -> PathBuf {
        let mut random = [0_u8; 8];
        rand::rng().fill_bytes(&mut random);
        let suffix = random
            .iter()
            .map(|byte| format!("{byte:02x}"))
            .collect::<String>();
        let path = env::temp_dir().join(format!("jarvis-config-test-{}-{suffix}", now_ms()));
        fs::create_dir_all(&path).expect("fixture");
        path
    }

    #[test]
    fn preview_redacts_secrets_and_ignores_desktop_managed_values() {
        let root = fixture();
        let store = DesktopConfigStore::open(root.clone()).expect("store");
        let preview = store
            .preview_legacy(
                "legacy.env",
                "MIMO_API_KEY=secret-value\nAPI_PORT=8000\nOLLAMA_MODEL=qwen3\n",
            )
            .expect("preview");
        assert_eq!(preview.fields.len(), 2);
        let secret = preview
            .fields
            .iter()
            .find(|field| field.name == "MIMO_API_KEY")
            .expect("secret field");
        assert!(secret.sensitive);
        assert!(!secret.display_value.contains("secret-value"));
        assert_eq!(preview.ignored_fields, vec!["API_PORT"]);
        let _ = fs::remove_dir_all(root);
    }

    #[test]
    fn import_splits_plain_and_protected_values_without_touching_source() {
        let root = fixture();
        let source = root.join("legacy.env");
        let original = b"MIMO_API_KEY=private-key\nOLLAMA_MODEL=qwen3:4b\n";
        fs::write(&source, original).expect("source");
        let store = DesktopConfigStore::open(root.join("桌面 数据")).expect("store");
        store
            .preview_legacy(
                ".env",
                std::str::from_utf8(original).expect("utf8 source"),
            )
            .expect("preview");
        let result = store
            .apply_pending(&["MIMO_API_KEY".to_owned(), "OLLAMA_MODEL".to_owned()])
            .expect("apply");
        assert_eq!(result.protected_fields, 1);
        assert_eq!(result.ordinary_fields, 1);
        assert_eq!(fs::read(&source).expect("source after"), original);
        let plain = fs::read_to_string(store.config_path()).expect("plain config");
        assert!(plain.contains("OLLAMA_MODEL=qwen3:4b"));
        assert!(!plain.contains("private-key"));
        let protected_on_disk = fs::read(store.protected_path()).expect("protected bytes");
        assert!(!String::from_utf8_lossy(&protected_on_disk).contains("private-key"));
        assert_eq!(
            store.load_environment().expect("environment").get("MIMO_API_KEY"),
            Some(&"private-key".to_owned())
        );
        assert!(!store.status().first_run);
        let _ = fs::remove_dir_all(root);
    }

    #[test]
    fn cancelling_preview_leaves_install_config_unchanged() {
        let root = fixture();
        let store = DesktopConfigStore::open(root.clone()).expect("store");
        let before = fs::read(store.protected_path()).expect("protected before");
        store
            .preview_legacy(".env", "DEEPSEEK_API_KEY=do-not-import")
            .expect("preview");
        store.cancel_pending().expect("cancel");
        assert_eq!(fs::read(store.protected_path()).expect("protected after"), before);
        assert!(store.status().first_run);
        let _ = fs::remove_dir_all(root);
    }

    #[test]
    fn dpapi_round_trip_is_bound_to_current_windows_user() {
        let plaintext = b"current-user-secret";
        let protected = protect_bytes(plaintext).expect("protect");
        assert_ne!(protected, plaintext);
        assert_eq!(unprotect_bytes(&protected).expect("unprotect"), plaintext);
    }
}
