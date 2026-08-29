use serde::{Deserialize, Serialize};
use std::fs::{self, OpenOptions};
use std::io::Write;
use std::path::{Path, PathBuf};
use std::sync::Mutex;
use std::time::{SystemTime, UNIX_EPOCH};

const MAX_DURATION_MS: u64 = 60 * 60 * 1000;
const MAX_LOG_BYTES: u64 = 5 * 1024 * 1024;
const LOG_BACKUPS: usize = 3;

#[derive(Clone, Copy, Debug, Deserialize, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ReliabilityEventKind {
    Startup,
    StartupStage,
    QuickOpen,
    QuickSend,
    QuickContinue,
    NotificationOpen,
    NotificationSnooze,
    FilePreview,
    FileConfirm,
    FileReject,
    FileAnalyze,
    VoicePermission,
    VoiceModel,
    VoiceTranscription,
    SupervisorRestart,
    SupervisorState,
    UpdateCheck,
    UpdateDownload,
    UpdateInstall,
    UpdateRollback,
    DiagnosticExport,
}

#[derive(Clone, Copy, Debug, Deserialize, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ReliabilityOutcome {
    Attempted,
    Succeeded,
    Failed,
    Cancelled,
    Degraded,
    Blocked,
    NotConfigured,
}

#[derive(Clone, Copy, Debug, Deserialize, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ReliabilityStage {
    Preflight,
    Database,
    Migration,
    Core,
    Companion,
    Interface,
}

#[derive(Clone, Copy, Debug, Deserialize, PartialEq)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct ReliabilityEventInput {
    pub kind: ReliabilityEventKind,
    pub outcome: ReliabilityOutcome,
    pub duration_ms: Option<u64>,
    pub stage: Option<ReliabilityStage>,
}

#[derive(Debug, Serialize)]
struct ReliabilityEvent {
    schema_version: u8,
    observed_at_ms: u128,
    app_version: &'static str,
    kind: ReliabilityEventKind,
    outcome: ReliabilityOutcome,
    #[serde(skip_serializing_if = "Option::is_none")]
    duration_ms: Option<u64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    stage: Option<ReliabilityStage>,
}

pub struct ReliabilityLedger {
    path: PathBuf,
    write_lock: Mutex<()>,
}

impl ReliabilityLedger {
    pub fn new(data_root: &Path) -> Self {
        Self {
            path: data_root.join("observations").join("desktop-reliability.jsonl"),
            write_lock: Mutex::new(()),
        }
    }

    pub fn record(&self, input: ReliabilityEventInput) -> Result<(), String> {
        if input.duration_ms.is_some_and(|value| value > MAX_DURATION_MS) {
            return Err("可靠性指标耗时超出允许范围。".to_owned());
        }
        let _guard = self
            .write_lock
            .lock()
            .map_err(|_| "可靠性指标写入锁不可用。".to_owned())?;
        if let Some(parent) = self.path.parent() {
            fs::create_dir_all(parent).map_err(|_| "无法创建可靠性指标目录。".to_owned())?;
        }
        rotate_if_needed(&self.path)?;
        let event = ReliabilityEvent {
            schema_version: 1,
            observed_at_ms: now_ms(),
            app_version: env!("CARGO_PKG_VERSION"),
            kind: input.kind,
            outcome: input.outcome,
            duration_ms: input.duration_ms,
            stage: input.stage,
        };
        let mut bytes = serde_json::to_vec(&event)
            .map_err(|_| "无法序列化可靠性指标。".to_owned())?;
        bytes.push(b'\n');
        OpenOptions::new()
            .create(true)
            .append(true)
            .open(&self.path)
            .and_then(|mut file| file.write_all(&bytes))
            .map_err(|_| "无法写入可靠性指标。".to_owned())
    }
}

fn rotate_if_needed(path: &Path) -> Result<(), String> {
    if path.metadata().map(|item| item.len()).unwrap_or_default() < MAX_LOG_BYTES {
        return Ok(());
    }
    for index in (1..=LOG_BACKUPS).rev() {
        let source = if index == 1 {
            path.to_path_buf()
        } else {
            path.with_extension(format!("jsonl.{}", index - 1))
        };
        let destination = path.with_extension(format!("jsonl.{index}"));
        if source.is_file() {
            if destination.is_file() {
                fs::remove_file(&destination)
                    .map_err(|_| "无法轮转可靠性指标备份。".to_owned())?;
            }
            fs::rename(source, destination)
                .map_err(|_| "无法轮转可靠性指标文件。".to_owned())?;
        }
    }
    Ok(())
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

    #[test]
    fn ledger_records_only_closed_content_free_fields() {
        let root = std::env::temp_dir().join(format!("jarvis-ledger-{}", now_ms()));
        let ledger = ReliabilityLedger::new(&root);
        ledger
            .record(ReliabilityEventInput {
                kind: ReliabilityEventKind::QuickSend,
                outcome: ReliabilityOutcome::Succeeded,
                duration_ms: Some(123),
                stage: None,
            })
            .expect("record reliability event");

        let text = fs::read_to_string(&ledger.path).expect("ledger text");
        let value: serde_json::Value = serde_json::from_str(text.trim()).expect("ledger json");
        let keys = value.as_object().expect("event object").keys().cloned().collect::<Vec<_>>();
        assert_eq!(
            keys,
            vec!["app_version", "duration_ms", "kind", "observed_at_ms", "outcome", "schema_version"]
        );
        assert_eq!(value["kind"], "quick_send");
        assert!(!text.contains("prompt"));
        assert!(!text.contains("content"));
        let _ = fs::remove_dir_all(root);
    }

    #[test]
    fn ledger_rejects_unbounded_duration() {
        let ledger = ReliabilityLedger::new(Path::new("unused"));
        assert!(ledger
            .record(ReliabilityEventInput {
                kind: ReliabilityEventKind::Startup,
                outcome: ReliabilityOutcome::Failed,
                duration_ms: Some(MAX_DURATION_MS + 1),
                stage: None,
            })
            .is_err());
    }
}
