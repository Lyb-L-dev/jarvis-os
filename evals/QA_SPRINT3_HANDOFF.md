# QA & Reliability Agent — Sprint 3 交接说明

- **日期**：2026-08-06
- **分支**：dev（共享工作区，未执行任何 git 写操作）
- **归属**：`apps/api/tests/**`、`evals/**`（由 Tech Lead 归档至 docs/）

---

## 1. 任务完成情况

| Sprint 3 任务 | 状态 | 产出 |
|---|---|---|
| 复核 Sprint 2 授权例外（7 个 QA 属主文件） | ✅ 通过 | `evals/QA_SPRINT2_EXCEPTION_REVIEW.md` |
| PG 集成测试框架（JARVIS_TEST_POSTGRES_URL 门控） | ✅ 无 PG 全 skip；真库运行手册见 §4 | `tests/conftest.py` + `tests/test_pg_integration.py` |
| 归档原子化测试（配合 Memory 单事务） | ✅ skip 门控已就位 | `tests/test_knowledge_archive_atomicity.py` |
| 备份演练 dry-run 验证（配合 Backend） | ✅ 常开契约测试 + skip 门控 | `tests/test_backup_drill.py` |

## 2. 测试命令与结果

### 2.1 授权例外复核（证据）

```powershell
& .venv\Scripts\python.exe -m pytest `
    apps/api/tests/test_prompts_registry.py `
    apps/api/tests/test_router_consistency.py `
    apps/api/tests/test_runtime_registry_dual.py `
    apps/api/tests/test_policy_reading_point.py `
    apps/api/tests/test_workflow_registry_audit.py -q
# → 29 passed

& .venv\Scripts\python.exe scripts/evaluate-prompts.py
# → 25/25（exit 0）
```

**结论：通过**（无断言弱化、无测试造假、覆盖合理）。5 条非阻塞建议见复核文档 §4。

### 2.2 新增测试（本机无 PG/无 Ollama/Backend 未落地的门控行为）

```powershell
& .venv\Scripts\python.exe -m pytest `
    apps/api/tests/test_pg_integration.py `
    apps/api/tests/test_knowledge_archive_atomicity.py `
    apps/api/tests/test_backup_drill.py -q
# → 2 passed, 27 skipped（skip 原因均与环境/未落地门控一致）
```

- PG 23 例：`JARVIS_TEST_POSTGRES_URL` 未设置 → 全 skip（与既有
  `test_growth_workflow_postgres.py` 同模式）。
- 归档原子化 2 例：`knowledge_archive.py` 仍为逐条 commit + per-item rollback
  （Memory Engineer 单事务未落地）→ skip；落地后自动激活。
- 备份演练 2 例常开（manifest 契约）+ 2 例 skip（Backend 恢复演练脚本 /
  `backup.ps1 -DryRun` 未落地）。

### 2.3 全量回归与门禁

```powershell
& .venv\Scripts\python.exe -m pytest apps/api/tests apps/api/app/db/tests apps/desktop/tests -q
# → 308 passed, 29 skipped（337 collected）

powershell -ExecutionPolicy Bypass -File scripts/check.ps1
# → exit 0（ruff + pytest + security-check + evaluate-prompts + typecheck + lint）
```

跳过项构成：Ollama 门控 1 + PG-postgres workflow 门控 1 + 新增环境/未落地门控 27。

## 3. 授权例外复核结论（摘要）

7 个文件全部通过：

- 5 个新测试（prompts registry / router consistency / runtime dual /
  policy reading point / workflow registry audit）断言均为精确相等、集合包含、
  `pytest.raises` 与 flag 双向断言；无 `assert True` 类占位；无 mock 伪造输出。
- `test_workflow_registry_audit.py` 用 monkeypatch 替换 `_invoke` 属合理接缝
  （被测对象是 AgentSpec 身份与 policy_gate 审计记录，图执行由既有 workflow
  测试覆盖），已标注。
