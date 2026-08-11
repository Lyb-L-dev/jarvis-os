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

## V3-1.5：Router 切流与可靠事件地基

- 完成日期：2026-08-10
- 状态：完成并验收；Router 与可靠事件流均保持默认关闭，等待按意图灰度
- 默认 Flag：`v2_router_enforcement_enabled=false`、`v3_reliable_event_feed_enabled=false`
- 相关提交：本节所在实现提交

### 交付

| 交付 | 证据 |
|---|---|
| RouterV2 深模块 | `route_chat_request(request) -> ChatRoutePlan` 集中处理旧路由比较、意图 allowlist、模型授权和 provider fallback |
| 真实灰度切流 | Flag 与 `v2_router_enforcement_intents` 同时命中才接管；关闭 Flag 或移出 cohort 立即回旧 ModelRouter |
| 路由不变量 | 私人请求强制本地；DeepSeek 未授权时在写消息和模型调用前返回 409；未配置 DeepSeek 时沿旧语义降级本地 |
| 编排前置字段 | `RouteDecision` 增加 `cross_agent_required`；只解释跨 Agent 需求，不在聊天中启动 Orchestrator |
| 固定评测集 | `evals/router-v2-cutover.jsonl` 17 条，覆盖普通、深度、隐私、Research/Growth、cohort 回滚和跨 Agent 解释 |
| 可靠事件日志 | `0034_reliable_ui_events` 新增单调 ID、事件类型、聚合引用、版本、创建/过期时间，不保存业务正文 |
| 事务 Outbox | 对话、Agent Run、模型审批、工具审批、主动建议的状态变更与事件记录使用同一数据库事务 |
| 事件适配器 | PostgreSQL 生产适配器与内存测试适配器隐藏在冻结的 `publish / stream / snapshot` 小接口后 |
| SSE 续传 | 读取 `Last-Event-ID` 并重放保留期内事件；缺失、无效、过期或不存在的游标回退完整 snapshot |
| 最终收敛 | 多连接从同一游标获得一致重放；慢消费者按数据库游标继续追赶；过期记录在连接建立时清理 |

### 验收记录

- Router 固定切流评测：17/17；Router/聊天/SSE/事件定向回归：68 passed；
- 默认环境完整后端（排除既有静默时段墙钟用例）：359 passed / 36 skipped / 1 deselected；
- 仓库统一门禁的测试阶段：381 passed / 36 skipped / 1 failed，唯一失败为 `test_scan_route_returns_summary` 在上海静默时段读取真实墙钟；
- PostgreSQL V3-1.5 定向测试：3 passed，覆盖并发单调 ID、跨会话重放、无正文 schema、查询计划和 Outbox 同事务提交/回滚；
- PostgreSQL 迁移演练：新库 upgrade 到 `0034`、`0034 -> 0033 -> 0034` 均通过，随机临时数据库均已删除；
- 四层契约测试：7 passed；桌面端：6 passed；Prompt/策略评测：25/25；
- 全量 Ruff、前端 typecheck、前端 lint、备份演练 dry-run 通过；安全检查通过并保留既有 `.env` 本地读取权限警告。

### 已知限制与后续边界

- `test_scan_route_returns_summary` 仍直接读取当前上海时间，在静默时段运行统一门禁会失败；该问题未由 V3-1.5 引入；
- 可靠事件流使用 PostgreSQL 轮询而非 Redis；默认 1 秒轮询、7 天保留，可通过配置调整；
- 两个新 Flag 默认关闭，尚未进行长期运行下的事件积压和 p95 采样；
- 下一阶段为 V3-2 Orchestrator 试点；本阶段没有启动 Orchestrator、V3-3 或任何外部副作用。

### 回滚记录

- 已实际执行 `0034 -> 0033 -> 0034`；downgrade 删除 `ui_events`，旧 V3-0 SSE 仍保留 snapshot、心跳和版本轮询；
- 关闭 `v3_reliable_event_feed_enabled` 立即回到旧 SSE；关闭 `v2_router_enforcement_enabled` 或清空意图 cohort 立即回到 ModelRouter；
- `v3_sse_enabled` 仍是整个 SSE 端点的外层开关，关闭后继续返回 404。

