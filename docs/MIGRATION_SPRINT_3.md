# MIGRATION_SPRINT_3.md — 迁移 Sprint 3 交付与验收记录

- **文档类型**：Tech Lead 产出（迁移路线图 Sprint 3：记忆与知识深化）
- **日期**：2026-08-06
- **状态**：✅ 已验收（合入 dev；main 保持基线）

---

## 1. 交付物总览

| Agent | 任务 | 状态 | 证据 |
|---|---|---|---|
| Memory Engineer | 归档批量原子化 | ✅ | `knowledge_archive.py` 单事务整批回滚（`_prepare_archive_item` 两段式，errors=total 语义） |
| Memory Engineer | Mem0 去全局单例阻塞（M6） | ✅ | `memory_engines.py` 每次调用独立会话，锁不覆盖 `add()`；provider 强约束与影子隔离不变 |
| Memory Engineer | ANN HNSW 设计 + 迁移草稿 | ✅ | 设计结论 HNSW `vector_cosine_ops`，m=16 / ef_construction=64；草稿经 Backend 落库 |
| Backend Platform | ANN 迁移 0031 落地 | ✅ | `migrations/20260806_0031_semantic_ann_hnsw.py`（up/down）+ `db/models/semantic.py` Index 声明，DDL 逐字符一致 |
| Backend Platform | 备份补 vault + 恢复演练 | ✅ | `backup.ps1`（manifest v2 + vault 归档）、`restore-backup.ps1`（-RestoreVault + 路径校验）、`verify-backup.ps1`、新增 `backup-drill.ps1`（dry-run/staging 恢复演练） |
| QA & Reliability | Sprint 2 授权例外复核 | ✅ | 7 个文件逐文件通读 + 实跑 29 passed；评测 25/25；5 条非阻塞建议（见归档复核文档） |
| QA & Reliability | PG 集成测试框架 | ✅ | `tests/conftest.py`（`JARVIS_TEST_POSTGRES_URL` 门控）+ `test_pg_integration.py` 23 例（无 PG 全 skip，真库自动激活） |
| QA & Reliability | 原子化测试 + 备份演练测试 | ✅ | `test_knowledge_archive_atomicity.py` 3/3（按 Memory 新契约重写）；`test_backup_drill.py` 4/4；`check.ps1` 已纳入 `backup-drill.ps1 -DryRun` |

## 2. 所有权核对与协作链

- 全部改动落在各自 Owned 路径；无越界写入。
- **ANN 串行链**：Memory 出设计+草稿（交接）→ Backend 落 `migrations/0031` + 模型 Index 同步
  （PostgreSQL 方言 DDL 与迁移 SQL 逐字符一致，create_all/Alembic 不漂移）→ QA 的
  `test_ann_index_used_when_hnsw_or_ivfflat_exists` 自动激活。
- **原子化契约闭环**：QA 首版测试与实现有 3 处偏差（门控启发式 / 失败注入点 / 期望契约），
  Memory 提交变更请求 → QA 重写并激活（3/3），成功/失败路径均覆盖。
- 迁移只落库不自动应用；应用时机统一走 MIGRATION_SPRINT_1.md §5 流程。

## 3. 测试与门禁结果（合并前最终复跑）

- `scripts/check.ps1`：exit 0；pytest **313 passed, 25 skipped**（338 collected）；
  安全扫描 1 WARN（既有 `.env` ACL）；prompt & policy 评测 25/25；
  `backup-drill.ps1 -DryRun` 已作为门禁步骤执行（输出 "Nothing was executed"）；
  web typecheck + lint 通过。
- 跳过项（25）：Ollama 门控 1、PG-postgres workflow 门控 1、PG 集成框架 23（未设
  `JARVIS_TEST_POSTGRES_URL`）。

## 4. ANN 设计决策（Tech Lead 采纳）

- **HNSW（`vector_cosine_ops`），m=16 / ef_construction=64**：个人规模（数千–数万 chunk）、
  索引随版本/模型频繁重建、支持增量写入；相比 IVFFlat 无聚类/质心漂移/probe 调参，回退
  （drop 索引）即回落全表扫描，应用零改动。
- 预检 SQL（扩展/列类型/存量规模/重复/查询计划基线）见 Backend 迁移文件与 Memory 交接。
- 可选后续：`semantic_candidates` PG 分支 `SET LOCAL hnsw.ef_search = 80`（待 PG 真库阶段评估）。

## 5. 遗留待办

1. **PG 真库验证（需 PostgreSQL 启动）**：应用 `0030` + `0031`（`backup.ps1` 建恢复点 →
   预检 SQL → `alembic upgrade head`）；跑 `test_pg_integration.py` 23 例回填真库结果；
   执行 `backup-drill.ps1` 真库演练。`JARVIS_TEST_POSTGRES_URL` 必须指向可丢弃测试库。
2. **Mem0 性能观察**：每次影子运行新建/关闭客户端成本高于旧单例（影子评测为用户主动触发，
   可接受）；记录为观察项。
3. **Sprint 6 收尾项**：check.ps1 与 CI 覆盖差异（pip-audit 网络依赖、desktop 测试仅在本地跑）。

## 6. 验收标准对照（Sprint 3）

| 验收项 | 状态 |
|---|---|
| ANN 索引迁移可回滚（0031 up/down + 模型声明一致） | ✅ |
| PG 集成测试框架跑通 | ✅ 框架就绪（真库回填待 PG 环境） |
| Mem0 故障不影响核心 | ✅（kill switch 最先检查、失败不掩盖结果、错误处理保持） |
| 归档批量原子化（一条失败整批回滚） | ✅ 实现 + 测试激活 |
| 备份补 vault + 自动恢复演练 | ✅ 脚本 + 门禁覆盖 |
