# Sprint 32：v2 核心稳定与 Agent Observatory

## 状态

已完成。Agent Observatory 提供了统一的 Agent、LangGraph 工作流、工具、审批与错误观测能力；同时修复了两个只有在真实 Windows + PostgreSQL 环境才会暴露的核心稳定性问题。

## 目标

为长期运行建立故障诊断能力：

- 展示 Agent、LangGraph、工具、审批和错误状态；
- 查看任务运行到哪一步、为什么暂停或失败；
- 不展示隐藏推理和私人正文；
- 保持只读观测，不新增任何写入口。

## 已交付

### 观测 API（`/api/v1/observatory`）

- `GET /observatory/overview`：运行/步骤/工具/审批统计、72 小时错误数、按 Agent 聚合的活跃与失败数、v2 功能开关状态；
- `GET /observatory/runs`：Agent 运行列表，支持按状态与 Agent 过滤；
- `GET /observatory/runs/{id}`：运行详情，包括步骤时间线（顺序、类型、状态、耗时、错误码、引用）、运行级审批和关联工具调用；
- `GET /observatory/tool-executions`：工具执行记录（元数据级）；
- `GET /observatory/approvals`：工具审批与模型审批统一列表；
- `GET /observatory/errors`：失败运行与失败工具调用的统一错误列表。

### Agent Observatory 页面

- 侧边栏新增 SYSTEMS 分组入口，地址 `/observatory`；
- 顶部指标卡：运行中、暂停、失败、待审批、已完成；
- 隐私横幅明示“观测 ≠ 窥探”，并展示当前隐私边界说明；
- Agent 运行区：状态/Agent 过滤、运行列表、详情面板（步骤时间线、审批、关联工具）；
- 工具调用区：风险等级、状态、审批状态、错误码；
- 审批记录区：工具与模型审批合并展示；
- 错误区：来源、Agent、工具、错误码与安全截断信息；
- 15 秒自动刷新 + 手动刷新；
- 视觉验收截图：`artifacts/observatory-sprint32.png`。

### 隐私边界

- 不展示隐藏推理、对话正文、笔记内容；
- 不序列化 `pending_payload`、工具 `input_parameters`、`output_summary`、`side_effect_proof`；
- 错误信息截断到 200 字符；
- 观测层只读复用现有 `agent_runs`、`agent_run_steps`、`agent_approvals`、`tool_executions`、`tool_approvals`，无新增表、无写入口。

### 核心稳定性修复

1. **Windows 事件循环修复**：新版本 uvicorn 在 Windows 上强制使用 ProactorEventLoop，而 psycopg 异步驱动只兼容 SelectorEventLoop，导致 LangGraph 的 PostgreSQL 检查点在真实环境一直无法运行（此前测试使用内存检查点，未暴露）。修复：`app.main` 提供 `selector_loop_factory`，`app/__main__.py` 在 Windows 上通过 `uvicorn.run(loop="app.main:selector_loop_factory")` 显式使用 Selector 循环。
2. **工作流路由惰性加载修复**：工作流服务提交后，路由构造响应时访问已过期的 ORM 属性会触发异步禁止的惰性加载（`MissingGreenlet`）。修复：`growth.py` 与 `research.py` 的 `workflow_response` 在读取前显式 `await db.refresh(run)`。
3. **失败步骤标记**：Growth 与 Research 工作流失败时，把当前步骤标记为 `failed` 并写入错误码，观测台因此能显示“在哪一步失败”。
4. **API 日志落盘**：`scripts/start.ps1` 为 Jarvis Core 增加 stdout/stderr 重定向到 `.runtime/api.log` 与 `.runtime/api-error.log`，长期运行时可排查问题。

## 当前验收

- API 回归：170 项通过、1 项按环境跳过（含新增 6 项观测测试 + 1 项事件循环回归测试）；
- 桌面伴侣：6 项通过；
- Browser Worker Node 安全测试：5 项通过；
- Prompt/策略评测：16/16 通过；
- Python Ruff、TypeScript、ESLint：通过；
- Next.js 生产构建：20 个页面通过（新增 `/observatory`）；
- 浏览器视觉验收：控制台错误 0，截图归档 `artifacts/observatory-sprint32.png`；
- 真实工作流验收：通过 HTTP 启动成长规划工作流，正确暂停于“等待补充信息”→补充后暂停于“等待 DeepSeek 确认”，观测台正确展示 3 步时间线、暂停原因与待审批记录；
- 隐私验收：运行详情响应不包含 `pending_payload` 等私人字段。

## 设计说明

- 观测视图全部由现有权威表派生，不做第二份状态副本，避免漂移；
- “暂停原因”由 `pending_kind` 映射为用户可读标签，不展示原始 pending 载荷；
- LangGraph 检查点内部数据（可能包含推理内容）不直接暴露，观测以 `agent_run_steps` 的确定性记录为准；
- 步骤引用只展示 `kind + ref_id`，不展开正文。

## 后续

[Sprint 33 Cost Center](SPRINT_33.md)：模型 Token 与调用次数、DeepSeek 确认费用、本地模型资源指标。
