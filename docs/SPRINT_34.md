# Sprint 34：Context Engineering

## 状态

已完成。聊天上下文现在按 Agent 执行独立字符预算，按“系统 / 记忆 / 知识 / 历史”分区控制；长期对话继续先压缩再发送，超出的记忆与历史在发送前截断。每次装配记录只保存统计，不保存正文，并随对话响应返回上下文摘要。

## 目标

- 根据任务只加载需要的记忆和 Obsidian 文档；
- 避免每次发送全部历史；
- 降低 Token、延迟和隐私暴露；
- 为不同 Agent 建立独立上下文预算。

## 已交付

### 上下文预算（配置驱动）

- 每个 Agent 独立预算：Jarvis Core 6000、English Coach 4000、Research 8000、Growth 8000、Local Doc 5000、Investment 7000，未匹配 Agent 使用默认 6000；
- 每个预算按比例分区：系统 10%、记忆 20%、知识 30%、历史 40%（`context_section_ratios` 可调）；
- Token 为本地估算：约每 3 字符 1 Token（`context_estimate_chars_per_token`），明确标注为估算；
- 全部可在 `.env` 调整（默认值在 `app/core/config.py`）。

### 上下文组装服务（`services/context_engineering.py`）

- `assemble_chat_context` 统一组装：系统提示（超长截断）→ 记忆（相关性检索 + 字符上限）→ 知识（按预算检索 Obsidian 片段）→ 历史（摘要 + 按预算保留最新消息）；
- `fit_history` 只保留能放入预算的最新消息，丢弃更早的消息并计入节省字符；
- `confirmed_memory_context` 新增 `max_chars` 上限，不再把 20 条长记忆全量发送；
- 聊天响应新增 `context` 字段：装配 ID、Agent、预算、实际字符、估算 Token、节省字符、分区明细；
- 每次装配写入 `context_assemblies` 表（新迁移 0026/0027），只存统计，不存对话正文、记忆内容或知识文档。

### Context API（`/api/v1/context`）

- `GET /context/overview`：各 Agent 预算与分区、今日装配次数、今日节省字符、平均上下文与估算 Token、估算说明；
- `GET /context/assemblies`：最近装配记录（Agent、模型、预算占用、估算 Token、节省、分区）。

### Context Engineering 页面

- 侧边栏 SYSTEMS 分组新增入口，地址 `/context`；
- 指标卡：今日装配、今日节省字符、平均上下文、平均估算 Token、总装配；
- 按 Agent 预算面板：预算条 + 系统/记忆/知识/历史分区占比；
- 装配规则说明：记忆按需加载、知识只取片段、历史先摘要再截断、记录不含正文；
- 最近装配表：预算占用条、分区明细、节省量与时间；
- 15 秒自动刷新 + 手动刷新；
- 视觉验收截图：`artifacts/context-engineering-sprint34.png`。

### 稳定细节

- 工作流（Growth/Research）与聊天共用同一套记忆/知识检索；本次只改造聊天链路，工作流行为不变；
- 组装过程对知识检索异常做了回滚兜底，不会因检索失败导致对话中断；
- 新表时间戳使用数据库 `now()` 默认值（迁移 0027 修正），与既有表保持一致；
- `fit_history` 先统计全部历史长度，再决定保留与丢弃，节省字符数准确。

## 当前验收

- API 回归：181 项通过、1 项按环境跳过（新增 7 项 Context Engineering 测试）；
- 桌面伴侣：6 项通过；
- Browser Worker Node 安全测试：5 项通过；
- Prompt/策略评测：16/16 通过；
- Python Ruff、TypeScript、ESLint：通过；
- Next.js 生产构建：22 个页面通过（新增 `/context`）；
- 浏览器视觉验收：控制台错误 0，截图归档 `artifacts/context-engineering-sprint34.png`；
- 真实链路验收：发送对话后，响应返回上下文统计（Jarvis Core / 6000 预算 / 166 字符 / 估算 55 Token / 四分区明细），`context_assemblies` 落库，概览正确汇总；
- 隐私验收：装配记录与列表接口均不包含对话正文、记忆内容或查询文本。

## 设计说明

- 预算只约束“发送给模型的上下文规模”，不改变检索的召回逻辑；
- “节省”按字符统计：被摘要压缩的历史（20 条以上触发）与超出预算被丢弃的消息；
- 上下文记录是纯统计账本，不存正文，天然满足“不展示隐藏推理和私人正文”；
- 估算 Token 与费用（Sprint 33）口径独立，互不混淆。

## 后续

[Sprint 35 Personality Layer](SPRINT_35.md)：建立稳定的 Jarvis 人格、称呼、语气与表达习惯，中文/英文保持一致，人格不覆盖事实与安全规则。
