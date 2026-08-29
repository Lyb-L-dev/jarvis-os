use std::sync::atomic::{AtomicBool, AtomicU32, Ordering};
use std::sync::{Arc, Mutex};

#[cfg(windows)]
use tauri::Manager;

const DEFAULT_QUICK_SHORTCUT: &str = "Ctrl+Alt+Space";
const DEFAULT_VOICE_SHORTCUT: &str = "Ctrl+Alt+V";

fn shortcut_binding(label: &str, voice: bool) -> Option<(u32, u32)> {
    let binding = match label {
        "Ctrl+Alt+Space" => (0x0002 | 0x0001 | 0x4000, 0x20),
        "Ctrl+Shift+Space" => (0x0002 | 0x0004 | 0x4000, 0x20),
        "Alt+Shift+Space" => (0x0001 | 0x0004 | 0x4000, 0x20),
        "Ctrl+Alt+V" => (0x0002 | 0x0001 | 0x4000, 0x56),
        "Ctrl+Shift+V" => (0x0002 | 0x0004 | 0x4000, 0x56),
        "Alt+Shift+V" => (0x0001 | 0x0004 | 0x4000, 0x56),
        _ => return None,
    };
    let is_voice = binding.1 == 0x56;
    (is_voice == voice).then_some(binding)
}

pub fn quick_shortcut_options() -> Vec<String> {
    ["Ctrl+Alt+Space", "Ctrl+Shift+Space", "Alt+Shift+Space"]
        .into_iter()
        .map(str::to_owned)
        .collect()
}

pub fn voice_shortcut_options() -> Vec<String> {
    ["Ctrl+Alt+V", "Ctrl+Shift+V", "Alt+Shift+V"]
        .into_iter()
        .map(str::to_owned)
        .collect()
}

#[derive(Clone)]
pub struct QuickShortcutController {
    quick_registered: Arc<AtomicBool>,
    voice_registered: Arc<AtomicBool>,
    quick_modifiers: Arc<AtomicU32>,
    quick_key: Arc<AtomicU32>,
    voice_modifiers: Arc<AtomicU32>,
    voice_key: Arc<AtomicU32>,
    quick_label: Arc<Mutex<String>>,
    voice_label: Arc<Mutex<String>>,
}

impl QuickShortcutController {
    pub fn start(app: tauri::AppHandle, quick_label: &str, voice_label: &str) -> Result<Self, String> {
        let normalized_quick_label = shortcut_binding(quick_label, false)
            .map(|_| quick_label)
            .unwrap_or(DEFAULT_QUICK_SHORTCUT);
        let normalized_voice_label = shortcut_binding(voice_label, true)
            .map(|_| voice_label)
            .unwrap_or(DEFAULT_VOICE_SHORTCUT);
        let quick = shortcut_binding(normalized_quick_label, false)
            .ok_or_else(|| "默认快速提问快捷键无效。".to_owned())?;
        let voice = shortcut_binding(normalized_voice_label, true)
            .ok_or_else(|| "默认按住说话快捷键无效。".to_owned())?;
        let controller = Self {
            quick_registered: Arc::new(AtomicBool::new(false)),
            voice_registered: Arc::new(AtomicBool::new(false)),
            quick_modifiers: Arc::new(AtomicU32::new(quick.0)),
            quick_key: Arc::new(AtomicU32::new(quick.1)),
            voice_modifiers: Arc::new(AtomicU32::new(voice.0)),
            voice_key: Arc::new(AtomicU32::new(voice.1)),
            quick_label: Arc::new(Mutex::new(normalized_quick_label.to_owned())),
            voice_label: Arc::new(Mutex::new(normalized_voice_label.to_owned())),
        };
        #[cfg(windows)]
        spawn_shortcut_loop(app, controller.clone());
        #[cfg(not(windows))]
        let _ = app;
        Ok(controller)
    }

    pub fn is_quick_registered(&self) -> bool {
        self.quick_registered.load(Ordering::SeqCst)
    }

    pub fn is_voice_registered(&self) -> bool {
        self.voice_registered.load(Ordering::SeqCst)
    }

    pub fn quick_label(&self) -> String {
        self.quick_label.lock().map(|value| value.clone()).unwrap_or_else(|_| DEFAULT_QUICK_SHORTCUT.to_owned())
    }

    pub fn voice_label(&self) -> String {
        self.voice_label.lock().map(|value| value.clone()).unwrap_or_else(|_| DEFAULT_VOICE_SHORTCUT.to_owned())
    }

