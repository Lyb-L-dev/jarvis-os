# Jarvis OS V4 Windows 人工验收记录

适用候选：`4.0.0-beta.3`  
安装器 SHA-256：`96CDAAD867F8588EC5BDE37DF4BAF0F238F4F5E76FA8E2C9A3955D75D195CD68`  
对应需求状态：`docs/JARVIS_OS_V4_ACCEPTANCE_MATRIX.md`

> 本文件是执行记录，不是预先勾选的声明。每个场景应填写设备、账户、时间、结果和证据文件；未执行项保持空白。截图不得包含 Prompt、文件正文、Token、Cookie 或密钥。

## 环境记录

| 字段 | 记录 |
|---|---|
| Windows 版本与 Build |  |
| 设备/CPU/内存 |  |
| 账户类型（普通/受限） |  |
| 用户名是否含中文 |  |
| 安装路径是否含中文/空格 |  |
| WebView2 版本 |  |
| Docker Desktop / PostgreSQL |  |
| Ollama / 本地语音模型 |  |
| 显示器与缩放 |  |
| 验收人、开始/结束时间 |  |

证据目录建议：`.runtime/release-evidence/manual-win11/<日期>-<设备>/`。

## 1. 安装、迁移与卸载

- [ ] 普通用户全新安装成功；WebView2 缺失时显示可见安装流程与用途，不静默捆绑 Docker/Ollama。
- [ ] 首次启动无需 Node/Python/终端；缺 Docker、PG 延迟、缺 Ollama、断网分别显示准确状态与恢复建议。
- [ ] 旧 `.env` 先预览再导入；取消与故意失败后，旧文件 SHA-256/时间戳不变。
- [ ] 覆盖升级后版本、配置、业务数据、回退安装器都存在。
- [ ] 中文用户名、中文/空格路径、普通受限账户分别完成安装与启动。
- [ ] 卸载移除程序、协议、Open With、Run 键，不删除 `%LOCALAPPDATA%\Jarvis OS` 与 PostgreSQL volume；重装后数据可用。
- [ ] 仅在隔离测试账户验证“导出并验证 → 精确短语 → 二次确认 → 删除”：导出包位于数据根之外且保留，数据根与 `jarvis_postgres_data` 被删除；篡改导出文件后清理必须拒绝。

记录：

| 场景 | 结果 | 证据路径/备注 |
|---|---|---|
| 全新安装 |  |  |
| 旧配置迁移/取消 |  |  |
| 覆盖升级 |  |  |
| 中文/空格/受限账户 |  |  |
| 卸载与重装 |  |  |
| 导出后删除（隔离测试账户） |  |  |

## 2. 生命周期、窗口与依赖故障

- [ ] 双击后 1 秒内有原生反馈；第二次启动 1 秒内聚焦现有窗口且无第二套运行时。
- [ ] 隐藏、原生最小化、关闭到托盘、设置为完全退出四条路径结果一致。
- [ ] 完全退出后无 Jarvis 自有孤儿进程；Docker Desktop、Ollama、非 Jarvis 端口进程保持原状。
- [ ] 主窗口在 100/125/150/200% 缩放和显示器拔插/主副屏切换后完全可见。
- [ ] 非 Jarvis 进程占用候选端口时 Jarvis 换端口或阻断，不终止该进程。
- [ ] 数据库迁移故意失败时不能进入 ready，错误日志和备份仍在。
- [ ] Core 连续崩溃只有限重试；开机连续失败三次后 Run 键被移除且只提示一次。

记录：

| 场景 | 结果 | 证据路径/备注 |
|---|---|---|
| 单实例/隐藏/最小化/退出 |  |  |
| 多显示器/四档缩放 |  |  |
| 端口冲突 |  |  |
| 迁移失败 |  |  |
| 崩溃退避/开机熔断 |  |  |

## 3. 快速窗口与全局快捷键

- [ ] 默认快捷键与浏览器、VS Code 及常用 IDE 无冲突；冲突组合不会覆盖其他应用，并提供修改入口。
- [ ] 连续 20 次唤起始终只有一个窗口、焦点在输入框；`Esc` 隐藏且不常驻最前。
- [ ] 标准消息只写入一次并流式显示；转主窗口后仍是同一 conversation。
- [ ] 30 分钟内复用、超时后新建；旧 conversation 仍可检索。
- [ ] 发送失败保留草稿；复杂卡片、R2/R3/付费/工具动作只能转主窗口确认。

## 4. 通知

