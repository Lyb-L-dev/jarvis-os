# Jarvis OS v1.1 架构总览

## 当前可运行架构

```mermaid
flowchart LR
    USER["用户"] --> WEB["Next.js 中文界面"]
    USER --> VOICE["离线男声 / Windows 备用语音 / 桌面通知"]

    WEB --> API["FastAPI / Jarvis Core"]
    VOICE --> API

    API --> DB["PostgreSQL：唯一业务数据源"]
    API --> ROUTER["Model Gateway"]
    API --> MODULES["成长 / 英语 / 情报 / 投资 / 记忆 / 提醒"]
    API --> KNOWLEDGE["Knowledge Bridge\n受限扫描 / 索引 / 受控归档"]
    KNOWLEDGE --> OBSIDIAN["Obsidian Vault\n仅 Jarvis/"]
    KNOWLEDGE --> REVIEW["冲突保护\n_review/ 待审核"]
    KNOWLEDGE --> RETRIEVAL["权限感知检索\n关键词排序 / 引用 / 审计"]
    RETRIEVAL --> ROUTER
    API --> CAPTURE["对话知识草稿\n本地 Qwen / 人工确认"]
    CAPTURE --> KNOWLEDGE
    CAPTURE --> INSIGHTS["知识提炼候选\n记忆 / 任务 / 待核验问题"]
    INSIGHTS -->|"逐条确认后"| MODULES

    ROUTER --> MIMO["MiMo 主路由\n应用 API 或显式启用 Token Plan"]
    ROUTER --> DS["DeepSeek\n用户逐次确认"]
    ROUTER --> LOCAL["Ollama Qwen3 4B\n本地 / 隐私 / 故障降级"]
    API --> EVAL["Personal Evaluation\n固定测试 / 性能 / 人工反馈"]
    ROUTER --> TRACE["Private Trace\n路由 / 引用数量 / 耗时 / Token"]
    EVAL --> ROUTER

    WORKER["Backup Worker"] --> DB
    WORKER --> BACKUPS["本地恢复点\nSHA-256 + 版本清单"]
    BACKUPS --> VERIFY["独立临时数据库恢复验证"]
```

## 主动语音链路

```mermaid
flowchart LR
    REMINDER["到期提醒"] --> POLICY["免打扰 / 配额 / 优先级"]
    POLICY --> PERSONA["分类措辞 / 语音人格 / 文本清理"]
    PERSONA --> DETECT["中英文识别与顺序分段"]
    DETECT --> ZH["离线中文男声\n16 kHz"]
    DETECT --> EN["离线美式英语男声\n22.05 kHz"]
    ZH --> MIX["统一采样率 / 切换停顿"]
    EN --> MIX
    MIX -->|"任一必要模型失败"| WINDOWS["Windows 系统语音"]
    MIX --> SPEAKER["本机扬声器"]
    WINDOWS --> SPEAKER
    ZH --> STATUS["Companion 状态上报"]
    EN --> STATUS
    WINDOWS --> STATUS
    STATUS --> UI["提醒页运行状态"]
```

- `auto` 默认优先离线双语男声，所需模型或运行时不可用时才使用 Windows 语音；
- `local_neural` 和 `windows` 允许在提醒页显式选择；
- 语音人格只改变播报文本与语速，不改变提醒原文和数据库记录；
- 中文、英文和中英混合文本不调用 LLM，而是由本地字符级规则分段；
- 本地合成不发送提醒内容到互联网；
- 两个模型固定使用 CPU，因此不会与本地 Qwen 争用 独立显卡 的显存。

## 平板专用终端

```mermaid
flowchart LR
    PAD["平板\nChrome / PWA"] -->|"USB ADB Reverse\n设备 127.0.0.1"| LOOPBACK["电脑 127.0.0.1"]
    LOOPBACK --> WEB["Next.js :3000 /tablet"]
    LOOPBACK --> API["FastAPI :8000"]
    API --> CORE["模型 / 数据库 / 记忆 / 提醒"]
```

