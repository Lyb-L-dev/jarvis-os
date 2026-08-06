# QA & Reliability Agent — Sprint 5 交接说明（R2/R3 不变量 + 工具扩展测试支撑）

- **日期**：2026-08-06
- **分支**：dev（共享工作区；未执行 git 写操作；Tool/AI 本轮未提交变更请求，故按任务执行“不变量审计 + skip 门控先行”）
- **范围**：R2/R3 不变量测试、AgentSpec↔ToolRegistry 对账审计、Sprint 5 落地 skip 门控、Sprint 1-4 回归

---

## 1. 审计结论

### 1.1 R2/R3 不变量（运行时 + 账本）

`apps/api/tests/test_tool_invariants.py`（3 例，全绿）：

- **R3 自动执行数 = 0**：账本断言——执行 R0/R1/R2 流程后，
  `tool_executions.risk_level = 'never_automate'` 计数恒为 0；另以伪造的
  R3 定义（`action_kind=PAYMENT`）验证参数校验层仍返回 `r3_prohibited`
  （不依赖注册表）。
- **R2 未确认写操作 = 0**：账本断言——`confirmed_write` 且状态
  `executing/succeeded` 的执行必须外连 `consumed` 的审批记录，否则计数非 0
  即失败；覆盖“未批准执行被拒”“批准后未执行”“执行成功且审批已消费”
  三个阶段均为 0。

### 1.2 AgentSpec ↔ ToolRegistry 白名单对账（H5 审计，当前零漂移）

`apps/api/tests/test_tool_reconciliation_audit.py`（6 例，全绿）按
`MIGRATION_SPRINT_2_TOOL_REGISTRATION_DESIGN.md` §3.1 R1-R5 落地：

- R1：spec 引用的工具全部已注册（无悬挂引用）；
- R2：spec.allowed_tools ↔ registry.allowed_agents 双向一致（13 工具 × 6 Agent）；
- R3：工具 risk_level 与 `RiskPolicy().classify(action_kind)` 完全一致；
- R4：R2 工具在其授权 Agent 的 `confirmation_actions` 内，且 Agent
  `max_risk_level` 足以到达 confirmed_write；
- R5：`PERMANENTLY_BLOCKED_ACTIONS` 恰为 4 个 R3 动作；无 R3 工具注册；
  4 个 R3 动作 disposition 均为 `prohibit_agent_execution`；
- 派生视图：按设计公式从 registry 计算的 effective_tools 与
  `spec.allowed_tools` 逐 Agent 相等（单一来源等价的静态闸门）。

> 该审计在 Tool/AI 合入对账重构后自动成为合并闸门：任一侧漂移即失败。

## 2. Sprint 5 落地 skip 门控（4 项，待 Tool/AI 提交后自动激活）

`apps/api/tests/test_tool_sprint5_gates.py`：

| 门控 | 激活条件 | 契约 |
|---|---|---|
| Computer-use 阶段 3 确认写 | `computer_use_stage >= 3` | 阶段 3 须暴露确认写入口，且不绕过 Gateway |
| 注册表对账函数 | tool_catalog 含 `def reconcile*` | `reconcile()` 返回零漂移 |
| Tool Gateway policy_gate 审计 | tool_gateway 含 `policy_gate` | flag 开启 + agent_run 时记录 `policy_gate` 步骤（`R1:allow_automatically` 类 ref） |
| AgentSpec 派生工具视图 | contracts 含 `effective_tools` | `spec.effective_tools` == registry 派生集合 |

## 3. 测试命令与结果

```text
pytest 新增 3 文件（audit 6 + invariants 3 + gates 4）
→ 9 passed, 4 skipped（skip 均为 Sprint 5 未落地门控）

全量回归（api/tests + db/tests + desktop/tests）
→ 322 passed, 29 skipped（较 Sprint 4 的 313+2 增加 9 通过 + 4 门控跳过）

scripts/check.ps1 → exit 0（ruff + pytest + security + prompt eval +
backup-drill dry-run + web typecheck + web lint）
```

## 4. 覆盖缺口清单

1. Computer-use 阶段 3 实拍验证（配置 `computer_use_stage=3` 后激活门控并补端到端确认写测试）。
2. 注册表对账函数 / 派生视图 / Gateway policy_gate 三项待 Tool/AI 落地后回填
   （门控已就位）。
3. n8n 真实工作流（日历写入/邮件草稿）验收需 Provider 可用环境（本机 Docker 不可用）。
4. R3/R2 账本不变量建议在 Sprint 6 全栈环境（PG 真库）复跑一次，确认 SQLite/PG
   行为一致。

## 5. 风险说明

1. 白名单对账审计当前零漂移，但依赖手工维护的 `AGENT_SPECS.allowed_tools` 与
   `TOOL_REGISTRY.allowed_agents` 双份数据；对账重构落地后本审计即为强制闸门，
   在此之前任何 Agent/工具新增必须保持双写一致（本测试会拦截漂移）。
2. skip 门控基于源码特征检测（`def reconcile`、`policy_gate`、`effective_tools`
   等），若落地实现抽取到新模块需同步更新检测。
3. 本机无 Docker/PG/Ollama/n8n：环境性验收（n8n 工作流、语义、审批全链）需
   全栈环境复跑。

## 6. 本轮改动清单（QA Owned）

| 文件 | 说明 |
|---|---|
| `apps/api/tests/test_tool_reconciliation_audit.py` | R1-R5 对账审计（6 例，常开） |
| `apps/api/tests/test_tool_invariants.py` | R2/R3 账本不变量（3 例，常开） |
| `apps/api/tests/test_tool_sprint5_gates.py` | Sprint 5 落地门控（4 例，skip） |
| `evals/QA_SPRINT5_HANDOFF.md` | 本交接 |

## 7. AI 辅助记录

全程本地执行：未调用外部模型、无 DeepSeek 费用、未发送个人数据；未修改产品
代码；未执行 git 写操作；所有新增测试离线、确定性，未弱化断言（账本计数与
双向对账均为严格断言）。
