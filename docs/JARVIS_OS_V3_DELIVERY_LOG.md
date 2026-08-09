# Jarvis OS V3 交付日志

> 本文件只记录已完成阶段的实现证据、测试环境和遗留项。
> 仍然有效的方向、阶段依赖和验收口径见 [JARVIS_OS_V3_PLAN.md](./JARVIS_OS_V3_PLAN.md)。

## V3-0：对话地基

- 完成日期：2026-08-07
- 状态：完成并验收
- 默认 Flag：关闭
- 相关提交：`79a876e`、`3166fdc`

### 交付

| 交付 | 证据 |
|---|---|
| Feature Flags | `v3_dialog_workspace_enabled`、`v3_sse_enabled`，均有运行时读取点和关闭测试 |
| 对话聚合接口 | `GET /api/v1/ui/dialog`，聚合会话、运行、审批、主动建议和今日摘要 |
| SSE 基座 | `GET /api/v1/ui/events`，连接快照、dialog 版本、15 秒心跳、自动重连 |
| 前端接口 | `apps/web/src/lib/api/dialog.ts` |
| 对话工作台 | `apps/web/src/components/chat/dialog-workspace-panel.tsx` |
| 验收脚本 | `scripts/verify_chat_workspace.cjs` |

### 验收记录

- `check.ps1`：exit 0；
- 默认测试环境：pytest 362 passed / 0 skipped / 0 xfailed；
- TypeScript typecheck、lint 通过；
- Flag-on：对话面板和契约键正常，浏览器控制台无错误；
- Flag-off：接口返回 404，前端静默降级到旧聊天。

### 已知限制

- 事件总线为进程内队列，只支持单 worker；
- `data_version` 仍通过周期查询生成；
- 事件 ID 按连接重新编号，尚不支持可靠 `Last-Event-ID` 续传；
- 业务模块尚未全面发布实时事件；
- 可靠 PG 事件日志纳入 V3-1.5。

### 回滚记录

- 已验证关闭 `v3_dialog_workspace_enabled` 与 `v3_sse_enabled` 后，聚合接口返回 404，前端静默降级到旧聊天；
- 当时未单独保存完整回滚演练记录，因此这里只声明已验证的 Flag-off 路径，不追溯补写未留存的操作过程。

## V3-1：记忆网络

- 完成日期：2026-08-07
- 状态：功能完成并验收；保持默认关闭，等待 V3-1.1 加固
- 默认 Flag：`v3_memory_network_enabled=false`
- 相关提交：`304aba8`、`809a0f6`、`71af03a`

### 交付

| 交付 | 证据 |
|---|---|
| 数据模型 | `memory_entities`、`memory_relations`、`memory_events` |
| 迁移 | `0032_memory_network`，已执行模型/迁移 DDL 一致性回归 |
| 接口 | candidates / extract / confirm / ignore / merge / query |
| 规则抽取 | Growth、English、Intelligence、Investment 结构化来源 |
| 本地模型抽取 | 最近对话与已确认记忆；Ollama 不可用时静默降级 |
| 候选确认制 | confirm 前不可进入网络检索；支持 ignore / merge |
| 多跳检索 | 最多 2 hop、溯源、候选状态过滤、初版预算裁剪 |
| 前端候选卡 | 确认、忽略、合并、触发抽取和刷新 |
| 评测集 | `evals/memory-network-eval-set.jsonl`，36 条 |
| 统计脚本 | `scripts/evaluate-memory-adoption.py` |

### 验收记录

两组测试来自不同环境，必须分开解读：

- PostgreSQL 真库全集：pytest 374 passed / 0 failed；
- 默认环境：pytest 344 passed / 30 skipped，跳过项为环境门控用例；
- PG 集成用例：30/30；
- Prompt 评测：25/25；
- `check.ps1`、ruff、typecheck、lint 通过；
- 浏览器验收：候选卡正常渲染，确认后候选移除，控制台无错误。

### 首次候选样本

- 规则抽取：4 确认、2 忽略；
- 旧口径采纳率：66.7%；
- Qwen：Ollama 未常驻，尚无有效实跑样本；
- v1.2 起改用“有效候选率”和“去重率”分开统计，历史样本保留但不据此宣告达标。

### 转入 V3-1.1 的加固项

