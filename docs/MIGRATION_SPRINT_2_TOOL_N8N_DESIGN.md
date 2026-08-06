# Tool & Automation — 交接说明 3/3：n8n 真实工作流（日历写入 / 邮件草稿 · 测试账号验收）

- **产出**：Tool & Automation Agent（Sprint 2 只读预研）
- **日期**：2026-08-06
- **类型**：设计交接说明（含现状证据行号），待 Tech Lead 审核后归档 `docs/`
- **对应任务**：MIGRATION_ROADMAP.md Sprint 5 L163「n8n 真实工作流（日历写入/邮件草稿，先测试账号验收）」；
  蓝图 §11.3（`docs/JARVIS_OS_V2_ARCHITECTURE_MIGRATION_PLAN.md:714-720`，L720「每个流程都必须先通过
  无真实账号或测试账号验收」）
- **本轮改动**：无

---

## 0. 结论摘要

1. 新增 **2 个 workflow JSON**（`calendar-event-upsert-test.json`、`email-draft-test-account.json`），
   **不改**现有 3 个无副作用 workflow（`calendar-read-only.json`、`email-draft-local.json`、
   `provider-status.json`）。
2. 新增 **2 个固定 ingress 路径**（`/v1/calendar/write`、`/v1/email/draft/create`），复用现有
   HMAC-SHA256/时间戳/nonce/正文哈希/固定 key id 校验；端口仍是 `127.0.0.1:5680`，容器拓扑与
   internal 网络不变。
3. 全部写操作走 **R2 预览-批准-执行**：启用已预留的 `calendar.event.upsert`（R2），新增
   `email.draft.create`（R2，在测试邮箱内建草稿、不发送）；`email.send` 保持不可用
   （ADR-0010 #13）。
4. 测试账号凭据只存在于 `.data/n8n-secrets`（gitignore 排除），仅挂入 n8n 容器；Core/ingress
   不接触凭据，Agent 结果与审计不含凭据原文。

---

## 1. 现状证据（文件:行）

| # | 事实 | 证据 |
|---|---|---|
1 | n8n 只做确定性 Tool Provider；独立容器；仅 ingress 映射 127.0.0.1:5680；HMAC 签名；入口仅 3 个固定路径；首批工作流无真实账号/外部写入；真实修改未来只能作为 R2；凭据仅存 `.data/n8n-secrets` | `docs/adr/0010-n8n-isolated-deterministic-provider.md:14-28`（#2/#3/#4/#5/#6/#7/#11/#12/#13/#16） |
2 | Core 侧入口路径白名单 3 个 | `apps/api/app/services/n8n_provider.py:16-22` |
3 | Core 侧 loopback 强校验、secret 必须落在 `.data/n8n-secrets`、长度校验 | `n8n_provider.py:33-56` |
4 | 签名头：X-Jarvis-Key-Id/Timestamp/Nonce/Signature；正文规范化 | `n8n_provider.py:72-97` |
5 | 调用边界：超时 12s、响应 ≤131_072 字节、禁重定向 | `n8n_provider.py:100-140` |
6 | ingress 路径映射（3 条 → n8n webhook）、HMAC 校验、nonce 防重放、body ≤65_536、响应 ≤131_072、转发仅到内部 N8N_INTERNAL_URL | `infra/n8n/ingress/server.js:22-26`（allowedPaths）、`:18`（maxBody）、`:58-62`（响应限制）、`:72-91`（forward，redirect manual）、`:93-126`（签名/重放校验） |
7 | n8n 容器无宿主端口、internal 网络、read_only、cap_drop ALL、镜像固定 1.123.5、禁公开 API/社区包/模板、执行正文不落盘；ingress 仅映射 127.0.0.1:5680 | `infra/docker-compose.yml`（n8n 服务段：image/security_opt/environment；`automation` 网络 `internal: true`；ingress `ports: 127.0.0.1:5680`；secrets 挂载） |
8 | 现有 3 个 workflow 均为无副作用响应（fixture 事件 / 本地草稿 / 状态），`active: false` 由 bootstrap 激活 | `infra/n8n/workflows/calendar-read-only.json`（read_only: true、account_alias=jarvis_sandbox）、`email-draft-local.json`（draft_only、not_sent: true）、`provider-status.json`（real_accounts_connected: false、external_writes_enabled: false） |
9 | bootstrap 发布目录内**全部** `*.json`（POST 新建 + 激活）；start.sh 以版本 marker 决定是否重跑 | `infra/n8n/bootstrap.js:39-46`、`infra/n8n/start.sh`（marker）；compose `JARVIS_N8N_WORKFLOW_VERSION: sprint30-v2` |
10 | 现有工具：`calendar.events.read`（R0，account_alias 限定 `^jarvis_sandbox$`）、`email.draft.prepare`（R1 本地草稿）；预留 `calendar.event.upsert`（R2，handler=None/available=False，已授权 GROWTH）、`email.send`（R2，allowed_agents=∅） | `apps/api/app/services/tool_catalog.py:85-89`（read schema）、`:100-108`（draft schema）、`:708-720`、`:722-736`、`:790-824`（预留段） |
11 | R2 映射：MODIFY_CALENDAR / EMAIL_ACTION → CONFIRMED_WRITE | `apps/api/app/services/agent_core/policy.py:30-36` |
12 | GROWTH AgentSpec 已声明 `calendar.event.upsert` 与 `confirmation_actions={MODIFY_CALENDAR}`、max_risk=CONFIRMED_WRITE | `apps/api/app/services/agent_core/catalog.py:136-148` |
13 | 状态面结构（isolated/signed_webhooks/real_accounts_connected/external_writes_enabled） | `n8n_provider.py:143-171`；`apps/api/app/schemas/tool.py:143-154` |

