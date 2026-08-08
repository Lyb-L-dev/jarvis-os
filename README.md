# Jarvis OS

Jarvis OS 是一个本地优先、桌面优先的个人 AI 成长操作系统。它把目标、任务、英语、情报、投资记录、长期记忆和主动提醒连接成一个持续运行的个人闭环。

当前阶段：**v3 演进中 ——「对话即界面（CUI）」收敛前端，记忆网络与 SSE 实时推送逐步落地；Computer-use 阶段 3 已启用（沙箱确认后修改，R2 预览-批准-执行）**

## 更新记录

- **2026-08-08**：修复情报页 3D 地球组件与 globe.gl 2.46.1 的兼容问题，情报中心恢复加载。
- **2026-08-07**：v3-1 记忆网络落地 —— 实体/关系/时间线表（迁移 0032）、多跳检索与评测集。
- **2026-08-07**：V3-0 对话工作台契约冻结 —— `/ui/dialog` 聚合接口、`/ui/events` SSE 事件流基座、前端 API 契约。
- **2026-08-07**：完成迁移路线图 Sprint 0-6 收尾项。
- **2026-08-06**：迁移路线图 Sprint 0-6 合入 `main`；PostgreSQL + pgvector 真库验证闭环；备份/恢复演练落地。
- 更早的历次 Sprint 记录见 [docs/](docs/) 下的 `SPRINT_*.md`。

分支约定：`main` = 发布基线；`dev` = 集成分支。

## 核心能力

### 对话与模型

- FastAPI 后端与版本化 API；Next.js 16 Dashboard 与真实聊天页面；PostgreSQL 开发环境；
- 首次启动、个人档案、会话与消息持久化；
- 多模型统一路由，本地优先，云端模型可选接入且需逐次确认；
- 模型调用来源、首字耗时、生成速度、Token、错误和满意度记录；
- 内置轻量本地对话模型，可完全离线运行；
- 流式回答、随时停止与自动保存部分回答；
- 最新回答一键重新生成，不重复写入用户提问；
- 会话重命名与标题、消息内容搜索；
- 长对话自动压缩摘要并保留最近原始上下文；
- 云端深度模式可接入，已完成真实连接验收；
- 云端付费调用必须由用户逐次确认，确认结果进入调用审计；
- 云端模型运行失败时自动降级本地模型，不会擅自产生云端费用；
- 固定评测集，可分别比较本地与云端模型；
- 隐私化执行过程，只展示路由、知识引用数量与性能，不复制私人正文。

### 记忆与知识

- 长期记忆中心：候选确认、手动添加、搜索、编辑、停用、删除；
- v3 记忆网络：实体/关系/事件表 + 多跳检索，与向量检索融合；
- 未确认记忆不会参与回答，云端模型只接收单独授权的记忆；
- 密码、API Key、验证码、证件号、银行卡号和私钥禁止进入长期记忆；
- Obsidian Knowledge Bridge：只访问 Vault 的 `Jarvis/` 子目录；
- 本地 Markdown 索引、关键词和类型搜索、重新扫描以及在 Obsidian 中打开；
- 已确认长期记忆和每日情报自动归档，周复盘、英语和投资研究手动确认归档；
- 归档具备幂等、内容哈希和冲突保护，用户修改不会被静默覆盖；
- 正式聊天可按问题检索 Obsidian，并在回答下方展示可打开的 `[K1]` 来源；
- 笔记逐篇控制是否参与检索和是否允许云端，默认只供本地模型使用；
- 本地语义向量模型为已确认记忆和 Obsidian 文档生成可重建索引；
- 关键词与语义排名融合，索引不可用时自动回退，云端仍只接收逐项授权内容；
- Obsidian 内容按不可信参考数据处理，笔记中的提示词或动作指令不会执行；
- 对话可以沉淀为知识草稿；
- 草稿必须人工编辑确认后才写入 `Jarvis/Conversations/`，不会自动处理历史对话；
- 知识草稿可拆分为长期记忆、行动任务和待核验问题候选；
- 每条候选必须人工确认，忽略项不会生效，敏感凭据不能进入长期记忆；
- 确认后的记忆默认仅限本地，行动与核验问题进入成长任务并保留草稿来源；
- 提炼和确认都具备幂等保护，不会因重复点击重复创建记忆或任务。

