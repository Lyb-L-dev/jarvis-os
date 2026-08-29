# ADR-0015：Windows Desktop Shell 与 Runtime 所有权

## 状态

已接受，2026-08-13。V4-0 的 Tauri/WebView2、静态构建、Sidecar 打包、动态 Runtime Connection 与进程回收均已完成实测；证据见 [`JARVIS_OS_V4_0_SPIKE_REPORT.md`](../JARVIS_OS_V4_0_SPIKE_REPORT.md)。

## 背景

Jarvis OS 当前通过 `.cmd` 和 PowerShell 启动 Next.js、FastAPI、Python Companion、备份 Worker、PostgreSQL 容器及可选 Provider。V4 要提供 Windows 安装、单实例、可解释启动、退出、恢复和更新，但不能把桌面壳变成第二业务后端，也不能破坏 PostgreSQL、Tool Gateway、模型授权和 R0–R3 的既有事实与权限语义。

当前已确认的本机事实：

- Windows 11 x64；
- Microsoft Edge WebView2 Runtime 已安装；
- Node.js 22 与现有 Next.js 16 项目可用；
- V4 启动时本机尚无 Rust/Cargo 与 MSVC Build Tools；
- `/onboarding` 使用 `force-dynamic`，桌面静态构建必须先完成迁移 Spike；
- 当前 Companion 已支持 `--no-tray`，本地语音与通知实现可以复用；
- 当前源码启动脚本已经包含端口所有权保护和运行记录，但规则仍集中在 PowerShell。

## 决策

1. Tauri 2 是 Jarvis OS V4 Windows Desktop Shell。
2. Desktop Shell 只承担窗口、单实例、托盘、受控原生入口和 Runtime Supervisor，不保存业务事实。
3. Runtime Supervisor 是深模块，对调用方只提供：

```text
start(profile) -> RuntimeSnapshot
status() -> RuntimeSnapshot
stop(reason) -> StopResult
```

4. 开发/恢复模式使用 `SourceRuntimeAdapter` 复用现有 `scripts/start.ps1` / `stop.ps1`；安装态使用 `BundledRuntimeAdapter`，调用方接口不变。
5. PostgreSQL 继续是唯一业务事实源；桌面壳不得持有数据库凭证或直接修改对话、记忆、审批和工具状态。
6. 启动窗口与业务主窗口分离：只有启动窗口进入 Tauri Capability；静态业务主窗口不获得 Runtime Command、Shell 或文件系统权限。
7. 主窗口只允许 Tauri 内嵌 App Origin；外部链接交给系统浏览器。
8. Tauri Command 使用封闭白名单，不提供任意 Shell、任意路径读取或任意进程终止接口。
9. 单实例回调只聚焦已有主窗口或启动窗口，不创建第二套运行时。
10. V4-0 不改变 PostgreSQL、Agent Runtime、UI Event Feed、模型授权、Tool Gateway 或 R0–R3 语义。
11. 安装态二进制固定在 `%LOCALAPPDATA%\Programs\Jarvis OS`，可写配置、运行记录、日志、备份和更新证据固定在 `%LOCALAPPDATA%\Jarvis OS`；卸载器不得递归删除数据根。
12. 更新采用独立 Stable/Beta 签名清单、SHA-256 与 Authenticode 双门禁。更新前必须完成可恢复备份；新版本 120 秒内未进入 ready/degraded 时，独立 watchdog 回装上一版二进制，但不执行数据库 downgrade。

## 接受证据

- Tauri/WebView2 已完成真实 V3-4b、SSE、中文界面、缩放、外链和麦克风实测；
- 单实例、关闭到托盘、完全退出和窗口恢复通过真实 Win32 验收；
- 26 个 Next.js App Router 路由可静态导出，桌面版不再启动 Node/3000；
- FastAPI/Alembic/Companion one-directory Sidecar 在不含 Python/Node 的 PATH 下通过；
- Bundled 模式使用动态端口、精确 Origin 和 256-bit 启动会话令牌，未授权业务请求返回 401；
- API 与 Companion 加入 `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` 进程组，正常退出和强制终止壳后均无孤儿进程；
- 当前开发机 Bundled 冷启动基线 18.06 秒；Sidecar 146.43 MiB/2056 文件，静态 UI 17.81 MiB/260 文件；
- 主业务窗口不在 Capability 的 `windows` 白名单中，且不存在通用 Shell/文件/进程 Command。
- beta.1 → beta.2 真实覆盖升级通过；故意不写启动成功标记后，watchdog 在 120 秒后自动回装 beta.1 并记录 `rolled_back`；
- 本机 NSIS 卸载后安装目录、协议、Open With、开机启动和进程均清空，DPAPI 配置、用户数据与更新证据保留。

## 结果

- 桌面壳保持小接口，复杂启动与恢复逻辑集中在 Runtime Supervisor；
- Source/Bundled 两个 Adapter 让发行方式可以替换而不修改 UI 调用方；
- Windows 原生能力不会绕过 FastAPI 和 Tool Gateway；
- V4-0 可以独立回滚，现有 `.cmd` 与浏览器路径保持可用。

## 未采用方案

### 直接把网页包进窗口

拒绝。不能解决启动、进程所有权、诊断、退出、升级和恢复问题。

### 把 FastAPI 业务迁入 Rust Command

拒绝。会复制业务规则、权限和事实源，使桌面壳成为第二后端。

### 让远程主窗口拥有完整 Tauri Capability

拒绝。会让 Web 内容获得不必要的本机权限，扩大 XSS 或导航错误的影响。

### V4-0 直接捆绑 Docker、PostgreSQL、Ollama 和模型权重

拒绝。包体积、许可、升级和用户设备所有权尚未验证；首版继续把它们视为可见外部依赖。