- `evaluate-prompts.py`：contract 按 `id@version` 取文并校验版本漂移；5 条
  live parity 逐字锁定；`prompt_render` 校验 contains + excludes。
- `prompt_policy_cases.jsonl`：20 例期望均为真实行为契约。

详见 [QA_SPRINT2_EXCEPTION_REVIEW.md](E:/贾维斯/evals/QA_SPRINT2_EXCEPTION_REVIEW.md)。

## 4. PG 集成测试框架

### 4.1 结构与门控

- `tests/conftest.py` 新增：
  - `pg_database_url`：读 `JARVIS_TEST_POSTGRES_URL`，缺失即
    `pytest.skip`（与 `test_growth_workflow_postgres.py` 同款文案）。
  - `pg_engine`：asyncpg 引擎 + `CREATE EXTENSION IF NOT EXISTS vector` +
    `Base.metadata.create_all`（函数级，规避 pytest-asyncio loop scope 差异）。
  - `pg_session`：函数级会话，teardown 逆序清空全部元数据表，保证用例独立。
- `tests/test_pg_integration.py` 覆盖：
  - asyncpg 驱动与 PG 方言断言；
  - pgvector 扩展存在性；
  - semantic index 写入 + cosine 距离查询排序（确定性固定向量，不调 Ollama）；
  - 条目元数据 round-trip（hash/chunk/index_version/dimensions）；
  - `invalidate_semantic_source` 删除；
  - `indexed_source_counts` 按源类型分组计数；
  - `semantic_index_supported` PG=True / SQLite=False；
  - ANN：HNSW/IVFFlat 索引存在时 `enable_seqscan=off` + EXPLAIN 断言走索引；
    索引未落地 → skip（配合 Memory 的 ANN 迁移）；
  - 状态枚举 CHECK：5 张表在 PG 上的约束名、合法值可写、非法值
    `IntegrityError`。

### 4.2 真库运行手册（有 PG 时全绿）

```powershell
$env:JARVIS_TEST_POSTGRES_URL = "postgresql+asyncpg://jarvis:jarvis@127.0.0.1:5432/jarvis_test"
& .venv\Scripts\python.exe -m pytest apps/api/tests/test_pg_integration.py -q
```

要求：目标库为**可丢弃的独立测试库**（框架会建 extension + 全 schema 并在每个
用例后清表）；用户需具备建 extension 权限；Ollama 不参与（向量为固定 fixture）。

## 5. 覆盖缺口清单（Sprint 3 收尾建议）

1. **有 PG 真库验证**：本机无 PG/Docker，23 个 PG 用例仅验证了 skip 路径；
   需在隔离 PG 环境跑一遍全绿并回填结果（可挂 CI 独立 job）。
2. **归档原子化激活**：Memory Engineer 落地单事务后，本套 skip 门控自动激活；
   若实现改为“外层整体 rollback”形态，需按最终行为微调断言。
3. **备份演练激活**：Backend 落地恢复演练脚本后，补充与脚本实际参数名一致的
   dry-run 调用（当前按 `-DryRun -BackupDirectory` 约定编写）。
4. **ANN 索引迁移后**：`test_ann_index_used_when_hnsw_or_ivfflat_exists` 自动
   激活；建议同时用真库 EXPLAIN 复核计划形状（enable_seqscan=off 已内置）。
5. **语义检索端到端**：`semantic_candidates` 依赖本地 Ollama embedding，
   未纳入 PG 框架（保持确定性）；后续可在“Ollama 就绪 + PG”双条件门控下补
   端到端用例。

## 6. 风险说明

1. `JARVIS_TEST_POSTGRES_URL` 若指向开发库，fixture 会建表/清表 —— 手册已
   明确要求独立测试库，合并前请 Tech Lead 在交接中向 Memory/Backend 重申。
2. PG 用例依赖 asyncpg 与 pgvector 扩展；CI 如启用需在 runner 预装/启动
   PG 17 + vector 镜像（沿用 infra compose 同款镜像）。
