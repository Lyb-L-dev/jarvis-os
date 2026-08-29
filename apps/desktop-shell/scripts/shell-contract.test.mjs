import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const repositoryRoot = join(root, "..", "..");
const read = (path) => readFile(join(root, path), "utf8");
const readRepository = (path) => readFile(join(repositoryRoot, path), "utf8");

test("the local splash is the only statically declared window", async () => {
  const config = JSON.parse(await read("src-tauri/tauri.conf.json"));
  assert.deepEqual(
    config.app.windows.map(({ label }) => label),
    ["splash"],
  );
  assert.equal(config.app.windows[0].url, "splash/index.html");
  assert.equal(config.build.frontendDist, "../../../.runtime/desktop-dist-ui-v4");
  assert.equal(config.app.withGlobalTauri, true);
});

test("runtime commands are scoped to the local splash", async () => {
  const capability = JSON.parse(
    await read("src-tauri/capabilities/splash.json"),
  );
  assert.deepEqual(capability.windows, ["splash"]);
  assert.equal(capability.remote, undefined);
  assert.ok(capability.permissions.includes("core:event:allow-listen"));
  assert.ok(capability.permissions.includes("core:event:allow-unlisten"));
});

test("the status center has a local-only diagnostic capability", async () => {
  const capability = JSON.parse(
    await read("src-tauri/capabilities/status.json"),
  );
  assert.deepEqual(capability.windows, ["status"]);
  assert.equal(capability.remote, undefined);
  assert.ok(capability.permissions.includes("core:event:allow-listen"));
  assert.ok(capability.permissions.includes("core:event:allow-unlisten"));
});

