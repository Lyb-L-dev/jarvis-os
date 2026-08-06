# Sprint 26：Research Agent Workflow

## 状态

已完成，2026-08-02。

## 目标

把情报中心已有的公开来源能力升级为一个可暂停、可恢复、引用可核验的 Research Agent 工作流。在不引入 Browser Agent、n8n 或静默付费的前提下，完成“研究问题 → 来源集合 → 模型授权 → 结构化草稿 → 正式报告 → 独立归档确认”的闭环。

## 本次完成

### 可恢复研究工作流

Research Workflow 包含：

1. 建立研究问题、范围和确定性研究计划；
2. 从用户选定或与问题匹配的 Intelligence 条目收集来源；
3. 使用 URL 指纹与内容指纹去重；
4. 少于两个唯一来源时暂停；
5. 来源足够后进入模型路线决策；
6. `auto` / `deep` 路线暂停并解释 DeepSeek 的作用、费用、数据和步骤；
7. 生成严格结构化的研究草稿；
8. 后端验证引用存在且至少综合两个来源；
9. 用户编辑后再次校验；
10. 用户确认后成为正式报告；
11. Obsidian 写入继续使用第二次独立确认。

工作流复用 Sprint 25 的 Agent Run、Step、Approval 与 PostgreSQL Checkpointer。Checkpoint 只保存业务记录引用和状态，不复制研究正文、来源摘录、Prompt 或报告内容。

### 来源边界

本阶段支持：

- Intelligence Center 已入库的公开 RSS / 手动情报；
- 用户手动添加的公开 HTTP(S) 链接与原文摘录；
- 公网地址安全校验；
- URL 与内容双重去重；
- 每个 Request 内稳定的 `S1`、`S2` 引用键；
- 来源名称、公开链接、发布日期、可信度和摘录。

本阶段没有 Browser Agent，也没有自动读取任意网页正文。模型 Prompt 明确声明只能使用给定来源，不能声称访问其他网页。

### 报告结构与引用

报告强制分区：

- 来源事实；
- 来源观点及观点主体；
- Jarvis 推断及依据、置信度；
- 不确定性；
- 建议的下一步研究。

模型输出与用户编辑都必须通过后端引用校验：不存在的引用、空引用或只使用一个来源都会被拒绝。Intelligence Center 和 Obsidian 报告均提供可打开的来源链接。

### DeepSeek 的作用

Research Agent 建议在复杂多来源任务中使用 DeepSeek，主要因为它更适合：

- 同时比较多个来源；
- 识别相互冲突的说法；
- 保持事实、观点和有限推断之间的边界；
- 输出结构完整的研究报告。

DeepSeek 不负责采集网页，也不执行任何动作。调用前界面说明：

- 本次用途；
- 只覆盖“生成报告”和“校验引用”；
- 发送研究问题、研究范围和公开来源摘录；
- 不发送凭据、私有文件或交易凭据；
- 会消耗 DeepSeek 钱包余额；
- 可改用 MiMo Token Plan 或本地 Qwen。

确认前 DeepSeek 不会被调用，一次确认只覆盖一个 Research Run。

### Intelligence Center 前端

情报中心新增 Research Agent 控制区：

- 五阶段进度轨迹；
- 研究问题、范围、类别、来源数量设置；
- 选择现有公开情报；
- 来源不足时补充情报条目或手动公开链接；
- 固定引用编号和可打开来源账本；
- DeepSeek / MiMo / 本地 Qwen 的透明路线选择；
- DeepSeek 单次付费授权界面；
- 事实、观点、推断分区的可编辑报告；
- 保存时引用复核；
- 正式报告确认；
- Obsidian 独立写入确认。

### Obsidian 归档

新增手动归档类型 `research_report`，目标目录：

```text
Jarvis/Intelligence/Research/
```

只有 `confirmed` 报告可成为归档候选。正式报告确认本身不会写文件；必须再次确认才调用知识库归档。原子写入、内容哈希和用户修改冲突保护继续生效。

### Feature Flags

代码安全默认值保持关闭：

```text
V2_WORKFLOW_RUNTIME_ENABLED=false
V2_RESEARCH_WORKFLOW_ENABLED=false
```

当前个人 Jarvis 环境已显式启用。关闭任一开关都不会创建 Research Run。

## 数据库迁移

迁移版本：

```text
20260802_0020 -> 20260802_0021
```

新增：

- `research_requests`；
- `research_sources`；
- `research_reports`。

## 安全结论

- 研究计划、读取来源和生成草稿可以自动进行；
- 来源不足时模型不会运行；
- DeepSeek 必须任务级确认，且仅覆盖列明步骤；
- 后台任务没有静默付费入口；
- 正式报告必须确认；
- Obsidian 写入必须再次确认；
- 不提供投资交易、支付、删除数据或凭据执行入口；
- 不提供日历、邮件和外部账号写入入口。

## 验收

- Research Workflow 专项后端测试：8 项通过；
- Research、Knowledge Archive 与 Feature Flag 联合测试：23 项通过；
- 完整后端回归：137 项通过，1 项隔离 PostgreSQL 测试按环境跳过；
- Python Ruff：通过；
- 前端 TypeScript：通过；
- 前端 ESLint：通过；
- Next.js 正式生产构建：17 个页面通过；
- Alembic 单一 Head：`20260802_0021`；
- 上线后 Live、Ready、Research Workflow API 与 Intelligence 页面均为 HTTP 200；
- Research Workflow API 上线时为空列表，验收过程没有创建真实 Research Run，也没有调用 DeepSeek、MiMo 或本地模型；
- `scripts/verify_research_workflow_ui.cjs`：研究问题、来源选择与四种模型路线可见，浏览器错误 0，失败请求 0；
- 视觉验收截图：`artifacts/research-workflow-sprint26.png`。

### 本机迁移与备份

- 迁移前备份：`jarvis-20260802T034201Z-950388c3.dump`；
- SHA-256：`32a9f97f17a4585069f023704703e7fe9534800ad6ddb11024f15e06eadb70ec`；
- 备份归档校验通过，并真实恢复到临时数据库；
- 恢复验证：50 张表，备份中的版本为 `20260802_0020`；
- 当前生产数据库：53 张表，版本为 `20260802_0021`；
- `research_requests`、`research_sources`、`research_reports` 均存在；
- 两个复合唯一约束使用明确且不同的名称，PostgreSQL 真实迁移通过；
- Jarvis Core、Web、Windows Companion 与自动备份服务已重新启动。

## 本阶段明确不实现

- Browser Agent；
- n8n；
- 任意网页自动正文抓取；
- Research 后台定时 DeepSeek；
- 自动归档 Obsidian；
- Personality Layer；
- Context Engineering Layer；
- Proactive Engine；
- Agent Observatory；
- Cost Center。

## 架构决策

- [ADR-0006：Research Agent 的来源、引用与归档边界](adr/0006-research-source-citation-and-archive-boundary.md)

## 下一阶段

Sprint 27：Semantic Memory with pgvector。

首先验证 PostgreSQL 当前部署是否具备可安全启用的 pgvector 扩展；向量索引必须可重建，PostgreSQL 继续是业务事实源，现有关键词检索保留为回退路径。
