# AI Agent Engineer — Sprint 5 交接说明（AgentSpec 白名单单一来源，H5）

- **日期**：2026-08-06
- **分支**：dev（共享工作树，未执行 git 写操作）
- **范围**：AgentSpec ↔ ToolRegistry 白名单单一来源 + 对账自动化 + 派生视图接口

---

## 1. 交付总览

| 交付 | 状态 | 关键产物 |
|---|---|---|
| 单一来源派生视图 | ✅ | `AgentSpec.effective_tools` 属性（contracts.py，懒加载，无 import 环）+ `agent_effective_tools`（catalog.py） |
| 消除双维护 | ✅ | `AGENT_SPECS.allowed_tools` 与当前注册表派生集逐 Agent 相等（含并行新增工具同步），对账兜底 |
| 对账自动化（漂移即失败） | ✅ | `agent_core/reconciliation.py`（R1-R5 + CLI，`python -m app.services.agent_core.reconciliation`，exit 0/1） |
| 接口契约（Tool 消费方） | ✅ | 见 §3：运行时消费 `spec.effective_tools`；漂移归因（spec-side / registry-side） |

## 2. 修改文件清单（我方 Owned）

| 文件 | 改动 |
|---|---|
| `apps/api/app/services/agent_core/contracts.py` | `AgentSpec.effective_tools` 派生视图属性（懒加载 TOOL_REGISTRY，避免 tool_catalog↔catalog 环） |
| `apps/api/app/services/agent_core/catalog.py` | 新增 `agent_effective_tools` / `effective_tools_for_spec`（懒加载）；`LOCAL_DOCUMENT.allowed_tools` 同步注册表新增的 `workspace.file.restore`（R2，MODIFY_FILE） |
| `apps/api/app/services/agent_core/reconciliation.py`（新建） | R1-R5 对账 + CLI；规则与 `MIGRATION_SPRINT_2_TOOL_REGISTRATION_DESIGN.md` §3.1 对齐 |
| `apps/api/app/services/agent_core/__init__.py` | 导出 `agent_effective_tools` / `effective_tools_for_spec` |

**设计说明**：`agent_core` 侧不模块级 import `tool_catalog`（设计文档 §5「catalog 不反向依赖 tool_catalog」）；
派生视图在调用期懒加载注册表。`AgentSpec.allowed_tools` 保留为受对账锁定的镜像声明（向后兼容
`tool_gateway._validate_definition_for_agent` 与 QA 静态审计），运行时单一来源视图为
`spec.effective_tools`。

## 3. 接口契约（Tool & Automation 消费）

1. **运行时派生视图**：`spec.effective_tools -> tuple[str, ...]`
   （`AgentSpec` 属性；等价于 `agent_core.catalog.agent_effective_tools`）。
   规则 = `{t.tool_id | t ∈ TOOL_REGISTRY, agent ∈ t.allowed_agents,
   risk(t) <= spec.max_risk_level, R2 需 action ∈ spec.confirmation_actions}`。
   `tool_gateway._validate_definition_for_agent` 可由 `spec.allowed_tools` 切换为
   `spec.effective_tools`（当前两者逐字相等，行为等价）。
2. **对账 API**：`agent_core.reconciliation.reconcile_agent_tool_whitelists() -> list[str]`
   （空 = 无漂移）；CLI `python -m app.services.agent_core.reconciliation`（漂移 exit 1）。
3. **漂移归因**：问题字符串带 `R1..R5` 前缀与 `[spec-side / registry-side]` 归属，
   按 FILE_OWNERSHIP 由对应 Owner 修复。
4. **新增工具流程**：Tool 侧在 `TOOL_REGISTRY` 注册（allowed_agents 为授权唯一事实）→
   对账 R2 会要求 AgentSpec 镜像声明（或消费方切 `effective_tools` 后无需镜像）→
   QA 审计/门控拦截漂移。

## 4. 对账结果

```text
python -m app.services.agent_core.reconciliation
AgentSpec <-> ToolRegistry reconciliation OK: agents=6 tools=15
  jarvis_core: 7 | english_coach: 1 | research: 4 | growth: 6
  local_document: 6 | investment_intelligence: 2
exit 0
```

- R1（无幽灵工具）/ R2（双向一致）/ R3（risk==policy）/ R4（R2 确认动作）/ R5（R3 禁授权）全部通过；
- 声明集 == 派生集 == `spec.effective_tools`（6 Agent × 15 工具，逐 Agent 校验通过）；
- QA 静态审计 `test_tool_reconciliation_audit.py`（6 例）全绿；
- QA 门控 `test_agent_spec_derived_tools_match_registry`（我的派生视图）**已激活且通过**。

## 5. 测试结果

- 我方相关 pytest（agent_catalog/contracts/policy/registry/runtime/router_v2/consistency/
  prompts/policy_reading_point/workflow_registry_audit + QA 审计）：**88 passed**；
- ruff：`agent_core` 全过；
- 共享树当前含 Tool & Automation **在途未提交**改动（tool_catalog/tool_gateway/computer_use/
  n8n_provider/infra-n8n）：`workspace_file_preview` 强制 `computer_use_stage>=3`，
  导致未设 stage 的既有 tool 测试失败 6 例（`COMPUTER_USE_STAGE=3` 复跑后该 6 例全过，
  证明非我方回归）；另 2 例门控失败（stage-3 `apply_plan` 入口、policy_gate step_key 格式）
  与 1 例跳过（tool_catalog `reconcile` 未落地）均属 Tool 侧待交付，非我方范围。

## 6. 风险说明

1. **并行在途**：Tool & Automation 的 tool_catalog/tool_gateway/computer_use 改动未提交，
   与 QA 门控存在格式契约差异（policy_gate step_key、reconcile 命名、stage-3 测试环境），
   需 Tech Lead 协调其与 QA 对齐后再合并；我方改动与其无文件重叠。
2. **派生视图懒加载**：`effective_tools` 在调用期 import tool_catalog；若在 tool_catalog
   模块加载过程中被调用会触发部分初始化异常——当前无此调用路径，属防御性设计说明。
3. **镜像声明过渡期**：`allowed_tools` 仍为锁定镜像（QA 审计兜底）；消费方切
   `effective_tools` 后（Tool 侧）镜像可后续移除，届时 R1/R2 规则自动退化为派生自检。
4. **回滚**：全部改动仅在 agent_core 内；任何一侧漂移由对账/审计拦截，无运行时静默失效。

## 7. AI 辅助记录

全程本地代码实现与确定性测试；未调用云端模型、无 DeepSeek 费用、未发送私人数据。
