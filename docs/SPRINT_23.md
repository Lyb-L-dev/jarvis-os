# Sprint 23：v2 架构基础与 Agent Contracts

## 状态

已完成，2026-08-02。

## 目标

建立 Jarvis OS v2 的架构骨架，同时保持现有页面、API、模型路由和业务结果不变。

## 本次完成

### 1. Agent Contract

新增 `app/services/agent_core`：

- `AgentSpec`：Agent 身份、职责、意图、Runtime、模型能力、记忆空间、工具白名单、步骤上限、费用和失败策略；
- `AgentRun`：一次任务的最小化运行信封；
- `AgentRunStep`：可恢复步骤的状态与引用；
- `ApprovalRequest`：DeepSeek 和 R2 动作的一次运行审批范围；
- `DataReference`：引用权威数据，不复制私人正文。

初始 Agent 规格包括：

- Jarvis Core；
- English Coach；
- Research；
- Growth；
- Local Document；
- Investment Intelligence。

### 2. 权限边界

新增确定性的四级风险策略：

- R0 读取：自动；
- R1 Jarvis 内部草稿：自动；
- R2 文件、日历、邮件和外部账号修改：确认；
- R3 交易、支付、删除和凭据：禁止 Agent 执行。

代码契约禁止为 R3 动作创建 Approval Request，避免把“绝不自动执行”错误实现成“确认后可以执行”。

### 3. DeepSeek 策略

Research 和 Growth 具备 `deep_reasoning` 能力，并声明：

```text
explain_and_confirm_per_run
```

这表示 DeepSeek 是复杂任务的首选模型，但调用前必须说明作用、步骤、数据类别和替代方案。授权仅覆盖一次明确运行。

### 4. Runtime 抽象

新增 Direct / Workflow Runtime 接口与 Runtime Registry。Runtime 在功能开关关闭时无法解析，因此 Sprint 23 的新代码不会接管现有请求。

### 5. Feature Flags

新增且默认关闭：

```text
V2_AGENT_CORE_ENABLED
V2_SHADOW_RUNS_ENABLED
V2_POLICY_ENFORCEMENT_ENABLED
V2_WORKFLOW_RUNTIME_ENABLED
V2_APPROVAL_CENTER_ENABLED
```

### 6. 架构决策

- [ADR-0001：Agent 与 Runtime 分离](adr/0001-v2-agent-runtime-boundary.md)
- [ADR-0002：自动化风险与不可委托权限](adr/0002-v2-automation-risk-policy.md)
- [ADR-0003：DeepSeek 逐任务确认与最小化运行记录](adr/0003-v2-model-consent-and-minimal-ledger.md)

## 验收结果

- 新增 Sprint 23 测试：32 项通过；
- 完整后端回归：97 项通过；
- Ruff 静态检查：通过；
- v2 功能默认全部关闭；
- 原 Model Gateway 未修改；
- 原 API 路由未修改；
- 没有数据库迁移；
- 没有接入 LangGraph、n8n、Browser Agent 或外部账号；
- 运行契约不包含正文、Prompt 或凭据字段。

## 下一阶段

Sprint 24：Router v2 与 Agent Registry。

重点是让新 Router 以影子模式观察现有请求，输出 Agent、Runtime、隐私、风险和模型建议，但暂不改变用户实际得到的回答。
