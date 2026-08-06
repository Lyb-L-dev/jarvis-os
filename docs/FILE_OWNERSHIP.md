# FILE_OWNERSHIP.md — Jarvis OS 文件所有权矩阵

- **文档类型**：Phase 4 文件所有权设计（技术负责人产出）
- **日期**：2026-08-06
- **目的**：防止两个 Agent 修改同一个文件。本文件是并行动作的**唯一仲裁依据**。
- **规则**：
  1. **Owner** = 唯一可写该路径的 Agent；
  2. **Reader** = 可读（默认所有 Agent 可读任意代码）；
  3. **禁改** = 绝对禁止写入，即使看似修复；
  4. **争议路径** = 需 Tech Lead 明确授权后才可动。

---

## 1. 顶层目录归属

| 路径 | Owner | 说明 |
|---|---|---|
| `docs/`（架构/ADR/Sprint/交接区） | **Tech Lead** | 唯一文档写者；Agent 的交接说明写入此处需 Tech Lead 批准 |
| `README.md`（根） | **Tech Lead** | |
| `.env.example` | **Tech Lead**（契约变更时） | Feature Flag 增删属契约变更 |
| `apps/api/app/core/config.py` | **Tech Lead**（冻结） | 新 Feature Flag 需 Tech Lead 批准（契约面） |
| `apps/api/pyproject.toml` | **Backend Platform** | 依赖治理 |
| `scripts/` | **QA & Reliability**（verify_*/check/security）+ **Backend Platform**（start/stop/backup） | 运维脚本按用途分属 |
| `.claude/` | **Tech Lead** | 协作规范 |

---

## 2. 后端细粒度归属（apps/api）

### 2.1 数据层 — **Backend Platform Agent 独占**

| 路径 | Owner |
|---|---|
| `apps/api/app/db/base.py` | Backend Platform |
| `apps/api/app/db/session.py` | Backend Platform |
| `apps/api/app/db/repositories/**`（新建） | Backend Platform |
| `apps/api/app/db/uow.py`（新建） | Backend Platform |
| `apps/api/app/db/checkpoint.py`（新建，checkpointer 下沉目标） | Backend Platform |
| `apps/api/app/db/models/**`（**全部 22 个模型文件**） | Backend Platform |

> ⚠️ **模型文件是最大争议区**：`db/models/memory.py` 虽属 Memory 领域，但结构变更必须由 **Backend Platform** 统一执行（保证与 Alembic 同步）。Memory Engineer 只能**读**，需要改结构时提交变更请求给 Backend Platform。

| 路径 | Owner |
|---|---|
| `apps/api/migrations/**` | Backend Platform（唯一迁移写者） |
| `apps/api/alembic.ini` | Backend Platform |

### 2.2 Agent 核心 — **AI Agent Engineer 独占**

| 路径 | Owner |
|---|---|
| `apps/api/app/services/agent_core/**`（contracts/registry/routing/policy/runtime/catalog） | AI Agent Engineer |
| `apps/api/app/services/model_gateway/**` | AI Agent Engineer |
| `apps/api/app/services/prompts/**`（新建，Prompt 注册表） | AI Agent Engineer |
| `apps/api/app/services/research_workflow.py` | AI Agent Engineer |
| `apps/api/app/services/growth_workflow.py` | AI Agent Engineer |

### 2.3 记忆/知识 — **Memory Engineer 独占**

| 路径 | Owner |
|---|---|
| `apps/api/app/services/memory.py` | Memory Engineer |
| `apps/api/app/services/memory_engines.py` | Memory Engineer |
| `apps/api/app/services/memory_shadow.py` | Memory Engineer |
| `apps/api/app/services/semantic_index.py` | Memory Engineer |
| `apps/api/app/services/knowledge.py` / `knowledge_archive.py` / `knowledge_capture.py` / `knowledge_insights.py` / `knowledge_retrieval.py` | Memory Engineer |
| `apps/api/app/services/conversation_summary.py` | Memory Engineer |
| `apps/api/app/services/context_engineering.py` | Memory Engineer |