- [ ] 冷启动和热运行点击“打开”都聚焦准确对象；不存在的 UUID 打开通知中心并显示过期说明。
- [ ] “稍后 10 分钟”重复点击幂等，只产生一次延后。
- [ ] 敏感通知在锁屏和通知中心不显示正文，只提供打开动作。
- [ ] 伪造 scheme、额外 URL 参数、错误 UUID、20 分钟 snooze 均安全拒绝。
- [ ] Toast 不出现批准 R2/R3、付费或外部工具的按钮。

## 5. 文件入口

- [ ] 拖入和 Explorer“使用 Jarvis 打开”走同一预览；不会抢占默认编辑器。
- [ ] 预览仅显示名称、大小、类型、来源、分析方式和隐私影响；确认前不读取正文。
- [ ] `.md/.txt` UTF-8/BOM 与 2 MiB 边界通过；目录、`.lnk`、符号链接、网络盘、错误编码和超限明确拒绝。
- [ ] 取消后不读取；确认后强制本地模式、默认不发送、不写知识库。
- [ ] 分析前后源文件 SHA-256 与时间戳相同；日志和诊断 ZIP 搜索不到人工植入的唯一正文片段。
- [ ] 关闭 Open With 后注册项消失，默认编辑器不变。

## 6. 麦克风与本地语音

- [ ] 第一次按住时 WebView2/Windows 正常请求麦克风权限；拒绝后可直接打开 Windows 隐私设置。
- [ ] 主窗口与快速窗口均为按住录音、松开转写；转写可编辑且不会自动发送。
- [ ] pointer 移出按钮后松开仍结束；取消、60 秒超时、录音中拔出设备均不转写或发送，界面恢复可操作。
- [ ] 模型缺失时显示降级原因和本地模型状态入口；键盘输入仍可用。
- [ ] 安静时段与敏感内容偏好阻止 TTS；关闭语音快捷键后无全局按键残留。

## 7. 更新、回退与安全

- [ ] N-1→N、覆盖同版本、篡改清单、篡改同大小安装包、磁盘不足、备份失败分别按预期处理。
- [ ] 对话流、审批、工具执行或迁移活跃时不强制重启。
- [ ] 新版无法 ready/degraded 时在 120 秒窗口内回装上一版二进制，不执行数据库 downgrade。
- [ ] 任意本地网页不能调用桌面 API；外部 URL 不在 WebView 内导航；协议/路径/command 注入均失败。
- [ ] 正式候选通过 Defender/SmartScreen，并具有 Valid Authenticode 与时间戳。

## 8. 稳定性观察

- [ ] 50 次最终安装器哈希绑定的启动/完全退出：0 孤儿进程。
- [ ] 20 次最终安装器哈希绑定的快捷唤起：0 重复窗口、0 丢焦点。
- [ ] 24 小时待机且至少两次睡眠恢复：无重启风暴。
- [ ] 168 小时窗口、至少 134 个不同小时桶、至少两次 resume、无 P0/P1。

旧 schema 1 观察绑定前一构建，不计入当前候选。当前最终包观察尚未开始；先完成首次引导并确认 1 个 App、1–2 个 Sidecar，再以安装器 SHA 前 12 位命名独立证据目录：

```powershell
$installer = Resolve-Path '.runtime\desktop-target-v4\release\bundle\nsis\Jarvis OS_4.0.0-beta.3_x64-setup.exe'
$evidence = Join-Path $env:LOCALAPPDATA 'Jarvis OS\observations\v4-beta.3-96cdaad867f8'
.\apps\desktop-shell\scripts\desktop-observation.ps1 -Mode Start -RequiredHours 168 -InstallerPath $installer -EvidenceDirectory $evidence
.\apps\desktop-shell\scripts\desktop-observation.ps1 -Mode Sample -EvidenceDirectory $evidence
.\apps\desktop-shell\scripts\desktop-observation.ps1 -Mode Verify -EvidenceDirectory $evidence
```

每条样本必须保持同一已安装 EXE/Manifest 哈希，且包含无正文可靠性指标；跨构建、进程数不符或缺少指标时脚本必须拒绝。

## 签字结论

| 角色 | 姓名/日期 | 结论 |
|---|---|---|
| 开发验收 |  |  |
| 安全/发布复核 |  |  |
| 产品验收 |  |  |

只有本文件必测项有真实证据、验收矩阵不再存在“待最终包/待人工/外部门禁”，且 `verify-v4-release-gate.ps1` 返回 `passed:true` 时，才允许标记 Windows Stable。
