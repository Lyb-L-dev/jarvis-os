# Sprint 4 交接说明 — 前端巨型组件拆分（Frontend Evolution Agent）

**日期**：2026-08-06 ｜ **归属**：Frontend Evolution Agent → Tech Lead 归档
**红线遵守**：未修改 `lib/api.ts`、`types/**`、`apps/api/**`、`apps/desktop/**`、`docs/**`；未新增依赖；未执行 git 操作（改动全部留在工作区，等 Tech Lead 按 ownership 分拣合并）。组件侧对 `@/lib/api` 的调用零改动（已程序化核验：新文件导入名全部存在于基线 api.ts 导出中）。

---

## 1. 拆分清单（前后行数）

| 文件 | 拆分前 | 拆分后 | 新增领域目录 |
|---|---|---|---|
| investment-center.tsx | 1876 | **280** | `components/investment/`（17 文件 / 2237 行） |
| english-coach.tsx | 1457 | **276** | `components/english/`（11 文件 / 1734 行） |
| chat-workspace.tsx | 1389 | **155** | `components/chat/`（新增 9 文件 + 既有 Message.tsx） |
| growth-center.tsx | 1182 | **177** | `components/growth/`（12 文件 / 1471 行） |

验收"无 1000+ 行组件"达成；目录内最大文件 289 行（investment-theses.tsx）。

**investment**：5 hooks（use-investment-data / use-investment-asset-form / use-investment-transaction-form / use-investment-thesis-form / use-investment-reviews）+ 11 子组件（header / telemetry / asset-form / transaction-form / stats / currency-summary / positions / transactions / theses / news / reviews）+ investment-utils。

**english**：use-english-collections / use-english-conversation / use-english-setup / use-english-mistake-book / use-english-reviews + 5 视图（session-rail / session-setup / conversation / mistake-book / review-view）+ english-utils（含 runAction/refreshAfterMistakeAction 共享辅助）。

**chat**：use-conversation-list / use-chat-stream / use-dictation + 5 视图（session-drawer / workspace-header / message-flow / composer-region / workspace-inspector）+ chat-utils（modeOptions、temporary 消息构建、displayAgentId、savedAgentRouting、deepSeekConfirmationText、refreshConversationUntil 等）。

**growth**：use-growth-data / use-task-form / use-goal-form / use-task-actions + 6 视图（task-card / task-form / today-view / milestone-row / goal-card / goals-view / review-view）+ growth-utils（runAction 带自动 refresh 语义）。

---

## 2. 行为红线核对表

| 红线项 | 处置 | 证据 |
|---|---|---|
| window.confirm/prompt 逐字保留 | 逐条随 handler 原样搬迁 | 四文件字符串字面量差集核验：**缺失 0**（唯一差异项来自共享 utils 常量，渲染等价） |
| 全局 busy 互斥 | investment 保留顶层 boolean busy；english/growth 保留 `string | null` 按 key 互斥；chat 保留 sending 等独立布尔 | 组件均从主组件接收 busy |
| 表单保存后全量 load()/refresh() 链路 | investment `saveAsset/saveTransaction/saveThesis` 末尾 `await load()`；growth runAction 内固定 `await refresh()`；english 各操作后 refreshCollections | hooks 内逐行保留 |
| editPosition 的 setTab+scrollTo | 从 hook 剥离后在主组件 wrapper 中复原：`editPosition(position); setTab("positions"); window.scrollTo(...)`；editTransaction 同法 | investment-center.tsx wrapper |
| SSE 乐观更新（chat） | submitMessage/regenerateMessage 的 onMeta/onDelta/onDone、pending/regenerating 消息合并、停止双通道（cancelChatStream+abort）原样移植 | use-chat-stream.ts |
| deepSeekConfirmationText + 付费确认流程（原 438-442/655-659） | 文本与 `window.confirm` + `paid_call_confirmed` 逻辑逐字保留 | chat-utils.ts + use-chat-stream.ts |
| createGrowthTask 跨域依赖（原 :847） | 保留在 use-chat-stream.convertMessageToTask，**未消除**，待架构评审 | use-chat-stream.ts |
| 挂载加载时序 | investment/english/growth 的 setTimeout(0)+AbortController+Promise.all 保留；investment 表单日期默认值由"mount effect 写入"改为 `useState(today())` 初始化——可见行为等价（加载屏期间表单不可见） | 各 data hook |

---

## 3. 工具函数下沉清单（lib/utils.ts）