---

## 2. 测试账号验收方案

### 2.1 账号与凭据边界

- 账号：专用 **`jarvis_test`** 测试账号别名（Google Calendar / Gmail 测试邮箱），与用户真实账号
  完全分离；沿用「测试账号先验收、真实账号后置」原则（ADR-0010:66 拒绝 Sprint 30 直连真实账号）。
- 凭据：OAuth/client 凭据文件只放 `.data/n8n-secrets/`（`.gitignore` 已排除 `.data/`），以
  `/run/secrets` 只读挂入 n8n 容器；n8n 凭据实体用现有 `N8N_ENCRYPTION_KEY` 加密。
- **不引入新凭据暴露**：ingress 仍只有 webhook secret；Core 仍只读 webhook secret 路径
  （`n8n_provider.py:49-56`）；状态接口、Agent 结果、审计记录不得含凭据原文或令牌
  （ADR-0010 #16，`:28`）。

### 2.2 新增工作流（不改现有 3 个 JSON）

1. `calendar-event-upsert-test.json`：
   webhook → Google Calendar API（测试账号）创建事件 → 返回 envelope：
   `{status: "completed", account_alias: "jarvis_test", event_id, requested_window, idempotent, credential_used: false}`。
2. `email-draft-test-account.json`：
   webhook → Gmail API（测试账号）创建草稿 → 返回 envelope：
   `{status: "draft_created", not_sent: true, account_alias: "jarvis_test", draft_id, idempotent, credential_used: false}`。

两者都不含 `email.send`（发送保持 Provider 不可用，ADR-0010 #13）；不引入 Code 节点，仅
HTTP Request + 确定性参数映射（ADR-0010 #9/#11 精神：禁 Code 节点、禁执行正文保存）。

### 2.3 入口与 Core Provider 扩展

- `n8n_provider.py:16-22` 的 `ALLOWED_INGRESS_PATHS` 增加 `/v1/calendar/write`、
  `/v1/email/draft/create`；`ingress/server.js:22-26` 的 `allowedPaths` 同步增加两条映射。
- 校验链不变：key id、时间戳（≤60s 偏差）、32 位 hex nonce 防重放、正文 SHA256、HMAC-SHA256、
  loopback-only、body/响应上限、`redirect: manual`（`server.js:18`、`:58-62`、`:93-126`）。
- 端口/网络不变：ingress 仍 `127.0.0.1:5680`，n8n 仍在 `automation`（internal）网络，无宿主端口。
- **注意**：ADR-0010 #6（`:18`）「入口只允许三个固定路径」与 #11（`:23`）「首批工作流…」的字面
  范围需要 ADR 修订（建议新增 ADR-0012 或修订 0010），由 Tech Lead 执行；本设计不自行改 ADR。

### 2.4 R2 工具注册与审批（结合交接 2/3 流程）

- `calendar.event.upsert`：从 reserved（`tool_catalog.py:790-807`）转为可用：补真实
  preview_builder（展示 title/starts_at/ends_at/timezone/account_alias=jarvis_test）与 handler
  （调 `/v1/calendar/write`），`available=True`；GROWTH 已获授权（`catalog.py:136-148`），无需改 spec。
- `email.draft.create`（新工具）：`action_kind=EMAIL_ACTION`（→R2，`policy.py:33`），授权
  CORE/RESEARCH/GROWTH（需同步 3 个 spec 或走派生视图——见交接 2/3）；input schema 限定
  `account_alias ^jarvis_test$`、to/subject/body、校验时间窗与长度；handler 调
  `/v1/email/draft/create`，envelope 强校验 `status=draft_created ∧ not_sent=true ∧ account_alias=jarvis_test`。
- 两者都走 Tool Gateway R2 管线：预览（含目标账号与操作摘要）→ 批准（可修改提案）→ 独立执行
  （参数哈希复核 + 幂等键）；审批在 Approval Center 可见（`routes/tools.py:266-366`）。
- 日历回读校验：`calendar.events.read` 的 schema（`tool_catalog.py:86`）与 handler 断言
  （`:373`、`:382`）当前限定 `jarvis_sandbox`；Sprint 5 需放开/新增 `jarvis_test` 回读路径
  （R0 读测试账号），用于验收断言「事件已创建且只创建一次」。

