# MIGRATION_SPRINT_2.md — 迁移 Sprint 2 交付与验收记录

- **文档类型**：Tech Lead 产出（迁移路线图 Sprint 2：AI 能力落地）
- **日期**：2026-08-06
- **状态**：✅ 已验收（合入 dev；main 保持基线）

---

## 1. 交付物总览

| Agent | 任务 | 状态 | 证据 |
|---|---|---|---|
| AI Agent Engineer | Prompt 集中管理 | ✅ | `services/prompts/**`（24 个模板 + registry/loader/versions.json） |
| AI Agent Engineer | Router v2 阶段 1（一致性校验） | ✅ | `agent_core/consistency.py` + `routes/chat.py` 最小接入（4 点） |
| AI Agent Engineer | Policy Router 阶段 2（读取点） | ✅ | `agent_core/policy.py` + 两 workflow `policy_gate` 审计步骤 |
| AI Agent Engineer | Workflow 走 Registry（G3/G4） | ✅ | 两 workflow 启动解析 AgentSpec；`build_runtime_registry()` 双 Runtime |
| Memory Engineer | M2 后台模型调用统一路由 | ✅ | `conversation_summary/knowledge_capture/knowledge_insights/memory_engines` 改走 ModelRouter（LOCAL 模式） |
| Tool & Automation | Sprint 5 预研（3 份设计） | ✅ 只读 | 已归档 `docs/MIGRATION_SPRINT_2_TOOL_*.md` |
| Frontend Evolution | Sprint 4 预研 | ⚠️ 未收到产出 | 见 §5 遗留 |

## 2. 所有权核对结论（Tech Lead）

- **chat.py（冻结区）已审核并授权**：4 处改动均为纯数据流接入（import + PreparedChatCall
  字段 + 两处 prepare 计算一致性结果 + metadata 写入），未改 409 语义、未改响应 schema、
  未改真实路由决策；flag 未开时行为与基线一致（inert record）。
- **QA 属主文件（授权例外，Sprint 3 由 QA 复核）**：`scripts/evaluate-prompts.py`、
  `evals/prompt_policy_cases.jsonl`、`apps/api/tests/test_{prompts_registry,router_consistency,
  runtime_registry_dual,policy_reading_point,workflow_registry_audit}.py`（5 个新测试）。
  沿用 Sprint 1 授权先例（checkpointer 测试 import 联动），内容与 Prompt 注册表强耦合。
- **契约冻结区由 Tech Lead 落地**：`config.py` + `.env.example` 新增两个 flag（见 §3）；
  AI Engineer 按 `getattr(..., False)` 编码，未擅动冻结文件。
- **Memory 改动**：4 个文件均为 Owned 路径，与 AI Engineer 无文件重叠。

## 3. Feature Flag 契约（2026-08-06 冻结）

| flag | 默认值 | 用途 | 状态 |
|---|---|---|---|
| `v2_router_enforcement_enabled` | False | Router 阶段 1 一致性校验（不一致记 metadata + 日志，不改路由） | ✅ 已落 config.py/.env.example |
| `v2_prompt_registry_enabled` | False | Prompt 注册表灰度（消费点渲染，flag 关时逐字回退） | ✅ 已落 |
| `v2_policy_enforcement_enabled` | False | 阶段 2 读取点（workflow 记 policy_gate 审计） | 已有，本轮接线 |

## 4. 死 flag 处置决定（Tech Lead）

- `v2_agent_core_enabled`：确认为死 flag（无读取点）；**清理延后至 Sprint 6**（需同步
  QA 的 `test_v2_feature_flags.py`，本轮不动）。
- `v2_shadow_runs_enabled`：无读取点，**保留**（预留给 chat 影子账本持久化门控）。
- `v2_mem0_chat_shadow_enabled`：**非死**（`api/routes/memory_shadow.py:367` 有读取点）——
  审计 M5 将其列为死 flag 属误报，已纠偏。
- `v2_policy_enforcement_enabled`：本轮新增读取点，不清理。

## 5. 测试与门禁结果（合并前最终复跑）

- `scripts/check.ps1`：exit 0；pytest **306 passed, 2 skipped**（308 collected，
  含 AI 新增 5 组测试 29 例）；安全扫描 1 WARN（既有 `.env` ACL）；web typecheck + lint 通过。
- `scripts/evaluate-prompts.py`：**25/25**（原 16 例 + 4 prompt_render + 5 逐字 parity）。
- 跳过项（环境门控）：Ollama 未运行 / 未设 `JARVIS_TEST_POSTGRES_URL`。

## 6. 遗留待办

1. **Prompt 消费点二期切换**（flag 灰度，清单见 `MIGRATION_SPRINT_2_AI_HANDOFF.md §6`）：
   personality/english/knowledge/memory/summary/intelligence/chat/evaluation 共 8 个消费点，
   本轮仅 growth/research 已接线；其余由各 Owner 在 flag 开前切换。
2. **Tool Gateway policy_gate 审计接线**：AI 已给建议代码（`MIGRATION_SPRINT_2_AI_HANDOFF.md §5`），
   由 Tool & Automation 在 Sprint 5 落地（不改变 R2/R3 执行语义）。
3. **Frontend Evolution Sprint 4 预研**：本轮未收到产出，需补（或 Sprint 4 开始时直接做）。
4. **QA 复核授权例外文件**：Sprint 3 开始时由 QA 复核 5 个新测试与评测改动。

## 7. 验收标准对照（Sprint 2）

| 验收项 | 状态 |
|---|---|
| Prompt 可版本化评测（evaluate-prompts 按 id@version + 逐字 parity） | ✅ |
| Router 在 Flag 下可回滚（默认关，409 语义不变） | ✅ |
| workflow 审计记录走 AgentSpec | ✅ |
| 后台模型调用统一走 ModelRouter（M2） | ✅ |
