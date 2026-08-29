# Jarvis OS V4 交付与发布门禁

> 版本：`4.0.0-beta.3`  
> 证据日期：2026-08-15  
> 结论：**功能候选已实现；Windows Stable 发布仍被外部门禁阻断。**

逐项状态以 [JARVIS_OS_V4_ACCEPTANCE_MATRIX.md](./JARVIS_OS_V4_ACCEPTANCE_MATRIX.md) 为准；其中覆盖 PRD 全部 61 条 `APP-*` 需求，并明确区分自动证据、最终包复验、Windows 人工记录与外部门禁。干净机器执行步骤与记录位置见 [JARVIS_OS_V4_WINDOWS_MANUAL_ACCEPTANCE.md](./JARVIS_OS_V4_WINDOWS_MANUAL_ACCEPTANCE.md)。

## 已交付

- Tauri 2 + WebView2 单实例壳，Next.js 26 路由静态嵌入，无 Node Server/3000；
- Runtime Supervisor、Source/Bundled Adapter、动态回环端口、短会话令牌、精确 Origin、Job Object 回收；
- 状态中心、DPAPI 配置与迁移、托盘暂停/恢复提醒、全局快捷键、快速窗口、通知深链、受控文本文件、按住说话、可选开机启动；
- per-user NSIS，二进制 `%LOCALAPPDATA%\Programs\Jarvis OS` 与数据 `%LOCALAPPDATA%\Jarvis OS` 分离；
- Stable/Beta 独立 RSA 签名清单、GitHub 主机白名单、SHA-256、Authenticode、活跃任务保护、备份恢复验证与 120 秒自动回退；
- CycloneDX SBOM、安全审计、机器可判定发布门禁，以及精确绑定安装器/Manifest/已安装 EXE 的 24h/7d 无正文可靠性台账。
- 卸载默认保留数据；设置页提供独立的“导出并验证后删除”流程，使用一次性 30 分钟凭据、精确确认短语、导出文件 SHA-256 清单、固定数据根与受控 Docker Compose 身份校验。

## 自动化证据

| 证据 | 结果 |
|---|---|
| API pytest（CI 同款目录） | 385 passed, 38 skipped |
| Desktop pytest | 8 passed |
| Rust 单元/故障测试 | 36 passed |
| Desktop Node 契约 | 22 passed |
| Web TypeScript / ESLint | passed / passed |
| Ruff API + desktop | passed |
| Next 静态生产构建 | 26/26 路由 |
| Web npm audit | 0 vulnerabilities |
| Desktop shell npm audit | 0 vulnerabilities |
| Python OSV audit | 0；`h2` 已由 4.4.0 升至 4.4.1 |
| RustSec（Windows x86_64，489 dependencies） | 0 vulnerabilities |
| CycloneDX 1.5 | 1186 components |

Rust 锁文件包含跨平台依赖，因此未限定目标时会显示 GTK3/unic 的 unmaintained 与 `glib 0.18.5` unsound 信息；Windows x86_64 目标审计为 0 个已知漏洞，Stable 仍应持续跟踪这些传递依赖。

## 本机 Windows 11 实测

| 场景 | 证据 |
|---|---|
| beta.1 首次静默安装 | exit 0；版本与资源完整 |
| 安装/数据分离 | 程序在 `Programs\Jarvis OS`，数据/回退在 `Jarvis OS` |
| beta.1 → beta.2 覆盖升级 | exit 0；注册表与 EXE 为 beta.2 |
| 覆盖升级资源收敛 | 安装前只清理程序目录 `resources`；旧依赖不会残留，用户数据目录不受影响 |
| 回退基线 | `previous-installer.exe` SHA-256 与安装器一致 |
| beta.2 启动 | 主进程 15 秒存活；DPAPI 与六类数据目录创建 |
| 启动失败自动回退 | beta.2 无成功标记；120 秒后回装 beta.1，`status=rolled_back` |
| 卸载 | 安装目录/注册表/协议/Open With/开机启动/进程清空；数据保留 |
| 无实例 `--quit` | 立即无副作用退出，不会误启动完整桌面运行时或阻塞维护 |

当前 beta.3 安装包（含 `nanoid 3.3.18`、语音确认/异常取消、自启动熔断、WebView2 可见安装，以及导出验证后删除本地数据流程）：

- 大小：69,499,831 bytes
- SHA-256：`96CDAAD867F8588EC5BDE37DF4BAF0F238F4F5E76FA8E2C9A3955D75D195CD68`
- Authenticode：`NotSigned`（因此禁止 Stable）
- SBOM SHA-256：`EDA9BF797F0389A5B714C7FDA015D2D0F3CC7C61D46921F502B6D3442252F1CF`（生成文件、安装资源与 Release Manifest 一致；1186 components）
- Release Manifest SHA-256：`3A1E0FD229A1C1CD9BD46A168140099EE64C1E200CD4B57C9C74BFCBDEA878B4`
- 已安装 EXE SHA-256：`C438C02DAB19C5E5EA90C530674282DDBA0586C866D61A257839B35878C28CF5`
- 覆盖安装：exit 0；注册版本 `4.0.0-beta.3`；中文用户名路径下数据根保留；安装版主进程已实测存活。现有用户数据缺少首次引导完成标记，Core/Companion 按设计不会提前启动。