| 工具 | 处置 |
|---|---|
| providerLabel 族（9 处语义各异） | 统一契约：`providerDisplayNames`（本地 Qwen）、`providerLabel(provider,{fallback})`、`providerBadge`（大写徽标）、`providerTitle`（dashboard 标题大小写）、`providerPlainLabels`（Ollama）。9 处调用点全部改为共享实现；**tablet-terminal 的 "LOCAL QWEN" 与 Message 的 "LOCAL · QWEN" 存在差异，已单独保留 wrapper 确保文案逐字不变** |
| SpeechResultEvent / SpeechRecognitionLike / SpeechRecognitionConstructor（3 份重复） | 下沉 utils（isFinal 改可选以兼容 chat 版本）；english/chat/tablet 三处本地副本删除 |
| formatDate（4 处差异实现） | 对齐合并：date-only 版→utils `formatDate`（growth 用）；medium+short 版→utils `formatDateTimeMedium`（data-protection/knowledge 用，fallback 参数保留各自文案）；dashboard 的 Date 输入版本签名不兼容，保留本地并在 §5 说明 |
| formatDateTime（2 处） | 合并为 utils `formatDateTime(value, fallback)`；english 传 "尚未安排"、intelligence 用默认 "尚未刷新" |
| formatNumber（2 处逐字重复） / splitLines（2 处） / today / localDateString | 全部下沉 utils；investment-utils 改为 re-export |

下沉过程零文案变化（见 §2 字面量核验）。

---

## 4. `[module]` 死路由——重要修正（未删除）

预研判定"空目录"系 **PowerShell 通配符误判**：`Get-ChildItem -Path "...\[module]"` 会把 `[module]` 当作字符类，实际列的是其他目录。用 `-LiteralPath` 复核：

- `apps/web/src/app/[module]/page.tsx` **存在**（1889 B，Sprint 2-7 占位页，含 6 个模块的占位映射 + `notFound()`），且**已纳入 git 基线**（`git show HEAD:...` 可读）。
- 22 个 app 目录全部有 page.tsx，**没有空目录**。

因任务清理项的前提（空目录）不成立，且删除 page.tsx 属于路由级行为变更，本轮**未删除**。建议 Tech Lead 决策：该占位页 6 个映射名（chat/growth/english/intelligence/investment/memory）均已被静态路由覆盖，实际不可达，可另行排期删除；但需路由冒烟验证，不应按"空目录清理"处理。

---

## 5. 验收结果

| 项 | 结果 |
|---|---|
| npm run typecheck | **exit 0**（基线通过；中途一度被并行 API Layer 未完成的 `types/generated.ts` 阻断，其补齐后恢复全绿） |
| npm run lint | **exit 0**（我方范围 `components/** + lib/utils.ts + app/**` 独立跑测亦为 0 告警；早前 lint 曾报 API Layer 的 `lib/api/contract/verify-contract.cjs` require 错误，已随其修复消失） |
| 文案/className/placeholder/aria-label/title 逐字核验 | 四文件缺失均 0（english 有 6 项经核实的假阳性：源自 utils 共享常量与 formatDateTime 参数） |
| api.ts 导出面 | 新文件导入名 ⊆ HEAD api.ts 导出，**调用路径零改动** |
| 视觉回归截图 | **待 QA 拍摄比对**（本 Agent 无截图基线；已提供投资 16 项清单来源：预研 §1.4，现按行号映射到新文件） |

---

## 6. 风险与协作观察

1. **跨 Agent 依赖**：`src/types/generated.ts`、`src/lib/api/**`、`package.json` 均由并行中的 Frontend API Layer Agent 改动，其未完成时会短暂阻断 typecheck；我方已确认未触碰这些文件。
2. **[module] 误判**已纠正，未造成路由删除（若按原指令执行将删除一个真实页面文件）。
3. **globals.css 令牌去重**为可选且谨慎项，本轮未做（避免与并行改动叠加风险），建议后续单独排期。
4. 拆分后 hooks 通过参数注入 setter/feedback，组件为纯展示；行为等价依赖 §2 核对表，最终以 QA Playwright diff 为准。
5. 工作区改动未提交（含并行 Agent 的文件混在同一工作树），需 Tech Lead 按 FILE_OWNERSHIP 分拣：我方为 `components/**`（新增 4 个领域目录 + 修改 13 个组件文件）+ `lib/utils.ts`。

---

## 7. AI 辅助记录

- 使用模型：本 Agent（默认模型），未调用 DeepSeek，未产生额外费用，未发送私人数据。
- 核验手段：typecheck/lint + 自建只读脚本（git 基线字符串/className 差集、api.ts 导出面比对、PowerShell 通配符陷阱排查），全部只读、无外部写入。