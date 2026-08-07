# ADR-0010：n8n 只作为隔离的确定性工具 Provider

## 状态

已接受，2026-08-03。

## 背景

Jarvis 已在 Sprint 29 建立 Tool Gateway、R0–R3 策略、审批、幂等和审计。n8n 适合承载可重复的外部服务流程，但如果把它放进核心路由、开放编辑器、复用个人 n8n、直接保存真实账号凭据或允许任意 Webhook，会扩大故障和权限边界。

## 决策

1. n8n 只实现确定性的 Tool Provider，不承担 Agent Router、Memory、Policy 或投资决策；
2. 使用独立的 `jarvis-n8n` 容器、数据卷和 Docker 内部网络，不复用用户已有的 `n8n`；
3. n8n 核心不映射宿主机端口，也不对外暴露编辑器；
4. 只有 `jarvis-n8n-ingress` 映射 `127.0.0.1:5680`，不监听局域网或公网；
5. Jarvis Core 与入口之间使用 HMAC-SHA256、时间戳、随机 nonce、正文哈希和固定 key id；
6. 入口只允许三个固定路径，并拒绝超时签名、重放、重定向、超限请求和超限响应；
7. 入口完成签名校验后，才通过仅两个容器可见的内部网络转发到 n8n；
8. n8n 镜像固定为本机已验证的 `1.123.5`，不使用浮动 `latest`；
9. 禁用公开 API、社区包、模板、遥测和成功/失败执行正文保存；
10. 不引入 Redis；当前低并发个人场景使用 n8n 自带 SQLite 和独立数据卷；
11. 首批工作流只有 Provider 状态、沙盒日历只读和本地邮件草稿，不包含真实账号、真实凭据、Code 节点或外部写入；
12. `calendar.events.read` 属于 R0，`email.draft.prepare` 属于 R1；两者都必须经 Tool Gateway 校验并写入执行审计；
13. 真实日历修改与邮件发送继续保持 Provider 不可用，未来只能作为 R2 经预览、批准和独立执行；
14. 投资交易、支付、删除数据和凭据操作继续属于 R3，不因引入 n8n 获得执行入口；
15. n8n 离线时 Provider 返回安全的 `offline`，但健康检查、聊天、记忆和其他核心工具继续运行；
16. 凭据文件只保存在被 `.gitignore` 排除的 `.data/n8n-secrets`，状态接口、Agent 结果和审计记录都不得返回凭据。

## n8n 安全审计说明

n8n 自带审计会把三个内部 Webhook 标记为“Authentication=None”。这是因为审计器只能看到工作流本身，无法识别容器外的签名入口。该发现由以下补偿控制覆盖：n8n 没有宿主机端口、只加入 internal 网络、该网络只有 n8n 和入口、入口先执行 HMAC/时效/nonce/路径校验。未签名请求实际返回 HTTP 401，重复请求也返回 HTTP 401。

如果未来 n8n 核心需要加入共享网络或开放编辑器，必须先重新设计第二层认证；不能沿用当前补偿控制直接扩大网络范围。

## 理由

- 保留 Jarvis Core 对权限、审批、模型和记忆的唯一控制权；
- 不让自动化平台故障拖垮个人 AI 核心；
- 不碰用户原有 n8n 数据和工作流；
- 先以无真实账号的 R0/R1 流程验证连接、审计和降级；
- 用最小组件满足当前个人低并发场景，避免提前引入 Redis 和额外运维成本。

## 后果

- 当前不能读取真实 Google/Outlook 日历，也不能发送邮件；
- n8n 工作流必须在仓库中以 JSON 维护，并由受控启动过程发布；
- Provider 状态会出现在 Approval Center，用户能区分“核心正常”和“自动化离线”；
- 未来每个真实外部账号都需要单独的凭据存储、最小权限、撤销和 R2 验收设计；
- 内部 Webhook 的审计发现必须随网络拓扑一起复核，不能只看 n8n 单点扫描结论。

## 被拒绝的方案

### 复用用户已有 n8n

拒绝。会混合个人工作流、凭据、升级节奏和故障边界。

### 让 Jarvis 直接调用 n8n 的公开编辑器或 API

拒绝。需要扩大管理权限并暴露不必要的工作流创建能力。

### 让 n8n 代替 LangGraph 或 Agent Router

拒绝。n8n 负责确定性执行，意图判断、模型选择、Memory 和 Policy 仍由 Jarvis Core 管理。

### Sprint 30 直接连接真实日历和邮箱

拒绝。先证明隔离、签名、重放防护、故障降级和 Tool Gateway 审计，再单独立项真实账号接入。

---

## Sprint 5 修订（2026-08-06，Supersedes #6/#11 的部分措辞）

本修订由 Tool & Automation Agent 在 Sprint 5 落地（Tech Lead 审核批准），不改变本 ADR 的
隔离/签名/凭据边界原则，仅扩展已受控的路径与工作流范围：

1. **#6 修订**：入口固定路径由 3 个扩为 **5 个**——新增
   `/v1/calendar/write` 与 `/v1/email/draft/create`（复用 HMAC/时效/nonce/正文哈希/固定 key id，
   仍仅监听 `127.0.0.1:5680` + internal 网络）。
2. **#11 修订**：新增**测试账号**工作流 `calendar-event-upsert-test.json` 与
   `email-draft-test-account.json`（webhook → Google Calendar 创建 / Gmail 创建草稿，
   envelope 强制 `not_sent: true` / `credential_exposed: false`）。凭据仍为占位符，
   工具注册 `available=False`（环境门控）；未配置测试账号前不产生任何真实外部写入。
3. **不变项**：#12/#13 的真实日历修改与邮件发送仍需 R2 预览-批准-执行；
   #14 投资交易、支付、删除数据、凭据操作仍为 R3；#16 凭据只在 `.data/n8n-secrets`。
4. **启用前置**：测试账号就绪后按 `infra/n8n/workflows/README.md` 校验节点 schema →
   替换凭据占位 → bump `JARVIS_N8N_WORKFLOW_VERSION`（bootstrap 已幂等化，不会重复发布）→
   置 `available=True` 并更新本 ADR 的“后果”节。
5. **状态面契约（2026-08-07 收尾）**：`N8nProviderStatusResponse` 新增
   `test_accounts_connected` 字段，与 `real_accounts_connected` 区分“测试账号已连接”
   与“真实账号已连接”。当前恒为 `false`（凭据占位未配置）；测试账号激活后该字段
   置 `true`，`real_accounts_connected` 仍保持 `false`，直至真实账号按 #12/#13
   R2 审批路径接入。前端类型与 `generated.ts` 已同步。
