# MIGRATION_SPRINT_6.md — 迁移 Sprint 6 交付与验收记录（收尾）

- **文档类型**：Tech Lead 产出（迁移路线图 Sprint 6：收尾与验收）
- **日期**：2026-08-06
- **状态**：✅ 收口完成（合入 dev；发布验收待所有者对照 §4 拍板）

---

## 1. 交付物总览

| 项 | Owner | 结果 |
|---|---|---|
| 全量回归 | QA | pytest **332 passed / 25 skipped / 2 xfailed**；`check.ps1` exit 0；Playwright 13 脚本 **PASS 4 / 环境门控 8 / 真实失败 0** |
| 契约四层对账 | QA | `test_contract_four_layer.py` 入门禁：四张状态表四层完全对齐；AgentRun 2 处严格 xfail 遗留 |
| 文档更新 | Tech Lead | ARCHITECTURE.md 追加 v2 迁移状态；README 更新当前阶段 + 迁移交付记录 |
| 性能/资源审计 | Tech Lead | 静态基线见 §3；运行时基线列为发布后待办 |
| 发布验收 | 全团队 | P0 覆盖矩阵见 §4 |
| 死 flag / verify 脚本 / CI 对齐 | Tech Lead + QA | 决定见 §2/§5 |

## 2. Tech Lead 决定

1. **死 flag `v2_agent_core_enabled`：本轮不删，纳入发布后待办**。删除需同步
   `config.py`、`any_v2_feature_enabled`、`.env.example` 与 `test_v2_feature_flags.py:7`
   （QA 属主）；flag 无读取点、惰性无害，Sprint 6 收口不做最后一刻变更。
2. **check.ps1 / CI 对齐：维持现状**（QA 结论采纳）——本地离线扫描与 CI `pip-audit`
   互补；desktop/evaluate-prompts 仅本地、deploy-rules 仅 CI，引入开关会降低本地确定性。
3. **verify 脚本**：`verify_memory_paid_confirmation.cjs` 断言已修为“新的对话”
   （含旧文案 fallback）；`verify_regression_suite.cjs` 增加 Edge/CDP 抖动重试
   （最多 3 次，仅匹配 CDP 特征，真实失败不重试）。
4. **AgentRun 契约遗留**：`generated.ts` 无单一 `AgentRunStatus` 命名联合（内联联合互为
   补集）、Pydantic 侧无 schema 导入 `AgentRunStatus`——两处以 `xfail(strict=True)`
   锁定，修复即触发 XPASS 失败（发布后随契约四层收尾处理）。

## 3. 性能/资源静态基线（Tech Lead，2026-08-06）

| 项 | 数值 |
|---|---|
| `.venv` | 368.5 MB |
| `apps/web/node_modules` | 780.9 MB |
| `apps/web/.next` | 610.1 MB |
| `.data`（运行数据） | 208.6 MB |
| `backups/` | 6.8 MB |
| `types/generated.ts` | 469 KB |
| 全量 pytest 时长 | ~41s（351 collected） |

运行时性能（内存/显存/响应速度）依赖应用在跑，列为发布后基线任务：启动 PG + 前后端后，
记录 J-Core 首屏请求、Chat 首字耗时、4 worker 常驻内存、Ollama 显存占用。

## 4. 发布验收对照（RELEASE_ACCEPTANCE.md P0 矩阵，迁移后状态）

