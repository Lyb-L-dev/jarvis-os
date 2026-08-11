---
version: 1
slug: "apps-web-src-app-chat-page-tsx"
primary_target: "apps/web/src/app/chat/page.tsx"
related_targets: ["apps/web/src/components/chat/twin-chat-workspace.tsx","apps/web/src/components/chat/twin-workspace-panels.tsx","apps/web/src/components/chat/twin-workspace.module.css"]
---

## Scope and mode

- Surface: `/chat` conversation workspace
- Mode: Operate

## Audience and job

Jarvis OS 的系统所有者需要在一段持续对话中引用真实资料、选择上下文、查看行动结果，并在不丢失当前话题的情况下切换功能。

## Primary task and evidence

中央对话是稳定控制中枢。左侧面板读取 CareerRadar、Memory 与 Knowledge 证据；右侧面板读取 Growth、Orchestrator 与 Approval 状态。有意义的面板动作作为明确提示进入真实对话，筛选与排序留在面板内部。

## Constraints

- 每侧最多三个面板；固定、最近使用、30 分钟无活动关闭；
- 同一对话中手动关闭的面板不得被关键词重新打开；
- 审批面板只解释和导航，不提供快捷批准；
- `V3_PAGE_CONVERGENCE_ENABLED` 关闭时保留旧时间线布局；
- 桌面双侧展开，普通笔记本单侧聚焦，手机底部后台切换。

## Chosen direction

以“平衡双翼”为结构骨架，融合“专注轨道”的单侧聚焦和“空间舞台”的错位卡片栈。视觉继承 Jarvis 现有深色本地终端世界，以细边界、克制状态色和真实数据列表表达可靠性。

## Memorable moment

用户在对话中提到“长期记忆”和“成长计划”时，对应面板在左右两侧切到前台；手机上同一组面板变成底部应用切换器。

## Unresolved decisions

- 话题结束信号将在后续结合对话事件契约替代纯超时判断；
- 意图置信度低时的“建议打开”交互仍需后端路由置信度支持。
