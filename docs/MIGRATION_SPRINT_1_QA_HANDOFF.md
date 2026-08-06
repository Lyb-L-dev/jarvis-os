# QA & Reliability Agent — Sprint 1 交接说明

- **日期**：2026-08-06
- **归属**：`apps/api/tests/**`、`evals/**`（本文件 + `TEST_BASELINE.md` 由 Tech Lead 归档至 `docs/`）
- **模式**：并行开发（未执行任何 git checkout/commit/merge；仅读他人目录）

---

## 1. 任务完成情况

| Sprint 1 任务 | 状态 | 产出 |
|---|---|---|
| 测试基线快照（40 文件 / 203 函数全绿） | ✅ | `evals/TEST_BASELINE.md` |
| 知识归档冲突 / include-exclude 覆盖缺口补测 | ✅ | `tests/test_knowledge_archive_coverage.py` |
| `scripts/check.ps1` 一键门禁 + 与 CI 一致性 | ✅ 已运行并复核 | 结论见 §5 |
| Repository/UoW 与状态枚举 CHECK 约束回归 | ✅ 已补测（含建议） | `tests/test_data_layer_regression.py` + §4 |

## 2. 测试命令与结果

### 2.1 基线（快照时）

```powershell
& .venv\Scripts\python.exe -m pytest apps/api/tests -q `
    --basetemp .runtime\qa-baseline-temp -o "cache_dir=.runtime\qa-baseline-cache"
```

→ **219 passed, 2 skipped（40 文件 / 203 函数 / 221 用例）**

跳过项（环境门控，允许）：

- `test_cost_center.py:192` — Ollama 进程未运行
- `test_growth_workflow_postgres.py:33` — 未设置 `JARVIS_TEST_POSTGRES_URL`

### 2.2 QA 新增测试

```powershell
& .venv\Scripts\python.exe -m pytest apps/api/tests/test_knowledge_archive_coverage.py `
    apps/api/tests/test_data_layer_regression.py -q
& .venv\Scripts\python.exe -m ruff check apps/api/tests/test_knowledge_archive_coverage.py `
    apps/api/tests/test_data_layer_regression.py