- 实体唯一性目前主要由查询后插入保证，需要数据库级并发约束；
- 已归档关系与同一关系再次成立的历史语义需要明确；
- 事件与实体关联目前为 JSON，需要补充外键完整性方案；
- 查询 `limit` 当前分别作用于实体、关系和事件，需要改成全局总预算；
- token 预算需要按最终渲染内容计算；
- Qwen、n8n/Ollama 全栈复跑仍属于环境门控；
- `research_reports` 模型/迁移约束不一致属于 V2 历史债务，不并入 V3-1 完成声明。

### 回滚记录

- `v3_memory_network_enabled` 保持默认关闭，关闭后继续使用旧检索路径；既有 Flag-off 契约由 404 与静默降级测试覆盖；
- 当时未单独保存完整回滚演练记录。V3-1.1 起按本文记录规则显式记录迁移回滚与 Flag-off 演练结果。

## V3-1.1：记忆网络加固

- 完成日期：2026-08-09
- 状态：完成并验收；默认保持关闭，等待后续灰度启用
- 默认 Flag：`v3_memory_network_enabled=false`
- 相关提交：`faea836`（计划基线）及本节所在实现提交

### 交付

| 交付 | 证据 |
|---|---|
| 并发实体唯一性 | 当前 candidate/active 实体使用数据库部分唯一索引；并发冲突通过 savepoint 收敛到既有实体 |
| 关系历史 | 当前断言使用部分唯一索引；归档记录写入 `valid_until`，允许同一关系后续重新成立 |
| 事件实体完整性 | 新增 `memory_event_entities` 外键关联表和查询索引；保留 `entity_ids` JSON 作为兼容副本并双写 |
| 迁移 | `0033_memory_network_hardening`，包含旧数据去重、关联回填、关系有效期修复及可逆 downgrade |
| 全局召回预算 | 实体、关系、事件合计不超过 `limit`（接口最大 12）；8K 预算按包含溯源字段的最终 JSON 计算 |
| 权限与来源复核 | 查询时重新检查规范来源状态；`for_cloud=true` 时排除 private 实体及包含 private 实体的关系、事件 |
| 回归测试 | 覆盖并发收敛、关系重建、事件外键/合并传播、来源复核、云端过滤、全局数量与渲染预算 |

### 验收记录

- 默认 SQLite 定向测试：13 passed；
- PostgreSQL 新增加固用例：3 passed，覆盖并发唯一性、事件外键拒绝和索引执行计划；
- PostgreSQL 旧数据迁移诊断：重复实体收敛、事件关联重指向、关系归档和 JSON 兼容副本同步均通过；
- PostgreSQL 迁移回滚演练：`0033 -> 0032 -> 0033` 通过，使用随机临时数据库并在结束后删除；
- 后端回归（排除既有的静默时段墙钟敏感用例）：350 passed / 32 skipped / 1 deselected；
- SSE/UI 定向回归：4 passed；Prompt 评测：25/25；
- Ruff、前端 typecheck、前端 lint、备份演练 dry-run、文档 diff 检查通过；安全检查通过并保留既有 `.env` 本地读取权限警告。

### 已知限制与后续边界

- PostgreSQL 全量临时库运行中，5 个既有用例仍受模型与历史迁移 status 约束漂移影响；涉及 `agent_runs`、`agent_approvals`、`tool_executions`、`tool_approvals`、`memories`，不由本阶段修改引入；
- `test_scan_route_returns_summary` 直接读取当前上海时间，在静默时段运行会失败；其余后端回归已通过；
- Qwen、n8n/Ollama 全栈复跑仍受环境门控，不影响本阶段数据库完整性与检索预算验收；
- 下一阶段为 V3-1.5 Router 切流与可靠事件地基，不进入 V3-2。

### 回滚记录

- 已在一次性 PostgreSQL 数据库实际执行 downgrade 到 `0032` 并重新 upgrade 到 `0033`，迁移链路通过；
- `v3_memory_network_enabled` 仍为默认关闭，旧检索 Flag-off 路径保留；新关联表不会在 Flag 关闭时接管用户请求。

## 记录规则

后续每个阶段只在完成验收后追加一节，至少记录：

1. 完成日期与提交；
2. 默认 Flag 状态；
3. 交付物与代码证据；
4. 按环境区分的测试结果；
5. 浏览器或真库验证；
6. 未完成项和转入下一阶段的债务；
7. 实际回滚演练结果。
