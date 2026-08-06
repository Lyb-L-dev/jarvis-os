# Jarvis OS 开源项目调研与优化报告

> 调研日期：2026-08-04
> 数据来源：GitHub 公开仓库 API（星标、许可证、最后活跃时间均为当日实测）
> 范围说明：本次只做调研与建议，不修改任何 Jarvis 代码与配置。

---

## 一、核心结论（TL;DR）

1. **Jarvis 不需要推翻重来，也不需要引入"全家桶式"平台**（如 Dify、Open WebUI、AnythingLLM、Khoj）。这些平台型项目适合从零搭建，而 Jarvis 已经有自己的后端、前端、记忆、知识库和权限体系，吸收它们的"能力点子"比引入整套系统性价比高得多。
2. **当前最有价值的五个吸收点**：
   - **LiteLLM 的成本核算与预算设计** → 直接解决 Sprint 33 Cost Center（借鉴设计，不一定要引入代理）。
   - **Opik / Arize Phoenix / Langfuse** → 直接解决 Sprint 32 Agent Observatory（自托管 LLM 观测）。
   - **FSRS（间隔复习算法）** → 让 English Coach 的五档复习升级为数据驱动的个人化排期。
   - **garak（LLM 漏洞扫描）** → 把 Prompt Injection 安全演练从"手工一次"变成"定期自动化"。
   - **changedetection.io（网页变化监控）** → 让 Career Radar 与情报中心具备"持续盯变化"的主动能力。
3. **长期记忆的下一步**：Jarvis 已用 Mem0 做过影子评测，正式记忆是自己的体系。下一步建议吸收 **Letta 的"记忆分块 + 自我管理"** 与 **Graphiti 的"时间感知知识图谱"** 这两个理念，而不是整体替换。
4. **受控电脑操作（Sprint 37+）**：browser-use、OmniParser、UI-TARS、Open Interpreter 都是成熟度足够高的预研对象，但只能作为"读 + 计划"阶段的参考，真实操作仍必须走 Tool Gateway 审批。
5. **许可证与风险提示**：Langfuse 已被 ClickHouse 收购、LiteLLM 转向 Rust 核心、OpenClaw 许可证非标准，这些项目的"长期战略风险"需要在吸收前评估。

---

## 二、候选项目总览

