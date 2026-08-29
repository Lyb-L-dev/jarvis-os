# Jarvis OS V4 Windows 用户指南

> 适用版本：`4.0.0-beta.3`。当前是验证候选，不是公开 Stable。

## 安装与目录

运行 `Jarvis OS_4.0.0-beta.3_x64-setup.exe`，普通用户即可完成 per-user 安装，不需要管理员权限。首次安装时 Windows 可能提示发布者未知，因为当前 beta 构建尚未使用生产 Authenticode 证书；不要把未签名 beta 安装包转发为正式版。

- 程序与只读资源：`%LOCALAPPDATA%\Programs\Jarvis OS`
- 配置、DPAPI 密钥、日志、备份与更新证据：`%LOCALAPPDATA%\Jarvis OS`
- PostgreSQL 数据：Jarvis 命名的 Docker volume

安装器不会静默安装 Docker Desktop、Ollama 或模型。缺失依赖会在启动页和运行状态中心显示用途、影响与恢复建议。

## 首次启动

首次启动先创建本机受保护配置。已有源码版 `.env` 时，通过迁移预览选择要导入的字段；取消不会修改、移动或删除旧文件。密钥写入 Windows DPAPI 存储，不进入前端资源、发行清单或诊断包。

Supervisor 会依次检查 PostgreSQL、数据库迁移、Core、Companion 与可选能力。必需组件失败时进入“已阻断”，可选组件失败时进入“已降级”；两者都不会伪装成就绪。

## 日常入口

- 主窗口：中央对话与双侧临时工作台共享同一对话事实源。
- 快速提问：默认 `Ctrl+Alt+Space`，可在设置中关闭或从三组白名单组合中选择。
- 按住说话快捷键：默认关闭；启用后可从三组白名单组合中选择，松开后只生成可编辑草稿。
- 托盘：显示主窗口、快速提问、运行状态、暂停提醒 1 小时、恢复提醒、切换开机启动与完全退出；提醒偏好仍通过 FastAPI 更新。
- 通知：只提供打开上下文或稍后提醒，不批准 R2/R3、付费或外部写操作。
- `.md`/`.txt`：拖入或“使用 Jarvis 打开”后先显示元数据与隐私影响，确认后才读取；仅限 UTF-8、单文件、2 MiB 内、本地普通文件。
- 按住说话：本地录音与转写，松开后先进入可编辑草稿，默认不自动发送。

首次关闭主窗口时，Jarvis 会在窗口内说明默认托盘行为；再次关闭才隐藏。也可在设置中改为完全退出；`.md`/`.txt` 的“使用 Jarvis 打开”入口可随时关闭并移除。完全退出只停止 Jarvis 自己创建且已验证归属的进程，不停止 Docker Desktop、Ollama 或其他应用。

## 运行状态与诊断

在托盘打开“运行状态中心”。它展示 Supervisor 的真实组件状态、版本、检查时间、直接原因与恢复建议。可用动作只有重新检查、重启 Core、打开日志和导出脱敏诊断，不提供任意命令入口。

诊断包不包含 Token、Cookie、Prompt 正文或私人文件内容。若某项依赖仍失败，请记录错误码、组件名和诊断包路径，不要复制真实密钥。

## 更新与回退

Stable 与 Beta 使用独立更新清单。清单先经 RSA 签名验证，安装包再校验大小、SHA-256 与 Windows Authenticode；开发 Beta 可以使用明确标记的开发公钥和未签名包，但 Stable 会强制拒绝。

更新不会在对话流、审批、工具执行或迁移活动期间强制重启。开始替换前会停止自有 Sidecar、生成 PostgreSQL 备份并恢复到临时库验证。新版本安装后必须在 120 秒内进入 ready/degraded；否则 watchdog 自动回装上一版二进制并保留结果。数据库只采用向前兼容迁移，不自动 downgrade。

## 卸载

从 Windows“已安装的应用”卸载 Jarvis OS。卸载器会移除程序、快捷方式、协议、Open With 与开机启动注册项，并停止残留自有进程；默认保留 `%LOCALAPPDATA%\Jarvis OS` 和 PostgreSQL volume。

如确实要彻底删除，在卸载前打开“设置 → Windows Integration → 本地数据维护”：

1. 选择“导出并验证本地数据”。Jarvis 会生成 PostgreSQL 备份，将其恢复到临时库验收，并把数据库备份、普通数据和 DPAPI 加密配置复制到“文档\Jarvis OS Exports”下的独立目录；
2. 确认页面显示“导出已验证”和导出路径；
3. 输入页面给出的完整确认短语，再接受 Windows App 内的二次确认；
4. Jarvis 停止自有运行时，独立清理进程只删除固定的 Jarvis PostgreSQL volume 与 `%LOCALAPPDATA%\Jarvis OS`，保留外部导出包，然后退出。

该入口不接受自定义删除目录。若数据库卷无法安全清理，文件数据不会继续删除。普通卸载始终不会隐式执行上述流程。

## 当前限制

- 只承诺 Windows 11 x64；ARM64、Windows 10、手机和平板原生客户端不在 V4 Stable 范围。
- 生产 Authenticode、Defender/SmartScreen、干净 Win11 路径矩阵、24 小时待机与 7 天观察尚未完成，因此 beta.3 不能标记 Stable。
- 本地模型、Docker Desktop 和 Ollama 仍是用户拥有的外部依赖，Jarvis 只观察或请求启动自己的命名资源。

发布验收人员应按 [Windows 人工验收记录](./JARVIS_OS_V4_WINDOWS_MANUAL_ACCEPTANCE.md) 留存干净账户、通知、文件、麦克风、多显示器、更新与稳定性证据。
