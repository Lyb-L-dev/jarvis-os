# ADR-0013：V3 按需 Orchestrator 与确认类型分离

## 状态

已接受，2026-08-09。

## 背景

Jarvis 已有 Agent Registry、Direct / Workflow Runtime、Growth / Research LangGraph、Agent Run/Step/Approval 账本和 PostgreSQL Checkpointer。V3 需要跨 Agent 分解与交接，但重新建立一套编排账本，或让所有聊天进入 LangGraph，会重复状态、增加延迟并扩大故障面。

现有 Approval Center 同时展示模型授权和工具审批。V3 若把计划审阅也统一称为 R2，会混淆产品审阅、云模型授权和外部副作用审批。

## 决策

1. Direct Runtime 继续是普通聊天和单 Agent 简单任务的默认路径；
2. Orchestrator 只有在 `complexity >= 7`，且需要至少两个 Agent 或明确需要暂停恢复时才可提出编排；
3. 用户必须先确认编排计划预览，Orchestrator 才能启动；
4. V3-2 首个生产试点限定为“Research 结果 → Growth 任务草稿”；
5. Orchestrator 对外只提供：

```text
start(goal_ref, context_refs) -> run_ref
resume(run_ref, decision_ref) -> RunStatus
cancel(run_ref) -> RunStatus
get(run_ref) -> RunView
```

6. 路由、前端和测试不得依赖内部节点名称、分派循环或 Checkpointer 结构；
7. 复用现有 Agent Run、Step、Approval 和 PG Checkpointer；默认只增加父子 Run 与 `plan_ref`，不新建重复账本；
8. 编排计划和草稿正文保存在业务草稿区，Run/Step/Checkpoint 只保存引用；
9. 子任务最多 5 个，每步权限为 AgentSpec 与 Tool Gateway 策略交集；
10. 跨 Agent 交接不得继承未披露的 DeepSeek 授权或扩大数据类别；
11. 三种确认必须分离：
    - Model Consent：云模型与付费授权；
    - Draft Review：R1 计划/草稿审阅；
    - Tool Approval：R2 外部副作用审批；
12. 三种确认可以共用 Approval Center 的展示壳，但类型、状态和审计字段互不替代；
13. R3 继续没有执行入口，任何编排都不能降低风险等级。

## 结果

- 普通聊天不承担 LangGraph 延迟与故障；
- 编排复杂度集中在一个深模块中，调用者只学习一个小接口；
- 不会出现 Agent Run、Orchestrator Run、LangGraph Checkpoint 三套状态互相漂移；
- 草稿审阅不会被误认为安全授权，减少不必要审批；
- V3-2 必须等待 RouterV2 真实切流和评测完成。

## 未采用方案

- 所有请求统一进入 Orchestrator；
- 每个 Agent 自行决定跨 Agent 分派；
- 为 V3 重新创建完整的 orchestration run/step 账本；
- 把“用户看过草稿”视为 R2 工具执行授权。