test("the shell exposes a narrow supervisor command surface", async () => {
  const main = await read("src-tauri/src/main.rs");
  const runtime = await read("src-tauri/src/runtime.rs");
  const commands = [
    ...main.matchAll(/#\[tauri::command\]\s*(?:async\s+)?fn\s+(\w+)/g),
  ].map(
    (match) => match[1],
  );
  assert.deepEqual(commands.sort(), [
    "desktop_config_apply",
    "desktop_config_cancel",
    "desktop_config_complete",
    "desktop_config_preview",
    "desktop_config_status",
    "desktop_delete_user_data",
    "desktop_export_user_data",
    "desktop_file_cancel",
    "desktop_file_read",
    "desktop_open_microphone_settings",
    "desktop_preferences",
    "desktop_record_reliability_event",
    "desktop_set_autostart",
    "desktop_set_close_behavior",
    "desktop_set_open_with",
    "desktop_set_quick_shortcut",
    "desktop_set_shortcut_binding",
    "desktop_set_voice_shortcut",
    "desktop_update_check",
    "desktop_update_download",
    "desktop_update_install",
    "desktop_update_set_activity",
    "desktop_update_set_channel",
    "desktop_update_status",
    "quick_continue_in_main",
    "quick_hide",
    "runtime_diagnostics",
    "runtime_export_diagnostics",
    "runtime_open_logs",
    "runtime_restart_core",
    "runtime_start",
    "runtime_status",
    "runtime_stop",
  ]);
  assert.doesNotMatch(main, /execute_command|shell_command|read_arbitrary_file/);
  assert.match(main, /run_on_main_thread/);
  assert.match(main, /COREWEBVIEW2_PERMISSION_KIND_MICROPHONE/);
  assert.match(main, /WebviewUrl::App\("chat\/index\.html"\.into\(\)\)/);
  assert.match(main, /WebviewUrl::App\("splash\/status\/index\.html"\.into\(\)\)/);
  assert.match(main, /tauri\.localhost/);
  assert.match(main, /COREWEBVIEW2_PERMISSION_STATE_DENY/);
  assert.match(main, /COREWEBVIEW2_PERMISSION_STATE_DEFAULT/);
  assert.doesNotMatch(main, /COREWEBVIEW2_PERMISSION_STATE_ALLOW/);
  assert.match(main, /configure_local_media_permissions_async/);
  assert.match(main, /media permission policy failed closed/);
  assert.match(main, /TrayIconBuilder::with_id\("jarvis-main"\)/);
  assert.match(main, /pause_reminders/);
  assert.match(main, /resume_reminders/);
  assert.match(main, /"PATCH",\s*"\/notifications\/preferences"/);
  assert.match(main, /CloseRequested/);
  assert.match(main, /api\.prevent_close\(\)/);
  assert.match(main, /DESKTOP_CLOSE_HINT_SHOWN/);
  assert.match(main, /jarvis:close-hint/);
  assert.match(main, /request_full_exit/);
  assert.match(main, /argument == "--quit"/);
  assert.match(main, /When no instance is running[\s\S]*argument == "--quit"[\s\S]*app\.handle\(\)\.exit\(0\)/);
  assert.match(main, /with_denylist\(&\["splash"\]\)/);
  assert.doesNotMatch(main, /StateFlags::VISIBLE/);
  assert.match(main, /tauri_plugin_window_state::Builder/);
  assert.match(main, /ensure_window_visible/);
  assert.match(main, /constrain_to_visible_monitor/);
  assert.match(main, /\.on_navigation/);
  assert.match(main, /\.on_new_window/);
  assert.match(runtime, /"app",\s*"Jarvis App"/);
  assert.match(runtime, /"local_voice",\s*"本地语音"/);
  assert.match(runtime, /GET \/api\/v1\/voice\/readiness/);
  assert.match(main, /NewWindowResponse::Deny/);
  assert.match(main, /app\.opener\(\)\.open_url/);
});

test("data deletion is export-gated and restricted to Jarvis-owned storage", async () => {
  const maintenance = await read("src-tauri/src/data_maintenance.rs");
  const settings = await readRepository("apps/web/src/components/desktop-settings.tsx");
  assert.match(maintenance, /DELETE_CONFIRMATION: &str = "删除 Jarvis 本地数据"/);
  assert.match(maintenance, /TICKET_TTL_MS: u128 = 30 \* 60 \* 1000/);
  assert.match(maintenance, /verify_export_manifest\(&manifest_path, &source_root\)/);
  assert.match(maintenance, /if export_directory\.starts_with\(&source_root\)/);
  assert.match(maintenance, /name: jarvis-os/);
  assert.match(maintenance, /jarvis_postgres_data/);
  assert.match(maintenance, /\.args\(\["down", "--volumes", "--remove-orphans"\]\)/);
  assert.match(maintenance, /fs::rename\(&expected_root, &staged_root\)/);
  assert.match(maintenance, /fs::rename\(&staged_root, &expected_root\)/);
  assert.match(maintenance, /fs::remove_dir_all\(&staged_root\)/);
  assert.doesNotMatch(maintenance, /remove_dir_all\(Path::new/);
  assert.match(settings, /desktop_export_user_data/);
  assert.match(settings, /desktop_delete_user_data/);
  assert.match(settings, /window\.confirm/);
  assert.match(settings, /deleteConfirmation !== dataExport\.confirmationPhrase/);
});

test("the updater is signed, host-allowlisted, backup-gated, and rollback-monitored", async () => {
  const updater = await read("src-tauri/src/update.rs");
  const main = await read("src-tauri/src/main.rs");
  const runtime = await read("src-tauri/src/runtime.rs");
  const hooks = await read("src-tauri/windows/installer-hooks.nsh");
  const settings = await readRepository("apps/web/src/components/desktop-settings.tsx");
  assert.match(updater, /BCryptVerifySignature/);
  assert.match(updater, /WinVerifyTrust/);
  assert.match(updater, /objects\.githubusercontent\.com/);
  assert.match(updater, /wait_for_file[\s\S]*Duration::from_secs\(120\)/);
  assert.match(updater, /rollback_installer/);
  assert.match(runtime, /prepare_update_backup/);
  assert.match(runtime, /desktop-update-backup\.ps1/);
  assert.match(hooks, /previous-installer\.exe/);
  assert.match(settings, /desktop_update_install/);
  assert.match(settings, /安装前停止 Sidecar/);
  assert.match(main, /core_update_activity_blocker/);
  assert.match(main, /\/observatory\/overview/);
  assert.match(main, /\/tool-gateway\/executions\?limit=200/);
  assert.doesNotMatch(updater, /Command::new\([^)]*(?:cmd|powershell)/i);
});

test("release tooling separates private keys, Stable signing, and CycloneDX evidence", async () => {
  const keygen = await read("scripts/new-update-signing-key.ps1");
  const envelope = await read("scripts/generate-update-envelope.ps1");
  const sbom = await read("scripts/generate-sbom.ps1");
  const observation = await read("scripts/desktop-observation.ps1");
  const releaseGate = await read("scripts/verify-v4-release-gate.ps1");
  assert.match(keygen, /ProtectedData\]::Protect/);
  assert.match(keygen, /private-key\.dpapi\.json/);
  assert.match(envelope, /development update key cannot sign the Stable channel/);
  assert.match(envelope, /Get-AuthenticodeSignature/);
  assert.match(envelope, /RSASignaturePadding\]::Pkcs1/);
  assert.match(sbom, /CycloneDX/);
  assert.match(sbom, /Cargo\.lock/);
  assert.match(sbom, /pip list --format=json/);
  assert.match(observation, /required time window has not elapsed/);
  assert.match(observation, /issue_severity/);
  assert.match(observation, /samples do not prove the observed app version/);
  assert.match(observation, /installer_sha256/);
  assert.match(observation, /release_manifest_sha256/);
  assert.match(observation, /installed_exe_sha256/);
  assert.match(observation, /installed_manifest_sha256/);
  assert.match(observation, /covered_hour_buckets/);
  assert.match(observation, /Sort-Object -Unique/);
  assert.match(observation, /distinct hourly sample coverage is below 80%/);
  assert.match(releaseGate, /Authenticode signature is not valid/);
  assert.match(releaseGate, /seven-day observation window has not elapsed/);
  assert.match(releaseGate, /observation evidence does not prove the release version/);
  assert.match(releaseGate, /observation evidence is not bound to this exact installer/);
  assert.match(observation, /desktop-reliability\.jsonl/);
  assert.match(observation, /reliability_metrics/);
  assert.match(observation, /Closed event kinds, outcomes and timings only/);
  assert.match(releaseGate, /privacy-safe product reliability metrics are missing/);
});