### 2.4 工具/自动化 — **Tool & Automation Agent 独占**

| 路径 | Owner |
|---|---|
| `apps/api/app/services/tool_catalog.py` | Tool & Automation |
| `apps/api/app/services/tool_gateway.py` | Tool & Automation |
| `apps/api/app/services/n8n_provider.py` | Tool & Automation |
| `apps/api/app/services/browser_provider.py` | Tool & Automation |
| `apps/api/app/services/computer_use.py` | Tool & Automation |
| `apps/api/app/services/career_matcher.py` | Tool & Automation（职业雷达工具链路） |

### 2.5 领域服务（不常改，冻结保护）

| 路径 | Owner | 理由 |
|---|---|---|
| `apps/api/app/services/growth.py` | **Tech Lead（冻结）** | 高频稳定模块，改动需审核 |
| `apps/api/app/services/english.py` | **Tech Lead（冻结）** | English 禁 DeepSeek 是安全红线 |
| `apps/api/app/services/intelligence.py` | **Tech Lead（冻结）** | 情报链路稳定 |
| `apps/api/app/services/investment.py` | **Tech Lead（冻结）** | 金融数据 + R3 红线 |
| `apps/api/app/services/monitoring.py` | **Tech Lead（冻结）** | |
| `apps/api/app/services/notifications.py` | **Tech Lead（冻结）** | |
| `apps/api/app/services/proactive.py` | **Tech Lead（冻结）** | |
| `apps/api/app/services/personality.py` | **Tech Lead（冻结）** | |
| `apps/api/app/services/observatory.py` | **Tech Lead（冻结）** | |
| `apps/api/app/services/evaluation.py` | **Tech Lead（冻结）** | |
| `apps/api/app/services/resource_metrics.py` | **Tech Lead（冻结）** | |
| `apps/api/app/services/data_export.py` | **Tech Lead（冻结）** | |
| `apps/api/app/services/backup.py` | **Backend Platform** | 备份链路属平台 |

### 2.6 API 路由层

| 路径 | Owner |
|---|---|
| `apps/api/app/api/router.py` | Backend Platform（注册新增） |
| `apps/api/app/api/routes/**`（23 个路由文件） | **Tech Lead（冻结）**——路由是共享契约面，端点增删需 Tech Lead 授权；具体实现改动委托对应领域 Agent，但写权限集中 |

### 2.7 Schema 层

| 路径 | Owner |
|---|---|
| `apps/api/app/schemas/**`（210 个 Pydantic 类） | **Tech Lead（冻结）**——共享契约面，字段变更会静默破坏前端 api.ts，必须走契约冻结流程 |

---

## 3. 前端细粒度归属（apps/web）

| 路径 | Owner |
|---|---|
| `apps/web/src/lib/api.ts` | **Frontend API Layer Agent（独占）** |
| `apps/web/src/lib/api/**`（拆分产物） | Frontend API Layer Agent |
| `apps/web/src/types/**`（含生成的 `generated.ts`） | Frontend API Layer Agent |
| `apps/web/src/components/**`（64 个组件，除 ui/） | **Frontend Evolution Agent** |
| `apps/web/src/components/ui/**`（shadcn 3 组件） | Frontend Evolution Agent |
| `apps/web/src/app/**`（页面，含 globals.css、layout） | Frontend Evolution Agent |
| `apps/web/src/lib/utils.ts` | Frontend Evolution Agent（工具函数下沉） |
| `apps/web/package.json` | Frontend API Layer Agent（依赖变更） |
| `apps/web/next.config.ts` / `postcss.config.mjs` / `tsconfig.json` | Frontend Evolution Agent |