### 成长与提醒

- 成长中心：长期目标、里程碑、任务状态与真实投入记录；
- 每日 4 小时计划先生成草稿，经确认后才安排任务；
- 周复盘只根据已确认任务、完成状态、阻塞原因和计时事件计算；
- Chat 消息可以直接转换为成长任务；
- 持久化任务提醒与独立提醒；
- Windows 桌面伴生组件定时领取到期提醒，浏览器关闭后仍可投递；
- 桌面通知、自动语音播报与逐渠道投递结果；
- 免打扰、每日上限、每小时语音上限、暂停、延迟、忽略、重试和历史；
- 系统托盘入口与可选的开机自启脚本。

### 语音

- 原创离线中英文男声、自动语言分段、沉稳/简洁/朴素三种语音人格和分类播报措辞；
- 中英混合提醒按原顺序切换声线，英语学习与复习使用美式英语男声；
- 语音合成固定使用 CPU，不占用独立显卡显存，本地男声故障时自动降级系统语音；
- 提醒页可查看语音运行状态、选择引擎与人格并调整语速和音量。

### 英语学习

- English Coach：自由、主题、面试和技术英语对话；
- 即时、温和和结束总结三档纠错；
- 语音转写与可编辑原句；
- 模型纠错先由用户确认，再进入可搜索、可修改的错题本；
- 同类错误聚合、五档间隔复习与掌握降频；
- 到期英语复习自动接入桌面和语音提醒；
- 英语学习路线只使用本地模型，不会自动调用云端付费模型。

### 情报中心

- 白名单 RSS、手动链接、来源状态与兴趣权重；
- RSS / Atom 统一解析、公共网络地址校验、重定向复核和大小上限；
- URL、正文指纹与近似标题三层去重，重复事件不会进入每日情报；
- 多主题分类筛选；
- 每日情报固定展示来源事实、整理摘要、AI 分析和建议行动；
- 情报路线默认只使用本地模型，不调用云端付费模型；
- 投资内容明确禁止生成买卖、调仓、仓位或价格预测；
- 收藏、忽略和转任务会反馈到个人兴趣权重；
- 每天早晨自动生成晨间情报，并接入桌面与语音提醒。

### 投资助手

- 手动录入资产、初始持仓、买入、卖出、分红和投资理由；
- 所有数量与金额使用定点数，历史交易修改或删除后按时间顺序重算持仓；
- 超额卖出和有交易后的币种修改会被阻止；
- 最新价格和日期由用户手动维护，无价格时不伪造市值或收益；
- 多币种分别汇总，不在没有汇率时生成误导性总资产；
- 投资理由保留版本历史、关键假设、观察事件和失效条件；
- 情报可与资产建立或解除关联，并进入基于事实快照的投资复盘；
- 投资复盘不自动交易、不预测价格，并固定显示“不构成投资建议”。

### 监控与自动化

- 投资与国际动态监控中心：资产、宏观与国际主题可分别建立监控项；
- 监控事件保留原始来源，展示相关原因、影响路径、等级和下一步核验；
- 高等级事件接入桌面和语音提醒，具备事件幂等、冷却时间和用户确认；
- 自动监控不调用云端付费模型、不自动交易，也不会把手工价格冒充实时行情；
- Tool Gateway 统一校验工具 Schema、Agent 白名单、R0–R3 风险、幂等与审计；
- Approval Center 统一展示工具动作与云端单次授权，R2 坚持预览、批准、执行三阶段；
- 工作流自动化使用独立容器与 internal 网络，不修改用户已有实例；
- 自动化核心不暴露端口，仅保留本机签名入口；
- 沙盒日历只读和本地邮件草稿已接入，真实外部账号、日历写入和邮件发送仍未开放；
- 自动化离线不会影响聊天、记忆、成长等核心能力；
- 职业机会雷达使用独立、回环地址监听的浏览器进程，只读取用户确认的精确域名公开招聘页；
- 每次岗位研究使用全新非持久浏览器上下文，不登录、不复用 Cookie、不上传、不下载、不填写表单、不投递；
- 公开页面中的 Prompt Injection 只作为不可信信号留痕，不能扩大 Agent 或 Tool Gateway 权限；
- 岗位必须具有结构化 JobPosting 证据，并保存来源、时间、内容哈希和本地证据截图；
- JD 与个人档案匹配使用可解释的本地规则，不调用云端付费模型。

