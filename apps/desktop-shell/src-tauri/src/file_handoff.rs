use rand::RngCore;
use serde::Serialize;
#[cfg(test)]
use sha2::{Digest, Sha256};
use std::collections::HashMap;
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::Mutex;
use std::time::{Duration, Instant, SystemTime};

const MAX_FILE_BYTES: u64 = 2 * 1024 * 1024;
const AUTHORIZATION_TTL: Duration = Duration::from_secs(10 * 60);

#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct FileHandoffPreview {
    pub token: String,
    pub name: String,
    pub extension: String,
    pub size_bytes: u64,
    pub source: String,
    pub local_only: bool,
    pub knowledge_write: bool,
    pub expires_in_seconds: u64,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct FileHandoffContent {
    pub name: String,
    pub content: String,
    pub local_only: bool,
    pub knowledge_write: bool,
}

struct AuthorizedFile {
    path: PathBuf,
    size_bytes: u64,
    modified: SystemTime,
    expires_at: Instant,
    name: String,
}

#[derive(Default)]
pub struct FileHandoffStore {
    pending: Mutex<HashMap<String, AuthorizedFile>>,
}

impl FileHandoffStore {
    pub fn preview(
        &self,
        candidate: impl AsRef<Path>,
        source: &str,
    ) -> Result<FileHandoffPreview, String> {
        let path = validate_candidate(candidate.as_ref())?;
        let metadata = fs::metadata(&path)
            .map_err(|error| format!("无法读取文件元数据：{error}"))?;
        let name = path
            .file_name()
            .and_then(|value| value.to_str())
            .ok_or_else(|| "文件名不是有效的 Unicode 文本。".to_owned())?
            .to_owned();
        let extension = normalized_extension(&path)?;
        let modified = metadata
            .modified()
            .map_err(|error| format!("无法确认文件修改时间：{error}"))?;
        let token = authorization_token();
        let authorized = AuthorizedFile {
            path,
            size_bytes: metadata.len(),
            modified,
            expires_at: Instant::now() + AUTHORIZATION_TTL,
            name: name.clone(),
        };
        let mut pending = self
            .pending
            .lock()
            .map_err(|_| "文件授权状态暂时不可用。".to_owned())?;
        pending.clear();
        pending.insert(token.clone(), authorized);
        Ok(FileHandoffPreview {
            token,
            name,
            extension,
            size_bytes: metadata.len(),
            source: source.to_owned(),
            local_only: true,
            knowledge_write: false,
            expires_in_seconds: AUTHORIZATION_TTL.as_secs(),
        })
    }

    pub fn read_confirmed(&self, token: &str) -> Result<FileHandoffContent, String> {
        let authorized = self
            .pending
            .lock()
            .map_err(|_| "文件授权状态暂时不可用。".to_owned())?
            .remove(token)
            .ok_or_else(|| "文件授权不存在或已经使用，请重新选择文件。".to_owned())?;
        if Instant::now() > authorized.expires_at {
            return Err("文件授权已过期，请重新选择文件。".to_owned());
        }
        let path = validate_candidate(&authorized.path)?;
        let metadata = fs::metadata(&path)
            .map_err(|error| format!("确认文件状态失败：{error}"))?;
        let modified = metadata
            .modified()
            .map_err(|error| format!("无法确认文件修改时间：{error}"))?;
        if metadata.len() != authorized.size_bytes || modified != authorized.modified {
            return Err("文件在预览后发生变化，已拒绝读取；请重新选择。".to_owned());
        }
        let bytes = fs::read(&path).map_err(|error| format!("读取文件失败：{error}"))?;
        if bytes.len() as u64 > MAX_FILE_BYTES {
            return Err("文件超过 2 MiB，已拒绝读取。".to_owned());
        }
        let decoded = std::str::from_utf8(&bytes)
            .map_err(|_| "仅支持 UTF-8 或 UTF-8 BOM 编码的文本文件。".to_owned())?;
        let content = decoded.strip_prefix('\u{feff}').unwrap_or(decoded).to_owned();
        Ok(FileHandoffContent {
            name: authorized.name,
            content,
            local_only: true,
            knowledge_write: false,
        })
    }

    pub fn cancel(&self, token: &str) -> Result<(), String> {
        self.pending
            .lock()
            .map_err(|_| "文件授权状态暂时不可用。".to_owned())?
            .remove(token);
        Ok(())
    }
}

