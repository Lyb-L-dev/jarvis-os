# Tool & Automation — 交接说明 2/3：工具注册扩展流程（AgentSpec ↔ ToolRegistry 交叉校验）

- **产出**：Tool & Automation Agent（Sprint 2 只读预研）
- **日期**：2026-08-06
- **类型**：设计交接说明（含现状证据行号），待 Tech Lead 审核后归档 `docs/`
- **对应任务**：MIGRATION_ROADMAP.md Sprint 5 L162「工具注册扩展流程（新增工具走 AgentSpec ↔ ToolRegistry 交叉校验，消除 H5）」、L164「AgentSpec 白名单单一来源校验（catalog ↔ tool_catalog 自动化对账）」
- **本轮改动**：无

---

## 0. 结论摘要

1. **单一来源 = Tool Registry**：`ToolDefinition.allowed_agents`（`tool_catalog.py`）是「工具↔Agent 授权」
   的唯一事实；`AgentSpec.allowed_tools`（`agent_core/catalog.py`）改为由注册表**派生**的视图，
   不再手工维护第二份列表，消除 H5 双维护。
2. **对账机制**：派生 + 双向一致性自检（spec↔registry、风险↔action_kind、R2↔confirmation_actions、
   R3 禁注册），在注册完成后的 import 阶段执行，并以 pytest 静态断言 + `check.ps1` 门禁兜底；
   任何一侧漂移即启动失败，杜绝「运行时才兜底」。
3. **新增工具流程**：8 步 checklist；对账失败明确「哪一侧漂移、归谁修」
   （`tool_catalog.py` 我方改，`agent_core/catalog.py` AI Agent Engineer 改）。

---

## 1. 现状取证（双维护证据）

### 1.1 审计结论

- H5：`docs/CURRENT_PROJECT_AUDIT.md:224`「AgentSpec 白名单双维护：catalog.py vs tool_catalog.py
  手工同步，无交叉校验；Agent 扩展时白名单漂移；运行时靠 tool_gateway 兜底」。
- ADR-0009 #4：`docs/adr/0009-tool-gateway-human-control-boundary.md:16`「Agent Catalog 与 Tool Registry
  必须双向允许，任一不允许即拒绝」；#8：`:20`「R3 不得注册为 Agent Tool」。

### 1.2 两侧白名单对照表（当前手工同步点）

| Agent | `catalog.py` allowed_tools | `tool_catalog.py` 对应授权 |
|---|---|---|
| CORE | `agent_core/catalog.py:29-37` | system.status.read L661-669；automation.provider.status L701；calendar.events.read L717；computer.file.read L784；computer.screen.info L768；draft.text.prepare L685；email.draft.prepare L733 |
| ENGLISH | `catalog.py:65` | draft.text.prepare L685 |
| RESEARCH | `catalog.py:97-102` | system.status.read L661-669；browser.jobs.research L645；draft.text.prepare L685；email.draft.prepare L733 |
| GROWTH | `catalog.py:136-143` | system.status.read L661-669；browser.jobs.research L645；calendar.events.read L717；draft.text.prepare L685；email.draft.prepare L733；calendar.event.upsert L801（预留） |
| LOCAL_DOCUMENT | `catalog.py:165-171` | computer.file.read L784；computer.screen.info L768；system.status.read L661-669；draft.text.prepare L685；workspace.file.write L749 |
| INVESTMENT_INTELLIGENCE | `catalog.py:196-199` | draft.text.prepare L685；system.status.read L661-669 |

### 1.3 运行时兜底（不是设计）

- `tool_gateway.py:88-124`（`_validate_definition_for_agent`）：运行时同时校验
  `spec.allowed_tools`（L96-102）与 `definition.allowed_agents`（L103-108）、风险上限（L109-114）、
  confirmation_actions（L115-123）。任何一侧遗漏都会在运行时 403，但**注册期不报错**，
  这正是 H5 描述「运行时靠 tool_gateway 兜底」。
- 注册期仅校验 R3 拒绝/重复/handler 存在：`tool_catalog.py:224-232`，**无 Agent 侧交叉校验**。

### 1.4 模型与注册器现状

- `AgentSpec`（`agent_core/contracts.py:156-191`）：`allowed_tools: tuple[str, ...] = ()`（L165）、
  `max_risk_level`（L169）、`confirmation_actions`（L170）；模型校验只拦 R3 进 confirmation_actions
  （L176-191），不校验工具存在性。
- `AgentRegistry`（`agent_core/registry.py:13-54`）支持版本化注册，但 gateway 目前直接走
  `get_agent_spec`（`catalog.py:211-215`），未经过 AgentRegistry 版本化路径（现状事实，非本轮改动点）。

---

## 2. 单一来源方案

### 2.1 推荐：注册表派生（消除第二份列表）

- **事实源**：`TOOL_REGISTRY`（`tool_catalog.py:630-860`）。每个工具必须声明 `allowed_agents`、
  `action_kind`（→ risk 由 `policy.py` 唯一决定）、preview_builder、handler。
- **派生规则**（对每个 AgentSpec 计算其有效工具集合）：

  ```text
  spec.effective_tools =
      { t.tool_id for t in TOOL_REGISTRY.list()
        if agent_id in t.allowed_agents
        and RISK_RANK[t.risk_level] <= RISK_RANK[spec.max_risk_level]
        and (t.risk_level != R2 or t.action_kind in spec.confirmation_actions) }
  ```

  - `allowed_tools` 不再手写；`get_agent_spec`（`catalog.py:211-215`）与 registry 的 active spec
    输出统一改用派生视图。
  - Agent 侧仍保留声明式约束：`max_risk_level`、`confirmation_actions`（这两个不是工具列表，
    而是 Agent 的风险意愿声明，无法从工具侧推导）。