    pub fn set_quick_enabled(&self, enabled: bool) -> Result<(), String> {
        self.set_enabled(enabled, false)
    }

    pub fn set_voice_enabled(&self, enabled: bool) -> Result<(), String> {
        self.set_enabled(enabled, true)
    }

    fn set_enabled(&self, enabled: bool, voice: bool) -> Result<(), String> {
        #[cfg(windows)]
        {
            let message = if voice && enabled {
                VOICE_ENABLE_MESSAGE
            } else if voice {
                VOICE_DISABLE_MESSAGE
            } else if enabled {
                QUICK_ENABLE_MESSAGE
            } else {
                QUICK_DISABLE_MESSAGE
            };
            post_shortcut_message(message)?;
            for _ in 0..20 {
                let registered = if voice { self.is_voice_registered() } else { self.is_quick_registered() };
                if registered == enabled {
                    return Ok(());
                }
                std::thread::sleep(std::time::Duration::from_millis(25));
            }
            return Err(if enabled {
                format!("快捷键 {} 已被其他应用占用或无法注册。", if voice { self.voice_label() } else { self.quick_label() })
            } else {
                "无法关闭 Jarvis 全局快捷键。".to_owned()
            });
        }
        #[cfg(not(windows))]
        {
            if voice { self.voice_registered.store(enabled, Ordering::SeqCst) } else { self.quick_registered.store(enabled, Ordering::SeqCst) };
            Ok(())
        }
    }

    pub fn set_binding(&self, label: &str, voice: bool) -> Result<(), String> {
        let (modifiers, key) = shortcut_binding(label, voice)
            .ok_or_else(|| "快捷键不在 Jarvis 审核白名单中。".to_owned())?;
        let was_enabled = if voice { self.is_voice_registered() } else { self.is_quick_registered() };
        let old_label = if voice { self.voice_label() } else { self.quick_label() };
        let (old_modifiers, old_key) = shortcut_binding(&old_label, voice)
            .ok_or_else(|| "当前快捷键配置无效。".to_owned())?;
        if was_enabled { self.set_enabled(false, voice)?; }
        let (modifier_target, key_target, label_target) = if voice {
            (&self.voice_modifiers, &self.voice_key, &self.voice_label)
        } else {
            (&self.quick_modifiers, &self.quick_key, &self.quick_label)
        };
        modifier_target.store(modifiers, Ordering::SeqCst);
        key_target.store(key, Ordering::SeqCst);
        if let Ok(mut value) = label_target.lock() { *value = label.to_owned(); }
        if was_enabled {
            if let Err(error) = self.set_enabled(true, voice) {
                modifier_target.store(old_modifiers, Ordering::SeqCst);
                key_target.store(old_key, Ordering::SeqCst);
                if let Ok(mut value) = label_target.lock() { *value = old_label; }
                let _ = self.set_enabled(true, voice);
                return Err(error);
            }
        }
        Ok(())
    }
}

#[cfg(windows)]
const QUICK_SHORTCUT_ID: i32 = 0x4A56;
#[cfg(windows)]
const VOICE_SHORTCUT_ID: i32 = 0x4A57;
#[cfg(windows)]
const QUICK_ENABLE_MESSAGE: u32 = windows::Win32::UI::WindowsAndMessaging::WM_APP + 31;
#[cfg(windows)]
const QUICK_DISABLE_MESSAGE: u32 = windows::Win32::UI::WindowsAndMessaging::WM_APP + 32;
#[cfg(windows)]
const VOICE_ENABLE_MESSAGE: u32 = windows::Win32::UI::WindowsAndMessaging::WM_APP + 33;
#[cfg(windows)]
const VOICE_DISABLE_MESSAGE: u32 = windows::Win32::UI::WindowsAndMessaging::WM_APP + 34;
#[cfg(windows)]
const USER_RUN_KEY: &str = "Software\\Microsoft\\Windows\\CurrentVersion\\Run";
#[cfg(windows)]
static SHORTCUT_THREAD_ID: std::sync::OnceLock<u32> = std::sync::OnceLock::new();

