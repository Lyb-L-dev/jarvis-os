# MULTI_AGENT_TEAM_PLAN.md — Jarvis OS 多 Agent 并行开发团队设计

- **文档类型**：Phase 3 多 Agent 团队设计（技术负责人产出）
- **日期**：2026-08-06
- **前提**：基于 `CURRENT_PROJECT_AUDIT.md`（真实目录扫描）+ `JARVIS_TARGET_ARCHITECTURE.md`（目标架构）
- **设计原则**：不设固定角色，**按真实目录划分所有权**。每个 Agent 是"目录领主"，只能写自己的目录，只读他人目录，破坏性改动必须走 Tech Lead 合并审核。

---

## 1. Agent 团队总览

本项目由 8 个 Agent 组成：1 个 Tech Lead + 7 个执行 Agent。执行 Agent 按**代码资产边界**划分，每个都拥有独立可运行的子系统。

| Agent | 类型 | 拥有目录 | 只读目录 | 关键任务 |
|---|---|---|---|---|
| **Tech Lead Agent** | 协调者 | `docs/`（架构/ADR/路由）、根 `README.md` | 全部 | 架构守卫、任务拆分、契约冻结、合并审核 |
| **Backend Platform Agent** | 执行 | `apps/api/app/db/`、`apps/api/app/core/`、`apps/api/migrations/`、`apps/api/app/api/`（仅路由注册） | `apps/api/app/services/`（只读） | Repository/UoW、状态枚举、checkpointer 下沉、契约层打通 |
| **AI Agent Engineer** | 执行 | `apps/api/app/services/agent_core/`、`services/model_gateway/`、`services/prompts/`（新建）、workflow 文件 | `apps/api/app/db/`、`apps/api/app/services/`（领域服务只读） | Router/Policy 接生产、Prompt 集中化、workflow 走 Registry |
| **Memory & Knowledge Engineer** | 执行 | `apps/api/app/services/memory*.py`、`semantic_index.py`、`knowledge*.py`、`conversation_summary.py`、`context_engineering.py` | 同上 | 事务去副作用、pgvector ANN、统一路由、Mem0 线程安全 |
| **Frontend Evolution Agent** | 执行 | `apps/web/src/**`（除 `lib/api.ts`） | `apps/api/app/schemas/`、`apps/api/app/api/routes/`（只读契约） | 巨型组件拆分、hooks 抽取、共享类型生成 |
| **Frontend API Layer Agent** | 执行 | `apps/web/src/lib/api.ts`、`apps/web/src/types/` | 同上 | api.ts 模块化拆分、OpenAPI 类型生成、路径对齐测试 |
| **Tool & Automation Agent** | 执行 | `apps/api/app/services/tool_*.py`、`n8n_provider.py`、`browser_provider.py`、`computer_use.py`、`apps/browser-worker/`、`infra/n8n/` | 全部（只读） | 工具扩展、Computer-use 阶段 3、自动化隔离加固 |
| **QA & Reliability Agent** | 执行 | `apps/api/tests/`、`scripts/verify_*.cjs`、`scripts/check.ps1`、`evals/` | 全部（只读） | 测试基线、CI 门禁、回归防护、安全审计 |

> 说明：Frontend 拆分两个 Agent 是因为 `lib/api.ts`（5,372 行）与 64 个组件是**两个独立的改动面**——一个改 API 契约，一个改 UI，天然不冲突（File Ownership 见下）。

---

## 2. Agent 详细设计

### 2.1 Tech Lead Agent

