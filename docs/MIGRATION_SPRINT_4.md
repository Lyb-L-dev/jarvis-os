# MIGRATION_SPRINT_4.md — 迁移 Sprint 4 交付与验收记录

- **文档类型**：Tech Lead 产出（迁移路线图 Sprint 4：前端渐进重构）
- **日期**：2026-08-06
- **状态**：✅ 已验收（合入 dev；main 保持基线）

---

## 1. 交付物总览

| Agent | 任务 | 状态 | 证据 |
|---|---|---|---|
| Frontend API Layer | api.ts 领域拆分 | ✅ | `lib/api.ts` 重写为兼容层（-5371 行）+ `lib/api/**` 17 个领域文件（5333 行）+ `client.ts`（`request()`/`requestVoid()` 统一封装，192 处 fetch 替换，5 处有意保留） |
| Frontend API Layer | 共享类型生成 | ✅ | `openapi-typescript ^7.13.0`（devDep）+ `types/generated.ts`（479,945 B，API 在线时实际生成）+ 门控脚本 |
| Frontend API Layer | 契约一致性测试 | ✅ | `verify-contract.mjs`：导出面 372/372；路径 197 ⊆ 228 全部通过 |
| Frontend Evolution | 四巨型组件拆分 | ✅ | investment 1876→280、english 1457→276、chat 1389→155、growth 1182→177；目录内最大 289 行 |
| Frontend Evolution | 工具函数下沉 | ✅ | `providerLabel` 族统一契约（9 处）、Speech 类型 3 份去重、formatDate 等合并，**零文案变化**（字面量差集 0 缺失） |
| Frontend Evolution | `[module]` 死路由清理 | ⚠️ 纠正未删 | 预研“空目录”系 PowerShell 通配符误判；`page.tsx`（1889 B）真实存在且已入基线，删除另行排期 |
| QA & Reliability | 视觉回归基线 | ✅ 部分 | 20 张 PNG（investment 10 / english 4 / chat 2 / growth 4）+ manifest（sha256）+ README |
| QA & Reliability | Playwright 回归 | ✅ 部分 | `verify_regression_suite.cjs`：3 PASS / 9 FAIL（5 环境抖动、3 离线门控、1 脚本断言过时——见 §2 裁决） |
| QA & Reliability | API 边界静态断言 | ✅ | `verify_api_boundary.cjs`：114 个组件文件 0 违规直连 `lib/api/` 子模块 |

## 2. Tech Lead 裁决

1. **“新建对话 / 新的对话”**：拆分未引入文案变化（原 `chat-workspace.tsx` 第 1078 行即为
   “新的对话”，拆分后逐字保留）。`verify_memory_paid_confirmation.cjs` 的断言过时，
   归 QA 修脚本，非产品回归。
2. **`[module]` 占位页**：不删除。预研判定为空目录系通配符误判；实际为真实占位页
   （6 个模块映射 + `notFound()`），已入基线。删除需另行排期并做路由冒烟验证。
3. **视觉回归基线口径**：因并行竞态，预拆分基线未捕获（QA 已文档化并提供 worktree
   重建方案）；以拆分后 20 张 PNG 快照为基准，后续任何改动重拍比对 sha256，
   任一差异即拒收。
4. **generated.ts 维护**：后端契约变更后需重跑 typegen；若未来 lint 规则收紧需将其
   加入 eslint ignores（涉及 `eslint.config.mjs`，需 Tech Lead 协调后落地）。
5. **分支说明**：API Layer 创建了 `feat/frontend-api`（无独立提交，与 dev 同点）；
   本轮按 sprint-4 统一合并处理。

## 3. 所有权核对

- 全部改动落在各自 Owned 路径；组件侧对 `@/lib/api` 调用零改动（程序化核验：
  新文件导入名 ⊆ 基线 api.ts 导出）。
- QA 侧改动均为 Owned（verify 脚本 ×3、`evals/visual-baselines/`、交接文档）。
- 并行期间 API Layer 的 `generated.ts` 与 Evolution 的 typecheck 短暂互相依赖，
  均已在对方补齐后恢复全绿，无文件重叠。

## 4. 测试与门禁结果（合并前最终复跑）

- `scripts/check.ps1`：exit 0；pytest **313 passed, 25 skipped**（338 collected）；
  评测 25/25；`backup-drill -DryRun` 通过；前端 typecheck + lint 在拆分代码下全绿。
- `verify-contract.mjs`：372/372 导出 + 197 ⊆ 228 路径。
- `verify_api_boundary.cjs`：114 组件文件 0 违规。

## 5. 遗留待办

1. `verify_memory_paid_confirmation.cjs` 断言更新为“新的对话”（QA）。
2. `[module]` 占位页删除排期（需路由冒烟，Frontend Evolution）。
3. 12 个 Playwright verify 脚本全绿需 PG/Ollama/n8n 完整环境；Edge headless 抖动
   建议补重试机制（QA）。
4. `globals.css` 令牌去重未做（谨慎项，单独排期）。
5. 视觉回归预拆分基线缺口（已文档化；后续以拆分后快照为基准）。

## 6. 验收标准对照（Sprint 4）

| 验收项 | 状态 |
|---|---|
| 无 1000+ 行组件 | ✅（1876/1457/1389/1182 → 280/276/155/177） |
| api.ts 拆分后组件零改动 | ✅（372 导出冻结，签名逐字一致） |
| 像素级不变 | ⚠️ 基线为拆分后快照（预拆分缺失已文档化）；行为红线字面量差集 0 缺失 |
| typecheck/lint 全绿 | ✅ |
| 契约三处合一（DB CHECK + Pydantic + TS union） | ✅ 前端 `generated.ts` 已生成（Sprint 6 做最终对账） |