3. 归档原子化检测基于源码特征（`await session.rollback()` 是否仍在循环内），
   属 best-effort 门控；若 Memory 重构为抽取子函数，需同步更新检测。
4. 本轮未修改产品代码、未修改他人 Owned 文件；未执行 git 写操作。

## 7. 本轮改动清单（QA Owned）

| 文件 | 改动 |
|---|---|
| `apps/api/tests/conftest.py` | +PG fixtures（pg_database_url / pg_engine / pg_session） |
| `apps/api/tests/test_pg_integration.py` | 新增，23 用例 |
| `apps/api/tests/test_knowledge_archive_atomicity.py` | 新增，2 用例（skip 门控） |
| `apps/api/tests/test_backup_drill.py` | 新增，4 用例（2 常开 + 2 skip 门控） |
| `evals/QA_SPRINT2_EXCEPTION_REVIEW.md` | 授权例外复核结论 |
| `evals/QA_SPRINT3_HANDOFF.md` | 本交接说明 |

## 8. AI 辅助记录

全程本地执行：未调用外部模型 API、未产生 DeepSeek 费用、未发送个人数据；
所有新增测试离线、确定性；未为通过而弱化任何断言；未修改产品代码。

---

## 9. Round 2（Memory 归档原子化落地 + Backend drill 交付后调整）

### 9.1 归档原子化测试按新契约激活（3/3 通过）

Memory Engineer 已落地 `knowledge_archive.py` 的 `_prepare_archive_item` +
`archive_automatic_sources` 单事务整批回滚。`test_knowledge_archive_atomicity.py`
按变更请求调整：

1. **门控**：由“源码无 per-item rollback”启发式改为功能检测
   `hasattr(archive_module, "_prepare_archive_item")` + 源码确认整批回滚存在。
2. **失败注入**：两条路径——预置不安全 `target_relative_path="../escape.md"`
   归档记录（触发 `_resolve_archive_path` 真实校验失败）与
   monkeypatch `_prepare_archive_item` 对指定项抛错（不再 monkeypatch
   `archive_source`）。
3. **期望契约**：单条失败 → `errors == processed`、`created == 0`、无新增归档
   记录/同步日志（按批处理前后计数对比，预置诱饵记录计入基线）、vault 无文件
   残留；成功路径仍全量落库（2 记录 + 2 archive 日志 + 2 文件）。

### 9.2 备份演练 dry-run 测试激活（4/4 通过）

Backend 已交付 `scripts/backup-drill.ps1` 及 `backup.ps1 -DryRun`。
`test_backup_drill.py` 的两个 skip 门控自动激活并强化断言：

- `backup-drill.ps1 -DryRun -BackupDirectory <tmp>`：exit 0 + 输出
  “Nothing was executed” + 不产生任何 dump/manifest。
- `backup.ps1 -DryRun -BackupDirectory <tmp>`：同上。

### 9.3 check.ps1 纳入 backup-drill dry-run

按 Tech Lead 建议，`scripts/check.ps1` 新增步骤：

```powershell
& (Join-Path $ProjectRoot "scripts\backup-drill.ps1") -DryRun
Assert-LastCommand "Backup drill dry-run"
```

该步骤离线、免 Docker、确定性（真库存在 manifest 时仅打印计划并退出 0）。

### 9.4 复核结果（Round 2）

```text
pytest test_knowledge_archive_atomicity.py test_backup_drill.py
→ 7 passed（原子化 3 + 备份 4）
全量 pytest（api + db + desktop）
→ 313 passed, 25 skipped（338 collected）
scripts/check.ps1
→ exit 0（含新增 backup-drill dry-run 步骤）
ruff（apps 全量）
→ All checks passed
```

### 9.5 覆盖缺口更新

- ✅ 归档原子化（§5-2）已闭环：测试激活且通过。
- ✅ 备份演练（§5-3）已闭环：drill dry-run 测试激活且通过，并纳入门禁。
- ⏳ PG 真库验证（§5-1）与 ANN 迁移后激活（§5-4）仍待隔离 PG 环境回填。
