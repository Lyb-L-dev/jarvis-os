# Sprint 24：Router v2 与 Agent Registry

## 状态

已完成，2026-08-02。

## 目标

在不改变现有回答路线的前提下，让 Jarvis 能解释一次请求适合由哪个 Agent、哪种 Runtime 和哪类模型处理，并由独立 Policy 层约束风险。

## 本次完成

### Agent Registry

- 注册版本化 AgentSpec；
- 每个 Agent 只有一个明确活动版本；
- 支持后续并存、切换和回滚版本；
- 拒绝重复版本和未知 Agent 版本。

### Intent Router

当前使用本地确定性规则进行第一阶段分类，不调用 LLM。输出：

- 意图；
- Agent；
- 复杂度；
- 隐私级别；
- 请求动作；
- 模型能力；
- 置信度；
- 简短路线原因。

### Policy Router

Policy Router 独立于 Intent Router，继续执行 Sprint 23 的边界：

- R0/R1 可自动；
- R2 必须确认；
- R3 禁止 Agent 执行。

用户文字和模型输出不能修改这套权限分类。

### Runtime Selector

- Jarvis Core、English、Local Document 等普通任务建议 Direct Runtime；
- Research、Growth 多步骤任务建议 Workflow Runtime；
- 本阶段只返回建议，不启动 LangGraph。

### Model Policy

- 普通请求建议 MiMo；
- 私人请求强制建议本地 Qwen；
- 复杂 Research/Growth 建议 DeepSeek；
- 未确认时 DeepSeek 只作为建议，selected provider 保持 MiMo；
- 用户明确选择 Standard 时继续使用 MiMo；
- 用户选择 Local 时使用本地 Qwen；
- DeepSeek 建议包含作用、覆盖步骤、数据类别和替代方案。
- 对话在发送 Deep 模式请求前，先调用本地 Preview API 展示上述说明；Preview 不保存正文，也不调用任何模型。

### Conversation 路由说明

对话响应新增 `agent_routing`，前端显示：

- 当前建议 Agent；
- Direct / Workflow；
- 路线原因；
- 推荐模型。

助手消息只保存结构化路由元数据，不复制用户正文。关闭影子开关后，该字段返回 `null`。

### Feature Flag

```text
V2_ROUTER_SHADOW_ENABLED=true
```

影子路由默认开启，因为它完全在本地运行且不改变实际调用；可随时设置为 `false` 恢复 Sprint 23 行为。

## 安全结论

- Router v2 不调用 MiMo、DeepSeek 或 Qwen；
- Router v2 不调用 Runtime、工具和外部服务；
- 未确认不会因路由建议产生 DeepSeek 费用；
- R3 请求只能被标记为禁止，不能生成 Approval；
- 当前 Model Gateway 仍是唯一真实模型路由。

## 架构决策

- [ADR-0004：Router v2 先以影子模式接入](adr/0004-v2-shadow-router-and-agent-registry.md)

## 验收

- Sprint 24 新增测试：24 项；
- 完整后端回归：121 项通过；
- 前端 ESLint：通过；
- 前端生产构建与 TypeScript：通过；

## 下一阶段

Sprint 25：LangGraph Growth Pilot。

在开始前，应先用实际对话样本检查 Router v2 的分类准确率。Sprint 25 只让 Growth 工作流获得受控运行能力，不直接开放 Research、n8n 或外部写入。
