# Tool & Automation — Sprint 5 交接说明

- **产出**：Tool & Automation Agent（Sprint 5 落地）
- **日期**：2026-08-06
- **分支上下文**：串行模式分支 `feat/tool-automation/`（共享工作树，未执行 git 操作）
- **范围**：Computer-use 阶段 3、工具注册交叉校验消费、n8n 测试账号工作流、Tool Gateway policy_gate 审计接线
- **主依据**：`docs/MIGRATION_SPRINT_2_TOOL_COMPUTER_USE_DESIGN.md`、
  `docs/MIGRATION_SPRINT_2_TOOL_REGISTRATION_DESIGN.md`、`docs/MIGRATION_SPRINT_2_TOOL_N8N_DESIGN.md`、
  `docs/MIGRATION_SPRINT_2_AI_HANDOFF.md` §5

---

## 1. 修改文件清单（全部在独占目录内）

| 文件 | 改动摘要 | 触及冻结契约 |
|---|---|---|
| `apps/api/app/services/tool_catalog.py` | Computer-use 阶段 3：`workspace_file_preview` 与 `handle_workspace_file` 强制 `computer_use_stage>=3`（D3 门禁下沉）；写入前备份 original.bin + manifest 到 `.data/tool-sandbox/.backups/{execution_id}`；写后 SHA256 校验 + TOCTOU 复检；`.backups` 从读写范围排除；新增 R2 工具 `workspace.file.restore`（仅 LOCAL_DOCUMENT，恢复写入前内容，新建文件不可恢复——删除仍是 R3）；handler 签名增加可选 `ToolExecutionContext`（向后兼容 2 参调用）；n8n 写工具 handler/preview：`calendar.event.upsert`（保留 available=False，挂真实 preview+handler）、`email.draft.create`（新增预留，available=False、授权空）；`reconcile_tools()` 消费入口 | 无 |
| `apps/api/app/services/tool_gateway.py` | 运行时交叉校验消费：`_validate_definition_for_agent` 改用 `effective_tools_for_spec(spec)`（注册表派生单一来源，AI 侧已落）；handler 调用传入执行上下文；`submit_tool` 在 `RiskPolicy().classify()` 后按 `v2_policy_enforcement_enabled` 写 `AgentRunStepRecord`（policy_gate 审计，仅审计不改 R2/R3 语义） | 无 |
| `apps/api/app/services/computer_use.py` | `read_workspace_file` 排除 `.backups`；阶段 3 写步骤 preview_hint 补充回滚说明（阶段 2 只读+计划预览行为不变） | 无 |
| `apps/api/app/services/n8n_provider.py` | `ALLOWED_INGRESS_PATHS` 增加 `/v1/calendar/write`、`/v1/email/draft/create`（复用 HMAC/时间戳/nonce/正文哈希，无新网络暴露） | 无 |
| `infra/n8n/ingress/server.js` | `allowedPaths` 增加两条固定映射（仍仅 127.0.0.1:5680、internal 网络） | 无 |
| `infra/n8n/bootstrap.js` | 发布幂等化：按 workflow name 查重，存在则 PUT 更新，不存在才 POST 新建；激活描述改为版本无关 | 无 |
| `infra/n8n/workflows/calendar-event-upsert-test.json`（新增） | 测试日历写入工作流（webhook → Google Calendar 创建 → 返回确定性 envelope） | 无 |
| `infra/n8n/workflows/email-draft-test-account.json`（新增） | 测试邮箱草稿工作流（webhook → Gmail 创建草稿 → `not_sent: true` envelope） | 无 |
| `infra/n8n/workflows/README.md`（新增） | 启用前置步骤（凭据、占位替换、schema 校验、marker bump 时机） | 无 |

**未改动**：`apps/web/**`、`memory*.py`、`knowledge*.py`、`english.py`、`investment.py`、
`intelligence.py`、`growth.py`、`apps/api/tests/**`、`docs/**`、`scripts/check.ps1` 等 QA 脚本、
`config.py`（无新增 flag）、`infra/docker-compose.yml`（marker 未 bump）、`apps/browser-worker/**`、
`infra/ollama/**`。

