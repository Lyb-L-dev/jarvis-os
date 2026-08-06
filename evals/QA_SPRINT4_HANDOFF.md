# QA & Reliability Agent — Sprint 4 交接说明（视觉基线 + 回归）

- **日期**：2026-08-06
- **分支**：dev（共享工作区；未执行 git 写操作）
- **范围**：视觉回归基线、Playwright 验收基线、门禁确认、拆分层静态断言

---

## 1. 运行环境（本机实拍环境）

| 服务 | 地址 | 说明 |
|---|---|---|
| 后端 | http://127.0.0.1:8000 | SQLite dev 覆盖库（`DATABASE_URL=sqlite+aiosqlite:///./.runtime/qa-s4.db`，相对 apps/api 工作目录），`AUTO_CREATE_SCHEMA=true` |
| 前端 | http://127.0.0.1:3000 | **生产构建** `npm run build && npm run start`（与 `scripts/start.ps1` 一致） |

启动命令（PowerShell）：

```powershell
# 后端（apps/api 工作目录）
$env:DATABASE_URL = "sqlite+aiosqlite:///./.runtime/qa-s4.db"
$env:AUTO_CREATE_SCHEMA = "true"
& .venv\Scripts\python.exe -m app
# 前端（apps/web 工作目录）
npm run build && npm run start --hostname 127.0.0.1
```

> ⚠️ `next dev`（Turbopack）在本机存在数据页卡 loading 现象（仅发出 1/5 数据
> 请求 + HMR WebSocket 报错）；生产构建正常。基线一律以生产构建为准。
> 常规全栈启动请用 `scripts/start.ps1`（需 Docker/PG，本机 Docker 守护进程
> 不可用，故本次采用 SQLite dev 覆盖 + 生产前端）。

## 2. 视觉基线清单（20 张，含 sha256 清单）

存档：`evals/visual-baselines/`（`manifest.json` + `README.md` + 20 PNG）

### 2.1 investment（10 张，映射预研 §1.4 十六项矩阵）

| 文件 | 覆盖项 |
|---|---|
| `01-loading-or-initial.png` | #1 加载/初始（含 #14 币种汇总、#15 CommandTelemetry） |
| `16a-tab-positions.png` | #3 持仓卡片（正/负浮动、缺价、目标仓位）、#4 未建仓资产卡、#16 Tab |
| `16b-tab-transactions.png` | #8 交易流水有数据、#16 |
| `16c-tab-theses.png` | #10 理由列表（当前/历史、云端徽标、失效/关闭）、#16 |
| `16d-tab-news.png` | #11 新闻（候选/已关联）、#16 |
| `16e-tab-reviews.png` | #12 复盘（draft + confirmed）、#16 |
| `05-asset-form-new.png` | #5 资产表单-新建 |
| `06-asset-form-edit.png` | #6 资产表单-编辑（币种禁用字段已确认 DISABLED） |
| `07-tx-form-buy.png` | #7 交易表单-买入 |
| `09-thesis-form.png` | #9 理由表单 |

待补项（已标记）：#2 无资产空态、#7 分红切换、#8 空态、#13 错误/提示条
（需空库/构造 409 等专用环境，见 README §1）。

### 2.2 english / chat / growth（10 张）

- English：对话训练 Tab、错题本 Tab、今日复习 Tab、会话设置表单（4）
- Chat：工作区空态、Composer 输入区（2；新对话弹层待补）
- Growth：今日/目标/复盘 Tab、任务表单（4）

## 3. Playwright 验收基线（verify_*.cjs 全量）

命令：`node scripts/verify_regression_suite.cjs`（新增，逐脚本超时 180s 并落盘
`<root>/.runtime/qa-s4-verify-results.json`）。

复跑结果（12 个验收脚本，两轮）：

| 轮次 | 结果 |
|---|---|
| 第 1 轮 | 2 PASS / 10 FAIL |
| 第 2 轮 | 3 PASS / 9 FAIL（Edge 抖动项有波动：growth_workflow_ui 由 FAIL→PASS） |

通过：`verify_growth_manager.cjs`、`verify_growth_workflow_ui.cjs`（第 2 轮）、
`verify_n8n_provider_ui.cjs`。

9 个失败分类：

