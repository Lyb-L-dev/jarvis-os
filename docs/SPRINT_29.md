# Sprint 29：Tool Gateway 与 Approval Center

## 状态

已完成，2026-08-02。

## 目标

让 Jarvis 第一次具备可审计的工具执行边界：模型和 Agent 只能提出工具请求，不能直接产生副作用；所有动作先经过工具定义、Agent 白名单、R0–R3 策略、参数 Schema、敏感信息和幂等校验。

## 已交付

### Tool Registry

每个工具必须声明：

- 稳定 `tool_id` 与版本；
- 输入与输出 Schema；
- R0–R3 对应动作类型；
- 作用域、数据敏感度与是否有外部副作用；
- 可调用 Agent 白名单和 Agent 风险上限；
- 幂等策略、超时、重试和失败策略；
- 凭据作用域和审计字段；
- Provider 是否已经可用。

Registry 在注册阶段拒绝全部 R3 动作。没有工具定义就没有 Agent 执行入口。

### 风险策略

| 级别 | 当前含义 | 执行方式 |
| --- | --- | --- |
| R0 | 本地读取、公开来源、知识搜索 | 可自动执行，保留审计 |
| R1 | 生成或保存 Jarvis 内部草稿 | 可自动执行，不对外发送 |
| R2 | 修改文件、日历、邮件、外部账号、浏览器提交 | 预览 → 用户批准 → 单独执行 |
| R3 | 投资交易、支付、删除数据、凭据操作 | 永不注册、永不自动执行 |

### 首批工具

已实际接通：

- `system.status.read`：R0，只读取本地功能状态；
- `draft.text.prepare`：R1，只生成 Jarvis 内部文本草稿；
- `workspace.file.write`：R2，只能写入 `.data/tool-sandbox`，只允许 `.md`、`.txt` 和 `.json`。

已登记但未连接 Provider：

- `calendar.event.upsert`；
- `email.send`；
- `external.account.update`；
- `browser.submit`。

这些预留工具不能提交执行请求。Sprint 29 没有连接真实日历、邮箱、浏览器或外部账号，也没有读取任何凭据。

### R2 三阶段确认

1. Agent 提交提案，只生成参数哈希和副作用预览；
2. 用户可以修改、批准或拒绝；任何修改都会重建预览和参数哈希；
3. 批准后仍不会自动执行，用户必须单独点击“执行已批准动作”。

批准是限时、单次使用的。执行前 Gateway 会再次校验 Agent、工具版本、Schema、敏感信息、路径和参数哈希。失败后不会自动重试可能有副作用的动作。

### 幂等与审计

- 幂等范围：`user + tool + version + idempotency_key`；
- 相同键、相同参数返回同一执行记录；
- 相同键、不同参数被拒绝；
- 成功动作重放只返回原结果，不再次调用工具；
- `tool_executions` 保存请求、结果和副作用证明；
- `tool_approvals` 保存预览、范围、决定、过期和消费时间；
- `tool_execution_events` 保存验证、审批、执行、失败和重放事件；
- 记录错误时不回显私人正文或凭据。

### Approval Center

新增 `/approvals`：

- 待确认、已批准待执行和历史三种视图；
- 工具审批与已有 DeepSeek 单次任务授权统一展示；
- 展示执行前预览、目标、大小、内容指纹、Agent、策略和过期时间；
- 用户可修改预览、拒绝、批准和单独执行；
- 固定展示 R3 四项永久禁用边界；
- 提供受控文件工具实验区，默认只生成预览。

## 验收证据

线上安全验收：

- R0 状态读取：`succeeded`，没有审批记录；
- R2 文件写入：停在 `pending_approval`；
- 未批准时直接调用执行：HTTP 409；
- 目标文件存在：`false`；
- Tool Catalog 中 R3 工具数：0；
- Approval Center 正确显示 4 个永久禁用动作；
- 浏览器错误：0；
- 失败请求：0；
- 截图：`artifacts/approval-center-sprint29.png`。

测试环境用临时目录完成了批准、执行和重放测试，证明成功重放不会再次修改文件。线上没有替用户批准或执行 R2 动作，保留一条无副作用的待确认验收预览供界面检查。

## 工程验收

- 数据库迁移：`20260802_0023 -> 20260802_0024`；
- 后端完整回归：153 项通过、1 项跳过；
- Python Ruff：通过；
- 前端 ESLint：通过；
- TypeScript：通过；
- Next.js 正式生产构建：18 个页面通过；
- API Live / Ready：通过；
- Tool Catalog 与 Approval Center Live API：通过；
- Approval Center 视觉验收：通过；
- 服务已重新启动。

## 恢复点

- 文件：`backups/jarvis-20260802T072526Z-9366c104.dump`；
- SHA-256：`9cf24901f6e0424d967a86c4e904c9441487fc4f9785dad59fa81ad7cf7fcbea`；
- 恢复验证：61 张表；
- Schema：`20260802_0024`。

## Feature Flags

代码默认安全关闭：

```text
V2_TOOL_GATEWAY_ENABLED=false
V2_APPROVAL_CENTER_ENABLED=false
```

当前个人环境在迁移和安全验收完成后显式启用两项功能。关闭它们不会破坏既有聊天、成长、研究、正式记忆或投资记录。

## 架构决策

- [ADR-0009：模型只能提出工具请求，副作用必须由 Tool Gateway 仲裁](adr/0009-tool-gateway-human-control-boundary.md)

## 下一阶段

Sprint 30：n8n Provider。先完成隔离部署、签名 Webhook、只读日历、本地邮件草稿和测试账号验收；真实外部写入继续由 Approval Center 逐次确认。
