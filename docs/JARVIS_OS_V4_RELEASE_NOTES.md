# Jarvis OS 4.0.0-beta.3 Release Notes

> 发布状态：Beta 验证候选，不是 Stable 公开发行版  
> 平台：Windows 11 x64  
> 安装器 SHA-256：`96CDAAD867F8588EC5BDE37DF4BAF0F238F4F5E76FA8E2C9A3955D75D195CD68`

## 本版重点

- 以 Tauri 2 + WebView2 提供原生 Windows 主窗口、启动页、单实例、托盘和窗口状态恢复；Next.js 业务界面静态嵌入，不依赖 Node Server 或固定 3000 端口。
- Runtime Supervisor 统一管理打包的 FastAPI Core 与 Companion，通过动态回环端口、短生命周期桌面会话凭证、精确 Origin 和 Windows Job Object 限定运行边界。
- 提供运行状态中心、结构化错误码、恢复建议、日志入口和二次脱敏诊断导出；PostgreSQL 仍是唯一业务事实源。
- 状态中心覆盖 Jarvis App、Core、PostgreSQL、Ollama、Companion、本地语音与 Browser Worker；可靠性台账只记录封闭状态、结果和耗时，不记录提示词、文件正文或对话内容。
- 新增全局快速提问窗口、通知深链与安全动作、受控 `.md/.txt` 文件预览、按住说话、麦克风权限恢复、托盘暂停/恢复提醒和可选开机启动。
- 提供 Stable/Beta 更新通道、签名清单、SHA-256/Authenticode 校验、更新前数据库恢复验证、120 秒启动 watchdog 与上一版二进制回退。
- 普通卸载默认保留数据；需要彻底清理时，必须在设置中完成“导出并验证 → 精确短语 → 二次确认”。清理目标固定为 Jarvis 数据根和专属 PostgreSQL volume，Docker 清理失败时回滚暂存目录。

## 安装与升级

- 安装方式：per-user NSIS，不要求管理员权限；默认安装到 `%LOCALAPPDATA%\Programs\Jarvis OS`。
- 数据目录：`%LOCALAPPDATA%\Jarvis OS`，与程序目录分离。
- 外部依赖：WebView2、Docker Desktop/PostgreSQL 和可选 Ollama 均保持可见，不静默捆绑或替用户安装。
- 旧源码配置只通过首次启动迁移向导导入；导入前显示白名单字段，密钥写入当前 Windows 用户绑定的 DPAPI 存储，原 `.env` 不被移动或修改。
- 覆盖升级前停止 Jarvis 自有 Sidecar，并对 PostgreSQL 备份执行临时库恢复验证；不自动 downgrade 数据库。

## 支持矩阵

| 环境/能力 | beta.3 状态 | 说明 |
|---|---|---|
| Windows 11 x64 | 支持，仍需干净机最终验收 | 当前开发机为 Windows 11 `10.0.26200` |
| Windows 10 | 不承诺 | 不进入 V4 Stable 关键路径 |
| Windows ARM64 | 不支持 | 当前只构建 `x86_64-pc-windows-msvc` |
| macOS / Linux | 不支持桌面安装包 | 源码 Web 模式不由本版 Windows 安装器覆盖 |
| Android / iOS / 平板原生 App | 不在范围 | V4 不改变现有平板伴生路径 |
| 普通 Windows 用户安装 | 设计支持，待干净机复验 | NSIS `currentUser`；程序与数据目录分离 |
| 中文用户名/路径 | 当前开发机通过 | 仍需另一普通受限账户补齐人工矩阵 |
| 无系统 Node/Python | 支持 | 静态 UI + PyInstaller one-directory Sidecar |
| Docker Desktop / PostgreSQL | 必需外部依赖 | 缺失时进入可诊断阻断状态，不静默安装 |
| Ollama / 本地模型 | 可选 | 不可用时降级，不冒充全部就绪 |
| n8n / Browser Worker | Feature Flag 可选 | 失败不得冒充 Core 失败 |
| 自动更新 | Beta 验证 | 当前仍嵌入开发更新公钥，禁止 Stable |
| Authenticode / SmartScreen | 未完成 | 当前安装器 `NotSigned`，禁止公开 Stable |

## 已知限制与风险

- 当前安装器未进行 Authenticode 签名，并使用开发更新公钥，只适合本机和受控测试。
- 本轮依赖集合未变化，但最终联网安全审计尚未获得授权；现有 audit summary 只能作为上一轮记录，不能冒充当前审计。
- 当前最终哈希尚未执行 50 次安装版启动/退出复验；既有 50 次结果来自 beta.3 前一构建。
- 旧 7 天观察记录绑定前一构建，不能复用；当前最终包须在完成首次引导、启动 Core/Companion 后重新开始 168 小时窗口，并补齐至少两次睡眠恢复样本。
- 尚未在独立干净 Windows 11 x64 普通账户完成安装、升级、卸载、数据删除、恢复、缩放、多显示器和麦克风矩阵。
- 不提供静默 Docker/Ollama 安装、持续监听唤醒词、任意文件读取、任意 Shell 或无审批高风险电脑控制。

## 验证摘要

- API：385 passed，38 skipped。
- Desktop Python：8 passed。
- Rust：36 passed。
- Desktop Node 契约：22 passed。
- Web：TypeScript、ESLint 和 26/26 静态路由构建通过。
- 最终安装器：69,499,831 bytes；SBOM 1186 components。
- Release Gate：正确拒绝当前候选进入 Stable，原因包括未签名、开发更新公钥、dirty manifest/worktree、7 天窗口和采样覆盖不足。

完整证据见 [V4 交付日志](./JARVIS_OS_V4_DELIVERY_LOG.md)、[验收矩阵](./JARVIS_OS_V4_ACCEPTANCE_MATRIX.md)和[人工验收清单](./JARVIS_OS_V4_WINDOWS_MANUAL_ACCEPTANCE.md)。
