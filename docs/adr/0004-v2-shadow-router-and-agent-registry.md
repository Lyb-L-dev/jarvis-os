# ADR-0004：Router v2 先以影子模式接入

- 状态：接受
- 日期：2026-08-02
- 适用版本：Jarvis OS v2.0

## 背景

Jarvis 已有稳定的 Model Gateway 和业务 API。Router v2 同时引入 Agent、Runtime、隐私、风险和模型能力判断，如果直接替换现有链路，分类错误会立即改变用户得到的回答。

## 决策

Router v2 第一阶段采用本地、确定性的影子模式：

```text
用户请求
├─ 原 Model Gateway → 真实回答
└─ Router v2 → Agent/Runtime/Policy/Model 建议 → 界面解释
```

影子 Router：

- 不调用任何模型；
- 不调用工具或 Runtime；
- 不改变现有 Provider 决策；
- 不保存用户正文副本；
- 只把最小化分类结果附加到响应和助手消息元数据；
- 可通过 `V2_ROUTER_SHADOW_ENABLED=false` 完全关闭。

Agent Registry 保存版本化 AgentSpec，并显式选择每个 Agent 的活动版本。Router 只能选择 Registry 中存在的 Agent，不能临时创造具备额外权限的 Agent。

## DeepSeek 行为

复杂 Research/Growth 可以得到“建议 DeepSeek”的结果，但未确认时影子策略的 selected provider 保持 MiMo。只有用户选择 Deep 模式或后续 Agent Run 中明确确认，现有 Model Gateway 才允许 DeepSeek 请求继续。

## 结果

- 可以采集分类准确率，而不承担切换风险；
- 用户能看到 Agent 和路线原因；
- 后续 Sprint 可比较影子建议与真实路线；
- Router v2 达到评测门槛后才能逐步获得执行权。