#[cfg(windows)]
fn spawn_shortcut_loop(app: tauri::AppHandle, controller: QuickShortcutController) {
    std::thread::spawn(move || unsafe {
        use windows::Win32::System::Threading::GetCurrentThreadId;
        use windows::Win32::UI::Input::KeyboardAndMouse::{
            GetAsyncKeyState, RegisterHotKey, UnregisterHotKey, HOT_KEY_MODIFIERS,
        };
        use windows::Win32::UI::WindowsAndMessaging::{GetMessageW, MSG, WM_HOTKEY};

        let thread_id = GetCurrentThreadId();
        let _ = SHORTCUT_THREAD_ID.set(thread_id);
        let mut message = MSG::default();
        // Create the thread message queue before callers can post enable/disable requests.
        let _ = windows::Win32::UI::WindowsAndMessaging::PeekMessageW(
            &mut message,
            None,
            0,
            0,
            windows::Win32::UI::WindowsAndMessaging::PEEK_MESSAGE_REMOVE_TYPE(0),
        );
        while GetMessageW(&mut message, None, 0, 0).as_bool() {
            match message.message {
                QUICK_ENABLE_MESSAGE => {
                    let result = RegisterHotKey(
                        None,
                        QUICK_SHORTCUT_ID,
                        HOT_KEY_MODIFIERS(controller.quick_modifiers.load(Ordering::SeqCst)),
                        controller.quick_key.load(Ordering::SeqCst),
                    );
                    controller.quick_registered.store(result.is_ok(), Ordering::SeqCst);
                }
                QUICK_DISABLE_MESSAGE => {
                    let _ = UnregisterHotKey(None, QUICK_SHORTCUT_ID);
                    controller.quick_registered.store(false, Ordering::SeqCst);
                }
                VOICE_ENABLE_MESSAGE => {
                    let result = RegisterHotKey(
                        None,
                        VOICE_SHORTCUT_ID,
                        HOT_KEY_MODIFIERS(controller.voice_modifiers.load(Ordering::SeqCst)),
                        controller.voice_key.load(Ordering::SeqCst),
                    );
                    controller.voice_registered.store(result.is_ok(), Ordering::SeqCst);
                }
                VOICE_DISABLE_MESSAGE => {
                    let _ = UnregisterHotKey(None, VOICE_SHORTCUT_ID);
                    controller.voice_registered.store(false, Ordering::SeqCst);
                }
                WM_HOTKEY if message.wParam.0 == QUICK_SHORTCUT_ID as usize => {
                    let _ = super::show_quick_window(&app);
                }
                WM_HOTKEY if message.wParam.0 == VOICE_SHORTCUT_ID as usize => {
                    let _ = super::show_quick_window(&app);
                    if let Some(window) = app.get_webview_window("quick") {
                        let _ = window.eval("window.dispatchEvent(new Event('jarvis:quick-voice-start'));");
                        let stop_window = window.clone();
                        let key = controller.voice_key.load(Ordering::SeqCst) as i32;
                        std::thread::spawn(move || {
                            while GetAsyncKeyState(key) < 0 {
                                std::thread::sleep(std::time::Duration::from_millis(20));
                            }
                            let _ = stop_window.eval("window.dispatchEvent(new Event('jarvis:quick-voice-stop'));");
                        });
                    }
                }
                _ => {}
            }
        }
        let _ = UnregisterHotKey(None, QUICK_SHORTCUT_ID);
        let _ = UnregisterHotKey(None, VOICE_SHORTCUT_ID);
        controller.quick_registered.store(false, Ordering::SeqCst);
        controller.voice_registered.store(false, Ordering::SeqCst);
    });
}

#[cfg(windows)]
fn post_shortcut_message(message: u32) -> Result<(), String> {
    use windows::Win32::UI::WindowsAndMessaging::PostThreadMessageW;
    use windows::Win32::Foundation::{LPARAM, WPARAM};

    for _ in 0..20 {
        if let Some(thread_id) = SHORTCUT_THREAD_ID.get().copied() {
            unsafe { PostThreadMessageW(thread_id, message, WPARAM(0), LPARAM(0)) }
                .map_err(|error| error.to_string())?;
            return Ok(());
        }
        std::thread::sleep(std::time::Duration::from_millis(25));
    }
    Err("Jarvis 快捷键服务尚未就绪。".to_owned())
}

pub fn autostart_enabled() -> Result<bool, String> {
    #[cfg(windows)]
    {
        return registry_value_exists(
            windows::Win32::System::Registry::HKEY_CURRENT_USER,
            USER_RUN_KEY,
            "Jarvis OS",
        );
    }
    #[cfg(not(windows))]
    Ok(false)
}

