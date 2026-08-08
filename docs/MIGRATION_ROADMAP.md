# MIGRATION_ROADMAP.md — Jarvis OS 升级路线图（含多 Agent 并行开发策略）

- **文档类型**：Phase 5 + 6 并行开发策略与开发顺序（技术负责人产出）
- **日期**：2026-08-06
- **目标**：把当前系统从"v2 影子代码"渐进升级为"Personal AI Operating System"，全程多 Agent 安全并行。
- **核心约束**：Migration 不 Rewrite；每个 Sprint 可独立运行/验收/回滚；Feature Flag 灰度。

---

## 1. 前置工程动作（P0 — 必须最先完成，否则并行无意义）

### 1.1 为什么并行开发必须先建工程地基

审计发现（CURRENT_PROJECT_AUDIT.md C1/C5/H10）：当前项目**不是 git 仓库**、无 CI、postgres 暴露公网端口。没有 git 就没有分支隔离，没有分支隔离就谈不上"并行"。因此 **Sprint 0 的产出是全部后续 Sprint 的前置条件**。

### 1.2 Sprint 0：工程地基（Tech Lead + Backend Platform + QA 联合）

| 任务 | Owner | 产出 |
|---|---|---|
| `git init` + `.gitignore` 核对 + **首次提交**（当前完整代码库作为基线） | Tech Lead | git 仓库 |
| 建立分支规范（见 §2） | Tech Lead | 分支策略文档 |
| postgres 端口改 `127.0.0.1:5432:5432` | Tool & Automation | 消除 C5 公网暴露 |
| 修复 `httpx2` 依赖（改回正确的 `httpx` 已存在→删除 `httpx2`） | Backend Platform | 消除 M1 供应链风险 |
| `scripts/check.ps1` 落地为 CI 门禁（本地 pre-commit + 可选 GitHub Actions） | QA & Reliability | check 门禁 |
| **测试基线快照**：记录当前 40 测试文件 / 203 测试函数全绿 = 合并门槛 | QA & Reliability | TEST_BASELINE.md |
| `.env.example` 与 config.py 对齐（补 `proactive_*/computer_use_stage`、清理 `OPENCLAW_*` 注释） | Tech Lead | 消除 M4 漂移 |

**验收**：`git log` 有基线提交；`check.ps1` 可一键跑全量门禁；postgres 不再公网暴露；依赖审计通过。

---

## 2. Git 并行开发策略

### 2.1 为什么不用 Git Worktree（本项目特殊决策）

标准方案是 Git Worktree，但**本项目是 Windows 单机 + 非 git 仓库 + 本地个人系统**，直接套用 Worktree 有现实障碍：

- 当前无 git 仓库 → 先初始化；
- Worktree 需要每个 Agent 一个工作目录 + 各自装依赖（.venv、node_modules 各一份），**16GB 内存 + 独立显卡 的机器会资源爆炸**（两个 node_modules + 两个 venv + 两个 ollama 模型池）；
- 单用户本地项目，不需要远程协同的"多工作树"隔离级别。

因此采用**更适合本项目的混合策略**：

### 2.2 推荐方案：分支 + 目录隔离 + 串行合并（Branch-per-Domain）

```text
main  ← 始终可运行的生产基线（check.ps1 必须全绿）
 └── dev  ← 集成分支（各 Agent 合并点，Tech Lead 维护）
      ├── feat/backend-platform/   ← Backend Platform Agent
      ├── feat/ai-engineer/        ← AI Agent Engineer
      ├── feat/memory/             ← Memory Engineer
      ├── feat/frontend-evolution/ ← Frontend Evolution Agent
      ├── feat/frontend-api/       ← Frontend API Layer Agent
      ├── feat/tool-automation/    ← Tool & Automation Agent
      └── feat/qa/                 ← QA & Reliability Agent
```

**分支 vs 目录隔离的映射**：

