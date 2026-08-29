# Jarvis OS V4 需求验收矩阵

更新时间：2026-08-14  
适用版本：`4.0.0-beta.3`  
需求基线：`docs/JARVIS_OS_V4_PRD.md`

本矩阵是 V4 发布门禁的事实索引，不以“代码存在”代替验收。状态含义：

- `自动通过`：当前源码对应的单元、契约或回归证据已通过。
- `待最终包`：源码证据已通过，但必须在下一次重建后的同哈希安装包上复验。
- `待人工`：PRD 明确要求真实 Windows Shell、通知、安装器、麦克风或多显示器人工记录。
- `外部门禁`：需要正式证书、干净 Windows 11 账户或时间窗口，不能由源码测试替代。

通用自动命令：

```powershell
npm --prefix apps/desktop-shell run check
npm --prefix apps/desktop-shell run check:rust
npm --prefix apps/web run typecheck
npm --prefix apps/web run lint
python -m pytest apps/api/tests
```

## 生命周期与运行时

| ID | 状态 | 当前实现与自动证据 | 尚需证明 |
|---|---|---|---|
| APP-LIFE-001 | 待最终包 | `tauri-plugin-single-instance`；安装版 50 次循环脚本检查单实例、反馈和孤儿进程 | 对最终安装 EXE 哈希重跑 50 次 |
| APP-LIFE-002 | 自动部分通过 / 待人工 | 托盘隐藏/恢复、原生最小化、`hide/quit` 关闭偏好；首次关闭保持窗口可见并显示托盘说明，记录后再次关闭才隐藏 | 三种动作与两种关闭偏好人工记录 |
| APP-LIFE-003 | 自动部分通过 / 待人工 | `tauri-plugin-window-state` 保存纯窗口状态；显示前把完全离屏、部分离屏或超大窗口约束到当前可见显示器，Rust 覆盖显示器移除与边缘裁切 | 拔插/切换显示器后 100/125/150/200% 缩放记录 |
| APP-LIFE-004 | 自动通过 | `on_navigation`/`on_new_window` 拒绝 WebView 外部导航，只经 opener 打开；Rust URL 单测 | 最终包抽检默认浏览器 |
| APP-LIFE-005 | 待最终包 | Job Object 仅收纳 Sidecar；停止实现不含 `taskkill`/`Stop-Process`；可靠性脚本只观测归属进程 | 最终哈希退出循环及外部 Docker/Ollama 保持运行记录 |
| APP-RUN-001 | 自动通过 | `RuntimeSupervisor` 单接口、依赖阶段和 ready/degraded/blocked 状态；Rust supervisor 单测 | — |
| APP-RUN-002 | 自动通过 | bundled adapter 在迁移成功前不启动 Core，失败保留 migration error log；契约锁定迁移顺序 | 最终包故障注入记录 |
| APP-RUN-003 | 自动通过 | 10 分钟窗口最多 3 次恢复；`automatic_recovery_stops_after_three_attempts_in_window` | — |
| APP-RUN-004 | 待人工 | 动态回环端口、健康校验与 Job 所有权；源码禁止按端口杀进程 | 用非 Jarvis 占用端口的故障注入记录 |
| APP-RUN-005 | 待最终包 | 本地 splash 为唯一静态窗口，结构化阶段/耗时来自 Supervisor；可靠性脚本检查 1 秒原生反馈 | 最终哈希冷/热启动计时 |
| APP-RUN-006 | 自动通过 | Status Center 聚合 Jarvis App、Core、PostgreSQL、Ollama、Companion、本地语音与可选 Worker 的状态/版本/原因/检查时间；语音通过不读取用户数据的 `/voice/readiness` 探测；Rust + Node 契约覆盖 | 最终包人工核对显示顺序与文案 |
| APP-RUN-007 | 自动通过 | Tauri command 闭集与 Capability 闭集；Node 契约拒绝通用 shell/任意文件接口 | — |
| APP-RUN-008 | 自动通过 | 诊断导出前后脱敏，移除 session token/私人正文；Rust redaction 与 export 单测 | 最终包人工抽检诊断 ZIP |

## 安装与迁移

| ID | 状态 | 当前实现与自动证据 | 尚需证明 |
|---|---|---|---|
| APP-INST-001 | 待最终包 | Tauri NSIS `currentUser`、x64 安装包已可生成 | 重建后全新/覆盖/卸载矩阵 |
| APP-INST-002 | 待人工 | 二进制位于 `%LOCALAPPDATA%\\Programs\\Jarvis OS`，数据位于 `%LOCALAPPDATA%\\Jarvis OS`；契约锁定分离 | 安装目录只读运行抽检 |
| APP-INST-003 | 待人工 | WebView2 bootstrapper 改为可见安装；Supervisor 明示 Docker/PostgreSQL/Ollama 用途与降级原因，不安装后两者 | 干净 Win11 缺依赖场景截图 |
| APP-INST-004 | 自动通过 | 配置只预览白名单字段，取消/失败不改源；3 条 config migration Rust 单测 | 最终包旧配置导入人工记录 |
| APP-INST-005 | 自动通过 | DPAPI 当前用户绑定；密钥不进前端/日志/manifest；DPAPI round-trip 与脱敏单测 | 发行物 token 扫描 |
| APP-INST-006 | 自动部分通过 / 待人工 | NSIS 卸载默认保留配置、备份和业务卷；设置页另设“导出并验证 → 精确短语 → 二次确认 → 独立清理进程”流程。清理目标固定为 Jarvis 数据根和受控 PostgreSQL volume；路径穿越、凭据不匹配、篡改导出包均有 Rust 单测 | 干净 Win11 测试账户完成导出、删除、导出包保留与重装空数据验证；不得在开发者真实数据上执行 |
| APP-INST-007 | 待人工 | 当前构建环境用户名、仓库路径均含中文，路径含空格夹具已覆盖 | 普通受限账户及自定义中文/空格安装矩阵 |

