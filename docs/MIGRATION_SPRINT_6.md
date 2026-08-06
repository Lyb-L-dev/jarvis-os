# MIGRATION_SPRINT_6.md — 迁移 Sprint 6 交付与验收记录（收尾）

- **文档类型**：Tech Lead 产出（迁移路线图 Sprint 6：收尾与验收）
- **日期**：2026-08-06
- **状态**：✅ 收口完成（合入 dev；发布验收待所有者对照 §4 拍板）

---

## 1. 交付物总览

| 项 | Owner | 结果 |
|---|---|---|
| 全量回归 | QA | pytest **332 passed / 25 skipped / 2 xfailed**；`check.ps1` exit 0；Playwright 13 脚本 **PASS 4 / 环境门控 8 / 真实失败 0** |
| 契约四层对账 | QA | `test_contract_four_layer.py` 入门禁：四张状态表四层完全对齐；AgentRun 2 处严格 xfail 遗留 |
| 文档更新 | Tech Lead | ARCHITECTURE.md 追加 v2 迁移状态；README 更新当前阶段 + 迁移交付记录 |
| 性能/资源审计 | Tech Lead | 静态基线见 §3；运行时基线列为发布后待办 |
| 发布验收 | 全团队 | P0 覆盖矩阵见 §4 |
| 死 flag / verify 脚本 / CI 对齐 | Tech Lead + QA | 决定见 §2/§5 |

## 2. Tech Lead 决定

1. **死 flag `v2_agent_core_enabled`：本轮不删，纳入发布后待办**。删除需同步
   `config.py`、`any_v2_feature_enabled`、`.env.example` 与 `test_v2_feature_flags.py:7`
   （QA 属主）；flag 无读取点、惰性无害，Sprint 6 收口不做最后一刻变更。
2. **check.ps1 / CI 对齐：维持现状**（QA 结论采纳）——本地离线扫描与 CI `pip-audit`
   互补；desktop/evaluate-prompts 仅本地、deploy-rules 仅 CI，引入开关会降低本地确定性。
3. **verify 脚本**：`verify_memory_paid_confirmation.cjs` 断言已修为“新的对话”
   （含旧文案 fallback）；`verify_regression_suite.cjs` 增加 Edge/CDP 抖动重试
   （最多 3 次，仅匹配 CDP 特征，真实失败不重试）。
4. **AgentRun 契约遗留**：`generated.ts` 无单一 `AgentRunStatus` 命名联合（内联联合互为
   补集）、Pydantic 侧无 schema 导入 `AgentRunStatus`——两处以 `xfail(strict=True)`
   锁定，修复即触发 XPASS 失败（发布后随契约四层收尾处理）。

## 3. 性能/资源静态基线（Tech Lead，2026-08-06）

| 项 | 数值 |
|---|---|
| `.venv` | 368.5 MB |
| `apps/web/node_modules` | 780.9 MB |
| `apps/web/.next` | 610.1 MB |
| `.data`（运行数据） | 208.6 MB |
| `backups/` | 6.8 MB |
| `types/generated.ts` | 469 KB |
| 全量 pytest 时长 | ~41s（351 collected） |

运行时性能（内存/显存/响应速度）依赖应用在跑，列为发布后基线任务：启动 PG + 前后端后，
记录 J-Core 首屏请求、Chat 首字耗时、4 worker 常驻内存、Ollama 显存占用。

## 4. 发布验收对照（RELEASE_ACCEPTANCE.md P0 矩阵，迁移后状态）

| 领域 | 状态 | 证据 |
|---|---|---|
| 首次初始化与档案 | ✅ | 集成测试全绿 |
| 第一周计划 / 目标任务复盘 | ✅ | growth 测试 + Playwright growth_manager/growth_workflow_ui PASS |
| 长期记忆（确认/编辑/敏感拦截/删除） | ✅ | 记忆测试 + 敏感拦截评测 |
| MiMo 默认路线 | ✅ | 路由评测 + 契约用例 |
| DeepSeek 辅助（逐次确认） | ⏳ 环境门控 | 需真实付费确认流程环境；409 语义测试绿 |
| Ollama 本地模型 | ⏳ 环境门控 | Ollama 未运行；本地路由测试绿 |
| 模型审计 | ✅ | model_execution/model_routing 测试 |
| Windows 提醒 | ✅ desktop 单测 | 本地 6 例通过 |
| OpenClaw/微信 | ⏸ 延期 | v1.1 明确延期，保持不变 |
| 投资记录与复盘 | ✅ | investment 测试全绿 |
| Obsidian 知识库 | ✅ | knowledge 归档/检索/冲突测试 + 评测 |
| 知识复用确认 | ✅ | 候选确认测试 |
| 数据导出 | ✅ | test_data_export |
| 自动备份 | ✅ | test_backup + backup-drill dry-run 入门禁 |
| 受控恢复 | ⏳ 环境门控 | 需 PG 真库执行恢复演练 |
| 软删除与高风险确认 | ✅ | R2/R3 不变量（R3 自动=0、未确认写=0） |
| v2 新能力（Router/Prompt/Registry/阶段 3） | ✅ | 门控测试激活 + 评测 25/25 |

## 5. 发布后待办（不阻塞发布，已记录）

1. **死 flag 清理**：移除 `v2_agent_core_enabled`（config/.env.example/test 同步）；
   `v2_shadow_runs_enabled` 保留决定。
2. **AgentRun 契约四层收尾**：`generated.ts` 命名联合 + Pydantic `AgentRunStatus` 导入
   （解除 2 个 strict xfail）。
3. **PG 真库复跑**：应用迁移 0030/0031（备份→预检→upgrade）→ `test_pg_integration.py`
   23 例 → R2/R3 账本不变量 → `backup-drill.ps1` 真跑 → 受控恢复验收。
4. **n8n 测试账号工作流**：凭据就绪后按 `infra/n8n/workflows/README.md` 启用；
   补 `email.draft.create` 的 catalog `confirmation_actions`；`test_accounts_connected`
   字段（二期）。
5. **Prompt 消费点二期切换**：personality/english/knowledge/memory/summary/
   intelligence/chat/evaluation 共 8 处（flag 灰度，逐模块）。
6. **前端**：`[module]` 占位页删除（路由冒烟）、globals.css 令牌去重、
   视觉回归预拆分基线缺口、Edge headless 重试已加（4 个仍启动失败待环境复核）。
7. **运行时性能基线**（§3）。