| 分组 | 项目 | Star | 许可证 | 最后活跃 | 一句话定位 |
|---|---|---:|---|---|---|
| 观测 | Langfuse | 32.4k | 自定义（需核实） | 2026-08-03 | 开源 AI 工程平台：trace、prompt 管理、eval、人工标注 |
| 观测 | Opik（Comet） | 21.1k | Apache-2.0 | 2026-08-04 | LLM 评测 + 追踪 + 监控一体，全功能可自托管 |
| 观测 | Arize Phoenix | 10.9k | 自定义（需核实） | 2026-08-04 | OpenTelemetry 原生的轻量 AI 可观测平台 |
| 成本 | LiteLLM | 55.5k | 自定义（需核实） | 2026-08-04 | 统一 AI 网关：100+ 模型、成本追踪、预算与限流 |
| 记忆 | Letta（原 MemGPT） | 24.1k | Apache-2.0 | 2026-08-01 | 有状态 Agent 平台，核心记忆 + 档案记忆分块管理 |
| 记忆 | Graphiti（Zep） | 29.5k | Apache-2.0 | 2026-08-03 | 时间感知知识图谱记忆，事实可带有效期与失效 |
| 记忆/RAG | LightRAG | 38.5k | MIT | 2026-08-04 | 轻量图结构 RAG，增量索引、双级检索 |
| 记忆/RAG | Microsoft GraphRAG | 35.2k | MIT | 2026-08-03 | 图 RAG + 社区摘要，适合全局归纳型问题 |
| 知识库 | RAGFlow | 86.8k | Apache-2.0 | 2026-08-04 | 深度文档解析 RAG 引擎，中文文档能力突出 |
| 情报 | RSSHub | 45.6k | AGPL-3.0 | 2026-08-04 | 把"没有 RSS 的网站"变成 RSS 订阅源 |
| 情报/主动 | changedetection.io | 32.6k | Apache-2.0 | 2026-07-31 | 自托管网页变化监控 + 85+ 渠道通知 |
| 情报/主动 | Huginn | 49.7k | MIT | 2026-08-01 | 自托管监控 Agent，事件触发行动 |
| 浏览器 | browser-use | 107.8k | MIT | 2026-08-03 | 让 AI 像人一样操作浏览器，自动化 Web 任务 |
| 浏览器 | JobSpy | 4.0k | MIT | 2026-02-18 | 聚合抓取 LinkedIn/Indeed/Glassdoor 等岗位 |
| 电脑操作 | Open Interpreter | 67.5k | Apache-2.0 | 2026-08-01 | 让模型在本地执行代码与命令的自然语言接口 |
| 电脑操作 | Microsoft OmniParser | 25.2k | CC-BY-4.0 | 2026-07-20 | 把屏幕截图解析成结构化 UI 元素，供 GUI Agent 使用 |
| 电脑操作 | ByteDance UI-TARS | 11.3k | Apache-2.0 | 2026-01-27 | 原生 GUI 操作模型，屏幕定位与交互 |
| 语音 | sherpa-onnx（k2-fsa） | 14.0k | Apache-2.0 | 2026-08-04 | 离线 ASR + TTS + 说话人分离统一运行时，支持中英混合 |
| 语音 | Kokoro-82M | 8.3k | Apache-2.0 | 2025-08-06 | 82M 参数高质量多语种 TTS（可由 sherpa-onnx 加载） |
| 英语 | FSRS4Anki | 4.0k | MIT | 2026-07-28 | 机器学习优化的间隔复习算法，替代固定公式排期 |
| 投资 | OpenBB | 71.4k | 自定义（需核实） | 2026-07-30 | 开源投资研究数据平台（股票/宏观/加密等） |
| 投资 | Ghostfolio | 9.1k | AGPL-3.0 | 2026-08-03 | 开源个人财富管理软件，持仓分析与仪表盘 |
| 安全 | NVIDIA garak | 8.7k | Apache-2.0 | 2026-08-03 | LLM 漏洞扫描器：注入、越狱、幻觉、泄露等探测 |
| 工作流 | n8n（已有） | — | — | — | Jarvis 已隔离部署，作为比较基准 |
| 工作流 | Activepieces | 23.6k | 自定义（需核实） | 2026-08-03 | AI 工作流 + MCP + 自动化（n8n 替代候选） |
| 工作流 | Windmill | 17.4k | 自定义（需核实） | 2026-08-04 | 脚本转 Webhook/定时任务 的开发者平台 |
| 工作流 | Temporal | 22.1k | MIT | 2026-08-04 | 持久化执行引擎，任务中断后可从断点恢复 |
| 工作流 | Hatchet | 7.7k | MIT | 2026-08-03 | 面向后台任务与 Agent 的持久化编排引擎 |
| 通知 | Apprise | 17.0k | BSD-2-Clause | 2026-08-04 | 一个库推送 80+ 种通知渠道 |
| 生态 | MCP Servers（官方） | 89.2k | 自定义（需核实） | 2026-08-03 | 模型上下文协议标准 + 官方服务器集合 |
| 平台型 | Open WebUI | 147.8k | 自定义（需核实） | 2026-08-02 | 自托管 AI 界面 + RAG + 工具（参考，不建议引入） |
| 平台型 | Dify | 151.3k | 自定义（需核实） | 2026-08-04 | Agent 工作流 + RAG 一站式平台（参考，不建议引入） |
| 平台型 | AnythingLLM | 64.3k | MIT | 2026-08-04 | 本地文档问答桌面应用（参考，不建议引入） |
| 平台型 | Khoj | 36.2k | AGPL-3.0 | 2026-08-02 | 自托管"第二大脑"，从文档/网页取答案（参考） |
| 平台型 | OpenClaw | 385.0k | 自定义（需核实） | 2026-08-04 | 个人 AI 助理框架（按既定决策继续延期，只借鉴设计） |
| 知识插件 | Obsidian Smart Connections | 5.3k | 自定义（需核实） | 2026-08-02 | Obsidian 本地语义联想插件（理念参考） |
| Agent 框架 | Pydantic AI | 19.0k | MIT | 2026-08-04 | FastAPI 原生 Agent 框架（与 LangGraph 对比参考） |
| Agent 框架 | OpenAI Agents SDK | 28.4k | MIT | 2026-08-04 | 多 Agent 工作流、guardrail、会话管理（理念参考） |

> 注：许可证标注为"自定义（需核实）"的项目，其仓库未提供标准 SPDX 标识，引入前需要逐字阅读许可证文件，确认自托管与商用边界。

---

## 三、按 Jarvis 路线图逐项分析

### 3.1 Agent Observatory（Sprint 32）—— 观测与故障诊断

**现状缺口**：能看到"跑没跑、成功没成功"，但缺少"跑到哪一步、为什么暂停/失败、调用了哪些工具、耗时与 token 分布"的完整视图。

**候选**：

| 项目 | 优势 | 顾虑 |
|---|---|---|
| Opik | Apache-2.0 最宽松；评测 + 追踪 + 监控一体；单容器易自托管 | 生态比 Langfuse 稍小 |
| Arize Phoenix | OpenTelemetry 原生，埋点标准、轻量，可只做 trace | 评测/提示词管理功能弱于 Langfuse |
| Langfuse | 功能最全：trace、prompt 管理、数据集、eval、人工标注 | 2026-01 被 ClickHouse 收购；自托管需要 Postgres + ClickHouse + Redis + S3 的较重组合 |
| OpenTelemetry GenAI 约定 | 中立埋点标准，避免绑定厂商 | 只是标准，需要自己接 |

**建议吸收方式**：
- 短期：在 Jarvis 现有的 Private Trace 基础上，把 Agent/LangGraph/工具调用/审批事件按 OpenTelemetry 的 GenAI 语义约定打点，先保证"事件可重放、可定位"。
- 中期：自托管 **Opik**（Apache-2.0、单容器、功能够用）作为观测后端；若后续需要 prompt 管理与人工标注一体化，再评估 Langfuse。
- 红线：观测数据只展示路由、工具名、耗时、token、审批结果和错误信息，不记录隐藏推理与私人正文——与 Jarvis 现有"隐私化执行过程"原则一致。

### 3.2 Cost Center（Sprint 33）—— 费用与资源