可靠性与资源证据：

- `desktop-quick-20-source-final.json`：20/20 唤起通过，单窗口，P50 39.8 ms、P95 139 ms；
- `desktop-lifecycle-50-final-strict.json`：50/50 启动/完全退出通过，孤儿进程 0，启动反馈 P50 23.6 ms、P95 37.8 ms；该轮绑定安全修复前一次 beta.3 重建哈希，最终重建 EXE 的 50 次复验因桌面进程授权策略待用户显式允许；
- 当前精确安装产物：安装体积 168,164,797 bytes、2,069 文件；Desktop Shell EXE 14,126,592 bytes；既有空闲宿主工作集 P50/P95 28,196,864 bytes 来自前一构建。

## 发布门禁状态

| 门禁 | 状态 | 解除条件 |
|---|---|---|
| 功能与自动化 | 通过 | 保持 CI 通过 |
| 本机 install/upgrade/rollback/uninstall | 通过 | 最终签名包再抽检 |
| 生产更新公钥 | 阻断 | 用离线生产 RSA 公钥构建，开发 key 不得进入 Stable |
| Windows Authenticode | 阻断 | 代码签名证书 + SHA-256 时间戳；安装器签名必须 Valid |
| Defender/SmartScreen | 阻断 | 对最终签名包留存扫描与启动证据 |
| 干净 Windows 11 普通账户 | 阻断 | 无源码/Node/Python 环境跑完整矩阵 |
| 中文、空格、受限账户、缩放/多显示器/麦克风 | 部分 | 完成人工记录与截图/日志证据 |
| 24 小时待机/两次睡眠唤醒 | 阻断 | `desktop-observation.ps1 -RequiredHours 24` 通过 |
| 7 天真实使用 | 阻断 | 168 小时、≥134 条采样、无 P0/P1 |
| 干净 worktree 的 Release Manifest | 阻断 | 提交后重建；`working_tree_dirty=false` |

任何一项阻断存在时，`verify-v4-release-gate.ps1` 必须退出非零；不得用“安装包能打开”替代 Stable 完成定义。

当前 beta.3 已重建并通过安装包/SBOM/Manifest 哈希一致性、覆盖安装和源码全量回归。依赖集合未变，但本轮联网安全审计因需要把依赖元数据发送到 npm/OSV/Rust advisory 服务而未获显式授权；当前 audit summary 仍是上一轮 0 漏洞记录，不得冒充本轮新审计。Stable 仍被未签名、开发更新公钥、dirty manifest/worktree、最终哈希 50 次复验、干净 Win11 人工矩阵、24 小时待机与 7 天观察阻断。

168 小时观察脚本已升级为 schema 2：开始时绑定精确安装器与 Release Manifest，每次采样校验已安装 EXE/Manifest，并汇总不含提示词、文件正文或对话内容的封闭可靠性事件。旧 schema 1 的 10.73 小时记录只属于前一构建，不能继承。当前最终包窗口尚未开始：须先在已打开的安装版中完成首次引导，使运行态达到 1 个 App 与 1–2 个 Sidecar。

2026-08-29 源码变更（进入下一次重建，未改变 beta.3 安装包）：主窗口显示后显式最大化——修复 window-state 插件恢复上一次小窗尺寸导致"打开即小页面"的问题；splash 开机窗 580×700、启动阶段点视觉升级并注明"就绪后自动全屏展开"。下一次重建产生的安装包哈希将使 beta.3 的精确绑定失效；因 168 小时观察窗口尚未开始，无既有证据作废。

## 复现命令

```powershell
npm --prefix apps/desktop-shell run check
npm --prefix apps/desktop-shell run check:rust
npm --prefix apps/web run typecheck
npm --prefix apps/web run lint
.\.venv\Scripts\python.exe -m pytest -q apps/api
.\.venv\Scripts\python.exe -m pytest -q apps/desktop
npm --prefix apps/desktop-shell run release:sbom
npm --prefix apps/desktop-shell run release:audit
```

观察先完成首次引导并确认精确进程归属，再显式开始；脚本拒绝伪造未经过的时间或跨构建复用证据：

```powershell
$installer = Resolve-Path '.runtime\desktop-target-v4\release\bundle\nsis\Jarvis OS_4.0.0-beta.3_x64-setup.exe'
$evidence = Join-Path $env:LOCALAPPDATA 'Jarvis OS\observations\v4-beta.3-96cdaad867f8'
.\apps\desktop-shell\scripts\desktop-observation.ps1 -Mode Start -RequiredHours 168 -InstallerPath $installer -EvidenceDirectory $evidence
.\apps\desktop-shell\scripts\desktop-observation.ps1 -Mode Sample -EvidenceDirectory $evidence
.\apps\desktop-shell\scripts\desktop-observation.ps1 -Mode Verify -EvidenceDirectory $evidence
```
