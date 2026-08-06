# Jarvis Sprint 4 视觉回归基线（QA & Reliability）

- **拍摄日期**：2026-08-06
- **环境**：生产构建（`npm run build && npm run start`，端口 3000）+ 后端
  127.0.0.1:8000（SQLite dev 覆盖库，含 QA 种子数据）
- **视口**：1440x900；浏览器：Edge headless（`channel: msedge`）
- **复拍命令**：`node scripts/verify_visual_baseline.cjs --capture-only`
- **对比结论口径**：复拍后对比 `manifest.json` 中每个 PNG 的 sha256；
  任一非零差异即拒收拆分改动。

> ⚠️ 重要顺序说明：本基线拍摄时，Frontend Evolution 的四文件拆分
> （investment/chat/english/growth 子组件 + hooks）**已在共享工作区落地**
> （未提交）。因此本基线为**拆分后（未提交）状态的快照**，而非拆分前。
> 预拆分基线因并行竞态无法补拍（证据：`git status` 显示四个巨型组件已薄壳化、
> `components/{investment,chat,english,growth}/` 与 `lib/api/` 已新增）。
> 拆分合并后如需“拆分前 vs 拆分后”对比，需 Tech Lead 用 `git stash` 或
> worktree 重建 pre-split 环境后补拍（本目录 manifest 仍可作 post-commit 回归基准）。

## 一、investment 16 项截图清单 → 文件映射

| # | 状态（预研 §1.4） | 文件 | 状态 |
|---|---|---|---|
| 1 | 加载屏/初始态 | `investment/01-loading-or-initial.png` | ✅ 已拍（尽力，含头部/Telemetry/统计/币种汇总） |
| 2 | 无资产空态 | — | ⏳ 待补：需空库或种子前补拍 |
| 3 | 持仓卡片（正/负浮动、缺价、目标仓位） | `investment/16a-tab-positions.png` | ✅ 已拍（含 4 持仓卡片） |
| 4 | 未建仓资产卡 | `investment/16a-tab-positions.png` | ✅ 已拍（OBSV 未建仓卡） |
| 5 | 资产表单-新建含初始持仓区 | `investment/05-asset-form-new.png` | ✅ 已拍 |
| 6 | 资产表单-编辑（币种禁用） | `investment/06-asset-form-edit.png` | ✅ 已拍（含 DISABLED 币种字段） |
| 7 | 交易表单-买入/分红切换 | `investment/07-tx-form-buy.png` | ✅ 买入已拍；⏳ 分红切换待补（自定义分段控件） |
| 8 | 交易流水表-有数据/空态 | `investment/16b-tab-transactions.png` | ✅ 有数据已拍；⏳ 空态待补（需空库） |
| 9 | 理由表单 | `investment/09-thesis-form.png` | ✅ 已拍（+ 记录新理由） |
| 10 | 理由列表（当前/历史、云端徽标、失效/关闭） | `investment/16c-tab-theses.png` | ✅ 已拍 |
| 11 | 新闻页（候选/已关联、关联说明） | `investment/16d-tab-news.png` | ✅ 已拍 |
| 12 | 复盘页（空态/草稿/已确认） | `investment/16e-tab-reviews.png` | ✅ 已拍（draft + confirmed） |
| 13 | 错误与提示条 | — | ⏳ 待补：需构造 API 失败（如重复 symbol 409） |
| 14 | 币种汇总多币种 + 缺价警告 | `investment/01-loading-or-initial.png` | ✅ 已拍（USD/CNY + TSLA 缺价） |
| 15 | CommandTelemetry 状态栏 | `investment/01-loading-or-initial.png` | ✅ 已拍 |
| 16 | 五个 Tab 切换态 | `investment/16a..16e-tab-*.png` | ✅ 已拍（持仓/交易/投资理由/关联情报/复盘） |

## 二、english / chat / growth 补拍

| 页面 | 文件 | 状态 |
|---|---|---|
| English-对话训练 Tab | `english/01-tab-practice.png` | ✅ |
| English-错题本 Tab | `english/02-tab-mistakes.png` | ✅ |
| English-今日复习 Tab | `english/03-tab-review.png` | ✅ |
| English-会话设置表单 | `english/04-session-setup-form.png` | ✅ |
| Chat-工作区（空态） | `chat/01-workspace-empty.png` | ✅ |
| Chat-输入区 Composer | `chat/03-composer-state.png` | ✅ |
| Chat-新对话弹层 | — | ⏳ 待补（按钮定位不稳） |
| Growth-今日 Tab | `growth/01-tab-today-empty.png` | ✅ |
| Growth-目标 Tab | `growth/02-tab-goals-empty.png` | ✅ |
| Growth-复盘 Tab | `growth/03-tab-review-empty.png` | ✅ |
| Growth-任务表单 | `growth/04-task-form.png` | ✅ |

## 三、种子数据（可复现）

- 用户 + 3 条新闻：`.runtime/qa-s4-bootstrap.py`（幂等）
- 投资数据（5 资产 / 4 持仓 / 6 交易 / 3 理由 / 2 复盘 / 1 关联新闻）：
  `scripts/verify_visual_baseline.cjs`（`--seed-only` 仅播种）

## 四、环境说明

- `next dev`（Turbopack）下页面数据加载会卡在 loading（仅发出 1/5 数据请求，
  HMR WebSocket 报错）；`npm run build && npm run start` 生产模式正常。
  基线一律以生产构建为准（与 `scripts/start.ps1` 一致）。
- Edge headless 偶发启动即退（CDP 抖动），截图脚本已内置 3 次重试；
  批量验收脚本中受此影响的失败已分类记录。

> 说明：`english/01-tab-practice-empty.png` 与
> `english/02-tab-mistakes-empty.png` 为早期 dev 模式拍摄的旧命名残留，
> 已被 `english/01-tab-practice.png` / `english/02-tab-mistakes.png` 取代，
> 不在 manifest 清单内，对比时以 manifest.json 为准。
