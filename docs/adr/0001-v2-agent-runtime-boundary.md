# ADR-0001：Agent 与 Runtime 分离

- 状态：接受
- 日期：2026-08-02
- 适用版本：Jarvis OS v2.0

## 背景

现有 Jarvis 已经有可用的聊天、专业模块和 Model Gateway。直接用 LangGraph 包装全部请求会增加延迟、状态复杂度和迁移风险。

## 决策

Agent 通过版本化 `AgentSpec` 声明能力与权限，运行方式通过独立 Runtime 接口提供：

- Direct Runtime：普通对话、英语练习、单次读取和简单草稿；
- Workflow Runtime：多步骤研究、成长规划、需要暂停审批和恢复的任务。

Router 负责选择 Agent 和 Runtime，但不能扩大 AgentSpec 中的模型、记忆或工具权限。Sprint 23 只建立接口，现有请求仍走原链路。

## 结果

- 现有 API 不需要立即重写；
- 后续可以逐 Agent 影子运行和灰度迁移；
- LangGraph 故障不会影响普通聊天；
- Runtime 必须由 Feature Flag 显式开启才能解析和执行。

## 未采用方案

- 所有请求统一进入 LangGraph；
- 每个 Agent 自己实现路由、权限和模型调用；
- 在当前阶段引入新的常驻微服务。