**现状缺口**：模型调用已有来源、耗时、token 记录，但缺少"按模型/Agent/任务聚合费用、DeepSeek 单独计费、本地模型资源指标"的统一面板。

**候选**：LiteLLM 是核心参考。它提供 100+ 模型统一网关、成本表、预算上限、限流与日志；2026 年已转向 Rust 核心，性能和体积都有提升。

**建议吸收方式**：
- **首选：借设计，不引入代理**。Jarvis 已有自己的 Model Gateway 和路由策略（MiMo 主导、本地降级、DeepSeek 逐次确认），引入 LiteLLM 作为代理会多一层依赖和故障点。可以直接参考它的三张表设计：**价格表（model × provider × token 单价）、调用记录表（请求级用量）、预算表（按 key/用户/模型的限额）**，在 Jarvis 现有记录表上补费用聚合。
- 本地资源指标：Ollama 已有 `/api/ps` 可看已加载模型与显存占用，结合 Windows 性能计数器（CPU/内存/显存）即可，不需要新项目。
- 红线：费用是"按公开价格估算"，必须像现在一样明确标注为估算值，不伪装成供应商账单；DeepSeek 付费调用仍只统计"经过逐次确认"的部分。

### 3.3 Context Engineering（Sprint 34）—— 按需加载上下文

**现状缺口**：已做对话压缩和权限感知检索，但"每次任务加载哪些记忆/文档、各 Agent 的上下文预算"还没有形成系统化的策略。

**候选**：

| 项目 | 核心理念 | 对 Jarvis 的价值 |
|---|---|---|
| Letta / MemGPT | 记忆分块：少量核心记忆常驻上下文，大量档案记忆按需取回，Agent 可自我管理 | 与 Jarvis"正式记忆 + 候选确认"天然互补，可借鉴分块与召回策略 |
| Graphiti / Zep | 时间感知知识图谱：每个事实带时间窗口，可失效、可演化 | 让记忆支持"当时是 A，现在是 B"的时序语义，避免旧事实干扰 |
| LightRAG / GraphRAG | 实体关系图 + 双级检索 / 社区摘要 | 提升 Obsidian 知识库的多跳问答能力 |
| OpenCE | 上下文策略（RAG/压缩/混合）的组合与评估工具包 | 用作对比评测，判断哪种加载策略更好 |

**建议吸收方式**：
- 优先吸收 **Letta 的分块思路**：给每条正式记忆增加"重要性/新鲜度/访问频率"元数据，形成"核心块（常驻）+ 档案块（按需）"两层结构。
- 其次评估 **Graphiti 的时序事实模型**：在记忆表中增加"有效起止时间"，支持事实修订而不丢失历史——这与 Jarvis 记忆的版本化方向一致。
- 知识图谱检索（LightRAG/GraphRAG）只允许使用本地 Qwen 生成图与摘要，不调用 DeepSeek，避免图索引产生付费费用。

### 3.4 Personality Layer（Sprint 35）—— 人格一致性

**现状缺口**：已有语音人格与提醒措辞分类，但"跨模型、跨语言、长期稳定"的人格层还没有正式建立。

**发现**：这个方向成熟的独立开源项目很少，多为提示词/配置工程。真正有参考价值的是 **OpenClaw 的人格与行为配置体系**（它把身份、语气、行为偏好做成可配置文件），但按 Jarvis 既定决策 OpenClaw 继续延期，因此只借鉴设计，不引入代码。

**建议吸收方式**：
- 不引入新框架，建立 Jarvis 自己的 **persona 配置结构**（称呼、语气、表达习惯、边界行为）作为 Agent 提示词的统一前置层。
- 用现有"固定个人测试集"扩展人格评测用例：验证同一提问在 MiMo / 本地 Qwen / 英文 / 中文下语气一致。
- 用 garak 或自建评测验证"人格不能覆盖事实、安全规则和用户最新要求"。

### 3.5 Proactive Engine（Sprint 36）—— 主动建议

**现状缺口**：提醒是固定时间 + 固定内容的，缺少"基于目标、情报、任务、习惯"的主动触发。

**候选**：

| 项目 | 价值 | 注意 |
|---|---|---|
| changedetection.io | 对任意 URL 做变化监控（支持 CSS 选择器、浏览器步骤、登录后页面），配合通知 | 与 Career Radar 定位互补：它盯"页面变了"，Browser Worker 盯"结构化岗位提取" |
| RSSHub | 把招聘页、公司博客、社交账号等无 RSS 源变成订阅源，直接扩充情报中心白名单 | AGPL-3.0；公共实例有速率限制，自托管更稳；路由质量参差需筛选 |
| Huginn | 自托管"监控 + 行动"Agent，事件驱动工作流 | 项目较老、界面旧，理念可借鉴，不建议直接引入 |
| Apprise | 80+ 通知渠道（Telegram、邮件、NTFY、企业微信等）的 Python 库 | 轻量，可让提醒不局限于 Windows 通知 |
| OpenClaw | 心跳机制（约 30 分钟检查邮件/日历/告警）与 cron 型自动化 | 继续延期，仅借鉴"心跳 + 检查清单"设计 |

