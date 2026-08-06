# Sprint 25：LangGraph Growth Pilot

## 状态

已完成，2026-08-02。

## 目标

把 Growth Agent 从一次性生成升级为可暂停、可补充、可恢复且有明确用户控制权的成长规划工作流，同时不改变 Direct Chat，也不提前开放 Research、n8n 或外部写入。

## 本次完成

### 可恢复工作流

Growth Planning Workflow 已包含：

1. 理解目标；
2. 检查每周投入时间等必要条件；
3. 信息不足时暂停，补充后从 Checkpoint 恢复；
4. 自动判断模型路线；
5. 需要 DeepSeek 时进入单次付费授权节点；
6. 生成结构化计划草稿；
7. 暂停并等待用户编辑、确认或放弃；
8. 确认后才创建正式目标、里程碑和任务。

### PostgreSQL Checkpointer

- 生产环境使用 LangGraph 官方 PostgreSQL Checkpointer；
- Checkpointer 在首次显式启动 Growth Workflow 时初始化官方内部表；
- 每个 Agent Run 使用独立 `thread_id`；
- Checkpoint State 只保存引用和状态，不保存目标正文、约束、Prompt 或模型回复；
- 规划请求和草稿正文仍由 Jarvis 自己的 PostgreSQL 业务表管理；
- SQLite 自动化测试使用内存 Checkpointer，不伪装成生产恢复能力。
- Windows 后端通过 `python -m app` 启动，并在 Uvicorn 创建事件循环前切换为 Selector Event Loop，以满足 Psycopg Async 的平台要求。

### Agent Run、Step 与 Approval

新增统一持久化结构：

- `agent_runs`：工作流状态、Runtime、模型选择、Token 摘要和错误码；
- `agent_run_steps`：步骤序号、状态和幂等键；
- `agent_approvals`：DeepSeek 单次授权的用途、步骤、数据类别与结果；
- `growth_planning_requests`：用户填写的目标和现实约束；
- `growth_plan_drafts`：可编辑草稿及正式记录引用。

Run/Step/Approval 不复制用户正文，避免为了可观测性扩大私人数据副本。

### DeepSeek 的作用和授权

Growth Agent 的复杂规划建议 DeepSeek，是因为它更适合：

- 同时权衡目标、时间和薄弱项；
- 设计长期阶段依赖；
- 检查任务密度与路线连贯性。

它不是普通对话默认模型，也不是自动执行器。界面会在调用前说明：

- 本次用途；
- 覆盖的生成和校验步骤；
- 将发送“本次规划目标与约束、个人成长资料、当前活跃目标”；
- 不会发送聊天历史；
- 不会修改文件、日历或账号；
- 不会直接创建正式目标和任务；
- 本次调用会消耗 DeepSeek 钱包余额。

用户可以授权本次 DeepSeek，也可以改用 MiMo Token Plan 或本地 Qwen。未授权时 DeepSeek 不会被调用。

### Growth Center 前端

成长中心新增 AI 成长规划器：

- 五阶段进度轨迹；
- 目标、时间、日期、约束录入；
- Jarvis / DeepSeek / MiMo / 本地 Qwen 路线选择；
- 云模型资料授权开关；
- 缺失信息补充界面；
- DeepSeek 透明授权界面；
- 里程碑和任务草稿完整编辑；
- 保存草稿、放弃草稿；
- 二次确认后创建正式计划；
- 完成后自动刷新 Growth Center 的目标和任务。

### Feature Flags

代码安全默认值保持关闭：

```text
V2_WORKFLOW_RUNTIME_ENABLED=false
V2_GROWTH_WORKFLOW_ENABLED=false
```

当前个人 Jarvis 环境已显式设置为 `true`。这保证自动化测试和新部署默认不获得执行能力，而本机 Sprint 25 可以正常使用。

## 安全与幂等结论

- 读取上下文和生成草稿可自动进行；
- DeepSeek 付费调用必须单次确认；
- 正式 Growth 目标和任务必须审核确认；
- 放弃草稿不会创建任何正式记录；
- `created_goal_id` 防止恢复或重试时重复写入；
- Step 使用唯一幂等键，适应 LangGraph 节点恢复时从节点开头重放；
- 工作流没有文件、日历、邮件、外部账号、投资交易、支付、删除数据或凭据执行入口。

## 数据库迁移

迁移版本：

```text
20260802_0019 -> 20260802_0020
```

启动脚本仍会在启动 Jarvis 时执行 `alembic upgrade head`。正式迁移前应先创建并校验 PostgreSQL 备份。

## 验收

- Sprint 25 专项后端测试：7 项通过；
- 完整后端回归：128 项通过；
- 隔离 PostgreSQL Checkpointer 验收：暂停后断开连接，以全新连接恢复并完成，1 项通过；
- Python Ruff：通过；
- 前端 TypeScript：通过；
- 前端 ESLint：通过；
- Next.js 正式生产构建：17 个页面通过；
- Alembic 单一 Head：`20260802_0020`；
- Direct Chat 路由未接入该工作流。

### 本机部署验收

- 迁移前备份：`jarvis-20260802T024905Z-72b26c36.dump`；
- SHA-256 与 Manifest 一致；
- 已真实恢复到临时数据库并验证 45 张表；
- 备份中的原版本：`20260802_0019`；
- 当前生产数据库版本：`20260802_0020`；
- Sprint 25 五张业务表全部存在；
- Jarvis Ready 检查：PostgreSQL、MiMo、DeepSeek、Ollama 均就绪；
- Growth Workflow API：HTTP 200；
- Growth Center：HTTP 200；
- `scripts/verify_growth_workflow_ui.cjs`：规划表单和目标输入可见，浏览器错误 0，失败请求 0；
- 视觉验收截图：`artifacts/growth-workflow-sprint25.png`。
- Windows Selector 启动入口已在最终重启后生效，Ready 与 Growth API 再次通过。

## 本阶段明确不实现

以下能力只保留在 v2.0 核心稳定后的架构路线，不在 Sprint 25 提前实现：

- Personality Layer；
- Context Engineering Layer；
- Proactive Engine；
- Agent Observatory；
- Cost Center。

## 架构决策

- [ADR-0005：Growth Agent 以 LangGraph 可恢复工作流试点](adr/0005-langgraph-growth-pilot-and-checkpoint-boundary.md)

## 下一阶段

Sprint 26：Research Agent Workflow。

复用 Sprint 25 的 Run、Step、Approval 与 Checkpoint 基础设施，增加研究计划、多来源采集与引用、事实/观点/推断分离。Research 的 DeepSeek 综合分析仍必须遵守任务级付费授权。