pub fn set_autostart(enabled: bool) -> Result<(), String> {
    #[cfg(windows)]
    {
        let value = format!("\"{}\" --autostart", executable_path()?.display());
        return set_registry_string(
            windows::Win32::System::Registry::HKEY_CURRENT_USER,
            USER_RUN_KEY,
            "Jarvis OS",
            enabled.then_some(value.as_str()),
        );
    }
    #[cfg(not(windows))]
    {
        let _ = enabled;
        Ok(())
    }
}

pub fn register_protocol_handler() -> Result<(), String> {
    #[cfg(windows)]
    {
        let executable = executable_path()?;
        let command = format!("\"{}\" \"%1\"", executable.display());
        set_registry_string(
            windows::Win32::System::Registry::HKEY_CURRENT_USER,
            "Software\\Classes\\jarvis",
            "",
            Some("URL:Jarvis OS Protocol"),
        )?;
        set_registry_string(
            windows::Win32::System::Registry::HKEY_CURRENT_USER,
            "Software\\Classes\\jarvis",
            "URL Protocol",
            Some(""),
        )?;
        set_registry_string(
            windows::Win32::System::Registry::HKEY_CURRENT_USER,
            "Software\\Classes\\jarvis\\shell\\open\\command",
            "",
            Some(&command),
        )?;
    }
    Ok(())
}

pub fn open_with_enabled() -> Result<bool, String> {
    #[cfg(windows)]
    {
        return registry_value_exists(
            windows::Win32::System::Registry::HKEY_CURRENT_USER,
            "Software\\Classes\\.md\\OpenWithProgids",
            "JarvisOS.Text",
        );
    }
    #[cfg(not(windows))]
    Ok(false)
}

pub fn set_open_with_enabled(enabled: bool) -> Result<(), String> {
    #[cfg(windows)]
    {
        if enabled {
            let executable = executable_path()?;
            let command = format!("\"{}\" \"%1\"", executable.display());
            register_open_with(".md", &command)?;
            register_open_with(".txt", &command)?;
        } else {
            delete_registry_tree("Software\\Classes\\JarvisOS.Text")?;
            set_registry_string(
                windows::Win32::System::Registry::HKEY_CURRENT_USER,
                "Software\\Classes\\.md\\OpenWithProgids",
                "JarvisOS.Text",
                None,
            )?;
            set_registry_string(
                windows::Win32::System::Registry::HKEY_CURRENT_USER,
                "Software\\Classes\\.txt\\OpenWithProgids",
                "JarvisOS.Text",
                None,
            )?;
        }
    }
    Ok(())
}

pub fn unregister_desktop_integrations() -> Result<(), String> {
    #[cfg(windows)]
    {
        set_autostart(false)?;
        delete_registry_tree("Software\\Classes\\jarvis")?;
        set_open_with_enabled(false)?;
    }
    Ok(())
}

#[cfg(windows)]
fn register_open_with(extension: &str, command: &str) -> Result<(), String> {
    set_registry_string(
        windows::Win32::System::Registry::HKEY_CURRENT_USER,
        &format!("Software\\Classes\\{extension}\\OpenWithProgids"),
        "JarvisOS.Text",
        Some(""),
    )?;
    set_registry_string(
        windows::Win32::System::Registry::HKEY_CURRENT_USER,
        "Software\\Classes\\JarvisOS.Text",
        "",
        Some("Jarvis OS controlled text handoff"),
    )?;
    set_registry_string(
        windows::Win32::System::Registry::HKEY_CURRENT_USER,
        "Software\\Classes\\JarvisOS.Text\\shell\\open\\command",
        "",
        Some(command),
    )
}

#[cfg(windows)]
fn delete_registry_tree(subkey: &str) -> Result<(), String> {
    use windows::Win32::Foundation::{ERROR_FILE_NOT_FOUND, ERROR_PATH_NOT_FOUND, ERROR_SUCCESS};
    use windows::Win32::System::Registry::{RegDeleteTreeW, HKEY_CURRENT_USER};

    let subkey = wide(subkey);
    let result = unsafe {
        RegDeleteTreeW(
            HKEY_CURRENT_USER,
            windows_core::PCWSTR(subkey.as_ptr()),
        )
    };
    if matches!(result, ERROR_SUCCESS | ERROR_FILE_NOT_FOUND | ERROR_PATH_NOT_FOUND) {
        Ok(())
    } else {
        Err(format!("无法清理 Windows 用户注册表项：错误码 {}", result.0))
    }
}

#[cfg(windows)]
fn executable_path() -> Result<std::path::PathBuf, String> {
    std::env::current_exe().map_err(|error| format!("无法确定 Jarvis 程序路径：{error}"))
}