| 项 | 内容 |
|---|---|
| **名称** | Jarvis Tech Lead |
| **职责** | 架构守卫、任务拆分、契约冻结、跨 Agent 合并审核、ADR 维护、路线图推进 |
| **拥有目录** | `docs/`（架构/ADR/设计）、根 `README.md`、`.claude/`（协作规范） |
| **只读目录** | 全部（默认只读，写操作仅限 docs/） |
| **禁止修改** | `apps/`、`infra/`、`scripts/`（除非紧急修复且经用户确认） |
| **必读文档** | `CURRENT_PROJECT_AUDIT.md`、`JARVIS_TARGET_ARCHITECTURE.md`、`MULTI_AGENT_TEAM_PLAN.md`、`FILE_OWNERSHIP.md`、`MIGRATION_ROADMAP.md`、全部 ADR |
| **任务** | ① 维护架构决策与文档；② 拆分 Sprint 任务并分配 Agent；③ 冻结/解冻契约；④ 审核所有跨目录改动与合并请求；⑤ 运行 `scripts/check.ps1` 验收合并 |
| **输出** | 每轮：任务分配表、契约变更记录、合并审核结论、风险清单 |
| **AI 辅助** | 可用任意模型（含 DeepSeek）做架构分析，不直接操作业务数据 |

### 2.2 Backend Platform Agent

| 项 | 内容 |
|---|---|
| **名称** | Jarvis Backend Platform |
| **职责** | 数据层治理：Repository/UoW、状态枚举、迁移规范、checkpointer 下沉、契约层与持久层统一 |
| **拥有目录** | `apps/api/app/db/`、`apps/api/app/core/`、`apps/api/migrations/`、`apps/api/app/api/router.py` |
| **只读目录** | `apps/api/app/services/**`、`apps/api/app/api/routes/**`（不直接改业务逻辑） |
| **禁止修改** | `apps/web/**`、`apps/desktop/**`、`apps/browser-worker/**`、`infra/**`、`scripts/**`、`docs/` |
| **必读文档** | `JARVIS_TARGET_ARCHITECTURE.md` §5、`CURRENT_PROJECT_AUDIT.md` §5（H1/H6/H2）、`FILE_OWNERSHIP.md` |
| **任务** | ① 建 `db/repositories/` + `db/uow.py`；② 统一状态枚举（DB CHECK）；③ checkpointer 下沉 `db/checkpoint.py` 并改 research/growth 引用；④ 修 `httpx2` 依赖；⑤ postgres 端口 `127.0.0.1` 绑定；⑥ 迁移命名规范统一 |
| **输出** | 修改文件清单、pytest 结果、迁移风险说明 |
| **红线** | 不改变任何业务行为；数据迁移前必须有恢复点；`db/models/` 结构变更必须同步 Alembic |

### 2.3 AI Agent Engineer

| 项 | 内容 |
|---|---|
| **名称** | Jarvis AI Agent Engineer |
| **职责** | Agent 核心落地：Intent/Policy Router 接生产、Agent Registry 全接入、Prompt 集中管理、Runtime 注册 |
| **拥有目录** | `apps/api/app/services/agent_core/`、`apps/api/app/services/model_gateway/`、`apps/api/app/services/prompts/`（新建）、`research_workflow.py`、`growth_workflow.py` |
| **只读目录** | `apps/api/app/db/`、`apps/api/app/services/`（领域服务，仅读契约）、`apps/api/app/api/routes/chat.py`（读路由流） |
| **禁止修改** | `apps/api/app/services/memory*.py`、`knowledge*.py`、`tool_*.py`、`intelligence.py`、`english.py`、`growth.py`、`investment.py`（这些归各自领域 Agent）；`apps/web/**` |
| **必读文档** | `JARVIS_TARGET_ARCHITECTURE.md` §3-C §5、`docs/JARVIS_OS_V2_ARCHITECTURE_MIGRATION_PLAN.md`、ADR 0001/0004 |
| **任务** | ① Prompt 目录 + 版本注册表 + 迁移全部硬编码 prompt；② Router v2 决策接入 chat 真实路由（Feature Flag 灰度）；③ workflow 从 Registry 解析 AgentSpec；④ RuntimeRegistry 注册 Direct/Workflow；⑤ 死 flag 清理 |
| **输出** | Prompt 清单、Router 接入 diff、评测集挂接说明 |
| **红线** | 不得绕过 Model Gateway 直连模型；不得扩大 Agent 权限；DeepSeek 确认逻辑只读 |

