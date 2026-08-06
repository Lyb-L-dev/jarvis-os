# Sprint 11：MiMo Token Plan 正式主路由

日期：2026-07-29

## 所有者决定

所有者在知晓小米当前 Token Plan 套餐规则以及服务暂停、密钥封禁风险后，
明确要求把 Token Plan 接入 Jarvis 正式主路由。

## 已完成

- 使用订阅专用 `token-plan-*` Base URL；
- 使用 `api-key` 鉴权，不与按量 API 的 Bearer 鉴权混用；
- Token Plan 使用 `max_completion_tokens`；
- 增加 `MIMO_TOKEN_PLAN_ENABLED` 显式开关；
- 只有专用密钥、专用地址和显式开关同时成立时才启用；
- 请求失败自动降级到 Ollama，不自动调用 DeepSeek；
- 模型状态保留 Token Plan 风险提示；
- 正式对话完成 MiMo 调用、自动保存和模型审计。

## 验证结果

- Jarvis 模型网关真实请求：成功；
- 正式对话路由：`mimo → mimo-v2.5-pro`；
- 降级原因：无；
- 助手消息：已自动保存；
- 模型审计：成功记录 Provider、模型、耗时与 Token；
- 自动测试：52/52；
- Prompt 与策略评测：13/13；
- 网页类型检查、Lint 与生产构建：通过；
- Jarvis Core、网页、Windows Companion 和 Backup Worker：运行中。

## 风险与关闭方式

小米当前套餐说明将 Token Plan 定位于编程与 Agent 工具，并限制明显的非编程
自定义应用后端。当前接入在协议上可用，不代表套餐规则允许。

关闭时把 `.env` 中的 `MIMO_TOKEN_PLAN_ENABLED` 改为 `false` 并重启 Jarvis；
标准路线将自动降级本地 Qwen。
