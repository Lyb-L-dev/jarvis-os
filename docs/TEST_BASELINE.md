# TEST_BASELINE.md — Jarvis OS 测试基线快照

- **产出方**：QA & Reliability Agent（Sprint 1）
- **日期**：2026-08-06
- **快照基线**：`git rev-parse HEAD` = `5470607`（Sprint 37 完成态 + .gitattributes）
- **归档**：本文件由 Tech Lead 归档至 `docs/`

---

## 1. 基线定义（合并准入门槛）

> 基线 = 后续所有合并的准入门槛：`apps/api/tests` 全量 pytest 必须
> **0 失败**，允许 2 个环境门控跳过（详见 §4）。新增测试只增不弱化断言。

## 2. 基线命令

```powershell
& .venv\Scripts\python.exe -m pytest apps/api/tests -q `
    --basetemp .runtime\qa-baseline-temp `
    -o "cache_dir=.runtime\qa-baseline-cache"
```

结果：**219 passed, 2 skipped（39.3s）**。

## 3. 基线口径

| 口径 | 数量 | 说明 |
|---|---|---|
| 测试文件 | 40 | `apps/api/tests/test_*.py`（另有 `conftest.py` 不计） |
| 测试函数 | 203 | `def test_*` / `async def test_*` 定义数 |
| 收集用例 | 221 | 含参数化展开 |
| 通过 | 219 | — |
| 跳过 | 2 | 环境门控，非失败 |

## 4. 允许的跳过项（基线的一部分）

| 用例 | 跳过原因 | 何时应激活 |
|---|---|---|
| `test_cost_center.py:192` | Ollama 进程未运行 | 本地 Ollama 就绪时 |
| `test_growth_workflow_postgres.py:33` | 未设置 `JARVIS_TEST_POSTGRES_URL` | 隔离 PG 集成运行 |

## 5. 基线工作区状态（可复现性说明）

快照时工作区含 Memory Engineer 未提交改动：

- `apps/api/app/services/knowledge_retrieval.py` — 检索函数去掉 `commit` 副作用
  （事务所有权移交调用方）。基线结果包含该改动；若回退该改动，需重跑基线复核。

## 6. Sprint 1 增补后的当前状态（扩展基线）

| 口径 | 数量 |
|---|---|
| 测试文件 | 42（QA 新增 2 个） |
| 测试函数 | 224 |
| 收集用例 | 257 |
| 通过 | 255 |
| 跳过 | 2（同上，环境门控） |

QA 新增：

- `apps/api/tests/test_knowledge_archive_coverage.py`（11 个函数 / 14 个用例）
- `apps/api/tests/test_data_layer_regression.py`（10 个函数 / 22 个用例）

> 注：Backend Platform 在 `apps/api/app/db/tests/` 新增 4 个测试文件
> （16 个用例），**当前不在门禁收集范围**（见交接说明 §5.3），需 Tech Lead 裁决归属。

## 7. 门禁复核

`scripts/check.ps1` 一键运行（ruff + pytest(api+desktop) + security-check +
evaluate-prompts + web typecheck + web lint）在快照后复跑 **exit 0 通过**
（约 131s）。与 `.github/workflows/ci.yml` 的五类门禁一致性结论见交接说明 §5。