| 领域 | 状态 | 证据 |
|---|---|---|
| 首次初始化与档案 | ✅ | 集成测试全绿 |
| 第一周计划 / 目标任务复盘 | ✅ | growth 测试 + Playwright growth_manager/growth_workflow_ui PASS |
| 长期记忆（确认/编辑/敏感拦截/删除） | ✅ | 记忆测试 + 敏感拦截评测 |
| MiMo 默认路线 | ✅ | 路由评测 + 契约用例 |
| DeepSeek 辅助（逐次确认） | ⏳ 环境门控 | 需真实付费确认流程环境；409 语义测试绿 |
| Ollama 本地模型 | ⏳ 环境门控 | Ollama 未运行；本地路由测试绿 |
| 模型审计 | ✅ | model_execution/model_routing 测试 |
| Windows 提醒 | ✅ desktop 单测 | 本地 6 例通过 |
| OpenClaw/微信 | ⏸ 延期 | v1.1 明确延期，保持不变 |
| 投资记录与复盘 | ✅ | investment 测试全绿 |
| Obsidian 知识库 | ✅ | knowledge 归档/检索/冲突测试 + 评测 |
| 知识复用确认 | ✅ | 候选确认测试 |
| 数据导出 | ✅ | test_data_export |
| 自动备份 | ✅ | test_backup + backup-drill dry-run 入门禁 |
| 受控恢复 | ⏳ 环境门控 | 需 PG 真库执行恢复演练 |
| 软删除与高风险确认 | ✅ | R2/R3 不变量（R3 自动=0、未确认写=0） |
| v2 新能力（Router/Prompt/Registry/阶段 3） | ✅ | 门控测试激活 + 评测 25/25 |

## 5. 发布后待办（不阻塞发布，已记录）

1. **死 flag 清理**：✅ 已移除 `v2_agent_core_enabled`（config/.env.example/test 同步，
   2026-08-07）；`v2_shadow_runs_enabled` 保留决定不变。
2. **AgentRun 契约四层收尾**：✅ `generated.ts` 单一 `AgentRunStatus` 命名联合 +
   Pydantic `AgentRunStatus` 导入（growth/research 工作流响应改用 enums 别名），
   2 个 strict xfail 已解除（见 §7）。
3. **PG 真库复跑**：✅ 已完成（2026-08-06，详见 §6），含备份/恢复演练的
   Docker 容器路径真跑（`backup.ps1` / `verify-backup.ps1` /
   `backup-drill.ps1` 全部实跑通过，见 §6.5）。
4. **n8n 测试账号工作流**：契约字段 `test_accounts_connected` 已落地（§7）；
   剩余外部步骤=凭据就绪后按 `infra/n8n/workflows/README.md` 启用（置 `available=True`、
   字段置 true）；`email.draft.create` 的 catalog `confirmation_actions` 随激活补齐。
5. **Prompt 消费点二期切换**：✅ 8 处（personality/english/knowledge/memory/summary/
   intelligence/chat/evaluation）全部接入注册表，`V2_PROMPT_REGISTRY_ENABLED=true`（§7）。
6. **前端**：✅ `[module]` 占位页已删除（构建/类型检查通过）；globals.css 令牌经审计
   无冗余可删（作用域主题变量为有意设计）；视觉回归预拆分基线缺口维持记录；
   Edge headless 重试已加（4 个仍为环境抖动，见 §7 Playwright 复跑）。
7. **运行时性能基线**：✅ 已采集（§7.6）。

---

## 6. PG 真库验证记录（2026-08-06 完成）

**环境**：本机原生 PostgreSQL 18.4（Windows x64，`E:\pgsql\pgsql`，trust 认证），
pgvector **0.8.6**（`andreiramani/pgvector_pgsql_windows` 官方 Windows 构建，
该发布标注在 PostgreSQL 18.4 上测试，与本机一致）。

### 6.1 数据库准备

