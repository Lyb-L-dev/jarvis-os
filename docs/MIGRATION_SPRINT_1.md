# MIGRATION_SPRINT_1.md — 迁移 Sprint 1 交付与验收记录

- **文档类型**：Tech Lead 产出（迁移路线图 Sprint，与 v1 的 `docs/SPRINT_N.md` 交付记录区分）
- **日期**：2026-08-06
- **状态**：✅ 已验收（2026-08-06，合入 dev）

---

## 1. 交付物总览（4 Agent 并行）

| Agent | 任务 | 状态 | 证据 |
|---|---|---|---|
| Backend Platform | Repository/UoW、状态枚举、checkpointer 下沉、迁移规范 | ✅ | `db/repositories/`、`db/uow.py`、`db/enums.py`、`db/checkpoint.py`、迁移 `20260806_0030`、models/schemas/pyproject |
| Memory Engineer | 检索类函数去 commit 副作用 | ✅ | `services/knowledge_retrieval.py`（自包含修复，无 Repository 依赖） |
| AI Agent Engineer | Prompt 集中管理规划 + Router v2 接入预研（只读） | ✅ 预研 | 22 处硬编码 prompt 迁移清单、注册表设计、4 阶段灰度方案 |
| AI Agent Engineer | checkpointer 引用下沉（H2，唯一写操作） | ✅ | research/growth workflow + PG 测试的 import 全部切换至 `db.checkpoint`，本地类已删除 |
| QA & Reliability | 测试基线快照、知识归档冲突补测、门禁复核 | ✅ | `evals/TEST_BASELINE.md`、`tests/test_knowledge_archive_coverage.py`、`tests/test_data_layer_regression.py` |

## 2. 所有权核对结论（Tech Lead）

- 全部改动均落在各自 Owned 路径；`research_workflow.py` / `growth_workflow.py` 未动（等 AI Engineer）。
- **授权例外**：`apps/api/tests/test_growth_workflow_postgres.py` 的 1 行 import 联动修改
  由 AI Engineer 落地（QA 目录），属 checkpointer 下沉的必要机械联动，Tech Lead 已核并授权。
- **冻结区例外（已授权）**：`schemas/memory.py`、`schemas/tool.py` 属 FILE_OWNERSHIP 冻结区，
  作为 Sprint 1「状态枚举 → Pydantic Literal」任务的必要部分，Tech Lead 已审核授权；
  TS 层同步点记入 Sprint 4（OpenAPI 类型生成时收敛）。
- 工作区并行模式：4 Agent 均未执行 git 写操作，改动保留在工作树，由 Tech Lead 统一提交。

## 3. 契约冻结决定

1. **状态枚举以实际状态机为准**（三处差异：Memory 增 `inactive/superseded`；ToolExecution
   采用 8 值实际状态机；AgentRun 采用 `waiting_for_*` 族）——已回写
   `JARVIS_TARGET_ARCHITECTURE.md §6.1`。权威来源 `db/enums.py`。
2. **`db/tests` 纳入门禁**：✅ 已落地——`scripts/check.ps1` 已补 `apps\api\app\db\tests`，
   新增 16 个单测纳入一键门禁（Backend 的 pyproject `testpaths` 对一键门禁无效，故以 check.ps1 为准）。
3. **依赖审计维持现状**：本地门禁离线，`pip-audit` 由 CI 负责（QA 交接结论采纳）。

## 4. 测试与门禁结果

- 基线（commit `5470607`）：40 文件 / 203 函数 / 221 用例 → **219 passed, 2 skipped**。
- Sprint 1 全量（含 Backend/Memory/QA 在途改动）：**271 passed, 2 skipped**（42 文件 / 224 函数 / 257 用例）。
- **合并前最终门禁（Tech Lead 复跑，2026-08-06）**：`scripts/check.ps1` exit 0；
  pytest **277 passed, 2 skipped**（279 collected，含 `db/tests` 16 例）；安全扫描 1 WARN
  （既有 `.env` ACL）；prompt & policy 评测 16/16；web typecheck + lint 全过。
- 跳过项（环境门控）：`test_cost_center.py:192`（Ollama 未运行）、
  `test_growth_workflow_postgres.py:33`（未设 `JARVIS_TEST_POSTGRES_URL`）。

## 5. 遗留待办（合入 dev 后）

1. **迁移 0030 应用（生产 PG 运行时）**：先 `scripts/backup.ps1` 建恢复点 → 跑五表
   `status` 分布预检 SQL → 若存量含非法值先修数据（Tech Lead 裁决）→ `alembic upgrade head`。
2. **check.ps1 与 CI 对齐**（QA 交接 §5 差异清单）：本地与 CI 的 security/覆盖范围
   非等价（离线安全扫描 vs pip-audit；desktop 测试仅本地跑），Sprint 6 收尾时统一。

## 6. 验收标准对照

| Sprint 1 验收项 | 状态 |
|---|---|
| 现有测试全绿 | ✅（合并前最终复跑） |
| 新增 Repository/UoW 单测 | ✅ 16 个（`db/tests`） |
| 事务边界文档化 | ✅ 本文件 + Backend 交接（命名规范、事务所有权规则） |
| H2 checkpointer 反向耦合解除 | ✅ research/growth 均从 `db.checkpoint` 引入，本地副本已删 |

## 7. 合并记录

- 分支：`sprint-1`（自 `dev` 分叉，五笔 Owner 分组提交）→ 合入 `dev`；`main` 保持
  基线不动（验收口径：dev 为集成分支）。
- 提交分组：Backend Platform（数据层+迁移）→ Memory Engineer（检索去副作用）→
  AI Agent Engineer（checkpointer 下沉）→ QA & Reliability（门禁+测试+基线）→
  Tech Lead（文档归档+契约冻结）。提交哈希见 `git log dev`。
