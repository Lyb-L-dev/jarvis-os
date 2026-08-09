# QA V3-1 交接说明（2026-08-07）

## 交付物

| 交付物 | 路径 | 说明 |
|---|---|---|
| 评测集 | `evals/memory-network-eval-set.jsonl` | 36 条标注样本：growth 11（goal 6 / milestone 5）、english 9（mistake 5 / review 4）、intelligence 6（news）、investment 4（thesis）、conversation 4（chat）、memory 2（confirmed_memory） |
| 采纳率脚本 | `scripts/evaluate-memory-adoption.py` | `采纳率 = 确认候选 / (确认+忽略+合并)`，规则（growth/english/intelligence/investment）与 Qwen（conversation/memory）分开统计；默认读 `.env` 的 `DATABASE_URL`，支持 `--db-url` |
| API 契约测试 | `apps/api/tests/test_memory_network.py` | 6 例：flag 默认关 404、结构化抽取幂等、候选生命周期（confirm/ignore/merge）、multi-hop ≤2 hop、cloud_allowed 往返、**迁移 0032 与模型 DDL 零漂移回归** |
| PG 集成用例 | `apps/api/tests/test_pg_integration.py` 追加 | 新表 ORM 插入默认时间戳 + 状态/类型 CHECK 拒绝非法值 |
| 浏览器验收 | `scripts/verify_memory_candidates.cjs` | flag 开：面板渲染、确认后候选移除、零控制台错误；flag 关：面板缺席（静默降级） |

## 验证结果

- 评测集 36 条全部 JSON 合规，覆盖 V3-1 交付契约要求的全部来源类型；
  当前加固口径见 `docs/JARVIS_OS_V3_PLAN.md` §5.4 与 ADR-0012。
- 采纳率脚本真库实测：`rule confirmed=2 ignored=1 decisions=3 adoption_rate=66.7%`，
  pending 候选不计入分母。
- API 契约测试 6/6；PG 集成测试真库 30/30（此前一直 skip，本次在
  `jarvis_v31_test` 可丢弃测试库实跑）。
- 浏览器验收（flag on，临时栈 127.0.0.1:3001/8001）：面板可见、确认实体后
  从候选列表移除、0 控制台错误（V3-0 的 /ui/dialog 404 属预期降级）。
- 门禁：`scripts/check.ps1` exit 0；pytest（api+db+desktop）344 passed /
  30 skipped；ruff 全绿；提示词评测 25/25。

## 真库验证过程中发现并修复的问题

1. **迁移 0032 缺 server_default**：`created_at/updated_at` 在迁移中没有
   `server_default=now()`，PG 插入报 NOT NULL 违反（SQLite 测不出）。
   已修复并应用；新增 DDL 零漂移回归测试锁定（`test_migration_0032_ddl_matches_model_create_all`）。
2. **路由双重前缀**：routes 文件自带 `/memory-network` 前缀 + router.py 再加一层，
   真实 URL 会变成 `/memory-network/memory-network/...`。已按项目惯例去掉
   routes 文件前缀。

## 覆盖缺口（如实标注）

- Qwen 抽取无实跑数据（Ollama 未常驻），`degraded=True` 降级路径由单元测试
  覆盖，采纳率基线先以规则抽取数据起算。
- flag 关闭的浏览器模式未在全新构建上实跑（组件逻辑 + API 404 测试覆盖），
  建议全栈环境就绪后复跑。
- n8n 真实工作流 / Ollama 全栈复跑仍属环境门控。

## AI 辅助记录

全程本地执行；未调用外部模型、无费用、未发送私人数据；未执行 git 写操作
（提交由 Tech Lead 统一执行）。
