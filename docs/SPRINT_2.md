# Sprint 2：Chat、模型路由与会话记录

## Sprint 目标

得到一个可以长期使用的文字对话闭环：用户在 Dashboard 中发送消息，Jarvis 按策略选择模型，保存完整会话，并让用户看见实际模型、降级原因、耗时和错误状态。

## 已完成

- [x] `chat_conversations` 会话表；
- [x] `chat_messages` 消息表；
- [x] `model_call_logs` 模型调用日志表；
- [x] PostgreSQL `20260728_0002` 迁移；
- [x] PostgreSQL `20260728_0003` 长对话摘要迁移；
- [x] 会话创建、列表和详情 API；
- [x] 消息发送与最近 24 条上下文组装；
- [x] 个人档案注入系统提示；
- [x] `standard / deep / local / auto` 模式；
- [x] MiMo 未配置时明确降级 Ollama；
- [x] DeepSeek 未配置时明确降级 Ollama；
- [x] 敏感内容强制使用 Ollama；
- [x] 禁止将 MiMo `tp-` Token Plan Key 配入 Jarvis Runtime；
- [x] 调用成功、失败、耗时和 Token 记录；
- [x] 真实 Chat 页面；
- [x] 会话列表与刷新恢复；
- [x] 会话归档；
- [x] 模型模式与隐私模式选择；
- [x] 每条回答显示实际 Provider 与降级原因；
- [x] 设置页模型调用审计面板；
- [x] 发送中、错误和空会话状态；
- [x] Dashboard 侧栏正确显示当前模块；
- [x] 模型路由与聊天持久化自动测试。
- [x] Ollama 模型存在性健康检查；
- [x] Windows 一键生产启动与停止；
- [x] SSE 流式回答与逐段渲染；
- [x] 显式停止生成，并自动保存已生成内容；
- [x] 重新回答（替换当前可见回答，不重复用户消息）；
- [x] 停止、错误、完成状态统一写入模型调用审计；
- [x] 会话标题手动重命名；
- [x] 按标题与消息内容搜索历史；
- [x] 长对话由本地 Qwen 自动生成压缩摘要；
- [x] 摘要上下文与最近 12 条原始消息组合；
- [x] Token Plan 密钥被安全忽略并显示配置问题，不阻塞启动；

## 本轮本地模型修正

原有 `qwen3:4b` 在当前 Ollama 标签中实际对应 Thinking 版本。短回答也可能消耗大量推理 Token，导致达到输出上限时仍没有最终答案。

Jarvis 的日常本地模型改为：

```text
qwen3:4b-instruct-2507-q4_K_M
```

该模型约 2.5GB，为非 Thinking 的指令版本，更适合 独立显卡 4GB 上的日常对话。

## 待完成

- [x] 完成 Instruct 模型下载和真实回答验收；
- [x] Chat 流式输出；
- [x] 停止生成；
- [x] 消息重新生成；
- [x] 会话手动重命名；
- [x] 对话历史搜索；
- [ ] 云端 MiMo `sk-` Key 连通测试；
- [x] DeepSeek Key 连通测试；
- [x] DeepSeek 付费调用前的确认交互；
- [x] 长会话自动摘要；
- [x] 从对话提取候选长期记忆。

## 完成定义

- 页面刷新后会话和消息仍存在；
- 默认模式优先请求 MiMo，未配置时清楚显示本地降级；
- 深度模式不会在未提示的情况下产生 DeepSeek 费用；
- 隐私模式不会调用云端 Provider；
- 每次调用都有可审计日志；
- 本地模型可以在当前电脑上稳定给出最终答案；
- 自动化检查与生产构建通过。

## 本轮验收

- 后端自动测试：18 项通过；
- 前端 TypeScript 与 ESLint：通过；
- Next.js 生产构建：通过；
- 真实 Ollama SSE：收到 `meta / delta / done`；
- 浏览器停止生成：页面显示“已停止生成”，数据库保存 `cancelled` 状态；
- 浏览器重新回答：触发独立流式请求，旧回答被新回答替换；
- DeepSeek 内部路由：`deepseek-v4-pro` 流式回答成功且无降级；
- 长对话摘要：本地 Ollama 生成、写入摘要状态并进入调用审计；
- 浏览器重命名、消息内容搜索、无结果状态与摘要标识：通过；
- DeepSeek 付费确认：取消后不保存消息、不发起模型请求；
- 候选记忆自动提取并进入 Sprint 3 记忆中心；
- 验收截图：
  - `artifacts/chat-stream-stop-verified.png`
  - `artifacts/chat-stream-retry-verified.png`
  - `artifacts/chat-search-rename-summary-verified.png`