test("the reliability ledger exposes only closed privacy-safe event fields", async () => {
  const ledger = await read("src-tauri/src/reliability_ledger.rs");
  const web = await readRepository("apps/web/src/lib/desktop-reliability.ts");
  assert.match(ledger, /enum ReliabilityEventKind/);
  assert.match(ledger, /enum ReliabilityOutcome/);
  assert.match(ledger, /deny_unknown_fields/);
  assert.match(ledger, /desktop-reliability\.jsonl/);
  assert.doesNotMatch(ledger, /prompt_text|file_content|voice_content/);
  assert.match(web, /desktop_record_reliability_event/);
});

test("the quick window is local-only and shares the authenticated chat fact source", async () => {
  const capability = JSON.parse(await read("src-tauri/capabilities/quick.json"));
  const script = await read("src-ui/quick/quick.js");
  const html = await read("src-ui/quick/index.html");
  assert.deepEqual(capability.windows, ["quick"]);
  assert.equal(capability.remote, undefined);
  assert.match(script, /SESSION_TTL_MS = 30 \* 60 \* 1000/);
  assert.match(script, /\/chat\/conversations/);
  assert.match(script, /\/chat\/routing\/preview/);
  assert.match(script, /disposition !== "allow_automatically"/);
  assert.match(script, /paid_call_confirmed: false/);
  assert.match(script, /mode = forceLocalMode \? "local" : "standard"/);
  assert.match(script, /MAX_FILE_BYTES = 2 \* 1024 \* 1024/);
  assert.match(script, /TextDecoder\("utf-8", \{ fatal: true \}\)/);
  assert.match(script, /\/voice\/transcriptions/);
  assert.doesNotMatch(script, /innerHTML|outerHTML|insertAdjacentHTML/);
  assert.match(html, /在主窗口继续/);
  assert.doesNotMatch(html, /批准|同意执行/);
});