## 快速窗口

| ID | 状态 | 当前实现与自动证据 | 尚需证明 |
|---|---|---|---|
| APP-QUICK-001 | 待人工 | 3 个审核组合、冲突失败不覆盖、可改/可关；shortcut 闭集 Rust 单测 | Windows/浏览器/VS Code/IDE 冲突矩阵 |
| APP-QUICK-002 | 待最终包 | 单 label 复用窗口；既有 20 次 source-mode 证据为 20/20 且仅一个窗口 | 最终安装哈希 20 次唤起 |
| APP-QUICK-003 | 待人工 | 使用同一 FastAPI conversation/stream/SSE，继续到主窗口；Node 契约 | 最终包流式首字与一次写入记录 |
| APP-QUICK-004 | 自动通过 | `SESSION_TTL_MS = 30 * 60 * 1000`，超时新建 conversation，旧 ID 保留于事实源 | — |
| APP-QUICK-005 | 自动通过 | 只在成功后清空 input；异常保留草稿，关闭只隐藏内存态 | — |
| APP-QUICK-006 | 自动通过 | routing preview 非自动允许即转主窗口；`paid_call_confirmed:false`，无批准按钮 | — |
| APP-QUICK-007 | 待人工 | 非 always-on-top；`Esc` 取消当前等待并隐藏 | 焦点不长期抢占抽检 |

## Windows 通知

| ID | 状态 | 当前实现与自动证据 | 尚需证明 |
|---|---|---|---|
| APP-NOTIFY-001 | 自动通过 | 只解析 `jarvis://notification/<uuid>` 与固定 snooze 路由；Rust 闭集单测拒绝 URL 注入 | — |
| APP-NOTIFY-002 | 待人工 | 运行时聚焦 main；冷激活先缓存，ready 后投递 detail | 冷/热 Toast 打开上下文记录 |
| APP-NOTIFY-003 | 自动通过 | 固定 10 分钟、action UUID；API `test_desktop_snooze_action_is_idempotent` | 最终 Toast 重复点击抽检 |
| APP-NOTIFY-004 | 待人工 | Companion 对 sensitive payload 使用通用正文且仅提供打开动作；API/Companion 回归 | 锁屏与通知中心截图 |
| APP-NOTIFY-005 | 待人工 | 通知中心按 UUID 聚焦，不存在时显示“过期/删除/非当前用户”，不回退其他对象 | 过期与伪造 UUID 激活记录 |
| APP-NOTIFY-006 | 自动通过 | Toast action 闭集只有打开/稍后；无 R2/R3、付费或工具批准路由 | — |

## 文件入口

| ID | 状态 | 当前实现与自动证据 | 尚需证明 |
|---|---|---|---|
| APP-FILE-001 | 待人工 | 主窗口 DropEvent 进入预览；拒绝不自动发送 | 最终包拖放合法/拒绝截图 |
| APP-FILE-002 | 待人工 | `.md/.txt` OpenWithProgids 激活单实例并复用 preview token | Explorer“使用 Jarvis 打开”记录 |
| APP-FILE-003 | 自动通过 | preview 只读取元数据，确认 command 才读正文；一次性 token 单测 | — |
| APP-FILE-004 | 自动通过 | 单文件、UTF-8/BOM、2 MiB、扩展名、目录、符号链接、UNC/网络盘校验 | 网络映射盘和 `.lnk` 人工抽检 |
| APP-FILE-005 | 自动通过 | pending 只保留一个、10 分钟过期、读取后 remove；无任意路径 command | — |
| APP-FILE-006 | 自动通过 | handoff 固定 `localOnly:true`、`knowledgeWrite:false`，云端路径需另行隐私确认 | — |
| APP-FILE-007 | 自动通过 | 读取前后 SHA-256 与 modified time 单测一致；无知识库调用 | — |
| APP-FILE-008 | 待人工 | handoff 无内容日志；诊断红线扫描/脱敏单测 | 最终诊断 ZIP 人工全文片段检索 |
| APP-FILE-009 | 待人工 | 只注册 OpenWithProgids、不改默认 ProgID；设置/卸载均删除键 | 默认编辑器不变及关闭后注册消失记录 |

## 本地语音

