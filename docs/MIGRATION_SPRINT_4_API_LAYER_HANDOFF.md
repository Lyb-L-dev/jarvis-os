全部工作完成，验收通过。以下是 Sprint 4 Frontend API Layer 的完整交接说明。

# Sprint 4 交接说明 — Frontend API Layer（api.ts 拆分与契约生成）

**日期**：2026-08-06 ｜ **归属**：Frontend API Layer Agent → Tech Lead 归档
**分支**：`feat/frontend-api`（任务书写的 `feat/frontend-api/` 尾斜杠非法，git 拒绝，已用最接近合法名）
**红线遵守**：未修改任何 `components/**`、`app/**`、`apps/api/**`、`lib/utils.ts`、`docs/**`；未执行 git 提交（默认约定）；仅创建任务要求的分支。
**必读文档**：已读 `CURRENT_PROJECT_AUDIT.md`（§5 C2/H8）、`JARVIS_TARGET_ARCHITECTURE.md`（G8）、`MULTI_AGENT_TEAM_PLAN.md`（§2.6）、`FILE_OWNERSHIP.md`（§3）、`MIGRATION_ROADMAP.md`（Sprint 4）、`MIGRATION_SPRINT_2_FRONTEND_PRE_STUDY.md`（§6.2 分区锚点）。

---

## 1. 拆分 diff 清单

| 路径 | 类型 | 说明 |
|---|---|---|
| `apps/web/src/lib/api.ts` | 重写（-5371 行） | 兼容层：`export { API_BASE_URL } from "./api/client"` + 17 个 `export *` |
| `apps/web/src/lib/api/client.ts` | 新增（79 行） | 共享基础设施：`API_BASE_URL`、`request<T>()`、`requestVoid()`、`responseError()` |
| `apps/web/src/lib/api/{system,knowledge,chat,memory,growth,english,intelligence,investment,notifications,tools,observatory,career,cost,context,personality,proactive,computer}.ts` | 新增（合计 5333 行） | 17 个领域文件，按后端 router 域一一对应 |
| `apps/web/src/types/generated.ts` | 新增（479,945 字节） | openapi-typescript 实际生成产物（见 §4） |
| `apps/web/package.json` / `package-lock.json` | 依赖变更 | `openapi-typescript ^7.13.0`（devDependencies，非运行时依赖） |
| `apps/web/src/lib/api/contract/verify-contract.mjs` | 新增（181 行） | 契约一致性测试（导出面 + 路径对齐） |
| `apps/web/src/lib/api/contract/expected-exports.json` | 新增 | 冻结的导出签名快照（372 个名字） |
| `apps/web/src/lib/api/typegen/generate-types.mjs` | 新增（66 行） | OpenAPI 类型生成脚本（运行门控） |

各领域文件行数：growth 830 / investment 738 / chat 583 / knowledge 395 / english 383 / memory 326 / system 312 / observatory 299 / tools 226 / notifications 212 / career 163 / cost 115 / proactive 111 / context 81 / computer 66 / personality 61。

## 2. 冻结的导出签名说明

- **372 个导出零变化**：`API_BASE_URL` + 200 个函数 + 171 个类型/接口，全部经兼容层 re-export，组件 `@/lib/api` 具名导入零改动。
- **签名级校验**：200/200 函数签名（含参数与返回类型）与 dev 分支原始文件**逐字一致**（脚本比对，非目测）。
- 内部辅助保持 api.ts 面外：`responseError` 在 client.ts；`consumeChatStream`（SSE）、`memoryAction`、`englishMistakeAction` 留在各自域文件私有。
- 跨域类型引用仅 2 处，已显式 `import type`：chat→context（`ContextAssemblyInfo`）、growth→intelligence（`NewsCategory`），无循环依赖。

## 3. 统一 request() 封装

- 192 处重复 fetch 全部替换为 `request<T>()` / `requestVoid()`（178 + 16）。
- **剩余 5 处 fetch 均为有意保留**：request 内部 2 处；`consumeChatStream`（SSE 流式解析，语义逐字未动）；`downloadUserDataExport`（blob/Content-Disposition）；`getProfile`（404→null 特殊流）。
- `cache: "no-store"` 与 `signal` 按原调用逐处保留；`Content-Type: application/json` 仅在带 body 时设置（与原行为一致）。
- 11 个自定义错误消息函数（如 `Health request failed with ${status}`）通过 `errorMessage` 回调保留原文案，无细节解析差异。