- 电脑网页和 API 仍只监听 `127.0.0.1`；
- ADB 只反向转发 `tcp:3000` 与 `tcp:8000`，没有 Windows 入站端口；
- 平板只承担显示、触控和可选浏览器语音转写，AI 运算仍在电脑；
- 连接脚本不安装 APK、不执行 Root、不访问平板文件；
- Android Platform Tools 必须由用户接受 Google SDK 许可后安装，并校验 Google
  数字签名；
- 断开脚本精确删除两个 Jarvis 端口映射，不清理其他应用的 ADB 规则。

## 交互与视觉层

```mermaid
flowchart LR
    DATA["任务 / 模型 / 情报 / 记忆 / 投资"] --> DASH["Command Dashboard"]
    DASH --> CORE["J-Core 状态核心"]
    DASH --> NAV["分组导航与统一线框图标"]
    CORE --> IDLE["待命"]
    CORE --> LISTEN["聆听"]
    CORE --> THINK["思考"]
    CORE --> EXECUTE["执行"]
    CORE --> ALERT["警报"]
```

- J-Core、网页图标和导航图形全部由本地 SVG / CSS 构成，不依赖外部视觉服务；
- 总览聚合现有只读接口，单个业务模块失败不会阻塞其他模块；
- 首次读取映射为“思考”，手动同步映射为“执行”，核心异常映射为“警报”；
- 状态预览只影响视觉反馈，不触发模型调用或业务写入；
- 动画遵守系统的减少动态效果设置；
- 视觉层不改变模型路由、数据库或安全权限。

### 模块遥测

```mermaid
flowchart LR
    MODULE["现有模块页面"] --> STATE["页面已有状态"]
    STATE --> TELEMETRY["CommandTelemetry 只读映射"]
    TELEMETRY --> VIEW["模式 / 队列 / 数据 / 安全边界"]
    VIEW --> USER["用户判断下一步"]
```

- 遥测组件不直接请求 API，只展示父页面已经取得的数据；
- Chat 遥测映射生成状态、模型路线、消息上下文和隐私/知识边界；
- 业务模块使用同一组件展示各自的当前视图、关键队列与安全状态；
- 遥测不执行动作、不调用模型、不改变数据库，因此不是新的权限入口。

## 个人闭环

```mermaid
flowchart TB
    PROFILE["个人档案与长期记忆"] --> PLAN["目标、里程碑与每日计划"]
    PLAN --> TASK["任务执行与真实投入"]
    TASK --> REVIEW["周复盘"]
    REVIEW --> PLAN

    INTEL["可追溯情报"] --> TASK
    INTEL --> INVEST["投资持仓与理由"]
    INVEST --> INVEST_REVIEW["事实投资复盘"]

    ENGLISH["英语会话"] --> MISTAKE["确认后的错题"]
    MISTAKE --> SPACED["间隔复习"]
    SPACED --> REMINDER["桌面与自动语音提醒"]
```

## 安全边界

```mermaid
flowchart LR
    INTERNET["互联网"] -->|仅白名单 RSS / 明确云端请求| API["Jarvis Core"]
    API -->|已确认且允许云端的内容| CLOUD["MiMo / DeepSeek"]
    API -->|敏感、本地、离线| LOCAL["Ollama"]
    API -->|仅 127.0.0.1| WEB["本机网页"]

    OPENCLAW["OpenClaw / 微信"] -.->|"未安装"| ISOLATION["未来隔离环境"]
    ISOLATION -.->|"最小权限 API"| API
```

