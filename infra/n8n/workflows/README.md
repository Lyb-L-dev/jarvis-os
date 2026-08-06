# Jarvis n8n workflows

- `provider-status.json` / `calendar-read-only.json` / `email-draft-local.json`
  — Sprint 30 首批无副作用工作流（**不可修改**，ADR-0010 #11）。
- `calendar-event-upsert-test.json` — 测试日历账号写入（R2 工具 `calendar.event.upsert`）。
- `email-draft-test-account.json` — 测试邮箱创建草稿（R2 工具 `email.draft.create`，不发送）。

## 启用前置（环境就绪前不要 bump `JARVIS_N8N_WORKFLOW_VERSION`）

1. 在 `.data/n8n-secrets/` 建立测试账号凭据（gitignore 排除），以 `/run/secrets` 只读挂入
   `jarvis-n8n` 容器，并写入 n8n 凭据实体（用现有 `N8N_ENCRYPTION_KEY` 加密）。
2. 将两个 JSON 中的凭据占位 id/name（`jarvis-test-calendar-credential` /
   `jarvis-test-gmail-credential`）替换为真实凭据实体。
3. 校验 Google Calendar / Gmail 节点参数名与 n8n 1.123.5 实际 schema 一致。
4. bootstrap 已幂等（按 name 更新），此时再 bump `JARVIS_N8N_WORKFLOW_VERSION`
   （`infra/docker-compose.yml` 现为 `sprint30-v2`）触发发布。

两个工作流都返回确定性 envelope（`credential_exposed: false`、不含令牌），
Core 侧 handler 会强校验后再入库；`email.send` 保持不可用（ADR-0010 #13）。