### 2.4 Memory & Knowledge Engineer

| 项 | 内容 |
|---|---|
| **名称** | Jarvis Memory Engineer |
| **职责** | 记忆/知识/语义检索：事务去副作用、pgvector ANN、后台调用统一路由、Mem0 线程模型 |
| **拥有目录** | `apps/api/app/services/memory.py`、`memory_engines.py`、`memory_shadow.py`、`semantic_index.py`、`knowledge*.py`、`conversation_summary.py`、`context_engineering.py`、`db/models/{memory,semantic,knowledge,context}.py` |
| **只读目录** | `apps/api/app/services/agent_core/`、`model_gateway/`、`apps/api/app/db/`（平台层只读） |
| **禁止修改** | `apps/web/**`、`tool_*.py`、`english.py`、`investment.py`、`intelligence.py`、`infra/**` |
| **必读文档** | `CURRENT_PROJECT_AUDIT.md` §5（H1/H7/M6）、ADR 0007/0008、`JARVIS_TARGET_ARCHITECTURE.md` §5.2 |
| **任务** | ① `knowledge_retrieval.py` 去 commit 副作用；② pgvector ANN 索引迁移；③ 后台模型调用改走 ModelRouter；④ Mem0 引擎去全局单例阻塞；⑤ 归档批量原子化 |
| **输出** | 事务边界改动清单、PG 集成测试、索引迁移 SQL |
| **红线** | 记忆确认流程、敏感拦截、`cloud_allowed` 门禁语义不可改变；删除传播必须完整 |

### 2.5 Frontend Evolution Agent

| 项 | 内容 |
|---|---|
| **名称** | Jarvis Frontend Evolution |
| **职责** | UI 演进：巨型组件拆分、hooks 抽取、样式令牌统一、死代码清理 |
| **拥有目录** | `apps/web/src/**`（**除 `lib/api.ts` 与 `types/`**） |
| **只读目录** | `apps/web/src/lib/api.ts`（读导出签名，不写）、`apps/api/app/schemas/`、`apps/api/app/api/routes/`（读 API 契约） |
| **禁止修改** | `apps/web/src/lib/api.ts`、`apps/web/src/types/`、`apps/api/**`、`apps/desktop/**` |
| **必读文档** | `CURRENT_PROJECT_AUDIT.md` §5（C4/H10）、`FILE_OWNERSHIP.md`（api.ts 边界） |
| **任务** | ① 拆分 `investment-center.tsx`(1876行) → hooks+子组件；② 同法处理 english/chat/growth；③ `providerLabel` 等重复工具函数下沉 `lib/utils.ts`；④ 清理 `[module]` 死路由；⑤ `globals.css` 令牌去重 |
| **输出** | 组件拆分清单、视觉回归截图、typecheck 结果 |
| **红线** | 不改变任何 API 调用路径；不引入新依赖；行为保持像素级不变（视觉回归验收） |

### 2.6 Frontend API Layer Agent