## V3-2：按需 Orchestrator 试点

- 完成日期：2026-08-10
- 状态：完成并验收；默认保持关闭，尚未进入 V3-3
- 默认 Flag：`v3_orchestrator_enabled=false`
- 相关提交：本节所在实现提交

### 交付

| 交付 | 证据 |
|---|---|
| 深模块接口 | `OnDemandOrchestrator` 对外只提供 `start / resume / cancel / get`；路由、前端和测试不依赖 LangGraph 节点或 Checkpointer 结构 |
| 三重启动门槛 | 计划必须满足 `complexity >= 7`，且至少两个 Agent 或明确暂停恢复；用户通过计划 Draft Review 后才能启动 |
| 首个试点 | 仅实现已确认 Research 报告到 Growth 任务草稿；最多 5 条草稿任务，不调用 Growth 正式应用路径 |
| 父子 Run | `agent_runs` 增加 `parent_run_id` 与 `plan_ref`；父编排 Run 和 Growth 子 Run 继续使用既有 Run/Step 账本 |
| 业务草稿 | 编排计划保存在 `orchestration_plan_drafts`，产物复用 `growth_plan_drafts`；Run、Step、Checkpoint 只保存引用 |
| 确认类型分离 | 新增独立 `draft_reviews` R1 状态机；Model Consent、Draft Review、Tool Approval 共享 Approval Center 展示壳但不互相授权 |
| 权限交集 | Research/Growth AgentSpec 都必须具备 `draft.text.prepare`，Tool Gateway 策略必须将内部草稿判定为 R1 自动允许 |
| 恢复与取消 | PostgreSQL Checkpointer 支持新服务实例从同一 `run_ref` 恢复；取消同步终止父子 Run |
| 前端试点 | 已确认研究报告可生成编排计划；Approval Center 明确展示并处理计划与成长任务草稿审阅 |
| 迁移 | `0035_v3_orchestrator_pilot`；本地开发库已升级到 `0035 (head)` |

### 验收记录

- 50 条简单请求评测：0 条提出编排，误触发 0/50；
- 20 条复杂试点：全部在 Growth 草稿审阅点暂停并恢复，产物各 1–5 条任务草稿；
- 权限与副作用：正式 `GrowthTask` 创建数为 0，Tool Approval 创建数为 0，Model Consent 创建数为 0，父 Run 均未继承 DeepSeek 授权；
- PostgreSQL 真库恢复：1 passed；使用新的 service/checkpointer 实例从同一 `run_ref` 恢复并完成；
- PostgreSQL 迁移演练：新临时库完整 upgrade 到 `0035`，实际执行 `0035 -> 0034 -> 0035` 后恢复测试通过，临时库已删除；
- 默认环境后端全量（排除既有静默时段墙钟用例）：387 passed / 37 skipped / 1 deselected；
- 统一后端测试阶段：387 passed / 37 skipped / 1 failed，唯一失败仍为 `test_scan_route_returns_summary` 在上海静默时段读取真实墙钟；
- 定向旧路径回归：Growth、Research、数据层、Tool Gateway、UI Event Feed 共 55 passed；
- Prompt/策略评测：25/25；Ruff、前端 typecheck、前端 lint、Impeccable 检测、备份演练 dry-run 均通过；
- 安全检查通过并保留既有 `.env` 本地读取权限警告；
- `alembic check` 未发现 0035 模型漂移，但仍报告既有 LangGraph/Mem0 外部表和 `research_reports` 唯一索引基线差异。

### 已知限制与后续边界