| ID | 状态 | 当前实现与自动证据 | 尚需证明 |
|---|---|---|---|
| APP-VOICE-001 | 自动通过 | 主窗口与 quick 均调用 `/voice/transcriptions`，复用同一 V3-4a 服务 | — |
| APP-VOICE-002 | 待人工 | 两处均按住开始、松开停止；转写写入可编辑草稿，`submitConfirmedVoice` 只在用户发送后调用 | 麦克风按住/松开/编辑/确认记录 |
| APP-VOICE-003 | 自动通过 | MediaRecorder Blob 仅发往本机会话 API，结束/取消停止 tracks 并释放引用 | — |
| APP-VOICE-004 | 待人工 | 权限/模型原因可见；新增固定命令打开 Windows 麦克风隐私设置和本地模型状态入口 | 首次授权、拒绝、模型缺失恢复记录 |
| APP-VOICE-005 | 待人工 | 60 秒上限、track `ended`、pointer cancel 均丢弃录音且不调用发送；Node 契约 | 拔出麦克风、超时、取消记录 |
| APP-VOICE-006 | 自动通过 | TTS 读取 Notification Preferences 的 quiet/sensitive policy；API/Companion 回归 | 安静时段与敏感文本听感抽检 |
| APP-VOICE-007 | 待人工 | 语音快捷键默认关闭、3 个白名单组合、按下/松开、冲突不覆盖 | 全局快捷键冲突与关闭残留记录 |

## 开机启动、更新与安全

| ID | 状态 | 当前实现与自动证据 | 尚需证明 |
|---|---|---|---|
| APP-START-001 | 自动通过 | 配置默认 false，安装/升级不写 Run 键 | — |
| APP-START-002 | 待人工 | 设置与托盘共用 `desktop_set_autostart`/注册事实；关闭删除 Run 值 | 两处切换同步及注册表抽检 |
| APP-START-003 | 待人工 | `--autostart` 隐藏启动；只有 setup/blocked 时显示 splash | 登录启动不抢焦点、阻断只提示一次 |
| APP-START-004 | 自动通过 | 持久化连续失败计数，第三次关闭自启动并发出 `AUTOSTART_CIRCUIT_OPEN`；2 条 Rust 单测 | 登录会话故障注入抽检 |
| APP-UPD-001 | 外部门禁 | Stable/Beta channel 与清单 key 分离，开发 key 禁止 Stable；契约测试 | 正式 Stable 公钥/私钥流程 |
| APP-UPD-002 | 外部门禁 | BCrypt 清单签名、WinVerifyTrust、SHA-256、版本闭集；篡改单测 | Authenticode 签名后的实际包 |
| APP-UPD-003 | 待人工 | Core busy、审批、工具执行、迁移均形成 update blocker | 活跃任务期间更新人工记录 |
| APP-UPD-004 | 待人工 | install 前执行 backup/recoverability 脚本，失败不替换 | 磁盘不足/备份失败故障注入 |
| APP-UPD-005 | 待人工 | 保留 previous-installer，watchdog 失败回滚二进制，不执行 DB downgrade | N-1→N 与二进制回滚演练 |
| APP-SEC-001 | 自动通过 | 四个窗口独立 Capability；custom command 精确闭集；无任意 shell/file/process 接口 | — |
| APP-SEC-002 | 自动通过 | 动态回环端口、短随机 session token、精确桌面 Origin/Header；任意本地网页被拒绝 | — |
| APP-SEC-003 | 自动部分通过 / 待联网复审 | 最终包已生成 CycloneDX SBOM 并通过安装资源、Manifest 哈希链校验；联网 npm/pip/Cargo 审计仍沿用上一轮 0 漏洞记录 | 获得联网授权后对最终依赖集合重跑并归档 |

## 当前证据与发布结论

- 当前自动基线：Desktop Node 22/22、Rust 36/36、Web typecheck/lint、Desktop pytest 8/8、Ruff 通过；API 完整回归为 385 passed、38 skipped。
- 当前安装器 SHA-256 为 `96CDAAD867F8588EC5BDE37DF4BAF0F238F4F5E76FA8E2C9A3955D75D195CD68`；已有生命周期/性能证据来自 beta.3 的前一构建哈希，不能绑定当前安装器。
- 当前 SBOM SHA-256 为 `EDA9BF797F0389A5B714C7FDA015D2D0F3CC7C61D46921F502B6D3442252F1CF`，生成文件、安装资源和 Manifest 记录一致，共 1186 个组件。
- 最终包观察台账采用 schema 2，绑定安装器、Release Manifest 和已安装 EXE 的不可变哈希，并只汇总封闭、无正文的启动/快捷窗口/通知/文件/语音/Supervisor/更新与诊断事件。
- 正式 Stable 仍受四类硬门禁约束：Authenticode 正式签名、非开发更新公钥、干净 Windows 11 普通账户矩阵、168 小时真实观察期。
- 旧观察记录为 schema 1 且绑定前一构建，不得复用于当前安装器。当前 168 小时窗口尚未开始；须先完成首次引导并确认 1 个 App 与 1–2 个受其持有的 Sidecar 后重新开始。
- 在上述“待最终包 / 待人工 / 外部门禁”归零前，不得把 V4 标记为 Stable 或把本矩阵改写成“全部完成”。