```

→ **36 passed（含 15 个参数化 CHECK 用例），ruff All checks passed**

### 2.3 全量（当前工作区，含 Backend/Memory 在途改动）

```powershell
& .venv\Scripts\python.exe -m pytest apps/api/tests -q
```

→ **255 passed, 2 skipped（42 文件 / 224 函数 / 257 用例）**

### 2.4 一键门禁

```powershell
powershell -ExecutionPolicy Bypass -File scripts/check.ps1
```

→ **exit 0**（约 131s；ruff / pytest / security-check / evaluate-prompts /
web typecheck / web lint 全过；security-check 1 条 WARN：`.env` 本机读取权限较宽，
不影响门禁）。

## 3. 知识归档覆盖缺口清单

### 3.1 本轮已补齐（`test_knowledge_archive_coverage.py`）

| 缺口 | 测试 |
|---|---|
| 自动归档 exclude：非 `ready` 日报不入选 | `test_auto_archive_excludes_non_ready_daily_briefs` |
| 自动归档 exclude：未确认 / 已删除记忆不入选 | `test_auto_archive_excludes_unconfirmed_and_deleted_memories` |
| 冲突保护：源变更 → `updated`，替换目标并清空 review 路径 | `test_archive_updated_replaces_target_and_clears_review` |
| 冲突保护：用户改动目标 → `user_modified`，保留用户内容 | `test_archive_user_modified_preserves_edited_target` |
| 冲突保护：目标缺失 → `user_modified`（记录 `missing`），不重写 | `test_archive_missing_target_reported_as_user_modified` |
| 路径安全：`../`、非 `.md`、`.obsidian`、非允许前缀全部拒绝 | `test_archive_rejects_unsafe_record_target_paths`（4 参数） |
| 扫描 include/exclude：非 md 与超限文档不入索引 | `test_scan_excludes_non_markdown_and_oversized_documents` |
| 冲突 review 文件被索引为 `review` 文档 + 同步日志 `conflict` | `test_conflict_review_file_is_indexed_as_review_document` |
| 自动归档后触发扫描，文档索引更新 | `test_auto_archive_scan_updates_document_index` |
| 手动候选 include：仅 completed 英语会话入选 | `test_manual_candidates_include_completed_english_sessions_only` |
| 非法 source_type 拒绝 | `test_unsupported_archive_source_type_is_rejected` |

### 3.2 剩余缺口（建议后续，未在本轮补）

1. **归档批量原子性**：`archive_automatic_sources` 目前逐条 commit + 逐条
   try/except（errors 计数）。Sprint 3 计划改单事务，落地后应补“一条失败整批回滚”
   测试。
2. **归档渲染 2MB 上限**：`_render_markdown` 超限抛错无直接测试（构造 >2MB
   负载开销大，建议用 monkeypatch 后补）。
3. **符号链接 / reparse 防护**：Windows 上创建 symlink 需特权，建议在 CI(Linux)
   或人工场景补 `_resolve_archive_path` 的链接拒绝用例。
4. **后台 worker**：`knowledge_archive_background_worker` 依赖 `SessionFactory`
   与首个 User，建议抽出可注入 session 的纯函数后再测。
5. **检索无副作用契约**：Memory Engineer 的 `knowledge_retrieval.py` 去 commit
   改动，建议补“检索日志在调用方提交前对其他会话不可见”的双会话测试。

## 4. Repository / UoW / 状态枚举回归

### 4.1 已补（`test_data_layer_regression.py`）

- 仓库层：`get` 缺失返回 `None`；`add` + commit + `get` 持久化；状态迁移
  （`update_status`/`mark_status`/`decide`）在提交前对其他会话不可见；按用户/
  状态过滤与排序、`count_by_status`；去重守卫（fingerprint / idempotency /
  thread_id / pending-by-kind）与决策时间戳。
- 状态枚举：5 张表（agent_runs / agent_approvals / tool_executions /
  tool_approvals / memories）的 CHECK 约束声明、全部合法值可写、非法值触发
  `IntegrityError`；`check_sql` 渲染；Literal 别名与值元组一致性。
- 无外部网络依赖；仅 SQLite 内存库 + 临时文件；断言未弱化。
- 约束未合并时对应用例自动 skip（门禁保持确定性），合并后自动激活。

### 4.2 待 UoW 合并后的建议（未写死，等最终 API）

1. UoW commit：多仓库写入原子提交，全部可见。
2. UoW rollback：任一步失败整批丢弃，无部分写入。
3. 上下文管理：`async with` 退出语义（成功自动 commit / 异常 rollback）。
4. 服务层无 commit：断言 service 调用后未产生独立提交（配合检索去副作用）。
5. 迁移 ↔ 模型 ↔ schema 三方一致性：`20260806_0030` 的 CHECK 字符串与
   `app/db/enums.py` 及模型 `__table_args__` 逐值比对（建议改为读迁移文件做
   静态断言，并纳入门禁收集范围）。

## 5. 门禁结论（check.ps1 与 ci.yml 一致性）

### 5.1 结论

**`scripts/check.ps1` 可一键运行且当前全绿；五类门禁（ruff + pytest +
typecheck + lint + security）在本地脚本与 CI 中均存在。** 但两侧“security”与
覆盖范围的实现**不完全等价**，差异如下。

### 5.2 差异清单

| 维度 | check.ps1（本地） | ci.yml | 说明 |
|---|---|---|---|
| security | `security-check.ps1`（离线：密钥扫描 / loopback / 端口 / .gitignore / .env ACL） | `pip-audit -r pyproject.toml`（依赖漏洞，需网络） | 互补但不等价；本地门禁不覆盖依赖审计 |
| dependency-audit.ps1 | 未接入 check.ps1 | —（CI 用 pip-audit 单侧） | 现有 `dependency-audit.ps1`（pip-audit + npm audit）未纳入一键门禁 |
| ruff 范围 | apps/api + apps/desktop | 仅 apps/api | desktop lint 本地查、CI 不查 |
| pytest 范围 | apps/api/tests + apps/desktop/tests | 仅 apps/api | desktop 6 用例 CI 不跑 |
| evaluate-prompts.py | 本地跑 | 无对应 job | 提示词策略评估仅在本地 |
| infra 语法（compose / node --check） | 不跑 | deploy-rules job 跑 | CI 多出的部署层校验 |

### 5.3 需要 Tech Lead 裁决的门禁缺口

1. **Backend 新增 `apps/api/app/db/tests/`（4 文件 / 16 用例）不在门禁收集范围**
   （check.ps1 与 CI 都只收集 `apps/api/tests`）。建议：迁入 `apps/api/tests/`
   或扩展 pytest `testpaths`。
2. **依赖审计网络依赖**：pip-audit 需联网拉漏洞库。建议本地门禁保持离线
   （维持现状），由 CI 负责依赖审计，或在 check.ps1 增加可选开关
   （默认关闭）接入 `dependency-audit.ps1`。
3. **状态枚举值集与目标架构 §6.1 不一致**：实现为“实际状态机的安全超集”
   （如 AgentRun 使用 `waiting_for_*`、Memory 增加 `inactive/superseded`、
   ToolExecution 使用 `created/pending_approval/executing/succeeded` 等）。
   Backend 已在交接中说明；需 Tech Lead 冻结最终契约（DB CHECK + Pydantic +
   TS union 四层统一后，QA 补一致性静态测试）。

## 6. 风险说明

1. **并行工作区在途变更**：本会话期间 Backend Platform 陆续落地 enums.py、
   repositories/、uow.py、checkpoint.py、迁移 0030、模型/schema 改动。中途一度
   出现 `schemas.tool` 引用不存在的 `ToolApprovalStatus`（3 个收集错误）与
   ruff UP040 ×5，随后由 Backend 修复；最终全量门禁通过。合并顺序需 Tech Lead
   把关：QA 新增测试与 Backend 数据层改动应同批合并，避免中间态红门禁。
2. **Memory Engineer 未提交改动**：`knowledge_retrieval.py` 去 commit 副作用
   在基线中生效；基线可复现性依赖该改动保持在工作区（详见 TEST_BASELINE §5）。
3. **CHECK 约束对存量数据的影响**：迁移 0030 若存量行含非法状态会整批中止
   （设计如此），需 Tech Lead 按 Backend 交接做预检 SQL 复核。
4. **新增测试针对仓库层接口快照**：若 Backend 最终 UoW/仓库 API 与当前观察
   不同，需微调测试适配（均为本地断言，风险低）。

## 7. AI 辅助记录

- 本 Agent 全程本地执行：未调用任何外部模型 API，**未产生 DeepSeek 费用**，
  未向云端发送个人数据。
- 未运行任何 git 写操作（无 checkout/commit/merge）；未修改他人 Owned 文件。
- 全部测试离线、确定性；无外部网络依赖；未弱化任何既有断言。
