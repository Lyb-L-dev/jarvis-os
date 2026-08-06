# QA & Reliability Agent — Sprint 6 交接说明（收尾与验收）

- **日期**：2026-08-06
- **分支**：dev（共享工作区；未执行 git 写操作）
- **范围**：全量回归、Playwright 验收分类、PG 门控、契约四层对账、check.ps1/CI 对齐决定、死 flag 同步、P0 覆盖矩阵

---

## 1. 全量回归

### 1.1 测试与门禁

```text
全量 pytest（apps/api/tests + app/db/tests + desktop/tests）
→ 332 passed, 25 skipped, 2 xfailed（xfail 为四层对账中 AgentRun 层的两个
  已文档化遗留，strict=True，修复后自动转为 XPASS 失败以强制移除标记）

scripts/check.ps1 → exit 0
（ruff + pytest + security-check + evaluate-prompts + backup-drill dry-run +
  web typecheck + web lint）
```

### 1.2 Playwright 验收脚本（13 个，含 Sprint 4 新增 verify_api_boundary）

`node scripts/verify_regression_suite.cjs` 复跑（含 Edge 抖动重试，最多 3 次，
仅对已知 CDP 启动特征重试，结果记录 attempts/retried）：

| 分类 | 脚本 | 说明 |
|---|---|---|
| PASS (4) | verify_api_boundary、verify_growth_manager、verify_growth_workflow_ui、verify_n8n_provider_ui | 全绿 |
| 环境门控 (8) | verify_data_protection / english_coach / information_intelligence / investment_assistant | Edge CDP 启动失败（3 次重试仍无法 attach，未进入产品断言） |
| | verify_approval_center_ui | 无待审批项（需先构造 R2/DeepSeek 审批） |
| | verify_memory_shadow_ui / verify_semantic_memory_ui | 需 Ollama/Mem0 就绪 |
| | verify_research_workflow_ui | 需本地模型渲染（页面未呈现研究面板） |
| | verify_memory_paid_confirmation | 选择器已修复（不再卡“新建对话”），现卡在流程按钮禁用态（付费确认需模型链路+记忆候选就绪） |
| 真实失败 (0) | — | 无证据指向产品回归 |

本轮脚本修改：

- `verify_memory_paid_confirmation.cjs`：按 Sprint 4 裁决把“新建对话”改为
  “新的对话”（保留旧文案 fallback）。
- `verify_regression_suite.cjs`：新增 Edge/CDP 抖动特征重试（最多 3 次），
  结果记录 attempts/retried；真实失败不会被重试掉。

> 验收口径：8 项环境门控项必须在全栈环境（PG + Ollama + n8n + 正常 Windows
> Edge）复跑后才可记为“已验”，不得以 skip/环境失败代替通过。

### 1.3 PG 集成测试（23 例）

- `JARVIS_TEST_POSTGRES_URL` 未设置（本机无 Docker/PG）→ **23 例全部 skip**
  （确认门控生效，0.36s）。
- 真跑命令：`$env:JARVIS_TEST_POSTGRES_URL=...; pytest apps/api/tests/test_pg_integration.py -q`
  （要求可丢弃测试库 + vector 扩展；无 PG 时不得计为通过）。

## 2. 契约四层对账报告（静态一致性测试）

新增 `apps/api/tests/test_contract_four_layer.py`（纳入门禁收集）：

| 层 | 结论 |
|---|---|
| DB CHECK（migrations/0030） | ✅ 5 张表（agent_approvals / agent_runs / tool_executions / tool_approvals / memories）CHECK 值与 `app/db/enums.py` 逐值相等 |
| DB 0031 | ✅ 无状态 CHECK 引入（仅 HNSW ANN） |
| Pydantic（schemas/tool.py、memory.py） | ✅ ToolExecutionStatus / ToolApprovalStatus / ApprovalStatus / MemoryStatus 均为 enums 同一对象（identity） |
| TS union（generated.ts） | ✅ ApprovalStatus / ToolApprovalStatus / ToolExecutionStatus / MemoryStatus 命名联合与 enums 逐值相等；AgentRun 全部 11 值可由内联联合表达 |
| TS AgentRun 命名联合 | ⚠️ 遗留：无单一 `AgentRunStatus` 类型（两个内联联合互为补集）——`xfail(strict=True)` 记录 |
| Pydantic AgentRun 别名 | ⚠️ 遗留：无 schema 从 enums 导入 `AgentRunStatus`——`xfail(strict=True)` 记录 |

**结论**：四层在 4 张状态表完全对齐；AgentRun 层 TS/Pydantic 两处为 Sprint 6
明确遗留（均以 strict xfail 在门禁内显式标记，修复即触发 XPASS 失败）。

## 3. R2/R3 账本不变量（SQLite 复跑）

`test_tool_invariants.py`（3 例）复跑全绿：R3 账本计数恒 0、R2 未确认写恒 0、
伪造 R3 定义被参数校验层拦截。建议 Sprint 6 全栈复跑时在 PG 真库再跑一次
确认方言无关。