---

## 2. 测试结果

### 2.1 全量 pytest（`apps/api/tests`）

**297 passed / 6 failed / 26 skipped**（skip 为既有环境门控：Ollama、PG、stage-3 等）。
另有 AI 侧 `agent_core.reconciliation` CLI 门禁：**OK（6 agents / 15 tools，0 drift）**。

### 2.2 6 个失败——同一根因，均需 QA 更新用例（详见 §5）

1. `test_tool_gateway.py::test_r2_requires_approval_then_separate_execution`
2. `test_tool_gateway.py::test_idempotency_replay_never_duplicates_side_effect`
3. `test_tool_gateway.py::test_idempotency_conflict_and_rejected_execution_are_blocked`
4. `test_tool_invariants.py::test_r3_never_appears_in_execution_ledger`
5. `test_tool_invariants.py::test_r2_never_succeeds_without_consumed_approval`
6. `test_tool_sprint5_gates.py::test_gateway_records_policy_gate_step_when_enabled`

失败原因：这些用例的 `gateway_settings()` 使用默认 `computer_use_stage=2` 走完整
`workspace.file.write` R2 流程；本轮的 D3 阶段门禁（设计文档第一优先修复）已按设计把
预览/执行强制为 stage>=3，因此 submit 在预览阶段抛 `ToolCatalogError`。用例 6 另含
`step_key == "policy_gate"` 的断言，与实现采用的执行级键不一致（见 §5.2）。

### 2.3 端到端自验证（临时脚本，非 tests/ 文件）

stage=3 下全链路通过：写入 → 备份（`original.bin` + manifest）→ 审批消费 →
执行成功 → `workspace.file.restore` 预览/批准/执行恢复原内容 → 二次恢复预览
`already_restored=True` → policy_gate 审计步骤落库（键含执行 ID）→ 幂等重放返回原执行。
stage=2 下提交写工具被预览门禁拒绝（pytest 已确证）。

### 2.4 静态检查

- ruff：4 个改动 Python 文件全过。
- `node --check`：`bootstrap.js` / `ingress/server.js` 通过；2 个新 workflow JSON 可解析。

---

## 3. 环境门控项（运行时验收待环境就绪，不阻塞合并）

| 项 | 状态 | 就绪后动作 |
|---|---|---|
| n8n 容器 / 测试账号 | 未就绪 | 按 `infra/n8n/workflows/README.md`：建 `.data/n8n-secrets` 测试账号凭据 → 替换 JSON 内凭据占位 → 校验 Google Calendar/Gmail 节点 schema → bump `JARVIS_N8N_WORKFLOW_VERSION`（bootstrap 已幂等，不会重复发布） |
| `calendar.event.upsert` / `email.draft.create` | `available=False`（环境门控，符合 ADR-0010 #14「未连接 Provider 只登记风险契约」） | 测试账号就绪后置 `available=True`；`email.draft.create` 需先由 AI Engineer 在 catalog 侧补 CORE/RESEARCH/GROWTH 的 `confirmation_actions`（EMAIL_ACTION）或改授权范围 |
| `computer_use_stage` | 仍为 2（config.py 冻结面） | Tech Lead 将 `config.py:134` 提升为 3 即激活阶段 3；届时 QA 的 `test_computer_use_stage3_confirmed_write_stays_through_gateway` 会激活，需先确认 `computer_use.apply_plan` 入口定义（本轮设计文档未定义该函数，未实现） |
| ADR-0010 #6/#11 修订 | 未做（docs 属 Tech Lead） | 新增路径数量与「测试账号工作流」条目需 Tech Lead 出 ADR 修订 |
| `N8nProviderStatusResponse` 增加 `test_accounts_connected` 区分字段 | 未做（schemas 冻结面） | Tech Lead 契约变更；当前状态面已保持 `real_accounts_connected: false` |

---

## 4. 红线合规自检

