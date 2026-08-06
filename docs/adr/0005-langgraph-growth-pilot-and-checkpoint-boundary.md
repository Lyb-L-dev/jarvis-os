# ADR-0005：Growth Agent 以 LangGraph 可恢复工作流试点

- 状态：接受
- 日期：2026-08-02
- 适用版本：Jarvis OS v2.0

## 背景

成长规划不是一次普通对话。它需要补充现实约束、选择模型、等待付费模型授权、生成草稿，并在用户确认后才创建正式目标和任务。用单次 HTTP 请求或大型条件分支承载这些状态，会使重启恢复、重试幂等和审批边界难以验证。

## 决策

Growth Agent 作为首个 LangGraph Pilot，采用以下边界：

```text
创建规划请求
→ 检查信息
→ 缺失时暂停
→ 选择模型
→ DeepSeek 单次授权（如需要）
→ 生成可编辑草稿
→ 用户审核
→ 确认后创建正式目标、里程碑和任务
```

- 生产环境使用 PostgreSQL Checkpointer；
- 每个 Agent Run 使用独立 `thread_id`；
- Checkpoint 只保存 Run、Request、Draft 的引用和工作流状态，不复制用户正文或 Prompt；
- 用户填写的规划正文由 Jarvis 业务表保存，PostgreSQL 是事实源；
- `interrupt()` 之前的步骤采用幂等 Step Key；
- 正式计划写入以 `created_goal_id` 作为幂等边界；
- SQLite 内存 Checkpointer 只用于自动化测试和本地轻量开发；
- Growth 通过专用 API 启动，不替换 Direct Chat 链路。

## DeepSeek 边界

复杂 Growth 规划默认建议 DeepSeek，因为它负责多目标权衡、长期路线和任务依赖校验。但 DeepSeek 是付费钱包模型，因此：

- 未确认前不调用；
- 授权界面显示用途、执行步骤、发送的数据类别和替代方案；
- 用户可改用 MiMo Token Plan 或本地 Qwen；
- 授权只覆盖本次规划；
- 模型只能生成草稿，不能创建正式记录。

## 结果

- API 重启后可使用同一 `thread_id` 恢复；
- 用户可以暂停、补充资料并继续；
- 草稿拒绝不会产生正式目标或任务；
- 重试不会重复创建目标和任务；
- Direct Chat 不经过 LangGraph，因此原有延迟与行为不变；
- 后续 Research Workflow 可以复用 Run、Step、Approval 和 Checkpointer 基础设施。

## 参考

- [LangGraph Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
- [LangGraph Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)
- [LangGraph Checkpointer Integrations](https://docs.langchain.com/oss/python/integrations/checkpointers/index)