## 4. check.ps1 / CI 对齐最终决定（Sprint 1 遗留收口）

**决定：维持现状，不落地开关**，理由如下：

| 差异 | 现状 | 结论 |
|---|---|---|
| 本地 security-check（离线扫描） vs CI pip-audit（依赖漏洞） | 互补 | 维持：本地离线确定性优先，CI 有网络可审计依赖；dependency-audit.ps1 保留为手动/CI 入口 |
| desktop 测试仅本地 | check.ps1 覆盖 | 维持：desktop 6 例本地跑，CI 后端 job 不覆盖（Windows 专属） |
| evaluate-prompts 仅本地 | check.ps1 覆盖 | 维持：CI 无对应 job，提示词策略评估属本地离线校验 |
| deploy-rules 仅 CI | compose/node --check | 维持：需 Docker/Node 环境，本地不重复 |

不落地“可选开关”的原因：引入开关会降低本地门禁确定性，且各差异均为
“互补而非冲突”，维持现状是最低风险选项。

## 5. 死 flag 同步（v2_agent_core_enabled）

- 现状：`config.py:53` 仍声明 `v2_agent_core_enabled: bool = False`（.env.example
  同步），Tech Lead 尚未落地移除。
- **测试未改动**（按任务约定：Tech Lead 保留则不动作）。`test_v2_feature_flags.py`
  当前断言 `settings.v2_agent_core_enabled is False` 仍为真，门禁全绿。
- 待 Tech Lead 移除后需同步：删除该断言行（`test_only_read_only_shadow_router_is_enabled_by_default`
  内）——已写入遗留清单，避免移除后 AttributeError 红门禁。

## 6. P0 覆盖矩阵（对齐 RELEASE_ACCEPTANCE.md）

图例：✅ 已验（门禁/自动化覆盖）｜⏳ 环境门控（需全栈环境复跑）｜⏸ 延期

| P0 领域 | 结论 | 证据 |
|---|---|---|
| 首次初始化与档案 | ✅ | onboarding/chat 测试 + 全量 pytest |
| 第一周计划（目标/里程碑/任务） | ✅ | test_growth / test_growth_workflow + verify_growth_workflow_ui PASS |
| 目标、任务、计时、周复盘 | ✅ | test_growth + verify_growth_manager PASS |
| 长期记忆（确认/编辑/权限/敏感拦截） | ✅ | test_memory + test_knowledge（SQLite） |
| MiMo 默认路线（Token Plan + 降级） | ✅ | evaluate-prompts route/resolve 25/25 |
| DeepSeek 辅助（付费确认） | ⏳ | 流程需模型链路：verify_memory_paid_confirmation 环境门控；单元层 test_router/contracts 通过 |
| Ollama 本地模型 | ⏳ | test_cost_center 跳过（Ollama 未运行）；语义/记忆 shadow 环境门控 |
| 模型审计 | ✅ | test_model_execution/test_model_routing + 审计日志断言 |
| Windows 提醒 | ⏳ | desktop 6 例本地通过（✅ 本地）；Companion 全栈推送需真机 |
| OpenClaw/微信 | ⏸ 延期 | 非本迁移范围（v1.1 已明确延期） |
| 投资记录与复盘 | ✅ | test_investment + 视觉基线 10 张 + verify（环境门控于 Edge CDP） |
| Obsidian 知识库 | ✅ | test_knowledge（SQLite）+ 归档冲突/原子化测试 |
| 知识复用确认 | ✅ | test_knowledge（capture/insights/候选确认） |
| 数据导出 | ✅ | test_data_export |
| 自动备份 | ✅ | test_backup + verify-backup 逻辑 + backup-drill dry-run 入门禁 |
| 受控恢复 | ⏳ | restore 演练需 Docker/PG 真库（本机不可用）；dry-run 已入门禁 |
| 软删除与高风险确认 | ✅ | R2/R3 不变量 + 软删断言（memory/growth/investment） |

## 7. 遗留清单

1. 8 项环境门控 verify 脚本需全栈环境复跑回填（PG + Ollama + n8n + 正常 Edge）。
2. PG 集成 23 例真跑回填（含 ANN/HNSW 激活后的 EXPLAIN 断言）。
3. 四层对账：TS 命名 AgentRunStatus 联合 + Pydantic AgentRunStatus 别名
   （strict xfail 已标记，修复后移除）。
4. `v2_agent_core_enabled` 移除时同步删除 test_v2_feature_flags.py 对应断言。
5. `[module]` 死路由清理纠正未删（Sprint 4 遗留，page.tsx 真实存在）。
6. globals.css 令牌去重（Sprint 4 谨慎项，单独排期）。

## 8. AI 辅助记录

全程本地执行：未调用外部模型、无 DeepSeek 费用、未发送个人数据；未修改产品
代码（verify 脚本与测试均为 QA Owned）；未执行 git 写操作；门控项如实标注，
未将 skip/环境失败计为通过；断言未弱化（四层对账逐值比对，遗留以 strict xfail
显式标记）。