- R3 永不自动化：`register()` 拒绝 R3（既有）；无删除工具；restore 只回写既有备份、新建文件不可恢复（删除仍 R3）。✓
- R2 预览-批准-执行：写与恢复均走同一三阶段管线，执行前参数哈希/审批状态复核保留。✓
- 不引入新凭据暴露：测试账号凭据仅在 `.data/n8n-secrets` + n8n 容器；Core/ingress 不接触；envelope 强制 `credential_exposed: false`。✓
- browser-worker 7 层隔离不削减：本轮未触碰 `apps/browser-worker/**`。✓
- n8n ingress HMAC 与 internal 网络边界不变：仅新增两条固定路径映射，端口/网络/签名/防重放不变。✓
- config.py 不新增 flag：未改 config.py。✓

---

## 5. 需 QA / Tech Lead 处理的变更请求

### 5.1 QA（tests/ 属主）——6 个用例更新建议

1. `test_tool_gateway.py` / `test_tool_invariants.py` 中跑 `workspace.file.write` 全流程的用例，
   在 `gateway_settings()`（或逐用例 overrides）加 `"computer_use_stage": 3`——这些用例测的是
   网关机制与 R2 不变量，不是阶段门禁本身。
2. `test_tool_sprint5_gates.py::test_gateway_records_policy_gate_step_when_enabled`：
   - 同样补 `computer_use_stage=3`；
   - `step_key` 断言改为 `startswith("policy_gate:")` 或按 `kind == "policy"` + `input_refs` 查询。
     **理由**：`AgentRunStepRecord` 有 `UniqueConstraint(run_id, step_key)`，而 workflow 启动时
     已在同一 run 写 `step_key="policy_gate"`（`growth_workflow.py:137` / `research_workflow.py:166`）；
     若网关也用字面 `policy_gate`，同 run 内第二次提交（或 workflow 内工具调用）必然撞唯一约束。
     执行级键 `policy_gate:{tool_id}:{execution_id}` 保证每次工具执行一条审计且不与 run 级步骤冲突。
3. 新增用例建议（附在变更请求内）：
   - stage=2 提交 `workspace.file.write` → `ToolCatalogError`（门禁）；
   - stage=3 写入后 `.backups/{execution_id}/manifest.json` 与 `original.bin` 存在；
   - restore 全流程 + 二次恢复拒绝 + 新建文件恢复拒绝；
   - `email.draft.create` / `calendar.event.upsert` 保持不可用（`available=False`）。

### 5.2 Tech Lead（冻结面）

- `config.py:134` `computer_use_stage` 2→3（阶段 3 激活开关，回滚即回退为 2）。
- ADR-0010 #6/#11 修订（路径数量、测试账号工作流条目）。
- `schemas/tool.py` 增加 `test_accounts_connected` 区分字段（可选，二期）。
- `computer_use.apply_plan` 入口是否立项（QA 门控测试引用，设计文档未定义）。

---

## 6. 风险说明

1. **并行在途**：本轮期间 AI Agent Engineer 并发落地了 catalog 派生视图
   （`agent_core/catalog.py` `agent_effective_tools`）与对账模块（`agent_core/reconciliation.py`），
   QA 并发新增了 `test_tool_sprint5_gates.py` / `test_tool_invariants.py`。已实测 import 链与
   对账门禁通过；`tool_catalog` 未反向依赖 `agent_core.catalog`，避免加重环。
2. **6 个测试失败**：均为阶段门禁的行为变更所致（设计要求），非回归；QA 更新后应全绿。
3. **n8n 工作流 JSON 未经运行时验证**：节点参数名按 n8n 1.123.5 惯例编写，凭据为占位；
   环境就绪后必须按 README 先校验再 bump marker（bootstrap 已幂等，避免重复发布）。
4. **回滚**：阶段 3 靠 `computer_use_stage` 回退；n8n 新路径靠 `v2_n8n_provider_enabled` 与
   工具 `available=False`；policy 审计靠 `v2_policy_enforcement_enabled`（默认 False，inert）。

---

## 7. AI 辅助记录

本轮仅做本地代码实现与确定性测试；未调用任何云端模型、未产生 DeepSeek 费用、未发送私人数据。