### 数据、备份与隐私

- PostgreSQL 每小时检查备份计划，约每天创建一次本地恢复点，最多保留 30 份；
- 每份备份保存 SHA-256、数据结构版本和清单，并通过独立临时数据库验证可恢复性；
- 设置页可查看、立即创建和验证恢复点，但不提供容易误触的覆盖恢复按钮；
- 设置页可把全部业务表导出为本地 JSON，导出内容不包含 API Key。

### 界面与状态

- 原创 J-Core 视觉标志、统一线框图标和全新的个人 AI 指挥总览；
- 待命、聆听、思考、执行和警报五种可区分的核心反馈状态；
- 总览直接读取当前任务、模型、情报、记忆、投资和英语数据，不再展示演示指标；
- Chat 直接展示核心状态、模型路线、对话上下文以及隐私/知识边界；
- 各模块使用统一遥测与 Cinematic 工作界面。

### 平板与桌面

- 平板专用 `/tablet` 全屏终端，模型、记忆和数据库仍在电脑运行；
- USB 反向隧道只转发本机端口，不开放局域网或公网访问；
- 平板端支持真实流式聊天、停止生成、自动保存、模型路线、知识增强和隐私模式；
- 平板端支持全屏、屏幕常亮及经隐私确认后的中英文浏览器语音转写。

### 工程与质量

- 首次初始化会幂等创建首周目标与任务，可选功能默认关闭并标记延期；
- Prompt/策略评测、安全预检、源码密钥扫描与依赖漏洞审计；
- 可创建并精确清理的无隐私演示数据；
- 技术设计、ER 图和历史 Sprint 文档。

## 项目结构

```text
apps/
  api/       FastAPI、数据库、Agent 与模型服务
  web/       Next.js Dashboard
  desktop/   Windows 后台提醒与语音组件
docs/        PRD、技术设计和 Sprint 计划
infra/       本地基础设施
scripts/     Windows 开发脚本
```

## 本地启动

### 日常使用：一键启动

双击项目根目录中的：

```text
启动 Jarvis.cmd
```

它会检查 Docker、启动 PostgreSQL、执行数据库迁移、启动后端、生产版网页和 Windows 后台提醒组件，并自动打开 Jarvis。

需要关闭后端与网页时，双击：

```text
停止 Jarvis.cmd
```

### 1. 创建本地配置

```powershell
Copy-Item .env.example .env
```

不要把真实 API Key 发到聊天中，也不要提交 `.env`。

完整的新电脑安装、日常使用和故障恢复步骤见
[使用与恢复指南](docs/USER_GUIDE.md)。

### 2. 启动 PostgreSQL

```powershell
docker compose -f infra/docker-compose.yml up -d
```