**建议吸收方式**：
- 先做 **changedetection.io 试点**：对用户确认的少量公开招聘/情报页面监控变化，变化事件进入 Jarvis 现有审批中心，由用户决定是否触发动作。
- 情报中心扩充来源时优先用 **RSSHub 自托管实例**（隔离网络、缓存可控），并沿用现有 2 MB 上限与三层去重。
- 主动引擎的默认行为仍是"只生成建议与草稿"，后台不静默调用 DeepSeek，继续遵守静默时段与频率限制。

### 3.6 受控 Computer-use（Sprint 37+）—— 预研对象

**现状缺口**：Browser Worker 已覆盖"只读浏览"，但屏幕理解、通用 GUI 操作、受控本地执行尚未开始。

**候选**：

| 项目 | 定位 | 预研价值 |
|---|---|---|
| browser-use | 让 AI 像人一样操作浏览器（107k star，MIT） | 可升级 Career Radar 的提取鲁棒性；也可作为未来"只读浏览"的通用引擎 |
| Microsoft OmniParser | 屏幕截图 → 结构化 UI 元素 | 屏幕理解的基础组件 |
| ByteDance UI-TARS | 原生 GUI 操作模型，屏幕定位 + 交互 | 本地可推理的 GUI 操作候选；活跃度一般（2026-01 后更新放缓） |
| Open Interpreter | 自然语言 → 本地代码/命令执行 | 直接相关但风险最高；其"确认后执行"流程可对照 Jarvis 的 R0–R3 |
| JobSpy | 岗位聚合抓取 | 与 Career Radar"不登录、全新建上下文、精确域名"策略冲突，只能参考结构化提取思路 |

**建议吸收方式**：
- 按既定分级路线：先"只读查看屏幕与文件"（OmniParser + 截图），再"生成操作计划与预览"，确认后逐步开放"修改文件/日历/邮件"。
- 所有真实操作仍走 Tool Gateway（幂等、审计、预览、审批），与现状一致。
- 明确不开放：自动交易、支付、凭据操作、不可恢复删除。

### 3.7 业务模块强化（英语 / 投资 / 职业 / 语音）

#### 英语学习
- **FSRS（强烈建议）**：FSRS 用机器学习根据个人复习历史优化间隔，是 Anki 的官方默认算法之一，有纯 Python 实现（py-fsrs），MIT 协议。English Coach 现有的"五档间隔"可升级为个人化排期，且完全本地计算、不产生模型费用。

#### 语音链路
- **sherpa-onnx（建议评估）**：统一的离线 ASR + TTS + 说话人分离运行时，Apache-2.0，中英混合支持好，还能加载 Kokoro 等高质量音色。Jarvis 目前 TTS 已满足需求，此项价值主要在：① 让平板端获得本地语音转写（替代浏览器在线识别）；② 统一语音引擎、减少维护面。

#### 投资助手
- **OpenBB（参考数据源）**：开源投资研究数据平台，适合做"宏观/行业研究"的背景资料，但 Jarvis 的"价格由用户手动维护、不伪装实时行情"原则不变——不接入自动行情。
- **Ghostfolio（参考设计）**：其持仓仪表盘、绩效视图、资产类别分析值得参考，不建议引入（避免第二个数据库）。

#### 职业雷达
- **changedetection.io（见 3.5）**：盯招聘页面变化。
- **JobSpy**：仅参考其"多源岗位 → 统一结构"的提取模型（JobPosting 字段设计），不改变"不登录、不投递"的安全边界。

### 3.8 安全、数据保护与生态

#### 安全演练自动化
- **garak（强烈建议）**：NVIDIA 的 LLM 漏洞扫描器，可对 MiMo/本地 Qwen 定期跑 Prompt Injection、越狱、幻觉、数据泄露等探测。Sprint 31 的 Prompt Injection 演练可借此常态化，结果进入现有评测体系。

#### 知识库补充
- **RAGFlow（P2 观察）**：对 PDF/扫描件等非 Markdown 资料的深度解析很强。若 Obsidian 之外存在大量文档资料，可作为"文档解析前置层"；否则暂不需要。

#### 数据保护
- Jarvis 的 PostgreSQL 备份/校验/恢复演练已经很扎实。可选增强：用 `age`（简单文件加密）或 restic 对导出包做加密异地备份——这是运维习惯，不是新系统。

#### 工具生态标准化
- **MCP（长远观察）**：Model Context Protocol 已是主流工具生态标准。Jarvis Tool Gateway 未来可考虑暴露 MCP 兼容接口，从而复用官方与社区 MCP 服务器生态，但这不是当前必须项。

---

## 四、优先级路线图