- **为何是注册表而非 AgentSpec**：工具定义含 scope/风险/凭据范围/幂等，是完整元数据；AgentSpec
  是消费方。以注册表为源、AgentSpec 为派生视图，一次变更只改一处。

### 2.2 兜底：双向对账（防派生逻辑自身漂移）

即使采用派生，仍保留显式对账函数，原因：派生规则可能被人为绕过（如直接把 spec 传给其他消费方），
对账把「注册表派生的期望值」与「spec 实际暴露值」比较，漂移即失败。

---

## 3. 对账机制（reconciliation）

### 3.1 规则（全部不满足即 fail-fast）

| # | 规则 | 拦截对象 |
|---|---|---|
| R1 | 每个 `spec.allowed_tools` 中的 tool_id 必须存在于 TOOL_REGISTRY | 幽灵工具（spec 引用了未注册/已删除工具） |
| R2 | 每个 spec 工具对 agent 的授权必须与 `definition.allowed_agents` 一致（双向） | 单向漂移（H5 主症状） |
| R3 | 工具 risk 必须等于 `RiskPolicy().classify(action_kind)` | 风险声明与策略表不一致（`policy.py:20-42` 为权威） |
| R4 | R2 工具的 action_kind 必须在该 Agent 的 `confirmation_actions` 中；R0/R1 不需要 | 审批缺口 |
| R5 | R3 action 不得出现在任何 spec/registry 授权（注册器已拦，对账二次确认） | 红线回归 |

### 3.2 执行时机

1. **import 期**：`tool_catalog.py` 完成全部注册（L630-860）后立即执行一次对账（置于
   `PERMANENTLY_BLOCKED_ACTIONS` 声明附近），不一致抛 `ToolCatalogError` 阻止启动。
2. **静态测试**：新增 pytest（归 QA 目录）断言「catalog 派生集 == registry 授权集」，
   覆盖 6 个 Agent × 全部工具；纳入 `scripts/check.ps1` 门禁。
3. **变更入口**：对账失败信息指明「registry 侧（tool_catalog.py）还是 spec 侧（catalog.py）」，
   按 FILE_OWNERSHIP 由对应 Owner 修复（§5）。

---

## 4. 新增工具流程（checklist）

1. 在 `tool_catalog.py` 定义输入 Schema（继承 `ToolInputModel`，extra=forbid，`tool_catalog.py:28-29`）
   与 preview_builder、handler。
2. 用 `_definition()` 注册（L578-627）：`action_kind` 决定风险等级（`policy.py` 权威）；
   `allowed_agents` 写明授权 Agent；R2 工具必须带真实 preview 与 handler。
3. **R3 工具不可注册**（注册器抛错，L224-232）；R2 工具的 `confirmation_actions` 由 AgentSpec
   声明（AI Agent Engineer 目录）——由对账 R4 自动验证，缺失即测试/启动失败。
4. 派生存量生效：spec 消费方（gateway、runtime）自动获得新工具，无需手工改 `catalog.py` 元组。
5. 运行对账测试与既有 gateway 测试（QA 门禁）。
6. Approval Center 与前端目录项展示（schemas/routes 属 Tech Lead 契约面，走契约冻结）。
7. Feature Flag 灰度 + 文档更新（Tech Lead 归档）。
8. 若工具来自 Provider（n8n/browser/computer-use），先验证 Provider 隔离边界（交接 1/3、3/3）。

**本轮设计中的两个落地例子**：交接 1/3 的 `workspace.file.restore`（R2，授权 LOCAL_DOCUMENT）；
交接 3/3 的 `calendar.event.upsert` 启用与 `email.draft.create`（R2）。二者都走本流程。

---

## 5. 归属与契约边界

| 对象 | Owner | 说明 |
|---|---|---|
| `tool_catalog.py` / `tool_gateway.py` | Tool & Automation（FILE_OWNERSHIP §2.4） | 注册、对账函数、派生视图实现方 |
| `agent_core/catalog.py` / `contracts.py` / `registry.py` | AI Agent Engineer（§2.2） | AgentSpec 声明与模型；我方只读 |
| `apps/api/app/db/**` | Backend Platform（§2.1） | 本轮不涉及表变更 |
| `apps/api/app/schemas/**`、`config.py`、`docs/**` | Tech Lead（冻结） | 契约/flag/文档变更需批准 |
| 对账测试 | QA & Reliability（§5） | 静态断言与门禁 |

对账函数位置建议：`tool_catalog.py` 尾部（注册完成后执行）或新增 `tool_reconciliation.py`
（新文件所有权需 Tech Lead 登记）；不得 import 环（tool_catalog 已依赖 contracts/policy，catalog 不反向依赖 tool_catalog）。

---

## 6. 风险与交接

- 风险 1：派生视图改变 gateway 行为 → 只改变 `allowed_tools` 来源，运行时校验逻辑
  （`tool_gateway.py:88-124`）保持不变，行为等价。
- 风险 2：对账 fail-fast 阻断启动 → 属于预期（比静默漂移安全）；测试先行可提前暴露。
- 风险 3：AI Engineer 与我方并行改两侧 → 对账测试成为合并门禁，冲突在 CI 暴露而非运行时。
- **修改文件清单**：无（只读预研）。**测试结果**：未运行。**AI 辅助记录**：未调用付费模型、未发送私人数据。