- `v3_orchestrator_enabled` 默认关闭；尚未进行长期运行的编排耗时、事件积压和资源 p95 采样；
- 首个试点使用已确认 Research 报告中的建议确定性生成 Growth 草稿，不调用云模型，也不支持其他 Agent 组合；
- Draft Review 通过只表示接受计划或草稿；不会创建正式 Goal/Milestone/GrowthTask，也不替代 R2 Tool Approval；
- PostgreSQL 环境验证覆盖一个跨连接恢复场景；20 条复杂场景矩阵在默认测试环境完成；
- 既有静默时段墙钟测试和 Alembic 外部表/历史索引基线不由 V3-2 引入；
- 下一阶段为 V3-3，但本阶段没有实现主动智能、扩大编排范围或增加外部副作用。

### 回滚记录

- 已在一次性 PostgreSQL 数据库实际执行 `0035 -> 0034 -> 0035`；downgrade 删除 Draft Review/计划表及父子/计划引用列，旧 Agent Run 账本保留；
- 关闭 `v3_orchestrator_enabled` 后，计划预览和运行入口不可用，普通聊天继续使用 Direct Runtime；
- 编排试点没有接管聊天执行路径，因此回滚不影响旧 Growth/Research 工作流。

## V3-3：会话级主动智能

- 完成日期：2026-08-10
- 状态：完成并验收；会话级能力默认关闭，旧 `/proactive` 与定时扫描继续保留
- 默认 Flag：`v3_conversational_proactive_enabled=false`
- 相关提交：本节所在实现提交

### 交付

| 交付 | 证据 |
|---|---|
| 主动智能深模块 | `ConversationalProactive` 以 `feed / decide / configure_category` 小接口封装过期、静默、排序、反馈和类别控制，路由与对话工作台不依赖内部查询结构 |
| 规则生成边界 | 继续复用既有任务、周复盘、情报、英语复习规则扫描；后台不导入或调用 Model Gateway，不扩大 Orchestrator 范围 |
| 反馈回流 | 复用 suggestion 的 `accepted / dismissed / expired` 状态和 `decision_reason`；按 `suggestion_type` 返回 `accept / (accept + dismiss)`，未新增通用 `feedback_signals` 表 |
| 个性化排序 | 领域模块内按优先级、分类型接受率和建议年龄进行确定性排序；反馈只是轻量权重，不成为跨领域万能偏好模型 |
| 去重与并发 | `user + source_type + source_id + suggestion_type` 的活动建议使用 PostgreSQL/SQLite 部分唯一索引；扫描器使用 savepoint 收敛并发冲突，dismiss 也遵守冷却期 |
| 静默与频控 | 对话 feed 与旧扫描器共同遵守静默时段；每日上限和每次扫描上限沿用原配置，不引入第二套频控 |
| 类别关闭 | `proactive_category_preferences` 保存四个既有来源类别的开关；关闭时使该类活动建议过期，后续扫描跳过，前端提供即时撤销 |
| 对话操作 | 对话工作台展示建议和理由，并提供接受、忽略、不再显示此类；接受只记录反馈，不创建正式 `GrowthTask` 或任何审批 |
| 可靠事件 | 创建、接受、忽略、过期和类别关闭导致的 suggestion 状态变化继续复用 V3-1.5 事务 outbox，不在事件正文复制建议内容 |
| 迁移 | `0036_conversational_proactive` 增加过期/决策字段、活动建议部分唯一索引和类别偏好表；本地开发库已升级到 `0036 (head)` |

### 验收记录

- 统一门禁：395 passed / 38 skipped；此前依赖上海真实墙钟的扫描路由用例已改为显式关闭静默配置，本轮无失败；
- V3-3 与 UI Event Feed 定向回归：23 passed，覆盖 Flag 默认关闭、规则 feed、零模型调用、静默时段、每日上限不变、类别关闭、过期、反馈统计、无正式任务副作用和可靠事件；
- PostgreSQL 并发去重：1 passed；两个独立会话并发写入同来源同类型建议时仅一个提交成功，活动记录数为 1；
- PostgreSQL 迁移演练：一次性数据库完整 upgrade 到 `0036`，实际执行 `0036 -> 0035 -> 0036` 后并发测试通过，临时数据库已删除；
- 本地迁移前检查：原库位于 `0035`，共有 7 条 suggestion、0 组活动重复；升级后为 `0036 (head)`；
- Ruff、Python compile、前端 typecheck、前端 lint、安全检查、Prompt/策略评测 25/25、备份演练 dry-run 全部通过；
- Impeccable 检测只报告 `globals.css` 中 4 条既有全局告警，本次 V3-3 新增区域没有命中；
- `alembic check` 未报告 0036 模型漂移，仍只报告既有 LangGraph/Mem0 外部表和 `research_reports` 唯一索引基线差异。