| 优先级 | 项目/能力 | 对应 Sprint | 建议动作 |
|---|---|---|---|
| P0 | 观测埋点 + Opik 自托管 | Sprint 32 | 按 OTel GenAI 约定打点；Opik 单容器接入 |
| P0 | 成本核算表设计（参考 LiteLLM） | Sprint 33 | 在现有模型调用记录上补价格表与预算表 |
| P0 | FSRS 复习调度 | English Coach | py-fsrs 本地集成，替换固定五档 |
| P0 | garak 定期安全扫描 | 安全基线 | 纳入评测流水线，覆盖 MiMo 与本地 Qwen |
| P0 | changedetection.io 试点 | Sprint 36 / Career Radar | 对用户确认的少量页面做变化监控，事件进审批中心 |
| P1 | Letta 记忆分块理念 | Sprint 34 | 正式记忆增加重要性/新鲜度元数据与两级结构 |
| P1 | Graphiti 时序事实模型 | Sprint 34 | 记忆表支持有效起止时间 |
| P1 | RSSHub 自托管 | 情报中心 | 扩充无 RSS 源，沿用去重与大小上限 |
| P1 | browser-use 评估 | Sprint 31 验收后 | 对比现有 Browser Worker 的提取鲁棒性 |
| P1 | Apprise 通知渠道 | 提醒 | 可选扩充 Telegram/NTFY 等渠道 |
| P1 | sherpa-onnx 评估 | 语音 | 平板本地语音转写 + 统一语音引擎 |
| P2 | OmniParser / UI-TARS / Open Interpreter | Sprint 37+ | 只读与计划阶段的预研 |
| P2 | RAGFlow | 知识库 | 仅在存在大量非 Markdown 资料时启用 |
| P2 | Temporal / Hatchet | 长期任务 | 暂不需要，n8n + LangGraph 已覆盖 |
| P2 | MCP 兼容接口 | Tool Gateway | 长远标准化方向，不急于实施 |
| 仅参考 | OpenClaw / Dify / Open WebUI / Khoj / AnythingLLM / Ghostfolio / OpenBB | — | 吸收设计理念，不引入系统 |

---

## 五、与 Jarvis 原则的兼容性检查

| Jarvis 原则 | 本报告建议是否冲突 | 说明 |
|---|---|---|
| 本地优先 | 不冲突 | 所有建议项目均可本地/内网自托管；图索引与复习调度只用本地 Qwen |
| DeepSeek 每次确认 | 不冲突 | 观测、成本、FSRS、garak、changedetection 均不调用 DeepSeek |
| 外部操作必须确认 | 不冲突 | changedetection / browser-use 的结果一律先进审批中心 |
| 投资交易/支付/凭据永不自动 | 不冲突 | 报告中明确排除，OpenBB 仅作研究参考 |
| 数据删除不可自动 | 不冲突 | 未引入任何自动清理类工具 |
| 微信/OpenClaw 延期 | 尊重既定决策 | OpenClaw 只作人格与主动性设计参考，不安装 |
| 隐私正文不进观测 | 不冲突 | 观测只记录路由、工具名、耗时、token、审批结果 |

---

## 六、引入前必须注意的风险

1. **许可证核实**：Langfuse、LiteLLM、OpenClaw、Smart Connections、Dify、Open WebUI、Ghostfolio、RSSHub 等不是标准 SPDX 标识或为 AGPL，自托管使用通常无碍，但若未来对外分发/修改需逐字读许可证。
2. **维护风险**：Kokoro 主仓库更新停在 2025-08（模型稳定但生态关注度下降）；UI-TARS 更新放缓；JobSpy 最后活跃为 2026-02。评估时应以"能力是否仍被维护"为准。
3. **被收购/转向风险**：Langfuse 已被 ClickHouse 收购；LiteLLM 转向 Rust 核心（API 兼容性需验证）。核心依赖应选择许可宽松、社区大、路线稳定的项目。
4. **不重复建设**：Jarvis 已有记忆、知识库、权限、备份体系，本报告的大部分建议是"借设计"而非"引系统"，避免双数据库、双记忆源。
5. **引入顺序**：建议严格按 Sprint 32 → 37 顺序推进，先观测与成本，再上下文与人格，最后才碰受控电脑操作。

---

## 七、追加调研：用户指定的四个项目分析（2026-08-04）

### 8.1 结论速览

| 项目 | 是否有必要 | 优先级 | 建议吸收方式 | 给 Jarvis 带来的功能好处 |
|---|---|---|---|---|
| koala73/worldmonitor | 有必要（情报增强） | P1 | 通过 MCP/REST 作外部情报源 + 借鉴"相关性信号"设计，不复制代码 | 国际动态、突发事件、宏观/金融信号的聚合情报 |
| huggingface/speech-to-speech | 有必要（交互语音） | P1 | 作为独立语音服务接入，默认全本地模型 | 双向实时语音对话、打断、边说边识别、英语口语练习 |
| Shubhamsaboo/awesome-llm-apps | 不必要（参考库） | P2 | 只作灵感索引，按需阅读/克隆个别示例 | 新功能开发时的现成模板库 |
| usestrix/strix | 可选（安全演练） | P2 | Docker 隔离运行，用户确认后定期触发 | 运行态渗透测试与真实漏洞验证 |

### 8.2 koala73/worldmonitor —— 实时全球情报仪表盘

**事实数据**：78.5k star；README 标注 AGPL-3.0（GitHub API 未返回标准 SPDX，以仓库 LICENSE 文件为准）；2026-01 创建但极活跃；单仓库支持 6 个站点变体（world/tech/finance/commodity/energy 等）。

**它是什么**：实时全球情报仪表盘，500+ 精选新闻源、AI 摘要简报、3D/平面地图（56 种图层）、跨流相关性分析（军事/经济/灾害/升级信号）、国家不稳定指数 CII、金融雷达（29 个交易所 + 商品 + 加密 + 7 信号市场复合指标）、本地 Ollama 可全离线运行；对外提供 MCP 服务器、REST API、CLI 与多语言 SDK。