- 安装 pgvector：`vector.dll` → `lib\`，`vector.control` + `vector--*.sql` → `share\extension\`。
- 创建 `jarvis` 角色与 `jarvis` 数据库（密码取自 `.env`，未回显），
  `CREATE EXTENSION vector` 启用，向量距离自检通过。
- 创建可丢弃测试库 `jarvis_pg_test`（Owner jarvis，预建 vector 扩展）。

### 6.2 迁移升级演练（真实存量数据）

- 将旧备份 `backups/jarvis-20260804T024832Z-6637c48e.dump`（PG 17 导出，
  alembic 0025、65 张表、1 用户/8 工具执行/4 记忆）恢复进 `jarvis` 库，
  表清单与 dump TOC **65/65 一致**。
- 恢复点：`backups/jarvis-20260806T164946-68cda93.dump`（迁移前状态）。
- 五表 status 分布预检：存量值全部落在 0030 CHECK 允许集内（0 非法）。
- `alembic upgrade head`：0025 → 0026 → 0027 → 0028 → 0029 → **0030** → **0031** 全部成功；
  验证版本 = `20260806_0031`、5 个状态 CHECK、HNSW 索引
  `ix_semantic_index_entries_embedding_hnsw`（m=16, ef_construction=64）、
  存量数据完好（1/8/4）。

> 权限注意：备份恢复后对象属主为 postgres，需将表/序列/视图属主改回 jarvis
> （`REASSIGN OWNED` 因扩展对象会报错，改用逐对象 `ALTER ... OWNER TO jarvis`；
> 扩展属主无独立 ALTER 语法，跟随创建者即可，不影响使用）。

### 6.3 PG 真库测试（JARVIS_TEST_POSTGRES_URL=jarvis_pg_test）

- `test_pg_integration.py`：**23/23 通过**（asyncpg、pgvector、语义写入 + cosine 查询、
  invalidate 删除、分组计数、PG/SQLite 差异、ANN/HNSW EXPLAIN 走索引、
  5 表 CHECK 约束名/合法值/非法值 IntegrityError）。
- `test_tool_invariants.py`（R2/R3 账本不变量）：**3/3 通过**（PG 方言，checkpoint 走
  Postgres 路径）。
- `test_growth_workflow_postgres.py`：**1/1 通过**。
- 同范围全量对比（`pytest tests app/db/tests`）：
  - 无 PG：**326 passed / 25 skipped / 2 xfailed**
  - 有 PG：**350 passed / 1 skipped / 2 xfailed**（24 个 PG 门控全部激活；
    剩余 1 跳过为 Ollama 门控）

### 6.4 测试代码修正（首次真跑暴露，QA 属主文件）

`test_pg_integration.py` 两处缺陷此前从未在真库执行过：
1. `test_pg_status_check_constraint_exists` 少一对括号（`await ... .first()` 作用在
   协程上）→ 改为先 `await execute` 再 `.first()`。
2. `test_pg_status_invalid_value_is_rejected` 非法值 30 字符超出字段宽度
   （memories.status 为 VARCHAR(16)），先触发长度错误而非 CHECK →
   改用 12 字符 `"bogus-status"`。

`test_tool_invariants.py` 增加 env-gated PG 支持：设 `JARVIS_TEST_POSTGRES_URL`
时 db_session/gateway_settings 指向 PG（含 vector 预建、teardown 清表），
未设置时保持原 SQLite 行为（两模式均复跑通过）。

### 6.5 受控恢复演练

- 迁移后恢复点：`backups/jarvis-20260806T170322-68cda93.dump`（0031 状态）。
- 手工 staging 演练（等价 `backup-drill.ps1` 的校验步骤；脚本 Docker 容器路径
  本机不可用）：`jarvis_drill_*` 临时库恢复 → 校验 **67 表 / alembic 0031 /
  ck=5 / hnsw=1 / 非法状态 0 / 数据 1-8-4** → 删除临时库，未触碰主库。
- **Docker 容器路径真跑（2026-08-06 晚）**：Docker 管道恢复可访问后，三脚本实跑：
  - `backup.ps1`（真实）：对 `jarvis-postgres`（pgvector/pgvector:pg17）容器执行
    `pg_dump` → `pg_restore --list` 校验 → `docker cp` → vault 归档（29 文件，
    `F:\obsidian\NewHub\NewHub`）→ manifest v2 + sha256；
    产物 `backups/jarvis-20260806T091347Z-8ecc0e06.dump` +
    `.vault.tar.gz` + `.manifest.json`。
  - `verify-backup.ps1`（真实）：**Restore verification passed: 71 tables,
    schema 20260804_0029**；vault 29 files 校验通过。
  - `backup-drill.ps1`（真实）：容器内 `jarvis_drill_*` 临时库恢复 → 校验
    **71 表 / schema 0029 / 关键表行数（memories 4、knowledge_documents 6、
    vault_configs 1、agent_runs 7、chat_messages 51、tool_executions 10）/
    五表状态预检 0 非法 / vault 校验和** → 临时库与容器内临时文件已清理。

### 6.6 正式库切换（2026-08-06 晚，用户决策）

**决策**：以 `jarvis-postgres` 容器库为正式库（项目 compose 原设计
`127.0.0.1:5432`；数据最新：51 聊天/10 工具执行/6 知识文档）。原生 PG 18.4
（127.0.0.1:5432）保留给其它应用，不停服。

**实施**：
- `infra/docker-compose.yml`：postgres 端口发布改为 `127.0.0.1:5433:5432`
  （宿主 5432 被原生 PG 占用；回环绑定安全姿势不变），容器已重建（数据卷
  `jarvis-os_jarvis_postgres_data` 保留，重建后数据 1/51/10/6/4 完好）。
- `.env`（gitignored）与 `.env.example`：`DATABASE_URL` 指向
  `127.0.0.1:5433/jarvis`。
- 迁移：五表状态预检 0 非法 → `alembic upgrade head`
  （0029 → 0030 → 0031）→ 验证 5 CHECK + HNSW 索引 + 数据完好。
- 容器真库测试：`test_pg_integration` 23 + R2/R3 不变量 3 +
  `test_growth_workflow_postgres` 1 = **27/27 通过**（PG 17.10 / pgvector 0.8.6）。
- 全量对比（`pytest tests app/db/tests`，测试库 `jarvis_pg_test` 建于容器内）：
  **350 passed / 1 skipped / 2 xfailed**；`check.ps1` exit 0
  （356 passed，含 desktop companion；security、prompt 25/25、typecheck/lint 全过）。

### 6.7 剩余项

- `restore-backup.ps1` 的 vault 恢复路径仍仅在 dry-run 覆盖（未做破坏性实跑，
  符合设计）。
- 原生 PG 18.4 保留为验证/备用环境（数据为 8/4 快照 + 0031 迁移，未接应用）。
- 全栈复跑剩余环境门控：Ollama 语义、n8n 工作流、Windows 提醒、Edge headless。

---

## 7. Sprint 0-6 收尾项完成记录（2026-08-07）

### 7.1 git 卫生

- 删除已合入 main 的遗留分支 `sprint-1..6` 与空分支 `feat/frontend-api`
  （`git branch -d`，安全删除）；`dev` 快进到 `main`（当前 main = dev）。

### 7.2 死 flag 清理

- 移除 `v2_agent_core_enabled`（config.py 字段 + `any_v2_feature_enabled` 元组 +
  `test_v2_feature_flags.py` 断言 + `.env.example`）。该 flag 无任何运行时读取点。

### 7.3 前端遗留

- 删除死路由 `apps/web/src/app/[module]/page.tsx`（全仓库无链接/引用），重建
  Next.js 产物后 typecheck/lint 通过，路由清单无 `[module]`。
- `globals.css` 令牌去重：全量扫描 153 处自定义属性声明，重复项均为各组件作用域
  的主题变量（orb/agent 分色），属有意设计；未发现可安全删除的冗余块（文件无整段
  重复，前后半段哈希不同）。结论：无需改动，防回归由视觉基线覆盖。

### 7.4 AgentRun 契约四层收尾（解除 2 个 strict xfail）

- `app/schemas/growth.py` / `research.py`：工作流响应 `status` 字段由本地 9 值
  Literal 改为 `app.db.enums.AgentRunStatus`（11 值规范别名）。
- `app/schemas/tool.py`：契约再导出 `AgentRunStatus`。
- 重新生成 `generated.ts`：新增命名联合
  `AgentRunStatus: "created" | ... | "failed"`（11 值），两个工作流响应的
  `status` 字段改为 `$ref` 引用。
- `test_contract_four_layer.py`：删除过渡性内联联合测试与两个 xfail 标记，
  更新 docstring。契约测试 **7/7 通过**。

### 7.5 Prompt 消费点二期切换（8 个模块全部接入注册表并启用）

- 新增 `render_or_fallback` 消费点：personality（block/chat_system/coach_line +
  route boundaries/disclaimer）、english（coach/summary_analysis/rewrite×2）、
  knowledge（capture/insight/retrieval_context）、memory（mem0_instructions/
  qwen_extract/confirmed_wrapper×2）、summary（context_wrapper/compress）、
  intelligence（editor/editor_user）、evaluation（harness）。
- 开关关闭时 fallback=原文本逐字不变；开关开启时逐模块验证字节一致
  （personality/english 抽样 MATCH；prompt 评测 25/25 两种开关状态均通过）。
- `V2_PROMPT_REGISTRY_ENABLED=true`（.env 与 .env.example）。

### 7.6 n8n 契约变更 + vault 恢复实跑

- `N8nProviderStatusResponse` 新增 `test_accounts_connected` 字段
  （schema/provider/测试/前端类型/`generated.ts` 同步；ADR-0010 记录）。
  当前恒 `false`；测试账号激活时置 true，`real_accounts_connected` 保持 false。
- 受控恢复实跑（临时目录演练，不触碰真实备份目录与真实 vault）：
  `backup.ps1` → 当前状态备份（0031+vault 29 文件）→ `restore-backup.ps1`
  （verify → safety backup → DB 交换 jarvis_before_* → vault 恢复到临时目录）。
  恢复后验证 **71 表 / alembic 0031 / 数据 1-51-10-6-4 / vault 15 个文件**；
  演练临时库与目录已清理（`.runtime/restore-drill` 保留产物备查）。

### 7.7 运行时性能基线（首次采集）

| 项 | 值 |
|---|---|
| GPU | RTX 3050 Laptop，885 MiB / 4096 MiB，0%（Ollama 无模型常驻） |
| 后端 API 进程 | ~155 MB（python） |
| 前端 | ~90 MB（node next start） |
| Browser Worker / n8n node | ~63 / ~42 MB |
| Windows Companion | ~36 MB |
| 容器 | postgres 89 MiB；n8n 395 MiB；ingress 37 MiB；neo4j 619 MiB |
| API 延迟（本机） | health 8–40ms；personality/chat/knowledge/approval 15–24ms |

### 7.8 门禁结果（2026-08-07，PG 容器真库）

- `check.ps1` **exit 0**：pytest **358 passed / 0 skipped / 0 xfailed**
  （含 PG 集成 23 + 不变量 3 + workflow PG 1；Ollama 门控本次通过）；
  security 通过（1 个既有 .env ACL WARN）；prompt & policy 评测 **25/25**；
  backup-drill dry-run 通过；前端 typecheck/lint 通过。
- Playwright 验收套件复跑：**PASS 4 / FAIL 9**——4 个 Edge/CDP 启动抖动
  （重试 3 次仍失败，环境性）+ 5 个环境门控（无待审批项、工作流等待模型授权、
  语义索引未重建、本地模型未加载渲染、付费确认按钮禁用态）；无本次改动引入的
  确定性回归（api_boundary/growth_manager/memory_shadow/n8n_provider_ui 均通过）。

### 7.9 仍待外部条件的项

- n8n 测试账号激活（Google Calendar/Gmail 凭据；代码与契约已就绪）。
- Ollama 模型常驻加载后的语义/研究全栈复跑（服务在跑，模型未常驻）。
- Windows 提醒真机验收（桌面单测本地已通过）。
- 原生 PG 18.4 仅保留为备用环境（数据为旧快照，未接应用）。