### 已知限制与后续边界

- Flag 保持默认关闭，尚无真实使用期的分类型接受率样本；当前接口只报告实际已决策数据，不伪造基线；
- 排序最多读取 100 条活动建议并返回 1–10 条；当前日上限远低于该界限，长期样本增长后再按实测决定是否分页；
- 本阶段完成类型、lint 与交互状态验证，但未新增浏览器视觉回归截图；V3-4b 再统一完成页面级浏览器验收；
- 类别只覆盖既有四种规则来源；新增领域必须先定义自身排序与关闭语义，不得直接扩张成通用反馈表；
- 后续可进入相互独立的 V3-4a 或 V3-4b；本阶段没有实现语音、删除旧页面或扩大 Orchestrator。

### 回滚记录

- 已在一次性 PostgreSQL 数据库实际执行 `0036 -> 0035 -> 0036`；downgrade 删除类别偏好、过期字段和活动建议唯一索引，既有 accepted/dismissed suggestion 与旧扫描器保留；
- 关闭 `v3_conversational_proactive_enabled` 后，会话 feed 与新决策/类别接口返回 404，对话工作台不展示会话建议；旧 `/proactive` 页面、接受/忽略接口和定时规则扫描继续工作；
- 迁移与 Flag 回滚互相独立：正常灰度只需关闭 Flag，不需要立即 downgrade。

## V3-4a：本地语音闭环

- 完成日期：2026-08-10
- 状态：实现与本地语音 Spike 完成；真实浏览器设备端到端性能采样环境门控
- 默认 Flag：`v3_voice_loop_enabled=false`
- 相关提交：本节所在实现提交

### 交付

| 交付 | 证据 |
|---|---|
| 本地语音深模块 | `VoiceLoop` 只公开状态、转写、合成和卸载能力；`LocalSherpaSpeechAdapter` 封装 PCM 校验、sherpa 配置、串行执行和模型生命周期 |
| 本地 STT | 小型中英双语 Zipformer int8；`scripts/install-voice.ps1` 从官方 `asr-models` release 安装并校验固定文件 |
| 本地双语 TTS | 复用既有中文/英文 VITS 模型，按原文顺序分段合成并在内存中生成 WAV |
| 状态机 | 对话页实现 `idle -> listening -> transcribing -> responding -> speaking`；任意活动态均可取消或打断回到 idle |
| 隐私边界 | 浏览器内存中转换 16kHz PCM；原始音频不上云、不落临时文件、业务库或事件正文；最长 60 秒 |
| 设备与策略降级 | 麦克风权限拒绝、设备缺失、录音/转写/播放失败、静默时段均保留文本聊天；不做常驻唤醒 |
| 生命周期 | STT/TTS 懒加载，默认空闲 300 秒后卸载；显式 unload 端点用于回滚与资源释放 |
| 前端接入 | 现有聊天麦克风改为本地语音；移除可能调用浏览器在线服务的 Web Speech Recognition 路径 |
| 配置与回滚 | `.env.example` 记录 Flag、模型路径和边界；关闭 Flag 后语音执行返回不可用，文本聊天保持原路径 |
| 基准 | `scripts/benchmark-voice-loop.py` 与 `docs/V3_VOICE_BENCHMARK.md` 固定设备、模型、语料、统计口径和目标 |

### 验收记录