**对 Jarvis 的价值**：
- 直接补强情报中心最薄弱的"国际动态"与"投资/宏观"两类：500+ 精选源 + AI 简报 = 现成的信息聚合上游，可替代大量手工 RSS 维护。
- "跨流相关性信号"（军事/经济/灾害汇聚出升级信号）是 Jarvis 投资监控中心"影响路径/等级"设计的成熟参考。
- 有官方 MCP 服务器与 REST API，接入成本低；也有本地 Ollama 模式，符合隐私取向。

**建议吸收方式**：P1。首选通过 MCP/公开 REST API 作为外部情报源接入 Jarvis 情报中心，沿用现有去重、来源引用与 2 MB 限制；如果要自托管，用 Docker 独立部署，通过隔离网络只开放本机访问。**不复制其代码**（AGPL 传染性 + 代码量庞大），只吸收产品与算法设计。

**风险**：AGPL 许可（个人私有自托管无碍，分发即传染）；部分高级数据需要 pro key；金融雷达是"信号参考"不是权威行情，与 Jarvis"价格手动维护、不伪装实时行情"原则不冲突，但必须标注来源与时效。

### 8.3 huggingface/speech-to-speech —— 本地语音 Agent 流水线

**事实数据**：10.7k star；Apache-2.0；2024-08 创建，持续活跃；已在 Reachy Mini 机器人上生产运行。

**它是什么**：模块化语音流水线 VAD（说话人检测）→ STT（语音转写）→ LLM（回复生成）→ TTS（语音合成），暴露为 OpenAI Realtime 兼容的 WebSocket API；每个组件可替换：STT 支持 Parakeet TDT / Whisper / faster-whisper / Paraformer，TTS 支持 Qwen3-TTS / Kokoro / ChatTTS，LLM 可指向任何 OpenAI 兼容服务（含本地 llama.cpp / vLLM / Ollama）；支持打断、实时转写、流式音频、工具调用。

**对 Jarvis 的价值**：这是目前 Jarvis 语音能力最缺的一块——**双向实时对话**。现状是：提醒单向播报（TTS）+ 平板浏览器在线语音转写（STT），没有"和 Jarvis 你一句我一句"的语音会话。引入后：
- 平板终端可以语音对谈 Jarvis，本地全离线（本地 STT + 本地 Qwen3-4B + 本地 TTS），隐私可控；
- 支持打断与边说边识别，交互体验接近真人；
- English Coach 可以增加"纯语音口语练习"模式（说英语、Jarvis 语音回应）；
- 现有提醒语音链路可保持不动，新服务作为独立 sidecar。

**建议吸收方式**：P1。作为独立服务运行（Python 包 + WebSocket），Jarvis API 通过 OpenAI Realtime 兼容客户端接入；LLM 槽位只允许本地 Qwen 或 MiMo，禁止静默接 DeepSeek；资源上默认 CPU 运行，中英切换沿用 Jarvis 已有的分段规则。适合放在"语音"专项 Sprint，或 Sprint 36/37 之前试点。

**风险**：新增一个常驻服务的资源占用；首次集成需要处理 WebSocket 鉴权（本地 127.0.0.1 + 简单 token 即可）；模型下载体积较大（Parakeet/Qwen3-TTS 均可选小模型）。

### 8.4 Shubhamsaboo/awesome-llm-apps —— 开源 AI 应用模板集

**事实数据**：130k star；Apache-2.0；持续活跃；100+ 经过端到端测试的 AI Agent / Agent Skill / RAG 应用模板。

**它是什么**：不是单一框架，而是一个"可运行示例库"：金融 Agent、语音应用、RAG、记忆、生产力工具等各类模板，声明兼容 Claude/Gemini/GPT/DeepSeek/Llama/Qwen。

**对 Jarvis 的价值**：开发新功能前的灵感索引。例如后续做金融研究、语音会话、上下文记忆增强时，可以直接参考其中成熟模板的实现（而非从零设计），也能对照检查 Jarvis 的实现有没有遗漏常见模式。

**建议吸收方式**：P2。不加入依赖、不克隆整个仓库到项目里；需要哪个功能时按需阅读或 clone 到临时参考目录，吸收代码思路后仍以 Jarvis 自己的架构落地。

**风险**：模板质量参差、依赖五花八门，直接照搬会产生依赖膨胀；只作参考。

### 8.5 usestrix/strix —— AI 渗透测试 Agent

**事实数据**：47.3k star；Apache-2.0；2025-08 创建，非常活跃；官方有托管云版本 app.strix.ai，开源仓库为框架本体。

**它是什么**：自主 AI 渗透测试 Agent：像真实黑客一样动态运行你的代码，发现漏洞并用实际 PoC 验证（而不是静态扫描的误报）；支持多 Agent 协同、自动修复建议与合规报告；官方要求 Docker + LLM API key（支持的提供商包括 OpenAI/Anthropic/Google 等）。

**对 Jarvis 的价值**：把现有"依赖漏洞审计 + Prompt 评测"升级为**运行态安全演练**：对 Jarvis 自己的 API 与前端做真实漏洞探测（SQL 注入、XSS、越权等），输出可复现 PoC 和修复建议，正好对应用户总结里"运行观测与安全基线"的长期需求。