## 4. 类型生成状态

- `openapi-typescript ^7.13.0` 已装入 devDependencies（非运行时依赖）。
- `typegen/generate-types.mjs`：探测 `http://127.0.0.1:8000/openapi.json`；**API 离线 → 输出 `[gated]` 提示并退出 0**（门控就绪，不产出文件）；在线 → 生成 `src/types/generated.ts`。
- 会话中后端 API 中途上线，**已实际跑通并回填** `generated.ts`（479,945 字节，含全部 paths 与 components schemas）。门控路径已单独验证（坏 URL → gated、退出 0、既有产物不受影响）。
- 运行方式：`cd apps/web && node src/lib/api/typegen/generate-types.mjs`（可用 `OPENAPI_URL` 覆盖）。

## 5. 契约一致性测试

- `verify-contract.mjs` 两个断言，运行：`cd apps/web && node src/lib/api/contract/verify-contract.mjs`：
  1. **导出面**：api.ts 公开面与 `expected-exports.json` 快照完全一致 —— **372/372 通过**。
  2. **路径对齐（C2）**：`lib/api/**` 中 **197 个唯一 method+path ⊆ 228 个后端 router 端点** —— 全部通过。含动作动词枚举展开（confirm/reject/master/dispute、start/pause/complete/cancel、read/save/ignore、approve/reject），前端联合类型逐值对后端字面量路由。
- 后端端点解析自 `apps/api/app/api/router.py` 挂载前缀 + 各 routes/*.py 的 router prefix 与装饰器，路径参数统一规范化为 `{}` 通配。

## 6. 验收结果

| 验收项 | 结果 |
|---|---|
| `npm run typecheck` | ✅ 全绿 |
| `npm run lint` | ✅ 0 error（我方文件 0 warning） |
| 组件零改动 | ✅ 我方 diff 仅限 `lib/api.ts`、`lib/api/**`、`types/**`、`package.json`/`package-lock.json` |
| 路径对齐测试 | ✅ 197 ⊆ 228 通过 |
| `generated.ts` | ✅ 已生成（门控亦就绪） |

## 7. 风险说明

- **共享工作树并行**：Evolution Agent 的组件拆分（`components/chat|english|growth|investment/**`、`lib/utils.ts`）在途未提交，非我方改动。验证时其两个在途文件产生 2 个 lint warning（`growth-milestone-row` 的 `busy`、`growth-task-form` 的 `setShowTaskForm`），与 API Layer 无关；我方拆分与签名冻结为并行组件拆分提供了稳定锚点。
- **generated.ts 维护**：后端契约变更后需重跑 typegen；API 离线时门控不更新产物（exit 0，不会误伤 CI）。若未来 lint 规则收紧，generated.ts 可能需要加入 eslint ignores（`eslint.config.mjs` 归 Evolution/QA，需 Tech Lead 协调）。
- **契约测试是单向断言**：只校验前端路径 ⊆ 后端端点；后端新增端点不会被拦截（符合 C2 防漂移目标）。
- **分支名**：任务指定的 `feat/frontend-api/` 以斜杠结尾非法，实际分支为 `feat/frontend-api`。

## 8. AI 辅助记录

- 机械拆分由生成脚本完成（逐字切片 + fetch→request 转换），两轮修复解析器缺陷：fetch 括号深度误入 `if (!response.ok)`、`JSON.stringify` 解包偏移、`Promise<` 起始深度、后端多行 `include_router` 正则。
- 三重校验：导出快照比对、路径对齐、函数签名与 dev 分支逐字比对（200/200）。
- openapi-typescript 7.13 程序化 API 返回 AST 节点数组而非字符串（与文档签名不同），改用官方 CLI（`bin/cli.js`）经子进程调用。
- `npm install` 受沙箱网络限制，经提权批准完成；`rg` 在当前环境被系统拒绝，全程使用 PowerShell `Select-String` / Node / Python 检索。
- 未执行任何 git 提交、push 或分支合并，等待 Tech Lead 按 Sprint 4 流程验收归档。

**一句话总结**：api.ts 已按领域拆为 17 个文件 + 统一 `request()` 封装，兼容层保住 372 个导出签名零变化；契约测试（导出 372/372、路径 197⊆228）通过，typecheck/lint 全绿，`generated.ts` 已随 API 上线实际生成且门控就绪。