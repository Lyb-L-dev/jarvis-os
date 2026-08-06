# BRANCH_STRATEGY.md — Jarvis OS 分支与协作规范

- **文档类型**：Sprint 0 工程地基产物（Tech Lead 产出）
- **日期**：2026-08-06
- **适用范围**：所有参与 Jarvis OS 的 AI Agent 与人工维护者

---

## 1. 分支模型：Branch-per-Domain

本项目为单机本地个人系统，采用**按域分支**而非 Git Flow / Worktree（理由见 `MIGRATION_ROADMAP.md` §2）。

```text
main   ← 始终可运行的生产基线（check.ps1 必须全绿）
 └── dev   ← 集成分支（各 Agent 合并点，Tech Lead 维护）
      ├── feat/backend-platform/
      ├── feat/ai-engineer/
      ├── feat/memory/
      ├── feat/frontend-evolution/
      ├── feat/frontend-api/
      ├── feat/tool-automation/
      └── feat/qa/
```

### 分支命名规则

| 分支 | 命名 | 说明 |
|---|---|---|
| 生产基线 | `main` | 只允许来自 dev 的合并，或紧急修复（`hotfix/*`） |
| 集成 | `dev` | Tech Lead 合并点 |
| 功能 | `feat/<domain>/<summary>` | 如 `feat/backend-platform/uow` |
| 紧急修复 | `hotfix/<summary>` | 直接基于 main，修复后并入 main+dev |

### 规则

1. **feature 分支只能写自己域的文件**（按 `docs/FILE_OWNERSHIP.md`）；
2. **每次提交粒度**：一个逻辑变更（一个任务/一个修复）；
3. **提交信息规范**：`<类型>(<域>): <摘要>`，类型用 `feat`/`fix`/`refactor`/`docs`/`chore`；
4. **合并到 dev 前必须**：跑 `scripts/check.ps1` 全绿 + 通过 Tech Lead 审核；
5. **main 永不直接接收 feature 分支**。

---

## 2. 首次提交与基线

Sprint 0 的首次提交（commit 1，`chore: initial baseline`)是**完整当前代码库**，作为：
- 全部后续 diff 的基准；
- 回滚的锚点；
- 测试基线快照（`scripts/check.ps1` 全绿）的对应版本。

首次提交后：**任何破坏性改动都必须可回滚到该基线**。

---

## 3. 提交前门禁（Gate）

每次提交前（或至少合并到 dev 前）必须通过：

```text
scripts/check.ps1
  ├── ruff check（backend lint）
  ├── pytest（backend tests）
  ├── security-check.ps1（安全门禁）
  ├── evaluate-prompts.py（Prompt 策略评测）
  ├── npm run typecheck（前端类型）
  └── npm run lint（前端 lint）
```

若配置了 Git 钩子（`scripts/install-git-hooks.ps1`），`pre-commit` 钩子会自动执行快检（ruff + typecheck）。**钩子未覆盖完整 check.ps1，完整门禁在合并前由 Tech Lead 执行**。

---

## 4. 合并协议（Tech Lead 执行）

```text
收到合并请求
├── 校验改动只落在 Owned 目录（FILE_OWNERSHIP.md）
├── 校验契约变更已冻结广播（config/schemas/routes）
├── 运行 scripts/check.ps1
├── 运行回归基线（QA 提供）
├── 批准 → 合并到 dev（squash）
└── 拒绝 → 回退 + 附原因
```

---

## 5. 应急处理

- **需要立即回滚**：`git checkout main && git revert <sha>` 或 `git reset --hard <基线sha>`；
- **基线被破坏**：从 `backups/` 或数据库恢复点重建；
- **跨域需要改文件**：提交"变更请求"给 Tech Lead，按 `FILE_OWNERSHIP.md` §7 流程。
