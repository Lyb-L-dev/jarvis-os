# AI Agent Engineer — Sprint 2 交接说明（AI 能力落地）

- **日期**：2026-08-06
- **分支**：dev（共享工作树，未执行 git checkout/commit/merge）
- **范围**：Prompt 集中管理、Router v2 阶段 1、Policy Router 阶段 2、Workflow 走 Registry、死 flag 处置、Feature Flag 契约清单

---

## 1. 交付总览

| 任务 | 状态 | 关键产物 |
|---|---|---|
| Prompt 集中管理 | ✅ 注册表 + 24 模板 + 评测挂接 | `services/prompts/**`、`scripts/evaluate-prompts.py`、`evals/prompt_policy_cases.jsonl` |
| Router v2 阶段 1 | ✅ 一致性校验（flag 默认关） | `agent_core/consistency.py` + `routes/chat.py` 最小接入（冻结区，4 点） |
| Policy Router 阶段 2 | ✅ 读取点接线（workflow 审计） | `agent_core/policy.py` 新增 + 两 workflow `policy_gate` 步骤；Tool Gateway 接线建议见 §5 |
| Workflow 走 Registry | ✅ G3 + G4 | 两 workflow 启动从 Agent Registry 解析 AgentSpec；`build_runtime_registry()` 注册 Direct/Workflow |
| 死 flag 处置 | ✅ 已核实（含一处审计纠偏） | 见 §4 |
| Feature Flag 契约 | ✅ 清单提交 Tech Lead（未落 config.py） | 见 §3 |

## 2. 修改文件清单

### 2.1 我方独占（services 侧）

| 文件 | 改动摘要 | 触及冻结契约 |
|---|---|---|
| `apps/api/app/services/prompts/__init__.py`（新建） | 导出 PromptRegistry/render_or_fallback/prompt_registry_enabled | 无 |
| `apps/api/app/services/prompts/schemas.py`（新建） | PromptSpec 数据模型 | 无 |
| `apps/api/app/services/prompts/loader.py`（新建） | versions.json + TOML 模板加载（tomllib，fail-fast） | 无 |
| `apps/api/app/services/prompts/registry.py`（新建） | register/get/render/list_active/agent_prompt_id/reconcile_agent_prompts | 无 |
| `apps/api/app/services/prompts/versions.json`（新建） | 24 个 prompt 元数据 + active 版本 + agent→prompt 映射 | 无 |
| `apps/api/app/services/prompts/templates/**`（新建，24 个 TOML） | 20 系统 prompt + 4 用户模板，逐字原文 | 无 |
| `apps/api/app/services/agent_core/consistency.py`（新建） | Router Stage 1 影子一致性校验（纯观察，不改变真实路由/409） | 无 |
| `apps/api/app/services/agent_core/policy.py` | + policy_enforcement_enabled / policy_step_refs（R0-R3 审计 refs） | 无 |
| `apps/api/app/services/agent_core/runtime.py` | + DirectRuntime / WorkflowRuntime / build_runtime_registry（G4） | 无 |
| `apps/api/app/services/agent_core/__init__.py` | 导出新模块 | 无 |
| `apps/api/app/services/growth_workflow.py` | start() 从 Registry 解析 AgentSpec（G3）；flag 开时记 policy_gate 步骤；generate_plan_draft 经 render_or_fallback 取 growth.agent_system/growth.planning（flag 关时逐字回退） | 无 |
| `apps/api/app/services/research_workflow.py` | 同上（research.agent_system/research.report） | 无 |

### 2.2 冻结区 / 跨 Owner（需 Tech Lead 审核）