| 隔离维度 | 机制 | 保证什么 |
|---|---|---|
| 空间隔离 | FILE_OWNERSHIP.md（每个文件唯一 Owner） | 两个 Agent 不可能改同一文件 |
| 时间隔离 | git 分支（每 Agent 一条 `feat/*`） | 各自改动互不可见，互不破坏 |
| 串行化 | 合并必须经 Tech Lead → 跑 check.ps1 → 合入 dev | 契约冲突在合并点被拦截 |

### 2.3 每个 Agent 的工作循环

```text
1. git checkout -b feat/<domain> dev      ← 从最新 dev 分叉
2. 在 Owned 目录实现任务（读他人目录只读）
3. git add <仅 Owned 路径> && git commit  ← 只提交自己的文件
4. 跑 Owned 目录相关测试
5. git pull --rebase dev                  ← 拉取他人已合入的变更
6. 解决冲突（若有——本方案下极罕见，因无文件级重叠）
7. 写交接说明 → 通知 Tech Lead 合并
```

### 2.4 合并协议

```text
Tech Lead 收到合并请求
├── 检查改动是否只落在 Owned 目录        ← FILE_OWNERSHIP 校验
├── 检查契约变更是否冻结广播过            ← config/schemas/routes 变更
├── 跑 scripts/check.ps1（ruff+pytest+typecheck+lint+security）
├── 跑 QA 提供的回归基线
├── 批准 → 合入 dev
└── 拒绝 → 回退改动 + 附原因
```

### 2.5 何时才用 Worktree（可选增强）

若未来需要"两个 Agent 同时跑完整应用做集成测试"（各自起 8000/3000 端口），才引入 Worktree 或第二份 clone。**默认不需要**——并行是在代码层面隔离的，运行时由 Tech Lead 串行验证。

### 2.6 无 git 环境下的临时方案（立即生效）

在 Sprint 0 完成 git 初始化前，用**目录快照**模拟隔离：

```text
备份目录：backups/agent-workspace/<domain>/   ← 每个 Agent 改动前快照 Owned 目录
```

此方案仅作过渡，Sprint 0 一完成即切换 git。

---

## 3. Sprint 计划（6 个 Sprint）

> 每个 Sprint = 一个可验收的阶段。**并行矩阵**见 §4。每个 Sprint 结束时的"Done"定义：check.ps1 全绿 + 对应功能验收 + 可回滚。

### Sprint 0 — 工程地基（1 周）
见 §1.2。产出：git 仓库、分支规范、CI 门禁、测试基线、端口/依赖修复。

### Sprint 1 — 后端架构治理（Backend Platform 主战场）
| 任务 | Owner |
|---|---|
| 建立 `db/repositories/` + `db/uow.py`（Repository/UoW 边界） | Backend Platform |
| `knowledge_retrieval.py` / 检索类函数去 commit 副作用 | Memory Engineer（经 Backend 协调） |
| 状态枚举统一：`AgentApproval`/`Memory`/`ToolExecution` 状态 → DB CHECK + Pydantic Literal | Backend Platform |
| checkpointer 下沉 `db/checkpoint.py`，解开 `research_workflow`↔`growth_workflow` 反向耦合（H2） | Backend Platform |
| 迁移命名规范统一（0022 后新表约束） | Backend Platform |

**验收**：现有测试全绿 + 新增 Repository/UoW 单测；事务边界文档化。

### Sprint 2 — AI 能力落地（AI Agent Engineer 主战场）
| 任务 | Owner |
|---|---|
| 新建 `services/prompts/` 注册表 + 版本表；迁移全部硬编码 prompt（personality/english/knowledge/research/growth/summary 等 10+ 处） | AI Agent Engineer |
| Intent Router v2 决策接入 chat 真实路由（Feature Flag `v2_router_*` 灰度） | AI Agent Engineer |
| Policy Router 强制入口接入（消除 `v2_policy_enforcement_enabled` 无读取点） | AI Agent Engineer |
| Workflow 从 Agent Registry 解析 AgentSpec；RuntimeRegistry 注册 Direct/Workflow | AI Agent Engineer |
| 清理死 flag（`v2_agent_core_enabled` 等 4 个） | AI Agent Engineer |
| 后台模型调用统一走 ModelRouter（M2：knowledge_capture/insights/summary/memory_engines） | Memory Engineer |