1. **Edge/CDP 启动抖动（环境性，5 个）**：data_protection、english_coach、
   information_intelligence、investment_assistant、memory_shadow_ui ——
   “Headless Edge did not expose a page target” / “Timed out: Page.enable”，
   与本机 Edge headless 偶发退出一致（截图脚本已加重试，验收脚本未加）。
2. **离线依赖门控（3 个）**：semantic_memory_ui（需 Ollama embedding）、
   research_workflow_ui（需本地模型渲染）、approval_center_ui（无待审批项，
   需先构造 R2/DeepSeek 审批流程）。
3. **疑似选择器漂移（1 个，待复核）**：memory_paid_confirmation 等待按钮
   `新建对话`，当前 chat 页面按钮为 `新的对话` —— 需 Tech Lead 裁决是脚本
   选择器过时还是拆分改动文案。

> 结论：本机环境（无 Docker/PG/Ollama/n8n）下验收基线为 3 PASS + 9 FAIL
> （8 环境性 + 1 待复核），无证据指向拆分引入的确定性回归；完整验收需在
> 全栈环境（start.ps1 起 PG/n8n/Ollama）复跑。

## 4. 对比结论口径（拆分后）

- **重要顺序声明**：基线拍摄时 Frontend Evolution 的拆分**已在共享工作区落地**
  （未提交）——四个巨型组件已薄壳化，`components/{investment,chat,english,growth}/`
  与 `lib/api/` 子模块已存在（`git status` 证据）。因此本次基线为
  **拆分后未提交状态快照**，预拆分基线因并行竞态无法补拍（已在
  `evals/visual-baselines/README.md` 明示，并提供 worktree 重建方案）。
- 拆分合并/进一步改动后：重跑 `node scripts/verify_visual_baseline.cjs
  --capture-only`，对比 `manifest.json` 中 20 张 PNG 的 sha256；**任一非零
  差异即拒收**。
- 拆分层静态断言已补：`node scripts/verify_api_boundary.cjs` —— 114 个组件
  文件 0 违规直连 `lib/api/` 子模块（83 个经冻结的 `@/lib/api` 索引导入）。

## 5. 门禁确认

```text
scripts/check.ps1 → exit 0（ruff + pytest 313+2 + security + prompt eval +
backup-drill dry-run + web typecheck + web lint）
```

前端拆分代码下 typecheck/lint 全绿；后端 pytest 不受影响（313 passed, 2 skipped）。

## 6. 覆盖缺口清单

1. 预拆分基线（#2 空态、#7 分红、#13 错误条等）需空库/专用环境补拍。
2. 全栈验收复跑（PG + Ollama + n8n 就绪）后回填 verify 套件 9 个 FAIL 中
   的环境性项。
3. `memory_paid_confirmation` 选择器漂移待 Tech Lead 裁决。
4. Chat 新对话弹层、交易表单分红切换截图待补。

## 7. 风险说明

1. **并行竞态**：拆分先于基线落地，预拆分对比缺失（已文档化 + worktree 方案）。
2. **Edge headless 不稳定**：本机 CDP 启动偶发失败，验收脚本无重试，建议
   Frontend Evolution 合入前在稳定环境复跑或为脚本补重试。
3. `next dev` 数据页卡 loading 为环境现象（生产构建正常），排查方向为
   Turbopack/HMR，非拆分回归证据。
4. 种子数据（.runtime/qa-s4.db）为临时 QA 库；复拍前需重跑 bootstrap + seed。

## 8. 本轮改动清单（QA Owned）

| 文件 | 说明 |
|---|---|
| `scripts/verify_visual_baseline.cjs` | 截图基线脚本（播种 + 20 状态拍摄 + manifest） |
| `scripts/verify_regression_suite.cjs` | verify_*.cjs 批量执行器（超时 + 结果落盘） |
| `scripts/verify_api_boundary.cjs` | 拆分层静态断言（组件不直连 lib/api 子模块） |
| `evals/visual-baselines/` | 20 PNG + manifest.json + README |
| `evals/QA_SPRINT4_HANDOFF.md` | 本交接 |
| `.runtime/qa-s4-*`（临时） | bootstrap/探针/启动包装（gitignored，不进库） |

## 9. AI 辅助记录

全程本地执行：未调用外部模型、无 DeepSeek 费用、未发送个人数据；未修改
产品代码；未执行 git 写操作；截图/断言均确定性可复现。
