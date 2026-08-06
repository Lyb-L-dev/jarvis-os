# JARVIS OS Frontend Redesign — Phase 3

## 状态

已完成 Conversation AI Workspace 与 Agent Selector 重构。

本阶段只调整对话工作区结构、状态反馈和交互外观。原有流式通信、模型路由、
自动保存、知识检索、长期记忆与任务转换接口保持不变。

## AI Workspace

Conversation 已不再采用“永久左侧历史记录 + 普通聊天气泡”的结构：

1. 对话记录改为按需打开的浮动抽屉。
2. 主区域用于展示用户输入、Jarvis 工作结果和执行上下文。
3. Jarvis 回答不再表现为普通聊天气泡，而是完整工作结果。
4. 每条回答显示实际模型、响应耗时、知识引用和安全执行状态。
5. 记忆更新、创建行动、重新回答仍可从结果下方直接操作。
6. 输入区域以浮动任务输入台呈现，包含模型、隐私和知识边界。

## Agent Selector

`src/components/agents/AgentSelector.tsx` 使用 Motion 共享布局动画，
连接四个真实工作区：

| Agent | 真实工作区 | 作用 |
| --- | --- | --- |
| General Jarvis | `/chat` | 综合理解与任务协作 |
| Growth Manager | `/growth` | 目标、计划和行动管理 |
| English Coach | `/english` | 英语对话、纠错和复习 |
| Research Agent | `/intelligence` | 情报与研究 |

Agent Selector 不会向用户展示虚假的“已切换 Agent”状态；点击后进入对应的真实
专项模块。1366px 宽度下自动只保留图标，避免压缩工作内容。

## AI 状态联动

Phase 2 的 Jarvis Orb 状态已接入对话过程：

| 状态 | 触发条件 |
| --- | --- |
| idle | 对话待命 |
| listening | 浏览器语音转写正在运行 |
| thinking | 请求已经发送，等待首段回答 |
| speaking | 流式回答正在输出 |
| error | 对话、语音或后端操作发生错误 |

空对话页面直接使用完整 Jarvis Orb；已有对话时由右侧 Jarvis Presence 显示实时
状态，避免重复占用内容区域。

## 语音输入

桌面对话新增浏览器语音转写入口：

- 首次使用前明确提示浏览器或系统可能调用在线语音服务。
- 明确禁止口述密码、API Key 或其他敏感信息。
- 用户必须主动确认后才会申请麦克风权限。
- 不支持 Speech Recognition 的浏览器会保留键盘输入并给出明确提示。
- 语音只填写输入框，不会绕过用户直接发送。

## 可审计而不暴露私人推理

设计文档中的 Reasoning 区域被实现为“执行上下文”，显示：

- 实际模型路由；
- 本地知识引用数量；
- 响应耗时；
- 是否执行高风险操作。

界面不会展示模型的私人思维链，也不会伪造后端没有提供的推理过程。

## 保留的真实能力

- SSE 流式回答；
- 随时停止生成并自动保存已有内容；
- MiMo 主力、本地 Qwen、DeepSeek 付费确认和自动路由；
- 隐私模式强制本地处理；
- Obsidian 知识增强与可打开引用；
- 对话搜索、新建、重命名和归档；
- 自动长对话摘要；
- 回答重新生成；
- 消息保存为长期记忆；
- 消息转换为成长任务；
- 对话沉淀为待确认知识草稿。

## 验收

- 1600×1000 已有对话视觉检查通过。
- 1366×768 紧凑桌面布局检查通过。
- 会话抽屉打开、搜索区和选中状态检查通过。
- 真实历史消息、Local Qwen 路由、响应耗时和边界状态正常显示。
- TypeScript、ESLint 与 Next.js 生产构建通过。
- `/tablet` 保持独立实现，本阶段未改动。

## 下一阶段

Phase 4 将分别重构：

- English Coach：学习进度、对话训练与 Mistake Memory。
- Information Intelligence：事件、影响、个人关系和行动建议。
- Growth Manager：目标树、Roadmap、今日行动与周复盘。

三个页面会复用 Agent Selector，并继续使用现有真实后端数据。