**验收**：Prompt 可版本化评测；Router 在 Flag 下可回滚；workflow 审计记录走 AgentSpec。

### Sprint 3 — 记忆与知识深化（Memory Engineer 主战场）
| 任务 | Owner |
|---|---|
| pgvector ANN 索引迁移（HNSW，`semantic_index_entries.embedding`） | Memory Engineer |
| PG 集成测试框架（`JARVIS_TEST_POSTGRES_URL` 自动化，覆盖 pgvector/asyncpg 路径） | QA + Memory |
| Mem0 引擎去全局单例阻塞（memory_engines.py 线程模型） | Memory Engineer |
| 归档批量原子化（knowledge_archive.py 逐条 commit → 单事务） | Memory Engineer |
| 备份补 vault 文件 + 自动恢复演练脚本 | Backend Platform |

**验收**：ANN 索引迁移可回滚；PG 测试跑通；Mem0 故障不影响核心。

### Sprint 4 — 前端渐进重构（双 Frontend Agent 主战场）
| 任务 | Owner |
|---|---|
| api.ts(5372行) 按领域拆分 `lib/api/**` + 统一 `request()` 封装 + **导出签名不变** | Frontend API Layer |
| OpenAPI 类型生成（openapi-typescript → `types/generated.ts`）+ 契约一致性测试 | Frontend API Layer |
| `investment-center.tsx`(1876行) 拆分 → hooks + 子组件（视觉回归验收） | Frontend Evolution |
| 同法处理 english/chat/growth 三个巨型组件 | Frontend Evolution |
| `providerLabel` 等重复工具函数下沉 `lib/utils.ts`；清理 `[module]` 死路由；globals.css 令牌去重 | Frontend Evolution |

**验收**：组件拆分后像素级不变（Playwright 截图对比）；api.ts 拆分后所有组件零改动；typecheck/lint 全绿。

### Sprint 5 — 工具与自动化扩展（Tool & Automation 主战场）
| 任务 | Owner |
|---|---|
| Computer-use 阶段 3：确认后沙箱文件修改（保持 R2 预览-批准-执行） | Tool & Automation |
| 工具注册扩展流程（新增工具走 AgentSpec ↔ ToolRegistry 交叉校验，消除 H5） | Tool & Automation |
| n8n 真实工作流（日历写入/邮件草稿，先测试账号验收） | Tool & Automation |
| AgentSpec 白名单单一来源校验（catalog ↔ tool_catalog 自动化对账） | AI Agent Engineer |

**验收**：R3 自动执行数 = 0；R2 未确认写操作 = 0；新工具经交叉校验。

### Sprint 6 — 收尾与验收（全团队）
| 任务 | Owner |
|---|---|
| 全量回归（check.ps1 + 12 个 Playwright verify 脚本 + PG 集成测试） | QA |
| 契约四层统一最终对账（DB CHECK + Pydantic + TS union） | QA + 各 Agent |
| 更新文档（ARCHITECTURE.md 反映新架构、README 交付记录） | Tech Lead |
| 性能/资源审计（内存、显存、响应速度） | Tech Lead |
| 发布验收（对照 RELEASE_ACCEPTANCE.md P0 矩阵） | 全团队 |

**验收**：所有 Sprint 验收项关闭；无回归；发布验收通过。

---

## 4. 并行矩阵（每个 Sprint 的并发分配）