- API 与网页只监听本机回环地址；
- DeepSeek 不自动产生费用，实际调用必须逐次确认；
- Token Plan 采用专用地址与 `api-key` 鉴权，且必须通过本机配置显式启用；
- 当前启用决定不改变小米套餐规则，仍存在服务暂停或密钥封禁风险；
- API Key 只保存在本机 `.env`，不进入数据库导出、长期记忆或源码；
- Obsidian 仅允许访问已验证 Vault 下的 `Jarvis/`，禁止 `.obsidian`、链接和越界路径；
- 记忆与每日情报可以自动归档；周复盘、英语和投资知识必须手动确认；
- 归档以来源唯一键和内容哈希保证幂等，用户修改冲突进入 `_review/` 而不覆盖原文件；
- 本地模型可使用所有已启用笔记，云端模型只能使用逐篇明确授权的笔记；
- 检索上下文视为不可信数据，回答保存来源引用，审计不重复保存查询正文或笔记摘录；
- 对话沉淀只能手动触发，草稿固定走本地 Qwen，确认后才进入 `Conversations/`；
- 草稿提炼同样固定走本地 Qwen，候选在人工确认前不进入记忆或任务；
- 已确认记忆默认禁止云端使用；待核验问题只创建核验任务，不作为事实进入回答；
- 草稿修改会撤销未接受候选，已接受结果及其来源链接继续保留；
- 模型执行追踪不复制提问、回答或笔记正文，只记录结构化性能与步骤元数据；
- 个人评测只使用固定非私人测试题，不自动改变正式路由或人工确认规则；
- DeepSeek 评测与正式调用一样必须逐次确认费用，失败时不自动降级；
- 网页不提供覆盖恢复按钮；
- OpenClaw 不属于当前运行依赖，也没有主机权限。

---

## v2 迁移状态（2026-08-06，迁移路线图 Sprint 0-6 完成）

本文档为 v1.1 架构总览；迁移路线图（Sprint 0-6）已在 v1 生产路径上渐进落地，
全部合入 `dev`（`main` 保持发布基线）。以下为本轮新增/改造的组件，权威细节见
`docs/MIGRATION_SPRINT_1..6.md` 与各 ADR：

```mermaid
flowchart TB
    subgraph v2["v2 新增/改造（Feature Flag 灰度，默认关）"]
        REPO["db/repositories + uow.py<br/>唯一数据出口"]
        ENUM["db/enums.py + CHECK 约束<br/>AgentApproval/Memory/ToolExecution/AgentRun"]
        CKPT["db/checkpoint.py<br/>checkpointer 下沉（H2）"]
        PROMPT["services/prompts/**<br/>24 模板 + 版本注册表（flag 灰度）"]
        ROUTER2["Router v2 阶段 1 一致性校验<br/>Policy 审计读取点"]
        REG["Agent Registry<br/>effective_tools 派生视图 + R1-R5 对账"]
        MROUTE["后台模型调用统一走 ModelRouter"]
        CU3["Computer-use 阶段 3<br/>沙箱确认后修改（R2）"]
        BACKUP2["backup.ps1 vault 归档 + backup-drill.ps1"]
        FE["前端 lib/api/** 领域模块 + generated.ts<br/>四巨型组件拆分"]
    end
    CORE["Jarvis Core API（FastAPI）"] --> REPO
    CORE --> ENUM
    CORE --> CKPT
    CORE --> PROMPT
    CORE --> ROUTER2
    CORE --> REG
    CORE --> MROUTE
    CORE --> CU3
    CORE --> BACKUP2
    CORE --> FE
```

要点：

- **数据层**：Repository/UoW 为新增边界（未强制迁移全部 service，渐进推进）；
  状态枚举四层统一（DB CHECK + Pydantic + TS union，AgentRun 命名联合为遗留项）；
- **AI 层**：Prompt 注册表、Router 一致性校验、workflow 走 AgentSpec 均默认关
  （`v2_prompt_registry_enabled` / `v2_router_enforcement_enabled` / `v2_policy_enforcement_enabled`），
  开即逐字等价或仅审计；
- **工具层**：Computer-use 阶段 3 已启用（`computer_use_stage=3`，R2 预览-批准-执行 +
  沙箱备份 + 可回滚）；n8n 测试账号工作流为环境门控（`available=False`）；
- **前端**：`lib/api.ts` 为兼容层（372 导出冻结），领域实现在 `lib/api/**`；
  四巨型组件已拆至 ≤289 行/文件；
- **迁移**：`20260608_0030`（状态 CHECK）、`20260608_0031`（HNSW ANN）已落库未应用，
  应用流程见 `docs/MIGRATION_SPRINT_1.md §5`。
