# ADR-0006：Research Agent 的来源、引用与归档边界

状态：Accepted  
日期：2026-08-02

## 背景

Sprint 26 要把当前情报中心升级为可暂停、可恢复的多来源研究工作流。Research Agent 需要完成计划、来源整理、综合分析和报告草稿，但不能冒充浏览器采集信息，也不能因为“深度研究”而绕过 DeepSeek 费用确认、文件写入确认或投资安全边界。

现有系统已经拥有：

- 经过公开地址校验的 RSS 与手动情报来源；
- 新闻条目的 URL 指纹与内容指纹去重；
- Model Gateway、DeepSeek 单次授权、Agent Run/Step/Approval；
- LangGraph PostgreSQL Checkpointer；
- Obsidian 受限目录与冲突保护。

Sprint 26 不引入 Browser Agent、n8n 或新的后台采集进程。

## 决策

### 1. 来源事实源

Research Workflow 只接受两类来源：

1. Intelligence Center 已入库、未忽略且不是重复条目的公开来源；
2. 用户手动提供的公开 HTTP(S) 链接与原文摘录。

手动链接继续使用现有公网地址安全校验，拒绝本机、私网和不安全协议。来源按规范化 URL 指纹与内容指纹双重去重，至少需要两个唯一来源才能进入模型阶段。

Research Agent 不在 Sprint 26 中声称自己访问了链接之外的网页，也不把模型已有知识描述成“刚刚采集的事实”。

### 2. 稳定引用键

每个 Research Request 内的来源获得固定引用键 `S1`、`S2`……。模型仅收到本次研究问题、范围、研究计划和这些来源的公开摘录。

结构化报告必须把内容分成：

- 来源事实：`source_refs`；
- 来源观点：观点主体与 `source_refs`；
- Jarvis 推断：`basis_refs` 与置信度；
- 不确定性；
- 后续研究建议。

后端在保存模型草稿和用户修改后的草稿时都重新验证引用：引用必须真实存在，整份报告至少使用两个唯一来源。前端和 Obsidian 报告均提供可打开的来源索引。

### 3. DeepSeek 授权范围

`auto` 与 `deep` 路线会暂停在 DeepSeek 授权节点。授权只覆盖本 Agent Run 的：

- `synthesize_report`；
- `validate_citations`。

会发送的数据类别固定为：

- 研究问题；
- 研究范围；
- 公开来源摘录。

不会发送凭据、私有文件、交易凭据或未说明的记忆。用户可以改用 MiMo Token Plan 或本地 Qwen。未授权前不产生 DeepSeek 调用；后台任务也没有静默进入该节点的入口。

### 4. 报告确认与文件确认分离

模型只创建 `draft`。用户可以修改报告正文，后端重新校验引用后，用户再确认将其提升为 `confirmed` 正式报告。

`confirmed` 不等于 Obsidian 写入。Obsidian 归档是单独的显式确认，并继续使用受限目录、原子写入和冲突审核机制。研究报告只允许写入：

```text
Jarvis/Intelligence/Research/
```

归档不会触发交易、支付、日历、邮件或外部账号操作。

### 5. Checkpoint 隐私边界

LangGraph Checkpoint State 只保存 Run、Request、Report 的引用、来源数量、所选 Provider 与工作流状态。研究问题、范围、来源摘录、Prompt 和报告正文保存在 Jarvis 业务表中，不复制到 LangGraph Checkpoint。

## 结果

优点：

- 研究结论可以逐项追溯；
- 模型无法用不存在的引用通过后端校验；
- DeepSeek 费用和数据范围可见且可拒绝；
- 报告确认不会意外产生文件写入；
- 复用现有情报与知识库安全基础，不增加常驻依赖。

代价：

- Sprint 26 不能自动访问任意网页正文；
- 来源不足时需要用户刷新情报源或手动补充摘录；
- 本地 Qwen 路线在复杂冲突分析上的质量可能低于 DeepSeek。

这些限制是有意的。Browser Agent 与 n8n 必须等 Tool Gateway、Approval Center 和隔离执行环境稳定后再引入。