```text
Sprint 1 并行：
  Backend Platform  ── db/repositories/, uow, 枚举迁移, checkpoint下沉
  Memory Engineer   ── 检索函数去副作用（不与 Backend 碰同文件，靠 FILE_OWNERSHIP）
  AI Engineer       ── (Sprint 2 预研：prompts 目录规划，只读不写)
  QA                ── 测试基线加固 + 补知识归档冲突测试
  冲突面：db/models（Backend 独占）+ migrations（Backend 独占）→ 零重叠

Sprint 2 并行：
  AI Engineer       ── prompts/, router接入, registry
  Memory Engineer   ── 后台调用统一路由
  Frontend Evolution ── (Sprint 4 预研：investment-center 结构分析，只读)
  Tool & Automation ── (Sprint 5 预研：computer-use 阶段3 设计文档)
  冲突面：chat.py 路由（Tech Lead 冻结，AI Engineer 提 PR）→ 串行化

Sprint 3 并行：
  Memory Engineer   ── ANN迁移, PG测试, Mem0
  Backend Platform  ── 备份/恢复演练
  QA                ── PG 集成测试框架
  冲突面：migrations（Backend 独占）→ Memory 提迁移脚本交 Backend 落库

Sprint 4 并行：
  Frontend API Layer   ── api.ts 拆分（独占 lib/）
  Frontend Evolution  ── 组件拆分（独占 components/ + app/）
  冲突面：types/（API Layer 独占）vs components 的 import → 靠签名冻结解耦
```

---

## 5. 风险登记册

| 风险 | 等级 | 缓解 |
|---|---|---|
| 多 Agent 并行导致契约漂移（后端字段改，前端不知） | High | 契约冻结流程 + OpenAPI 生成 + 契约一致性测试（Sprint 4） |
| 迁移过程中破坏现有安全边界（R0-R3/敏感拦截） | High | 安全红线 = Agent 禁改目录（FILE_OWNERSHIP §2.5）+ QA security-check 门禁 |
| 无 git 期间并行冲突 | High | Sprint 0 优先建 git；过渡期用目录快照 |
| 资源瓶颈（多 venv/node_modules） | Medium | 采用分支方案而非 Worktree；运行时由 Tech Lead 串行验证 |
| 巨型文件拆分引入回归 | Medium | Playwright 视觉回归 + 行为测试先于拆分（QA 提供基线） |
| DeepSeek 误调用产生费用 | Medium | DeepSeek 确认逻辑冻结 + 审计监控（QA 定期对账） |
| 迁移中断导致数据不一致 | Low | 每个迁移前备份 + staging 库恢复验证（现有机制） |

---

## 6. 成功验收标准（整体）

1. **git 仓库**可追溯全部改动，任何提交可回滚；
2. **7 个执行 Agent** 各自在 Owned 目录并行工作，合并冲突趋近于零；
3. **Intent/Policy Router 接生产**，前端展示"当前 Agent/模型/费用/审批"（v2 蓝图 Conversation Workspace）；
4. **Prompt 可版本化**、可评测、可回滚；
5. **pgvector ANN 索引 + PG 集成测试**就位；
6. **前端可维护**：无 1000+ 行组件、无 5000+ 行 api.ts、契约三处合一；
7. **Computer-use 阶段 3** 在 R2 审批下可用；
8. 全程 **check.ps1 全绿**、安全边界零突破、无新 DeepSeek 误调用。

---

## 7. 与现有 v2 蓝图的关系

本路线图不替代 `JARVIS_OS_V2_ARCHITECTURE_MIGRATION_PLAN.md`（那份是架构约束），而是它的**工程执行计划**：

```text
v2 蓝图（已有）     → 定义"变成什么样"       → docs/JARVIS_OS_V2_ARCHITECTURE_MIGRATION_PLAN.md
本路线图（新增）    → 定义"怎么多 Agent 完成" → docs/MIGRATION_ROADMAP.md
FILE_OWNERSHIP（新增）→ 定义"谁改哪里"        → docs/FILE_OWNERSHIP.md
MULTI_AGENT_TEAM（新增）→ 定义"谁做什么"      → docs/MULTI_AGENT_TEAM_PLAN.md
```

> 所有新增文档都以现有 v2 蓝图为架构北极星，不引入新的架构方向，只解决"如何在真实代码上安全并行落地"这一工程问题。