| 文件 | 改动摘要 | Owner |
|---|---|---|
| `apps/api/app/api/routes/chat.py` | **Router 阶段 1 最小接入，共 4 点**：(1) import `check_shadow_consistency/ShadowConsistencyResult`；(2) `PreparedChatCall` 增 `shadow_consistency` 字段（默认 None）；(3) `prepare_chat_call` 与 `prepare_regeneration` 在 `require_paid_call_confirmation` 之后计算一致性结果并传入（`enabled=getattr(settings,"v2_router_enforcement_enabled",False)`）；(4) `persist_assistant_result` 将结果写入 assistant message metadata（不新增响应 schema 字段，不动 409 语义） | Tech Lead（冻结） |
| `apps/api/tests/test_prompts_registry.py`（新建） | 注册表/渲染/对账/逐字 parity（含 growth.planning 与 research.report 模板 == 原函数输出） | QA（授权请求） |
| `apps/api/tests/test_router_consistency.py`（新建） | 一致性校验行为 + flag 默认关 | QA（授权请求） |
| `apps/api/tests/test_runtime_registry_dual.py`（新建） | 双 Runtime 注册/启用门控/事件 | QA（授权请求） |
| `apps/api/tests/test_policy_reading_point.py`（新建） | policy flag 读取点 + R1/R3 审计 refs | QA（授权请求） |
| `apps/api/tests/test_workflow_registry_audit.py`（新建） | workflow 启动记录 AgentSpec 身份 + policy_gate 步骤开关 | QA（授权请求） |
| `scripts/evaluate-prompts.py` | 由 import 函数改为按 prompt id@version 从注册表取内容；contract 用例校验版本；新增 prompt_render 类型；新增 5 条 live parity 锁定逐字 | QA（授权请求） |
| `evals/prompt_policy_cases.jsonl` | 4 条 contract 用例加 `prompt_ref`；追加 4 条 prompt_render 用例 | QA（授权请求） |

> 以上 QA 属主文件改动沿用 Sprint 1 授权先例（checkpointer 测试 import 联动），请 Tech Lead 确认/追认。

### 2.3 非我方在途改动（未触碰，仅记录）

`conversation_summary.py` / `knowledge_capture.py` / `knowledge_insights.py` / `memory_engines.py`
—— Memory Engineer 的 M2 任务（后台模型调用统一走 ModelRouter），与我方改动无文件重叠。

## 3. Feature Flag 契约清单（提交 Tech Lead 落 config.py + .env.example）

| flag | 默认值 | 用途 | 灰度期 |
|---|---|---|---|
| `v2_router_enforcement_enabled` | False | Router 阶段 1：影子决策与真实 ModelRouter 一致性校验（不一致记 shadow run metadata + 结构化日志，仍走原链路） | 本轮代码已按 getattr 默认 False 编码；Tech Lead 落 flag 后逐个环境开启，可一键关 |
| `v2_prompt_registry_enabled` | False | Prompt 注册表灰度：growth/research workflow 消费点从注册表渲染（内容与原文逐字一致已锁定） | 本轮 4 个消费点已接线；其余消费点由各 Owner 按清单切换后再开 |
| `v2_policy_enforcement_enabled`（已有） | False | 阶段 2 读取点：workflow 启动记 policy_gate 审计步骤；Tool Gateway 接线建议见 §5 | 本轮已接线 workflow 侧；Tool Gateway 侧由 Tool & Automation 落 |

## 4. 死 flag 处置报告

| flag | 读取点 | 结论与建议 |
|---|---|---|
| `v2_agent_core_enabled` | 无（仅 config 声明 + any_v2_feature_enabled 聚合） | **死**，建议清理（config.py 由 Tech Lead 落） |
| `v2_shadow_runs_enabled` | 无 | **死**，建议清理；或预留为「chat 影子账本持久化」门控（需 Tech Lead 定 AgentRun 写入契约，本轮未接） |
| `v2_mem0_chat_shadow_enabled` | 有：`api/routes/memory_shadow.py:367`（chat_auto_shadow_enabled 状态响应） | **非死**，保留。审计 M5 列其为死 flag 属误报，建议 Tech Lead 纠偏 |
| `v2_policy_enforcement_enabled` | 本轮新增读取点 | 不清理，已接线 |

## 5. Tool Gateway 前置校验接线建议（交 Tool & Automation / Tech Lead）