- 固定语音 Spike（Windows 11、16 逻辑处理器、Python 3.13.3、CPU）：STT 30 次 p50 148.37 ms / p95 400.56 ms；TTS 15 次 p50 709.18 ms / p95 991.13 ms；进程峰值工作集 512.96 MB；
- 冷启动：STT 1014.50 ms；中英 TTS 双模型 1536.46 ms；
- 仓库统一门禁完成后新增两条语音路由边界测试并复采测试全集：403 passed / 38 skipped；V3-4a 定向测试 8 passed；安全检查、Prompt/策略评测 25/25、备份演练 dry-run、前端 typecheck 与 lint 全部通过；
- 前端 TypeScript typecheck 与 ESLint 通过；Impeccable 检测对已扫描的新增语音 UI 文件返回 0 条，目标参数中的工作台路径写错导致该单文件未扫描，已由 ESLint/typecheck 覆盖；
- sherpa 真实适配器烟测通过：官方 WAV 成功转写，中英 TTS 成功生成内存 WAV，显式 unload 后模型状态恢复未加载；
- Next.js 生产构建在沙箱外复验通过；首次沙箱内运行仅因既有 `.next/trace` 的 EPERM 被阻止，不是代码构建失败。

### 已知限制与后续边界

- LLM TTFT 与麦克风结束到首音需要已配置模型路由和真实浏览器音频设备，本轮未运行，明确不记为通过；冻结目标与补采口径见语音基准文档；
- 固定 STT 模型语料只用于延迟复现，没有可靠参考文本，不能据此声称真实麦克风识别准确率达标；
- 当前 TTS 在完整 WAV 生成后开始播放，尚未做流式音频；若真实设备体感 p95 超过 5 秒，优先评估句级流式播放，不扩大云端边界；
- V3-4a 不包含常驻唤醒词、云端语音、音频持久化或 V3-4b 页面收敛；
- V3-4b 第一批只做 `/chat` 与 `/approvals` 两个高保真原型，视觉方向经用户确认后才逐页推进。

### 回滚记录

- 默认 Flag 已验证为关闭；关闭时 `VoiceLoop` 在加载模型前拒绝转写，文本聊天接口和输入框不依赖语音模块；
- 删除/不安装 STT 模型时状态端点报告本地模型未就绪，麦克风按钮禁用但文字发送可用；
- `POST /voice/unload` 与 300 秒空闲定时器均释放 STT/TTS 引用；无需数据库 downgrade，本阶段没有 schema 迁移。

## V3-4b：对话驱动的混合双翼工作台

- 完成日期：2026-08-10
- 状态：生产前端、真实 API 联机与浏览器门禁完成；Flag 保持默认关闭，等待实际灰度观察
- 默认 Flag：`V3_PAGE_CONVERGENCE_ENABLED=false`
- 相关提交：本节所在实现提交

### 交付

| 交付 | 证据 |
|---|---|
| 原型决策 | `/chat?variant=A/B/C` 提供三套开发环境隔离原型；用户确认 A 平衡双翼为骨架、B 单侧聚焦、C 错位卡片栈的混合方向 |
| 真实聊天内核 | 中央工作区复用既有会话列表、流式回答、模型模式、语音、记忆候选、知识沉淀和消息转任务，不复制第二套聊天状态 |
| 双侧面板栈 | 新会话默认不预铺模块；左侧按任务出现 CareerRadar / Memory / Knowledge，右侧按任务出现 Growth / Orchestrator / Approval；每侧最多 3 个，支持置顶、前后台切换、关闭、恢复和最近使用 |
| 真实只读数据 | 六个面板分别调用现有领域 API；数据选择与解释请求可进入真实对话，Approval 不提供快捷批准或隐式授权 |
| 意图联动 | 对话提交前使用确定性高置信关键词把相关面板切到前台；同一对话中手动关闭的面板不会被自动重开 |
| 生命周期 | 面板顺序、置顶和最近使用保存在浏览器本地；同一对话的手动关闭抑制按会话保存在 sessionStorage 并跨刷新生效；未固定面板 30 分钟无活动关闭；每侧第 4 个面板替换最久未使用且未固定项 |
| 响应式 | 宽屏双侧展开，普通笔记本自动保留一侧与另一侧轨道；手机底部切换当前面板，空白时提供资料/行动入口，并以不可穿透焦点的侧滑卡片栈展示 |
| 灰度回滚 | `V3_PAGE_CONVERGENCE_ENABLED` 默认关闭；开发使用 `/chat?workspace=twin`；关闭 Flag 立即回到旧时间线布局，原结构化页面全部保留 |
| 设计记录 | `PRODUCT.md` 固化产品真相；`.impeccable/surfaces/apps-web-src-app-chat-page-tsx.md` 记录 `/chat` Surface Brief；根目录 `DESIGN.md` 与 `.impeccable/design.json` 从已交付实现提取全局视觉系统和可复用组件 |