> **api.ts 隔离墙**：Frontend Evolution Agent **不得修改** `lib/api.ts` 或 `types/`，只能读其导出签名；Frontend API Layer Agent **不得修改**任何 `components/**` 或 `app/**`。两 Agent 通过"签名冻结"解耦（见 MULTI_AGENT_TEAM_PLAN §2.6）。

---

## 4. 自动化/基础设施归属

| 路径 | Owner |
|---|---|
| `apps/browser-worker/server.cjs` / `server.test.cjs` | Tool & Automation |
| `infra/docker-compose.yml` | Tool & Automation（postgres 端口修复、n8n 加固） |
| `infra/n8n/**`（ingress/bootstrap/workflows） | Tool & Automation |
| `infra/ollama/**` | Tool & Automation |
| `apps/desktop/**` | **Tech Lead（冻结）**——稳定桌面组件，非本轮升级重点 |

---

## 5. 测试/脚本/评测归属

| 路径 | Owner |
|---|---|
| `apps/api/tests/**`（40 个测试文件） | **QA & Reliability（独占）**——但按领域分片：改 memory 逻辑的 Memory Engineer 需 QA 协助跑测 |
| `scripts/verify_*.cjs` / `verify_*.py`（12+ 个验收脚本） | QA & Reliability |
| `scripts/check.ps1` / `security-check.ps1` / `preflight.ps1` / `dependency-audit.ps1` / `evaluate-prompts.py` | QA & Reliability |
| `scripts/start.ps1` / `stop.ps1` / `backup*.ps1` / `restore-backup.ps1` / `setup*.ps1` | Backend Platform |
| `evals/**` | QA & Reliability |

---

## 6. 争议路径速查表（遇到先查这里）

| 路径 | 当前 Owner | 争议原因 | 处置 |
|---|---|---|---|
| `apps/api/app/db/models/memory.py` | Backend Platform | Memory 领域 vs 结构变更 | 结构改→Backend Platform；逻辑读取→Memory Engineer 只读 |
| `apps/api/app/api/routes/chat.py` | Tech Lead（冻结） | 路由与 AI Agent 都碰 | 端点/字段变更→Tech Lead；AI 内部逻辑→委托 AI Engineer 提 PR |
| `apps/api/app/schemas/memory.py` | Tech Lead（冻结） | 契约面 | 变更需契约冻结 + 通知 Frontend API Layer |
| `apps/web/src/lib/api.ts` | Frontend API Layer | 全局唯一 API 客户端 | 独占，组件侧只读签名 |
| `apps/api/app/services/growth.py` | Tech Lead（冻结） | 高频稳定 | 改动需明确授权 |
| `apps/api/app/services/research_workflow.py` | AI Agent Engineer | 跨领域 | 已明确归属 AI Engineer |
| `apps/api/app/core/config.py` | Tech Lead（冻结） | Feature Flag 契约 | 新增 flag 需 Tech Lead |
| `apps/api/pyproject.toml` | Backend Platform | 依赖 | httpx2 修复归 Backend Platform |

---

## 7. 所有权变更流程

1. Agent 需要改**他人目录**的文件 → 提交"变更请求"给 Tech Lead；
2. Tech Lead 评估影响面 → 冻结或授权 → 记录到本文件"争议路径速查表"；
3. 所有权变更本身也是文档变更 → 由 Tech Lead 在本文件修订；
4. 任何 Agent 不得绕过此流程直接写他人目录。

---

## 8. 与并行开发策略的关系

FILE_OWNERSHIP.md 是 Phase 5（Git Worktree/分支）的**逻辑前提**：

- Git 分支保证**时间上的隔离**（不同分支不互相干扰）；
- FILE_OWNERSHIP 保证**空间上的隔离**（同一文件不被两个 Agent 同时改）；
- 两者叠加 = 真正的无冲突并行。

> 合并冲突的根源永远是"两个分支改了同一文件"。FILE_OWNERSHIP 把这种概率降到最低——**每个文件只有一个 Owner，交叉改动必须经 Tech Lead 串行化**。
