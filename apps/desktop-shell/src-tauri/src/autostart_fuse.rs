use serde::{Deserialize, Serialize};
use std::fs;
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

const FAILURE_LIMIT: u32 = 3;
const STATE_FILE_NAME: &str = "autostart-fuse.json";

#[derive(Clone, Debug, Default, Deserialize, Serialize)]
struct FuseState {
    schema_version: u32,
    consecutive_failures: u32,
    tripped: bool,
    updated_at_ms: u128,
}

#[derive(Clone, Debug, PartialEq)]
pub struct AutostartFailureOutcome {
    pub consecutive_failures: u32,
    pub newly_tripped: bool,
}

pub fn record_failure(data_root: &Path) -> Result<AutostartFailureOutcome, String> {
    let path = state_path(data_root);
    let mut state = read_state(&path)?;
    let was_tripped = state.tripped;
    state.schema_version = 1;
    state.consecutive_failures = state.consecutive_failures.saturating_add(1);
    state.tripped = state.consecutive_failures >= FAILURE_LIMIT;
    state.updated_at_ms = now_ms();
    write_state(&path, &state)?;
    Ok(AutostartFailureOutcome {
        consecutive_failures: state.consecutive_failures,
        newly_tripped: state.tripped && !was_tripped,
    })
}

pub fn clear(data_root: &Path) -> Result<(), String> {
    let path = state_path(data_root);
    match fs::remove_file(path) {
        Ok(()) => Ok(()),
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => Ok(()),
        Err(error) => Err(format!("无法清除开机启动熔断记录：{error}")),
    }
}

fn state_path(data_root: &Path) -> PathBuf {
    data_root.join("config").join(STATE_FILE_NAME)
}

fn read_state(path: &Path) -> Result<FuseState, String> {
    if !path.is_file() {
        return Ok(FuseState::default());
    }
    let bytes = fs::read(path).map_err(|error| format!("无法读取开机启动熔断记录：{error}"))?;
    let state: FuseState = serde_json::from_slice(&bytes)
        .map_err(|error| format!("开机启动熔断记录格式无效：{error}"))?;
    if state.schema_version != 1 {
        return Err("开机启动熔断记录版本不受支持。".to_owned());
    }
    Ok(state)
}

fn write_state(path: &Path, state: &FuseState) -> Result<(), String> {
    let directory = path
        .parent()
        .ok_or_else(|| "开机启动熔断记录目录无效。".to_owned())?;
    fs::create_dir_all(directory)
        .map_err(|error| format!("无法准备开机启动熔断目录：{error}"))?;
    let temporary = path.with_extension("json.partial");
    fs::write(
        &temporary,
        serde_json::to_vec_pretty(state)
            .map_err(|error| format!("无法序列化开机启动熔断记录：{error}"))?,
    )
    .map_err(|error| format!("无法写入开机启动熔断记录：{error}"))?;
    fs::rename(&temporary, path)
        .map_err(|error| format!("无法提交开机启动熔断记录：{error}"))
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
    use std::sync::atomic::{AtomicU64, Ordering};

    static FIXTURE_ID: AtomicU64 = AtomicU64::new(0);

    fn fixture() -> PathBuf {
        let path = std::env::temp_dir().join(format!(
            "jarvis-autostart-fuse-{}-{}-{}",
            std::process::id(),
            now_ms(),
            FIXTURE_ID.fetch_add(1, Ordering::Relaxed),
        ));
        fs::create_dir_all(&path).expect("fixture");
        path
    }

    #[test]
    fn third_consecutive_failure_trips_once_and_clear_resets() {
        let root = fixture();
        for expected in 1..=2 {
            let outcome = record_failure(&root).expect("record failure");
            assert_eq!(outcome.consecutive_failures, expected);
            assert!(!outcome.newly_tripped);
        }
        let third = record_failure(&root).expect("third failure");
        assert_eq!(third.consecutive_failures, 3);
        assert!(third.newly_tripped);
        let fourth = record_failure(&root).expect("fourth failure");
        assert!(!fourth.newly_tripped);
        clear(&root).expect("clear");
        let reset = record_failure(&root).expect("failure after clear");
        assert_eq!(reset.consecutive_failures, 1);
        assert!(!reset.newly_tripped);
    }

    #[test]
    fn corrupt_state_fails_closed_without_being_overwritten() {
        let root = fixture();
        let path = state_path(&root);
        fs::create_dir_all(path.parent().expect("parent")).expect("directory");
        fs::write(&path, b"not-json").expect("corrupt state");
        assert!(record_failure(&root).is_err());
        assert_eq!(fs::read(&path).expect("preserved"), b"not-json");
    }
}