`tool_gateway.py` 已在 `submit_tool`（L455）与 `_execute_record`（L232）调用
`RiskPolicy().classify()` 并强制执行 R3 禁止 / R2 审批，R3 永不自动化语义已成立。
建议补充的「flag 读取点」仅为审计接线（不改变执行结果）：

```python
# tool_gateway.py submit_tool，policy = RiskPolicy().classify(...) 之后
from app.services.agent_core.policy import policy_enforcement_enabled, policy_step_refs

if policy_enforcement_enabled(settings) and agent_run_id is not None:
    max_seq = (
        await session.scalar(
            select(func.max(AgentRunStepRecord.sequence)).where(
                AgentRunStepRecord.run_id == agent_run_id
            )
        )
        or 0
    )
    session.add(
        AgentRunStepRecord(
            run_id=agent_run_id,
            sequence=max_seq + 1,
            step_key="policy_gate",
            kind="policy",
            status="completed",
            input_refs=[{"kind": "tool_execution", "ref_id": str(execution.id)}],
            output_refs=policy_step_refs(policy),
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )
    )
```

## 6. 跨 Owner 消费点切换清单（逐模块灰度，二期实施）

统一模式：`render_or_fallback("id", settings, fallback=原实现)`（flag 关时逐字回退）。

| 文件（Owner） | 待切换 prompt id |
|---|---|
| personality.py（Tech Lead 冻结） | personality.block / chat_system / coach_line / boundaries / disclaimer / tones |
| english.py（冻结） | english.coach / english.summary_analysis / english.rewrite |
| knowledge_capture.py / knowledge_insights.py / knowledge_retrieval.py（Memory） | knowledge.capture / knowledge.insight / knowledge.retrieval_context |
| memory_engines.py（Memory） | memory.qwen_extract / memory.mem0_instructions |
| conversation_summary.py / context_engineering.py（Memory） | summary.context_wrapper / summary.compress / memory.confirmed_wrapper |
| intelligence.py（冻结） | intelligence.editor / intelligence.editor_user |
| api/routes/chat.py（冻结） | memory.confirmed_wrapper（L283） |
| api/routes/evaluation.py（冻结） | evaluation.harness |

## 7. 测试结果

- `scripts/evaluate-prompts.py`：**25/25 通过**（原 16 例 + 4 prompt_render + 5 live parity；contract 用例按 prompt id@version 校验）
- pytest 全量（`apps/api/tests`）：**284 passed, 2 skipped**（skip 为既有环境门控：Ollama 未运行 / 未设 JARVIS_TEST_POSTGRES_URL）
- 新增测试 29 项全绿（prompts registry 12、router consistency 5、runtime dual 4、policy reading point 4、workflow registry audit 5，含 2 条模板逐字 parity）
- ruff：改动文件全过

## 8. 风险说明

1. **chat.py 冻结区**：4 处改动均为最小数据流接入，未改 409 语义、未改响应 schema、未改真实路由决策；flag 未落前行为与基线逐字一致（inert record）。请 Tech Lead 逐点审核。
2. **Prompt 逐字锁定**：常量 prompt 由 live parity 锁定；变量模板（growth.planning / research.report / personality.block zh）由渲染 parity 测试锁定。消费点切换均在 flag 关时回退原文，切换风险为零行为变化。
3. **QA 属主文件**：evaluate-prompts.py / prompt_policy_cases.jsonl / 5 个新测试文件属 QA 目录，已按 Sprint 1 授权先例实施，请 Tech Lead 追认。
4. **并行在途**：Memory Engineer 的 4 个文件在途改动（M2）与我方无重叠；合入时注意两方文件不冲突。
5. **回滚**：新能力全部由 flag 控制且默认关；关闭 `v2_router_enforcement_enabled` / `v2_prompt_registry_enabled` / `v2_policy_enforcement_enabled` 即回到基线行为。

## 9. AI 辅助记录

本轮仅做本地代码实现与确定性测试；未调用任何云端模型、未产生 DeepSeek 费用、未发送私人数据。