test("desktop integrations are explicitly reversible", async () => {
  const main = await read("src-tauri/src/main.rs");
  const config = await read("src-tauri/src/config_store.rs");
  const integration = await read("src-tauri/src/windows_integration.rs");
  assert.match(integration, /RegisterHotKey/);
  assert.match(integration, /HOT_KEY_MODIFIERS/);
  assert.match(integration, /快捷键不在 Jarvis 审核白名单中/);
  assert.match(integration, /GetAsyncKeyState/);
  assert.match(integration, /UnregisterHotKey/);
  assert.match(main, /quick_shortcut\.set_quick_enabled\(enabled\)/);
  assert.match(main, /quick_shortcut\.set_voice_enabled\(enabled\)/);
  assert.match(main, /desktop_set_shortcut_binding/);
  assert.match(integration, /set_autostart/);
  assert.match(integration, /RegDeleteValueW/);
  assert.match(main, /handle_activation_uri/);
  assert.match(main, /is_valid_object_id/);
  assert.match(integration, /Software\\\\Classes\\\\jarvis/);
  assert.match(integration, /OpenWithProgids/);
  assert.match(integration, /unregister_desktop_integrations/);
  assert.match(config, /DESKTOP_QUICK_SHORTCUT_ENABLED/);
});

test("file handoff is one-time, local-only and confirmation gated", async () => {
  const handoff = await read("src-tauri/src/file_handoff.rs");
  const main = await read("src-tauri/src/main.rs");
  const dialog = await readRepository("apps/web/src/components/desktop-file-handoff.tsx");
  assert.match(handoff, /MAX_FILE_BYTES: u64 = 2 \* 1024 \* 1024/);
  assert.match(handoff, /pending\.clear\(\)/);
  assert.match(handoff, /\.remove\(token\)/);
  assert.match(handoff, /modified != authorized\.modified/);
  assert.match(handoff, /from_utf8/);
  assert.match(main, /DragDropEvent::Drop/);
  assert.match(main, /activation_file_argument/);
  assert.match(dialog, /desktop_file_read/);
  assert.match(dialog, /localOnly: true/);
  assert.match(dialog, /不上传、不修改源文件、不写入知识库/);
  assert.doesNotMatch(handoff, /println!|eprintln!/);
});

test("the status center renders supervisor evidence without HTML injection", async () => {
  const html = await read("src-ui/status/index.html");
  const script = await read("src-ui/status/status.js");
  const style = await read("src-ui/status/status.css");
  assert.match(html, /Runtime Supervisor/);
  assert.match(html, /导出脱敏诊断/);
  assert.match(script, /runtime_diagnostics/);
  assert.match(script, /runtime_restart_core/);
  assert.match(script, /runtime_open_logs/);
  assert.match(script, /runtime_export_diagnostics/);
  assert.match(script, /setAttribute\("role", "cell"\)/);
  assert.match(script, /renderUnavailable/);
  assert.match(script, /停止加载并清除陈旧证据/);
  assert.doesNotMatch(script, /innerHTML|outerHTML|insertAdjacentHTML/);
  assert.match(style, /:focus-visible/);
  assert.match(style, /prefers-reduced-motion/);
});

test("the source adapter delegates to the reviewed repository scripts", async () => {
  const runtime = await read("src-tauri/src/runtime.rs");
  const startScript = await readRepository("scripts/start.ps1");
  assert.match(runtime, /join\("scripts"\)\.join\(name\)/);
  assert.match(runtime, /script\("start\.ps1"\)/);
  assert.match(runtime, /script\("stop\.ps1"\)/);
  assert.match(runtime, /JARVIS_DESKTOP_SHELL/);
  assert.match(startScript, /--no-tray/);
  assert.match(startScript, /desktop_shell/);
  assert.match(runtime, /trait RuntimeAdapter/);
  assert.match(runtime, /struct RuntimeSupervisor/);
  assert.match(runtime, /struct BundledRuntimeAdapter/);
  assert.match(runtime, /JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE/);
  assert.match(runtime, /DESKTOP_SESSION_TOKEN/);
  assert.match(runtime, /reserve_loopback_port/);
  assert.doesNotMatch(runtime, /Stop-Process|taskkill|docker compose/);
});

