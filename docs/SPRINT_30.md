# Sprint 30：n8n Provider

## 状态

已完成，2026-08-03。

## 目标

在不改变 Jarvis 核心控制权、不影响用户已有 n8n、不接入真实外部账号的前提下，引入一个隔离、可审计、可降级的确定性自动化 Provider。

## 已交付

### 独立部署

- `jarvis-n8n`：固定镜像 `docker.n8n.io/n8nio/n8n:1.123.5`；
- `jarvis-n8n-ingress`：本机签名入口；
- `jarvis-os_jarvis_n8n_data`：专用数据卷；
- `jarvis-automation-internal`：Docker internal 网络；
- `jarvis-automation-ingress`：只供入口绑定本机端口。

n8n 核心没有宿主机端口，编辑器不对电脑、局域网或公网开放。入口只监听 `127.0.0.1:5680`。用户原有名为 `n8n`、端口为 5678 的容器始终保持运行，未被重建、改名或写入。

当前不使用 Redis。n8n 的公开 API、社区包、模板、遥测、版本提醒和执行正文保存均已关闭；容器使用只读文件系统、无新增 Linux capabilities 和 `no-new-privileges`。

### 签名入口

Jarvis Core 的每次请求都包含：

- HMAC-SHA256 签名；
- Unix 时间戳；
- 128-bit 随机 nonce；
- HTTP 方法和固定路径；
- 请求正文 SHA-256。

入口仅允许：

- `/v1/status`；
- `/v1/calendar/read`；
- `/v1/email/draft`。

超过 60 秒的请求、重复 nonce、错误签名、未知路径、过大正文和过大响应都会被拒绝。未签名请求与签名重放均已实测返回 HTTP 401。

### 首批工作流

1. `provider_status`：报告 Provider 就绪状态和已发布工作流；
2. `calendar_read_only`：读取 `jarvis_sandbox` 的确定性测试日历，不创建或修改事件；
3. `email_draft_local`：只生成 Jarvis 内部邮件草稿，固定返回 `not_sent=true`。

三个工作流不包含真实账号、真实凭据、外部网络请求或 Code 节点。

### Tool Gateway 接线

- `automation.provider.status`：R0，本地状态读取；
- `calendar.events.read`：R0，沙盒日历只读；
- `email.draft.prepare`：R1，本地邮件草稿。

输入经过固定账号别名、时间窗口、数量、邮箱格式和正文长度校验。输出会再次验证只读/未发送标记、账号别名、收件人和主题，并固定返回 `credential_exposed=false`。

`calendar.event.upsert` 和 `email.send` 仍为不可用的 R2 预留工具，线上提交均返回 HTTP 409。Tool Catalog 没有任何 R3 工具。

### Approval Center

审批中心新增“隔离自动化通道”：

- 显示 Provider 就绪、独立网络、HMAC、Redis、编辑器、真实账号和外部写入状态；
- 显示三个已发布工作流；
- 提供“读取沙盒日历”和“生成本地邮件草稿”测试；
- 测试结果明确展示 `read_only`、`not_sent` 和 `credential_exposed`；
- Provider 离线会显示离线，但不会把整个 Jarvis 标记为不可用。

## 故障降级验收

短暂停止且仅停止 `jarvis-n8n` 后：

- Jarvis `/health/ready`：`ready`；
- n8n Provider：`offline`；
- `system.status.read`：`succeeded`。

随后 Provider 已恢复到 `ready`。该演练没有停止 PostgreSQL、Jarvis Core 或用户原有 n8n。

## 安全审计

n8n 自带审计确认社区包、公开 API、模板、版本通知和诊断遥测均已关闭。它同时报告三个工作流 Webhook 在 n8n 内部为 `Authentication=None`；这是预期发现，因为 HMAC 验证位于外部签名入口。n8n 核心无宿主机端口并只连接 internal 网络，因此无法绕过入口从主机直接调用。完整决策和未来网络扩展限制见 ADR-0010。

## 工程验收

- API 完整回归：159 项通过、1 项跳过；
- API 与桌面伴侣联合回归：165 项通过、1 项跳过；
- Python Ruff：通过；
- 前端 ESLint：通过；
- TypeScript：通过；
- Next.js 正式生产构建：18 个页面通过；
- 签名请求：HTTP 200；
- 未签名请求：HTTP 401；
- 重放请求：HTTP 401；
- R0 日历读取：`succeeded`、`read_only=true`、无审批；
- R1 邮件草稿：`succeeded`、`not_sent=true`、无审批；
- 两项结果：`credential_exposed=false`；
- 真实日历写入与邮件发送：HTTP 409；
- 浏览器错误：0；
- 失败请求：0；
- 截图：`artifacts/n8n-provider-sprint30.png`；
- 服务已重新启动，Provider 已恢复到 `ready`。

最终本机安全检查全部阻断项通过；保留一项非阻断提醒：`.env` 继承了 Windows 的宽泛本机读取权限。因此当前仍应只使用个人 Windows 账号，不要把该账号或电脑作为多人共享环境。按既定规则，Jarvis 没有自动修改凭据文件 ACL。

## 恢复点

- 文件：`backups/jarvis-20260803T033700Z-b8ff0d2b.dump`；
- SHA-256：`c60e3f067638aab4002474b7c91114f24b35df5f5fc0cf329d0b47f84a8e0f59`；
- 恢复验证：61 张表；
- Schema：`20260802_0024`。

n8n 当前没有真实账号和不可重建业务数据；工作流以版本化 JSON 保存在仓库，专用卷可由启动过程重新生成。`.data/n8n-secrets` 不进入数据库备份，也不会被自动导出或提交；丢失时应重新运行 Provider 设置流程，而不是从日志或 Agent 记录恢复。

## Feature Flag

代码默认安全关闭：

```text
V2_N8N_PROVIDER_ENABLED=false
```

当前个人环境已在隔离、签名、故障演练和恢复点验收后显式启用。关闭该开关不会影响聊天、记忆、成长、研究、投资或其他核心工具。

## 架构决策

- [ADR-0010：n8n 只作为隔离的确定性工具 Provider](adr/0010-n8n-isolated-deterministic-provider.md)

## 下一阶段

Sprint 31：Read-only Browser Research。先做隔离 Browser Worker、公开白名单来源、来源与截图证据、Prompt Injection 防护；不登录主账号、不上传简历、不自动投递。