### 验收记录

- 前端 TypeScript typecheck 与 ESLint 通过；Impeccable detector 对生产新增 UI 返回 0 条；
- Next.js 16.2.12 生产构建通过，`/chat` 以动态路由生成；临时构建目录已清理，生成器对 `next-env.d.ts` 与 `tsconfig.json` 的改动已还原；
- Playwright 在 1720×1000、1280×900、390×844 三种视口完成定稿走查；手机面板打开后位于 `x=7`、宽 358px，关闭态两个离屏面板均为 inert；
- 六个生产面板均通过真实 API 浏览器联机覆盖；CareerRadar 渲染 1 条真实演练岗位，Growth 渲染真实空目标/任务状态，Memory、Knowledge、Orchestrator、Approval 均完成接口与渲染；
- 浏览器交互验证通过：空白状态 0 个预加载卡片、同会话手动关闭跨刷新保留、手动恢复清除抑制、31 分钟未固定面板在加载时立即清理、手机焦点进入与归还、默认关闭 Flag 回退旧聊天；页面和非预期响应错误为 0；
- 既有可选 `/ui/dialog` 与 `/memory-network/candidates` 在对应后端 Flag 关闭时仍返回预期 404；它们不属于六个侧面板，本次没有把这些基线请求记为新实现错误；
- 开发入口 `/chat?workspace=twin` 返回 HTTP 200；最终截图位于忽略提交的 `artifacts/v3-4b-prototype/production-final-*.png`；
- 生产构建产物中已检索到 `jarvis-chat-twin-v3-4b` 设计契约；契约明确记录 A+B+C 用户决策来源，未虚构 concept seed。
- Impeccable finish reviewer 最终 disposition 为 `ship`，FINISH 原文、生产产物命中与回归均为 resolved/none，无剩余 material findings；documenter 子代理超时后按降级流程完成同格式 `DESIGN.md` 与 sidecar，并通过 JSON 结构和 canonical heading 校验。

### 已知限制与后续边界

- 低置信意图的“建议打开”仍等待 Router 提供稳定置信度，不用前端猜测替代；
- “话题彻底结束”尚无后端事件，当前只实现同对话手动关闭抑制和 30 分钟无活动关闭；
- 当前真库中 Career 有 1 条演练岗位，Growth 无活跃目标，Memory 为空；已保留真实完成态与空态证据，但更高数据密度仍需在灰度期继续观察；
- 当前不下线旧 `/chat` 时间线或任何领域页面，不接入新的写接口，不扩大 R1/R2/R3 权限边界。

### 回滚记录

- Flag 默认关闭，旧时间线仍是正式入口；开发查询参数只在非 production 环境生效；
- 双翼状态只保存在浏览器本地，不是业务事实源；清除 `jarvis:twin-workspace:v2` 与 `jarvis:twin-workspace:closed:*` 即可恢复默认状态；
- 原型、生产双翼和旧时间线三条路径相互隔离，关闭 Flag 不需要数据库迁移或后端回滚。

## 记录规则

后续每个阶段只在完成验收后追加一节，至少记录：

1. 完成日期与提交；
2. 默认 Flag 状态；
3. 交付物与代码证据；
4. 按环境区分的测试结果；
5. 浏览器或真库验证；
6. 未完成项和转入下一阶段的债务；
7. 实际回滚演练结果。