test("desktop assets use a runtime connection instead of a fixed API port", async () => {
  const client = await readRepository("apps/web/src/lib/api/client.ts");
  const dialog = await readRepository("apps/web/src/lib/api/dialog.ts");
  assert.match(client, /__JARVIS_RUNTIME__/);
  assert.match(client, /X-Jarvis-Desktop-Session/);
  assert.match(client, /runtimeUrl/);
  assert.match(dialog, /Last-Event-ID/);
  assert.match(dialog, /runtimeRequestHeaders/);
});

test("the splash never renders runtime output as HTML", async () => {
  const script = await read("src-ui/app.js");
  assert.doesNotMatch(script, /innerHTML/);
  assert.match(script, /textContent/);
  assert.match(script, /desktop_config_preview/);
  assert.match(script, /desktop_config_apply/);
  assert.match(script, /desktop_config_cancel/);
  assert.match(script, /desktop_config_complete/);
  assert.match(script, /file\.size > 1024 \* 1024/);
  assert.match(script, /replaceChildren/);
});

test("the installer is per-user and keeps writable data outside the install tree", async () => {
  const config = JSON.parse(await read("src-tauri/tauri.conf.json"));
  const compose = await read("resources/infra/docker-compose.yml");
  const store = await read("src-tauri/src/config_store.rs");
  const hooks = await read("src-tauri/windows/installer-hooks.nsh");
  assert.equal(config.bundle.active, true);
  assert.equal(config.bundle.targets, "nsis");
  assert.deepEqual(config.bundle.resources, { "../resources/": "resources/" });
  assert.equal(config.bundle.windows.nsis.installMode, "currentUser");
  assert.equal(config.bundle.windows.webviewInstallMode.type, "downloadBootstrapper");
  assert.equal(config.bundle.windows.webviewInstallMode.silent, false);
  assert.match(hooks, /StrCpy \$INSTDIR "\$LOCALAPPDATA\\Programs\\\$\{PRODUCTNAME\}"/);
  assert.match(hooks, /RMDir \/r "\$INSTDIR\\resources"/);
  assert.match(hooks, /\$LOCALAPPDATA\\Jarvis OS\\updates\\rollback/);
  assert.match(hooks, /\$INSTDIR\\\$\{MAINBINARYNAME\}\.exe/);
  assert.equal(config.bundle.windows.nsis.installerHooks, "windows/installer-hooks.nsh");
  assert.match(compose, /POSTGRES_PASSWORD: "\$\{POSTGRES_PASSWORD:/);
  assert.doesNotMatch(compose, /POSTGRES_PASSWORD:\s+jarvis_dev_only/);
  assert.match(store, /CryptProtectData/);
  assert.match(store, /CryptUnprotectData/);
  assert.match(store, /MoveFileExW/);
  assert.match(store, /source_unchanged: true/);
});

test("release preparation mirrors assets and records traceable artifact hashes", async () => {
  const prepareUi = await read("scripts/prepare-ui.ps1");
  const prepareBundle = await read("scripts/prepare-bundle.ps1");
  const manifest = await read("scripts/generate-release-manifest.ps1");
  assert.match(prepareUi, /robocopy\.exe/);
  assert.match(prepareUi, /\/MIR/);
  assert.match(prepareBundle, /generate-sbom\.ps1[\s\S]*generate-release-manifest\.ps1/);
  assert.match(prepareBundle, /resources\\jarvis-os-v4\.cdx\.json/);
  assert.match(manifest, /schema_version = 2/);
  assert.match(manifest, /working_tree_dirty/);
  assert.match(manifest, /sbom_sha256/);
  assert.match(manifest, /runtime_scripts_sha256/);
  assert.match(manifest, /installer_hooks_sha256/);
  assert.match(manifest, /Stable release manifest requires a clean Git worktree/);
});

test("desktop reliability evidence is measured from the installed app", async () => {
  const script = await read("scripts/desktop-reliability.ps1");
  assert.match(script, /LifecycleIterations = 50/);
  assert.match(script, /QuickIterations = 20/);
  assert.match(script, /no measurable native process feedback within one second/);
  assert.match(script, /end-to-end native process feedback exceeded one second/);
  assert.match(script, /visible_window_p95_ms/);
  assert.match(script, /unique quick window was not visible within 1\.5 seconds/);
  assert.match(script, /MainWindowTitle -eq "Jarvis OS"/);
  assert.match(script, /WaitForUniqueTitle/);
  assert.match(script, /matches\.Count == 1/);
  assert.match(script, /1500 - \[int\]\$watch\.ElapsedMilliseconds/);
  assert.match(script, /MainWindowTitle/);
  assert.match(script, /titles \| Select-Object -Unique/);
  assert.match(script, /\$quitTimeout = 30000/);
  assert.match(script, /Start-Sleep -Milliseconds 1000/);
  assert.match(script, /orphan sidecar remained/);
  assert.match(script, /working_set_bytes/);
  assert.match(script, /\$owned = @\(\$appProcesses\) \+ @\(\$sidecarProcesses\)/);
  assert.match(script, /runtime_mode = \$RuntimeMode/);
  assert.match(script, /Test-RuntimeRecord/);
  assert.match(script, /Test-TcpPort/);
  assert.match(script, /Get-FileHash/);
  assert.doesNotMatch(script, /Stop-Process|taskkill|TerminateProcess/);
});

test("source adapter persists reviewed startup diagnostics", async () => {
  const runtime = await read("src-tauri/src/runtime.rs");
  assert.match(runtime, /desktop-source-adapter\.log/);
  assert.match(runtime, /\.stdout\(stdout\)/);
  assert.match(runtime, /\.stderr\(stderr\)/);
});

test("bundled startup cannot become ready before migration succeeds", async () => {
  const runtime = await read("src-tauri/src/runtime.rs");
  const migration = runtime.indexOf("self.run_migration(&environment)?;");
  const connection = runtime.indexOf("let port = reserve_loopback_port()?;", migration);
  const core = runtime.indexOf('self.start_child("api"', migration);
  assert.ok(migration >= 0);
  assert.ok(connection > migration);
  assert.ok(core > connection);
  assert.match(runtime, /MIGRATION_FAILED/);
  assert.match(runtime, /migration-error\.log/);
});

test("autostart failures trip a persistent circuit breaker", async () => {
  const fuse = await read("src-tauri/src/autostart_fuse.rs");
  const main = await read("src-tauri/src/main.rs");
  assert.match(fuse, /const FAILURE_LIMIT: u32 = 3/);
  assert.match(fuse, /consecutive_failures/);
  assert.match(fuse, /newly_tripped/);
  assert.match(main, /AUTOSTART_CIRCUIT_OPEN/);
  assert.match(main, /AUTOSTART_FUSE_INVALID/);
  assert.match(main, /set_autostart\(false\)/);
  assert.match(main, /autostart_fuse::clear/);
});

test("voice capture is confirmation gated and fails safely", async () => {
  const hook = await readRepository("apps/web/src/components/chat/use-voice-loop.ts");
  const workspace = await readRepository("apps/web/src/components/chat-workspace.tsx");
  const twin = await readRepository("apps/web/src/components/chat/twin-chat-workspace.tsx");
  const quick = await read("src-ui/quick/quick.js");
  assert.match(hook, /RECORDING_TIMEOUT_MS = 60_000/);
  assert.match(hook, /track\.onended/);
  assert.match(hook, /voiceDraftRef\.current = true/);
  assert.match(hook, /submitConfirmedVoice/);
  assert.doesNotMatch(hook, /setInput\(result\.text\);[\s\S]{0,120}onTranscript\(result\.text\)/);
  assert.match(workspace, /voice\.submitConfirmedVoice\(input\)/);
  assert.match(twin, /voice\.submitConfirmedVoice\(input\)/);
  assert.match(quick, /RECORDING_TIMEOUT_MS = 60 \* 1000/);
  assert.match(quick, /track\.onended/);
  assert.match(quick, /setPointerCapture/);
  assert.match(quick, /abortRecording\("录音已达到 60 秒上限/);
  assert.match(quick, /input\.value = result\.text/);
  const composer = await readRepository("apps/web/src/components/chat/chat-composer-region.tsx");
  const main = await read("src-tauri/src/main.rs");
  assert.match(composer, /desktop_open_microphone_settings/);
  assert.match(composer, /href="\/notifications"/);
  assert.match(main, /ms-settings:privacy-microphone/);
});