**建议吸收方式**：P2。每季度一次、用户确认后手动触发；必须运行在 Docker 隔离容器中，扫描目标只指向 `127.0.0.1` 的 Jarvis 自身服务，绝不指向外部账号或真实凭据；LLM 调用若使用云端模型，按 Jarvis 规则逐次确认（或先验证是否支持本地模型）。

**风险**：本质是攻击性工具，作用域必须严格收敛；若用云端 LLM 会产生费用；扫描结果含敏感信息，应只存本地并纳入备份。

### 8.6 综合建议

- **P1 先行**：speech-to-speech 的语音会话试点（补齐交互语音），worldmonitor 情报源接入（可与 RSSHub 一起扩充情报中心）。
- **P2 按需**：awesome-llm-apps 作为新功能模板库随用随查；strix 作为季度安全演练。
- 两个 P1 都不改动现有架构核心：语音作为独立 sidecar，情报作为外部数据源，均保持"本地优先 + 确认边界"。

---

## 八、开发期帮手：前端设计与构建辅助项目（2026-08-04）

### 8.0 从四个指定项目里，谁对"搭建过程"有帮助

| 项目 | 对搭建过程的价值 |
|---|---|
| worldmonitor | 前端参考价值最高：它本身就是一个 Next.js/Vite + TypeScript 的"态势感知仪表盘"（3D 地球 globe.gl、WebGL 地图 deck.gl + MapLibre、深色 Cinematic 风、PWA、一套代码多站点变体）。Jarvis 情报中心要升级地图/全球视野时，直接看它的视觉与交互方案（AGPL，只参考不复制代码） |
| awesome-llm-apps | 每个模板都带完整前端页面，可当作"功能页面应该长什么样"的参考库（聊天页、Agent 面板、RAG 检索页） |
| speech-to-speech | 与前端无关（语音后端流水线） |
| strix | 与前端无关（安全测试工具） |

### 8.1 推荐的前端/开发辅助项目（星标为 2026-08-04 实测）

| 类别 | 项目 | Star | 许可证 | 说明 |
|---|---|---:|---|---|
| 动效组件 | Magic UI | 21.8k | MIT | 可复制粘贴的动效组件（渐变、粒子、卡片动效），契合 Cinematic 风格 |
| 动效组件 | Aceternity UI | — | 需以官网为准 | 100+ 高级动效组件，通过 `npx shadcn@latest add @aceternity/...` 安装，与 Jarvis 现有 shadcn/ui 生态兼容；深色高级感强 |
| 图表 | Apache ECharts | 67.0k | Apache-2.0 | 中文生态最好的图表库；投资持仓、成长进度、复盘图表首选 |
| 地图/3D | globe.gl | 3.1k | MIT | 3D 地球可视化（worldmonitor 同款），适合"全球动态"视图 |
| 地图/3D | deck.gl | 14.4k | MIT | WebGL 大规模数据图层框架（worldmonitor 同款），地图叠加情报事件 |
| 地图/3D | MapLibre GL JS | ~10k | BSD-3（需核实） | 免 API Key 的开源地图引擎，情报中心全球/区域视图 |
| UI 库 | HeroUI（原 NextUI） | 30.3k | Apache-2.0 | 完整 React 组件库，可补充 shadcn 之外的高级组件（表格、表单、虚拟化） |
| 聊天/Agent 前端 | Vercel AI SDK | 26.0k | 自定义（需核实） | Next.js 原生的流式聊天/工具调用前端 SDK，官方维护 |
| 仪表盘组件 | Tremor | 3.5k | Apache-2.0 | 仪表盘组件不错，但 2025-10 后更新放缓，备选 |
| AI 生成前端 | Bolt.new | 16.5k | MIT | 对话式生成完整 Web 应用，可用来快速出页面原型；开源仓库活跃度一般，在线版即可 |
| AI 结对编程 | Aider | 47.9k | Apache-2.0 | 终端 AI 结对编程，改代码时用（适合日常开发辅助） |
| 可视化工作流 | Langflow | 152.8k | MIT | 拖拽式搭建 Agent 工作流，可用来快速画流程草图再落地到 LangGraph |
| 可视化工作流 | Flowise | 55.1k | 自定义（需核实） | 可视化构建 AI Agent 工作流，同上（备选） |

### 8.2 组合建议（针对 Jarvis 现状：Next.js + shadcn/ui + Cinematic 风 + 19 页 + 平板终端）

- **立即能用**：Apache ECharts（投资/成长图表）、Magic UI（动效点缀，注意已有"减少动态效果"设置）、HeroUI（按需补组件）。
- **情报中心升级**：globe.gl + deck.gl + MapLibre，复刻 worldmonitor 的"全球视野 + 事件图层"视觉层级；全部本地、免 Key。
- **聊天/Agent 页面**：若现有流式聊天是手写的，可对照 Vercel AI SDK 的流式与工具调用规范。
- **开发辅助**：Aider 日常改代码；Bolt.new 出页面原型再本地化；Langflow 画 Agent 流程草图（只当白板，不替代 LangGraph）。
- **不推荐**：Tremor（维护放缓）；整套 Dify / Open WebUI / AnythingLLM（前端与架构重复建设）。

### 8.3 注意事项