### 3. 启动后端

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e "apps/api[dev]"
.\.venv\Scripts\python.exe -m app
```

后端文档地址：

```text
http://127.0.0.1:8000/docs
```

### 4. 启动前端

```powershell
npm --prefix apps/web install
npm --prefix apps/web run dev
```

常用页面：

```text
http://127.0.0.1:3000              Command Center
http://127.0.0.1:3000/chat         对话
http://127.0.0.1:3000/english      English Coach
http://127.0.0.1:3000/intelligence 情报中心
http://127.0.0.1:3000/investment   投资助手
http://127.0.0.1:3000/growth       成长中心
http://127.0.0.1:3000/memory       长期记忆中心
http://127.0.0.1:3000/knowledge    Obsidian 知识库
http://127.0.0.1:3000/notifications 主动提醒
http://127.0.0.1:3000/career       职业机会雷达
http://127.0.0.1:3000/evaluation   模型评测
http://127.0.0.1:3000/settings     数据保护
http://127.0.0.1:3000/tablet       平板专用终端
```

需要随 Windows 登录自动启动时，手动执行：

```powershell
.\scripts\enable-startup.ps1
```

关闭开机自启：

```powershell
.\scripts\disable-startup.ps1
```

## 文档

- [Jarvis OS v2.0 架构与迁移计划](docs/JARVIS_OS_V2_ARCHITECTURE_MIGRATION_PLAN.md)
- [Sprint 23 v2 架构基础与 Agent Contracts](docs/SPRINT_23.md)
- [Sprint 24 Router v2 与 Agent Registry](docs/SPRINT_24.md)
- [Sprint 25 Growth LangGraph Pilot](docs/SPRINT_25.md)
- [Sprint 26 Research LangGraph Pilot](docs/SPRINT_26.md)
- [Sprint 27 本地语义记忆与 pgvector](docs/SPRINT_27.md)
- [Sprint 28 Mem0 影子评测](docs/SPRINT_28.md)
- [Sprint 29 Tool Gateway 与审批中心](docs/SPRINT_29.md)
- [Sprint 30 n8n Provider](docs/SPRINT_30.md)
- [Sprint 31 Read-only Browser Research](docs/SPRINT_31.md)
- [Sprint 32 Agent Observatory](docs/SPRINT_32.md)
- [Sprint 33 Cost Center](docs/SPRINT_33.md)
- [Sprint 34 Context Engineering](docs/SPRINT_34.md)
- [Sprint 35 Personality Layer](docs/SPRINT_35.md)
- [Sprint 36 Proactive Engine](docs/SPRINT_36.md)
- [Sprint 37 受控 Computer-use](docs/SPRINT_37.md)
- [产品需求文档](docs/Jarvis_OS_v1.1_PRD.md)
- [技术设计](docs/TECHNICAL_DESIGN.md)
- [数据库 ER 模型](docs/DATABASE_ER.md)
- [Sprint 1 任务清单](docs/SPRINT_1.md)
- [Sprint 2 任务清单](docs/SPRINT_2.md)
- [Sprint 3 任务清单](docs/SPRINT_3.md)
- [Sprint 4 任务清单](docs/SPRINT_4.md)
- [Sprint 5 任务清单](docs/SPRINT_5.md)
- [Sprint 6 任务清单](docs/SPRINT_6.md)
- [Sprint 7 任务清单](docs/SPRINT_7.md)
- [Sprint 8 OpenClaw 延期与安全门槛](docs/SPRINT_8.md)
- [Sprint 9 稳定性与数据保护清单](docs/SPRINT_9.md)
- [Sprint 10 桌面版发布验收](docs/SPRINT_10.md)
- [Sprint 12 Obsidian Knowledge Bridge](docs/SPRINT_12.md)
- [Sprint 13 Obsidian 受控归档](docs/SPRINT_13.md)
- [Sprint 14 Obsidian 对话检索增强](docs/SPRINT_14.md)
- [Sprint 15 对话知识沉淀](docs/SPRINT_15.md)
- [Sprint 16 本地知识提炼与复用](docs/SPRINT_16.md)
- [Sprint 17 个人模型评测与隐私化执行追踪](docs/SPRINT_17.md)
- [Sprint 18 Visual Identity 2.0](docs/SPRINT_18.md)
- [Sprint 19 Cinematic Command Interface](docs/SPRINT_19.md)
- [Sprint 20 Voice Persona](docs/SPRINT_20.md)
- [Sprint 21 Tablet Companion](docs/SPRINT_21.md)
- [Sprint 22 投资与国际动态监控中心](docs/SPRINT_22.md)
- [发布验收报告](docs/RELEASE_ACCEPTANCE.md)
- [架构总览](docs/ARCHITECTURE.md)
- [使用与恢复指南](docs/USER_GUIDE.md)
- [无隐私演示与视频脚本](docs/DEMO_GUIDE.md)
- [Obsidian 知识库未来升级计划](docs/FUTURE_OBSIDIAN.md)