fn validate_candidate(candidate: &Path) -> Result<PathBuf, String> {
    let requested_metadata = fs::symlink_metadata(candidate)
        .map_err(|error| format!("无法检查所选文件：{error}"))?;
    if requested_metadata.file_type().is_symlink() {
        return Err("不支持符号链接或快捷方式，请直接选择源文件。".to_owned());
    }
    let path = candidate
        .canonicalize()
        .map_err(|error| format!("无法访问所选文件：{error}"))?;
    let metadata = fs::symlink_metadata(&path)
        .map_err(|error| format!("无法检查所选文件：{error}"))?;
    if !metadata.file_type().is_file() {
        return Err("只支持单个普通文本文件，不支持目录或快捷方式。".to_owned());
    }
    if is_network_path(&path) {
        return Err("V4 暂不读取网络位置中的文件，请先保存到本机。".to_owned());
    }
    normalized_extension(&path)?;
    if metadata.len() > MAX_FILE_BYTES {
        return Err("文件超过 2 MiB，已拒绝读取。".to_owned());
    }
    Ok(path)
}

fn normalized_extension(path: &Path) -> Result<String, String> {
    let extension = path
        .extension()
        .and_then(|value| value.to_str())
        .map(str::to_ascii_lowercase)
        .ok_or_else(|| "文件没有受支持的扩展名。".to_owned())?;
    if !matches!(extension.as_str(), "md" | "txt") {
        return Err("V4 仅支持单个 .md 或 .txt 文件。".to_owned());
    }
    Ok(extension)
}

#[cfg(windows)]
fn is_network_path(path: &Path) -> bool {
    use std::path::{Component, Prefix};
    use windows::Win32::Storage::FileSystem::GetDriveTypeW;

    match path.components().next() {
        Some(Component::Prefix(prefix)) => match prefix.kind() {
            Prefix::UNC(_, _) | Prefix::VerbatimUNC(_, _) => true,
            Prefix::Disk(letter) | Prefix::VerbatimDisk(letter) => {
                let root = format!("{}:\\", letter as char);
                let encoded = root.encode_utf16().chain(std::iter::once(0)).collect::<Vec<_>>();
                unsafe { GetDriveTypeW(windows_core::PCWSTR(encoded.as_ptr())) == 4 }
            }
            _ => false,
        },
        _ => false,
    }
}

#[cfg(not(windows))]
fn is_network_path(_path: &Path) -> bool {
    false
}

fn authorization_token() -> String {
    let mut bytes = [0_u8; 32];
    rand::rng().fill_bytes(&mut bytes);
    bytes.iter().map(|byte| format!("{byte:02x}")).collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn fixture(name: &str, content: &[u8]) -> PathBuf {
        let directory = std::env::temp_dir().join(format!("jarvis-file-handoff-{}", authorization_token()));
        fs::create_dir_all(&directory).expect("create fixture directory");
        let path = directory.join(name);
        fs::write(&path, content).expect("write fixture");
        path
    }

    #[test]
    fn preview_does_not_read_content_and_confirm_is_one_time() {
        let path = fixture("notes.md", b"# private\n");
        let before = fs::metadata(&path).expect("before metadata");
        let before_hash = Sha256::digest(fs::read(&path).expect("before bytes"));
        let store = FileHandoffStore::default();
        let preview = store.preview(&path, "test").expect("preview");
        assert_eq!(preview.name, "notes.md");
        assert!(preview.local_only);
        assert!(!preview.knowledge_write);
        let content = store.read_confirmed(&preview.token).expect("read");
        assert_eq!(content.content, "# private\n");
        let after = fs::metadata(&path).expect("after metadata");
        let after_hash = Sha256::digest(fs::read(&path).expect("after bytes"));
        assert_eq!(before_hash, after_hash);
        assert_eq!(before.modified().expect("before modified"), after.modified().expect("after modified"));
        assert!(store.read_confirmed(&preview.token).is_err());
    }

    #[test]
    fn changed_file_is_rejected_after_preview() {
        let path = fixture("notes.txt", b"before");
        let store = FileHandoffStore::default();
        let preview = store.preview(&path, "test").expect("preview");
        fs::write(&path, b"after-change").expect("change fixture");
        assert!(store.read_confirmed(&preview.token).is_err());
    }

    #[test]
    fn unsupported_extension_is_rejected() {
        let path = fixture("notes.pdf", b"not a pdf");
        let error = FileHandoffStore::default()
            .preview(&path, "test")
            .err()
            .expect("unsupported");
        assert!(error.contains(".md") && error.contains(".txt"));
    }
}