- Jarvis 已有 shadcn/ui（`apps/web/components.json`），优先选 shadcn 生态兼容的组件（Aceternity 正好如此），避免引入第二套设计体系。
- 动效组件要遵守 Jarvis 已有的"减少动态效果"系统设置与平板端性能约束，不要整页堆特效。
- 地图类组件注意：只用免 Key 的矢量瓦片源，或本地缓存；不把位置数据发到第三方。

---

## 九、附录：核实的 GitHub 仓库数据（2026-08-04 实测）

| 仓库 | Star | 许可证 | 最后活跃 |
|---|---:|---|---|
| OpenClaw/Openclaw | 385,049 | 自定义 | 2026-08-04 |
| open-webui/open-webui | 147,757 | 自定义 | 2026-08-02 |
| langgenius/dify | 151,252 | 自定义 | 2026-08-04 |
| infiniflow/ragflow | 86,752 | Apache-2.0 | 2026-08-04 |
| Mintplex-Labs/anything-llm | 64,302 | MIT | 2026-08-04 |
| BerriAI/litellm | 55,461 | 自定义 | 2026-08-04 |
| huginn/huginn | 49,740 | MIT | 2026-08-01 |
| DIYgod/RSSHub | 45,562 | AGPL-3.0 | 2026-08-04 |
| HKUDS/LightRAG | 38,471 | MIT | 2026-08-04 |
| khoj-ai/khoj | 36,186 | AGPL-3.0 | 2026-08-02 |
| microsoft/graphrag | 35,225 | MIT | 2026-08-03 |
| langfuse/langfuse | 32,448 | 自定义 | 2026-08-03 |
| dgtlmoon/changedetection.io | 32,608 | Apache-2.0 | 2026-07-31 |
| getzep/graphiti | 29,523 | Apache-2.0 | 2026-08-03 |
| openai/openai-agents-python | 28,363 | MIT | 2026-08-04 |
| microsoft/OmniParser | 25,219 | CC-BY-4.0 | 2026-07-20 |
| letta-ai/letta | 24,073 | Apache-2.0 | 2026-08-01 |
| activepieces/activepieces | 23,567 | 自定义 | 2026-08-03 |
| temporalio/temporal | 22,074 | MIT | 2026-08-04 |
| comet-ml/opik | 21,095 | Apache-2.0 | 2026-08-04 |
| pydantic/pydantic-ai | 19,042 | MIT | 2026-08-04 |
| windmill-labs/windmill | 17,434 | 自定义 | 2026-08-04 |
| caronc/apprise | 16,991 | BSD-2-Clause | 2026-08-04 |
| k2-fsa/sherpa-onnx | 13,951 | Apache-2.0 | 2026-08-04 |
| bytedance/UI-TARS | 11,258 | Apache-2.0 | 2026-01-27 |
| Arize-ai/phoenix | 10,881 | 自定义 | 2026-08-04 |
| ghostfolio/ghostfolio | 9,063 | AGPL-3.0 | 2026-08-03 |
| NVIDIA/garak | 8,678 | Apache-2.0 | 2026-08-03 |
| hexgrad/kokoro | 8,262 | Apache-2.0 | 2025-08-06 |
| hatchet-dev/hatchet | 7,659 | MIT | 2026-08-03 |
| brianpetro/obsidian-smart-connections | 5,333 | 自定义 | 2026-08-02 |
| open-spaced-repetition/fsrs4anki | 4,033 | MIT | 2026-07-28 |
| speedyapply/JobSpy | 4,003 | MIT | 2026-02-18 |
| browser-use/browser-use | 107,767 | MIT | 2026-08-03 |
| modelcontextprotocol/servers | 89,167 | 自定义 | 2026-08-03 |
| OpenInterpreter/open-interpreter | 67,545 | Apache-2.0 | 2026-08-01 |
| openbb-finance/OpenBB | 71,352 | 自定义 | 2026-07-30 |
| koala73/worldmonitor | 78,538 | AGPL-3.0（README 明示） | 2026-08-03 |
| huggingface/speech-to-speech | 10,736 | Apache-2.0 | 2026-08-03 |
| Shubhamsaboo/awesome-llm-apps | 130,265 | Apache-2.0 | 2026-08-03 |
| usestrix/strix | 47,327 | Apache-2.0 | 2026-08-04 |
| magicuidesign/magicui | 21,788 | MIT | 2026-07-31 |
| apache/echarts | 66,971 | Apache-2.0 | 2026-08-04 |
| vasturiano/globe.gl | 3,116 | MIT | 2026-05-16 |
| visgl/deck.gl | 14,352 | MIT | 2026-08-04 |
| heroui-inc/heroui | 30,287 | Apache-2.0 | 2026-08-03 |
| vercel/ai | 25,999 | 自定义 | 2026-08-04 |
| stackblitz/bolt.new | 16,490 | MIT | 2024-12-17 |
| Aider-AI/aider | 47,915 | Apache-2.0 | 2026-05-22 |
| langflow-ai/langflow | 152,824 | MIT | 2026-08-04 |
| FlowiseAI/Flowise | 55,129 | 自定义 | 2026-08-03 |
| tremorlabs/tremor | 3,546 | Apache-2.0 | 2025-10-10 |

---

*报告结束。如需针对其中某个项目深入评估（架构对比、接入方案、风险清单），可以继续单独展开。*
