# Jarvis OS Desktop Shell

V4 Windows 桌面发行层。当前候选版本为 `4.0.0-beta.3`；源码启动入口仍作为 Stable 前的回滚路径保留。

## 当前能力

- Tauri 2、WebView2 与单实例原生窗口；
- per-user NSIS 安装、静态 Next.js 26 路由与 PyInstaller Sidecar；
- Source/Bundled Runtime Adapter、动态本地会话连接与进程所有权监管；
- 托盘、状态中心、可配置全局快捷键、快速提问、通知深链、文件接入、按住说话和可选开机启动；
- 签名更新清单、备份验证、自动回退、SBOM、安全审计和发布门禁。

## 前置条件

- Windows 11 x64；
- Microsoft Edge WebView2 Runtime；
- 构建源码时需要 Rust stable MSVC、Visual Studio 2022 C++ Build Tools、Windows SDK、Node 与项目 Python 环境。

安装态不依赖系统 Node/Python。Docker Desktop/PostgreSQL 与 Ollama 仍是可见的外部依赖，不由安装器静默捆绑。

## 开发与验证

```powershell
cd apps\desktop-shell
npm install
npm run check
npm run check:rust
npm run dev
```

`scripts/native.ps1` 自动发现 Windows 构建工具，并把临时产物放在仓库 `.runtime/`。可用环境变量：

- `JARVIS_PROJECT_ROOT`：覆盖源码 Adapter 自动发现的仓库根目录；
- `JARVIS_DESKTOP_START_TIMEOUT_SECONDS`：启动超时，默认 240 秒。

## 构建与发布门禁

```powershell
npm run build
npm run release:audit
.\scripts\desktop-reliability.ps1 -Mode Lifecycle -LifecycleIterations 50
.\scripts\desktop-observation.ps1 -Mode Start -RequiredHours 168
```

安装态使用 `BundledRuntimeAdapter`，开发/回滚态使用 `SourceRuntimeAdapter`，两者共享同一 `RuntimeSupervisor` 契约。当前 Beta 未使用生产 Authenticode 证书，且 7 天观察与干净 Windows 11 人工矩阵未完成，因此不得标记 Stable。