### 2.5 验收用例（先测试账号）

| 用例 | 步骤 | 期望 |
|---|---|---|
| 日历写入-成功 | R2 提交 → 预览 → 批准 → 单独执行 | 返回 `event_id`；回读测试日历可见且时间窗一致；`credential_used: false` |
| 日历写入-幂等 | 同 idempotency_key + 同参数重放 | 仅一次副作用；gateway 返回原执行记录（`tool_gateway.py:411-453`） |
| 日历写入-未批准 | 提交后直接调 execute | 409 approval_required（`tool_gateway.py:275-280`） |
| 邮件草稿-成功 | R2 提交 → 预览 → 批准 → 执行 | 测试邮箱出现草稿；`not_sent: true`；收件人/主题与请求一致（对照 `tool_catalog.py:408-409` 的校验思路） |
| 邮件草稿-不发送 | 全流程后核对 | 无已发送邮件；`email.send` 仍 404/不可用 |
| 签名-重放 | 重放已用 nonce | 401（`server.js:104`、`:118-122`） |
| 边界-参数漂移 | 批准后改参数再执行 | 409 参数哈希不一致（`tool_gateway.py:281-286`、`:292-297`） |
| 边界-离线 | 停止 n8n 容器后调用 | Provider 返回安全 offline，核心功能不受影响（`n8n_provider.py:124-127`；ADR-0010 #15） |

测试数据清理：删除测试日历事件/草稿是删除动作（R3），**不由 Agent 执行**；由用户手动或独立
运维脚本在测试账号内清理，脚本不得注册为 Agent 工具。

---

## 3. 边界保持清单（对照 ADR-0010）

- 容器拓扑：n8n 无宿主端口、ingress 仅 127.0.0.1:5680、internal 网络不变（#3/#4/#7）。✓
- 签名与防重放：HMAC-SHA256/时间戳/nonce/正文哈希/固定 key id 不变（#5/#6）。✓
- 镜像/加固：固定 1.123.5、read_only、cap_drop、禁编辑器/公开 API/社区包/模板/遥测不变（#8/#9）。✓
- 凭据：仅 `.data/n8n-secrets`；状态/结果/审计无凭据（#16）。✓
- 现有 3 个 workflow JSON **零改动**；只新增文件。✓
- `email.send` 保持不可用；删除数据保持 R3（#13/#14）。✓
- browser-worker 7 层隔离不削减：本设计不触碰 browser-worker。✓

---

## 4. 必须的配套契约变更（实施时提交 Tech Lead）

1. **ADR 修订**：ADR-0010 #6（路径数量）与 #11（首批范围）需增补「测试账号工作流」条目。
2. **bootstrap 幂等化**（我方 `infra/n8n/bootstrap.js`）：当前 POST 新建不查重（`:39-46`），
   新增 workflow 后 bump `JARVIS_N8N_WORKFLOW_VERSION`（compose 现为 `sprint30-v2`）会在既有卷
   **重复创建**工作流；必须先改为按 name 查存在则更新/跳过，再 bump marker。
3. **config/schema 契约**：`account_alias` 扩展、`N8nProviderStatusResponse` 增加
   `test_accounts_connected` 区分字段（`schemas/tool.py:143-154`）→ Tech Lead。
4. **Provider 状态面**：`n8n_provider.py:143-171` 保持 `real_accounts_connected: false`，
   新增 `test_accounts_connected` 语义，避免把测试账号误报为真实账号。
5. **工具注册**：`email.draft.create` 新增走交接 2/3 交叉校验流程（spec 侧授权由 AI Engineer 目录
   同步或派生视图落地）。

---

## 5. 风险与回滚

- 风险 1：测试账号凭据泄漏 → 最小权限测试账号 + 可随时撤销；凭据不落日志/状态/Agent 结果。
- 风险 2：工作流响应不可信（envelope 异常）→ handler 强校验并抛错拒收（沿用
  `tool_catalog.py:370-376`、`:400-409` 模式），绝不把 n8n 输出当可信指令。
- 风险 3：bootstrap 重复发布 → §4.2 幂等化先行，否则禁止 bump marker。
- 风险 4：Provider 故障 → 离线降级不伤核心（ADR-0010 #15）；回滚方式：feature flag 关闭新增路径
  与工具、恢复旧 ingress 路径表即可。

---

## 6. 交接说明

- **修改文件清单**：无（只读预研；未写任何产品文件）。
- **测试结果**：未运行（本轮禁止写代码/测试）。
- **风险说明**：ADR 路径数条款与 bootstrap 幂等是两个前置依赖，Sprint 5 实施顺序应为
  「ADR 修订 → bootstrap 幂等 → ingress 路径 → workflow JSON → 工具注册 → 测试账号验收」。
- **AI 辅助记录**：未调用付费模型、未发送私人数据。