#[cfg(windows)]
fn registry_value_exists(
    root: windows::Win32::System::Registry::HKEY,
    subkey: &str,
    name: &str,
) -> Result<bool, String> {
    use windows::Win32::Foundation::{ERROR_FILE_NOT_FOUND, ERROR_SUCCESS};
    use windows::Win32::System::Registry::{RegGetValueW, RRF_RT_REG_SZ};

    let subkey = wide(subkey);
    let name = wide(name);
    let result = unsafe {
        RegGetValueW(
            root,
            windows_core::PCWSTR(subkey.as_ptr()),
            windows_core::PCWSTR(name.as_ptr()),
            RRF_RT_REG_SZ,
            None,
            None,
            None,
        )
    };
    if result == ERROR_SUCCESS {
        Ok(true)
    } else if result == ERROR_FILE_NOT_FOUND {
        Ok(false)
    } else {
        Err(format!("无法读取 Windows 启动项：错误码 {}", result.0))
    }
}

#[cfg(windows)]
fn set_registry_string(
    root: windows::Win32::System::Registry::HKEY,
    subkey: &str,
    name: &str,
    value: Option<&str>,
) -> Result<(), String> {
    use windows::Win32::Foundation::{ERROR_FILE_NOT_FOUND, ERROR_SUCCESS};
    use windows::Win32::System::Registry::{
        RegCloseKey, RegCreateKeyExW, RegDeleteValueW, RegSetValueExW, HKEY, KEY_SET_VALUE,
        REG_OPTION_NON_VOLATILE, REG_SZ,
    };

    let subkey = wide(subkey);
    let name = wide(name);
    let mut key = HKEY::default();
    let create_result = unsafe {
        RegCreateKeyExW(
            root,
            windows_core::PCWSTR(subkey.as_ptr()),
            None,
            windows_core::PWSTR::null(),
            REG_OPTION_NON_VOLATILE,
            KEY_SET_VALUE,
            None,
            &mut key,
            None,
        )
    };
    if create_result != ERROR_SUCCESS {
        return Err(format!("无法打开 Windows 用户注册表项：错误码 {}", create_result.0));
    }
    let result = if let Some(value) = value {
        let encoded = wide(value);
        let bytes = unsafe {
            std::slice::from_raw_parts(encoded.as_ptr().cast::<u8>(), encoded.len() * 2)
        };
        unsafe {
            RegSetValueExW(
                key,
                windows_core::PCWSTR(name.as_ptr()),
                None,
                REG_SZ,
                Some(bytes),
            )
        }
    } else {
        unsafe { RegDeleteValueW(key, windows_core::PCWSTR(name.as_ptr())) }
    };
    let _ = unsafe { RegCloseKey(key) };
    if result == ERROR_SUCCESS || (value.is_none() && result == ERROR_FILE_NOT_FOUND) {
        Ok(())
    } else {
        Err(format!("无法更新 Windows 用户注册表项：错误码 {}", result.0))
    }
}

#[cfg(windows)]
fn wide(value: &str) -> Vec<u16> {
    value.encode_utf16().chain(std::iter::once(0)).collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn shortcut_state_defaults_to_disabled() {
        let controller = QuickShortcutController {
            quick_registered: Arc::new(AtomicBool::new(false)),
            voice_registered: Arc::new(AtomicBool::new(false)),
            quick_modifiers: Arc::new(AtomicU32::new(0)),
            quick_key: Arc::new(AtomicU32::new(0)),
            voice_modifiers: Arc::new(AtomicU32::new(0)),
            voice_key: Arc::new(AtomicU32::new(0)),
            quick_label: Arc::new(Mutex::new(DEFAULT_QUICK_SHORTCUT.to_owned())),
            voice_label: Arc::new(Mutex::new(DEFAULT_VOICE_SHORTCUT.to_owned())),
        };
        assert!(!controller.is_quick_registered());
        assert!(!controller.is_voice_registered());
    }

    #[test]
    fn shortcut_bindings_are_closed_sets() {
        for label in quick_shortcut_options() {
            assert!(shortcut_binding(&label, false).is_some());
            assert!(shortcut_binding(&label, true).is_none());
        }
        for label in voice_shortcut_options() {
            assert!(shortcut_binding(&label, true).is_some());
            assert!(shortcut_binding(&label, false).is_none());
        }
        assert!(shortcut_binding("Ctrl+Alt+Delete", false).is_none());
    }
}
