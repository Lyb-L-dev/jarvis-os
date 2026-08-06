# MIGRATION_SPRINT_5.md — 迁移 Sprint 5 交付与验收记录

- **文档类型**：Tech Lead 产出（迁移路线图 Sprint 5：工具与自动化扩展）
- **日期**：2026-08-06
- **状态**：✅ 已验收（合入 dev；main 保持基线）

---

## 1. 交付物总览

| Agent | 任务 | 状态 | 证据 |
|---|---|---|---|
| Tool & Automation | Computer-use 阶段 3 | ✅ | `tool_catalog.py` 预览/执行强制 `stage>=3`；写前备份 `.backups/{execution_id}` + SHA256 + TOCTOU；新增 R2 工具 `workspace.file.restore`；阶段 2 只读+计划预览兼容 |
| Tool & Automation | 工具注册交叉校验消费 | ✅ | `tool_gateway.py` 运行时消费 `effective_tools_for_spec(spec)`（注册表派生单一来源） |
| Tool & Automation | n8n 测试账号工作流 | ✅ 代码（环境门控） | 新增 2 条 ingress 路径 + 2 个 workflow JSON（`available=False`，凭据占位）+ bootstrap 幂等化 + README |
| Tool & Automation | Tool Gateway policy_gate 审计 | ✅ | `submit_tool` 按 `v2_policy_enforcement_enabled` 写执行级审计步骤（仅审计，不改 R2/R3 语义） |
| AI Agent Engineer | AgentSpec 白名单单一来源（H5） | ✅ | `contracts.py` 派生视图 `effective_tools` + `catalog.py` 派生 API + `reconciliation.py`（R1-R5 + CLI，漂移 exit 1） |
| QA & Reliability | R2/R3 不变量 + 对账审计 + 门控 | ✅ | `test_tool_invariants.py`（R3=0 / R2 未确认写=0）、`test_tool_reconciliation_audit.py`（6 例，零漂移）、`test_tool_sprint5_gates.py`（4 门控激活） |

## 2. Tech Lead 裁决

1. **Computer-use 阶段 3 激活**：`config.py` + `.env.example` 的 `computer_use_stage` 2→3
   （Sprint 5 目标；回滚 = 改回 2）。激活后阶段 2 只读+计划预览能力保持兼容；
   写/恢复均走 R2 预览-批准-执行 + 沙箱备份。
2. **ADR-0010 修订**（Supersedes #6/#11 部分措辞）：入口固定路径 3→5；
   新增测试账号工作流条目；隔离/HMAC/凭据边界不变。
3. **policy_gate 执行级键**：`step_key = "policy_gate:{tool}:{execution}"`——因
   `AgentRunStepRecord(run_id, step_key)` 唯一约束与 workflow 启动级 `policy_gate`
   （growth:137 / research:166）冲突；QA 断言已同步改为 `startswith("policy_gate:")`。
4. **`computer_use.apply_plan` 不存在**：QA 门控测试原引用该函数（设计未定义），
   已修正为验证实际入口 `tool_catalog.handle_workspace_file` + 完整 R2 三阶段落盘/备份。
5. **环境门控项不阻塞合并**：n8n 容器/测试账号未就绪，工具保持 `available=False`；
   启用流程见 `infra/n8n/workflows/README.md`。

## 3. 所有权核对

- 全部改动落在各自 Owned 路径；QA Round 2 仅改测试文件（3 处契约修正 + 门控检测点），
  未动产品代码。
- AI 侧 `agent_core` 未反向 import `tool_catalog`（设计 §5 禁反向依赖）；
  `allowed_tools` 保留为对账锁定镜像，运行时单一来源为 `spec.effective_tools`。

## 4. 测试与门禁结果（合并前最终复跑）

- `scripts/check.ps1`：exit 0；pytest **326 passed, 25 skipped**（351 collected，
  含 4 个 Sprint 5 门控激活）；评测 25/25；`backup-drill -DryRun` 通过；web typecheck + lint 全绿。
- `agent_core.reconciliation` CLI：exit 0（6 Agent × 15 工具，0 drift）。
- 跳过项（25）：Ollama 1、PG-postgres workflow 1、PG 集成 23（环境门控）。

## 5. 遗留待办

1. **n8n 真实工作流验收**：测试账号就绪后按 README 校验 schema → 替换凭据占位 →
   bump `JARVIS_N8N_WORKFLOW_VERSION` → 置 `available=True`；启用前需 AI 在 catalog 侧为
   `email.draft.create` 补 CORE/RESEARCH/GROWTH 的 `confirmation_actions`（或改授权范围）。
2. **`test_accounts_connected` schema 字段**（`N8nProviderStatusResponse`）：二期契约变更。
3. **全栈复跑**：PG 真库跑 `test_pg_integration.py` 23 例 + R2/R3 账本不变量
   （确认 SQLite/PG 行为一致）；Ollama 就绪后跑语义门控用例。
4. **验证产物**：n8n workflow JSON 未经运行时验证（n8n 1.123.5 惯例参数），启用前必须校验。

## 6. 验收标准对照（Sprint 5）

| 验收项 | 状态 |
|---|---|
| R3 自动执行数 = 0 | ✅ 账本 + 守卫测试（`risk_level='never_automate'` 恒 0，伪造 R3 定义被拒） |
| R2 未确认写操作 = 0 | ✅ 账本断言 `confirmed_write` 执行必须外连 `consumed` 审批 |
| 新工具经交叉校验 | ✅ 白名单单一来源 + 对账自动化（漂移即失败）+ 运行时消费派生视图 |
| Computer-use 阶段 3 可用（R2 审批下） | ✅ 已激活；写/恢复全链路 + 备份 + 幂等自验证通过 |