| 项 | 内容 |
|---|---|
| **名称** | Jarvis Frontend API Layer |
| **职责** | API 客户端治理：api.ts 模块化、共享类型生成、前后端契约对齐 |
| **拥有目录** | `apps/web/src/lib/api.ts`、`apps/web/src/lib/api/**`（拆分产物）、`apps/web/src/types/` |
| **只读目录** | `apps/api/app/schemas/**`（读 Pydantic 契约）、`apps/api/app/api/routes/**`（读端点）、`apps/web/src/components/**`（读调用方，不写） |
| **禁止修改** | `apps/web/src/components/**`、`apps/web/src/app/**`、`apps/api/**`（后端改契约需提交 Tech Lead 协调） |
| **必读文档** | `CURRENT_PROJECT_AUDIT.md` §5（C2/H8）、`FILE_OWNERSHIP.md` |
| **任务** | ① api.ts(5372行) 按领域拆分 `lib/api/{chat,memory,growth,investment,intelligence,knowledge,notifications,tools,system}.ts`；② 引入 OpenAPI 类型生成（`openapi-typescript`）产物落 `types/generated.ts`；③ 路径对齐测试（断言 api.ts 路径 ⊆ router 端点）；④ 统一 `request()` 封装替换 200 个重复 fetch |
| **输出** | 拆分 diff、生成的类型文件、契约一致性测试 |
| **红线** | **不修改任何组件调用签名**——先拆分后重构，保持 `lib/api.ts` 导出名不变（兼容层），组件层零改动 |

### 2.7 Tool & Automation Agent

| 项 | 内容 |
|---|---|
| **名称** | Jarvis Tool & Automation |
| **职责** | 工具网关扩展、自动化隔离加固、Computer-use 阶段 3 |
| **拥有目录** | `apps/api/app/services/tool_catalog.py`、`tool_gateway.py`、`n8n_provider.py`、`browser_provider.py`、`computer_use.py`、`apps/browser-worker/**`、`infra/n8n/**` |
| **只读目录** | `apps/api/app/services/agent_core/`（读 AgentSpec 白名单）、`apps/api/app/db/` |
| **禁止修改** | `apps/web/**`、`memory*.py`、`knowledge*.py`、`english.py`、`investment.py`、`intelligence.py`、`growth.py` |
| **必读文档** | `docs/JARVIS_OS_V2_ARCHITECTURE_MIGRATION_PLAN.md` §10/§12、ADR 0009/0010/0011、`CURRENT_PROJECT_AUDIT.md` §5（C5） |
| **任务** | ① Computer-use 阶段 3（确认后沙箱修改）；② 工具注册扩展（新增工具走 AgentSpec 交叉校验）；③ n8n 真实工作流（日历写入/邮件草稿，先测试账号）；④ postgres 端口绑定 127.0.0.1（基础设施项） |
| **输出** | 工具定义清单、R2 审批测试、隔离验证 |
| **红线** | R3 永不自动化；R2 必须预览-批准-执行三阶段；不引入新凭据暴露；browser-worker 7 层隔离不削减 |

### 2.8 QA & Reliability Agent

| 项 | 内容 |
|---|---|
| **名称** | Jarvis QA & Reliability |
| **职责** | 测试基线、CI 门禁、回归防护、安全审计 |
| **拥有目录** | `apps/api/tests/**`、`scripts/verify_*.cjs`、`scripts/check.ps1`、`evals/**`、`scripts/preflight.ps1`、`scripts/security-check.ps1` |
| **只读目录** | 全部（写操作仅限测试/脚本/评测文件） |
| **禁止修改** | `apps/**`（产品代码，除非修复测试所需的明显错误并经 Tech Lead 确认） |
| **必读文档** | `CURRENT_PROJECT_AUDIT.md` §5、`MIGRATION_ROADMAP.md`、所有 ADR |
| **任务** | ① 建立"测试基线快照"（当前 203 个测试全过 = 合并门槛）；② 补充缺失覆盖（knowledge_insights/archive 冲突逻辑、pgvector 集成测试）；③ 维护 CI 门禁脚本；④ 定期安全审计（密钥扫描/依赖审计/端口检查）；⑤ 跨 Agent 改动回归验证 |
| **输出** | 测试报告、覆盖缺口清单、安全审计结果、合并前验收结论 |
| **红线** | 测试必须是确定性的（无外部网络依赖）；不得为了通过而弱化断言 |

---

## 3. 协作规则（如何并行而不冲突）

### 3.1 并行动作的黄金法则

