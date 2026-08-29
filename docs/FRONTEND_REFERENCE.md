# 前端重建参考项目清单（GitHub）

- **文档类型**：前端重建参考资料（2026-08-08 检索整理）
- **背景**：Jarvis v3 已定稿「对话即界面（CUI）」方向，前端收敛为四个壳：对话工作台（主）/ 审批 / 设置 / 平板 + 首次引导；需要流式对话、SSE 实时推送、语音闭环、本地优先、中文界面与平板触控。
- **定位**：按 Jarvis 需求在 GitHub 检索的优质前端项目。用于抄结构、借鉴交互与信息架构，不直接采用任何项目的视觉皮肤（视觉沿用 `DESIGN.md` 的 Archive World 设计 token）。
- **注意事项**：拷贝代码前请核对各仓库 License；个人私用一般无碍，公开或商用需注意限制性许可（LobeHub Community License、n8n Sustainable Use License 等）。

---

## 1. 对话主界面（v3「对话即界面」主壳）

| 项目 | 为什么值得看 | 重点借鉴 |
|---|---|---|
| [LobeChat / LobeHub](https://github.com/lobehub/lobehub) | 全栈 AI 聊天工作台标杆（Next.js），现已演变为「Agent 团队 OS」，与 Jarvis v3（多 Agent、个人记忆、编排、主动汇报）愿景同构 | 会话列表 + 消息流 + 输入栏整体信息架构；Markdown/表格/代码渲染；工具调用结果卡片；TTS/STT hooks；PWA 与桌面壳 |
| [Open WebUI](https://github.com/open-webui/open-webui) | 自托管 LLM 界面，本地优先（SvelteKit） | 工作区（聊天 + 知识库 + 文档）整合方式；流式渲染；语音输入；设置页形态 |
| [LibreChat](https://github.com/LibreChat-AI/LibreChat) | Next.js + MongoDB，多模型 + Agents + 消息搜索 | 多模型切换 UI；会话/消息搜索；工具调用与审批式交互面板 |
| [NextChat (ChatGPT-Next-Web)](https://github.com/ChatGPTNextWeb/ChatGPT-Next-Web) | MIT 协议、代码量小、中文友好 | 完整 chat 前端的最小实现：流式、多语言、移动端、PWA |
| [big-AGI](https://github.com/enricoros/big-AGI) | Next.js，多模型 + personas + 语音 | Beam 多模型对比；对话侧栏快捷操作；响应流式体验 |
| [Chatbox](https://github.com/Bin-Huang/chatbox) | 桌面客户端形态的 AI 助手（Tauri） | Windows 托盘「对话常驻入口」的形态参考 |

## 2. Agent 执行、审批与进度（v3「推进到审批」）

| 项目 | 为什么值得看 | 重点借鉴 |
|---|---|---|
| [OpenHands](https://github.com/All-Hands-AI/OpenHands) | 开源智能体平台，前端含完整事件时间线与确认机制 | 任务运行时的实时事件流卡片（对应 SSE 推送的「状态/进度」）；R2/R3 审批的确认/驳回交互 |
| [OpenClaw](https://github.com/openclaw/openclaw) | 单操作员个人 AI 网关 + Control UI（v3 文档已列为借鉴对象） | Control UI 的 chat/config/sessions 组织方式；技能与工具面板；社区 [openclaw-dashboard](https://github.com/actionagentai/openclaw-dashboard) 将 CLI 命令映射为 UI 页面的思路 |
| [n8n](https://github.com/n8n-io/n8n) | 工作流执行平台 | Executions 列表与节点级运行状态展示；注意 Sustainable Use License |

## 3. 本地优先个人 OS / 仪表盘 / 平板

| 项目 | 为什么值得看 | 重点借鉴 |
|---|---|---|
| [Home Assistant frontend](https://github.com/home-assistant/frontend) | 最成熟的「本地优先个人 OS」前端（Apache-2.0） | 仪表盘卡片系统；平板墙挂/全屏触摸布局（对应 `/tablet`）；实体状态展示体系 |
| [Homepage](https://github.com/gethomepage/homepage) | Next.js 个人主页仪表盘，40+ 语言 | 组件化 widget（天气/时间/服务状态）；一屏信息密度；i18n 结构；后端 API 代理思路 |
| [Glance](https://github.com/glanceapp/glance) | Go + Vue 的自托管仪表盘 | RSS、书签、股票、天气一屏聚合（与 `/intelligence` 情报中心同构）；信息密度与卡片设计 |

## 4. 知识 / 记忆 / 第二大脑

| 项目 | 为什么值得看 | 重点借鉴 |
|---|---|---|
| [SiYuan 思源笔记](https://github.com/siyuan-note/siyuan) | 本地优先、中文优先、块级引用、数据全离线 | 中文 UI 排版与编辑器体验；隐私优先的产品表达；块级知识索引 |
| [Memos](https://github.com/usememos/memos) | 极简时间线式速记 | capture 交互的极简程度；移动端/平板端体验 |
| [Khoj](https://github.com/khoj-ai/khoj) | 自托管 AI 第二大脑，浏览器/Obsidian/桌面多端（v3 文档已列入） | 个人资料与文档问答界面；agent 与自动化调度入口 |

## 5. 成长 / 任务 / 投资

| 项目 | 为什么值得看 | 重点借鉴 |
|---|---|---|
| [Vikunja](https://github.com/go-vikunja/vikunja) | 自托管任务管理（列表/看板/甘特） | 任务状态流转；多视图切换（对应成长中心） |
| [Actual Budget](https://github.com/actualbudget/actual) | 本地优先记账（MIT） | 本地优先数据同步模型；交易录入与报表 UI（对应投资模块） |

## 6. 可直接复用的库（不重新造轮子）

- [@lobehub/ui](https://github.com/lobehub/lobe-ui)：AIGC 聊天应用 React 组件库（会话侧栏、消息流、输入栏）
- [Vercel AI SDK](https://github.com/vercel/ai)：`useChat` 等流式 hooks，简化 SSE 解析
- 已在使用且建议保留：shadcn/ui、motion、lucide-react、Geist / Geist Mono

## 7. 重建建议

「重新开始」不换框架，换架构：

1. 新前端只做四个壳：对话工作台（主）/ 审批 / 设置 / 平板；其余 21 个路由页面收敛为对话内卡片或抽屉；
2. 抄结构不抄代码：LobeChat 的会话 + 消息 + 输入栏骨架、OpenHands 的实时事件卡片 + 确认按钮、Homepage 的组件化 widget、思源的中文排版；
3. 先定数据契约再写 UI：`/ui/dialog` 聚合接口 + SSE 事件类型（状态 / 提醒 / 审批 / 进度 / 建议），让前端保持薄；
4. 视觉沿用 `DESIGN.md` 的 Archive World 设计 token，不套用参考项目的皮肤；
5. 许可证核对：LobeHub（Community License）、n8n（Sustainable Use License）拷贝代码前需确认；其余多为 MIT / Apache / AGPL。