1. **文件级独占**：任何时刻，一个文件只能被一个 Agent 修改（由 FILE_OWNERSHIP.md 保证）。
2. **只读自由，写需授权**：所有 Agent 可读任意代码；写操作仅限 Owned 目录。
3. **契约变更必须冻结**：状态枚举、API 路径、AgentSpec 白名单等共享契约变更前，必须由 Tech Lead 冻结并广播。
4. **Feature Flag 默认关**：新能力不改变现有行为；验收后再开。
5. **每改动必过门禁**：提交前运行对应测试；合并前跑完整 `check.ps1`。

### 3.2 并行单元划分（一次 Sprint 的并行矩阵）

```text
Sprint N 并行分配示例：
├── Backend Platform Agent    → db/repositories/ + 状态枚举迁移
├── AI Agent Engineer         → prompts/ 目录 + Router 接入（Flag 关）
├── Memory Engineer           → pgvector ANN 迁移 + 去 commit 副作用
├── Frontend Evolution Agent  → investment-center 拆分（不改 api.ts）
├── Frontend API Layer Agent  → api.ts 模块化（不改组件）
├── Tool & Automation Agent   → Computer-use 阶段 3 规划 + 工具注册
└── QA & Reliability Agent    → PG 集成测试框架 + 覆盖补齐
    冲突面：仅 db/migrations（Backend Platform 独占）+ api.ts（API Layer 独占）
    交叠点：Memory 与 Backend Platform 都碰 db/models → 由 FILE_OWNERSHIP 裁决
```

### 3.3 跨 Agent 交接协议

当 Agent A 的产出被 Agent B 依赖时：

1. A 完成 Owned 目录改动 → 跑测试 → 在 `docs/` 写"交接说明"（改动清单 + 依赖项 + 风险）；
2. Tech Lead 审核 → 合并到 `dev` 分支；
3. B 从 `dev` 拉取 → 读交接说明 → 在 Owned 目录实现依赖消费。

### 3.4 冲突仲裁

- **文件冲突**：FILE_OWNERSHIP.md 仲裁（谁拥有谁改）；
- **契约冲突**：Tech Lead 冻结决策（改接口需书面理由 + 影响面评估）；
- **行为回归**：QA 基线测试不通过 = 合并拒绝；
- **安全红线**：任何 Agent 违反 R0-R3/敏感数据规则 → 立即回滚 + Tech Lead 审查。

---

## 4. 每个 Agent 的输出规范

每个 Agent 每轮任务完成后，必须在 Owned 目录内（或 `docs/` 交接区）输出：

| 输出项 | 要求 |
|---|---|
| **修改文件清单** | 文件路径 + 改动摘要 + 是否触及共享契约 |
| **测试结果** | 运行的测试命令 + 通过/失败数（必须跑 Owned 目录相关测试） |
| **风险说明** | 对现有行为的影响面、回滚方式、需要用户确认的变更 |
| **AI 辅助记录** | 使用了哪些模型、是否产生 DeepSeek 费用、是否发送私人数据 |

---

## 5. 与现有 v2 蓝图的映射

本团队的 Agent 划分直接对应 `JARVIS_OS_V2_ARCHITECTURE_MIGRATION_PLAN.md` 的能力模块：

| v2 能力 | 负责 Agent |
|---|---|
| Agent Contracts / Registry | AI Agent Engineer |
| Intent/Policy Router | AI Agent Engineer |
| LangGraph Workflow | AI Agent Engineer |
| Memory v2 / pgvector | Memory Engineer |
| Mem0 Shadow | Memory Engineer |
| Tool Gateway / Approval | Tool & Automation Agent |
| n8n / Browser | Tool & Automation Agent |
| Conversation Workspace / Command Center / Approval Center 前端 | Frontend Evolution Agent |
| 数据层演进 | Backend Platform Agent |
| 可观测性 / 评测 | QA & Reliability Agent |

> 这套映射保证：**每个 Agent 的改动都落在 v2 蓝图既定的能力上**，不会偏离架构方向。
