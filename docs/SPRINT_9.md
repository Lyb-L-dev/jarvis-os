# Sprint 9：稳定性与数据保护

## Sprint 目标

在不安装 OpenClaw 的前提下，先保护 Jarvis 已经积累的个人数据，并确认现有核心模块可以持续协作：

```text
情报 → 成长任务
英语错误 → 间隔复习 → 桌面与语音提醒
投资情报 → 持仓关联 → 事实复盘
云端异常 → 本地 Ollama
PostgreSQL → 自动备份 → 临时数据库恢复验证
```

## 已完成：OpenClaw 安全决定

- [x] 不在主力 Windows 电脑安装 OpenClaw；
- [x] 不承诺无法验证的“绝对安全”；
- [x] 微信通道不再阻塞 Jarvis 核心开发；
- [x] 虚拟机隔离、低权限、插件审计、最小 Channel API 和可回滚快照成为恢复开发的前置门槛；
- [x] OpenClaw 不能直接获得 Jarvis 数据库、项目目录、Docker Socket、主机密钥或任意执行权限。

详细门槛见 `docs/SPRINT_8.md`。

## 已完成：自动备份与可恢复性

- [x] Jarvis 启动时同时启动独立备份 Worker；
- [x] 每小时检查一次，约每 20 小时创建 PostgreSQL custom-format 备份；
- [x] 备份写入 `backups/`，默认最多保留 30 份；
- [x] 生成前后使用临时文件和原子移动，避免半成品恢复点；
- [x] 每份恢复点保存 SHA-256、大小、创建时间和 Alembic 数据结构版本；
- [x] 创建时使用 `pg_restore --list` 校验归档结构；
- [x] 可把备份恢复到独立临时数据库，验证表数量和数据结构版本；
- [x] 设置页可以查看、立即创建和验证恢复点；
- [x] 网页不提供覆盖恢复按钮；
- [x] 正式恢复要求 Jarvis API 已停止、完整确认文字、预先验证和恢复前安全备份；
- [x] 正式恢复先进入临时数据库，再交换数据库名称并保留原数据库。

主要端点：

```text
GET  /api/v1/system/backups
POST /api/v1/system/backups
POST /api/v1/system/backups/{backup_id}/verify
```

维护脚本：

```text
scripts/backup.ps1
scripts/backup-worker.ps1
scripts/verify-backup.ps1
scripts/restore-backup.ps1
```

## 已完成：模型运行时故障降级

- [x] MiMo 或 DeepSeek 已被选中但运行失败时，自动尝试一次本地 Ollama；
- [x] 流式回答只有在云端尚未输出正文时才切换本地；
- [x] 已输出部分正文后不混入另一个模型的回答；
- [x] 界面收到新的路由信息，不静默伪装成原 Provider；
- [x] 调用审计同时保留云端错误和实际成功的本地 Provider；
- [x] 不会因为 MiMo 失败自动产生 DeepSeek 费用；
- [x] DeepSeek 继续要求用户明确选择并逐次确认。

## 跨模块验收

- [x] 情报：官方白名单来源生成分层简报，收藏与转成长任务成功；
- [x] 英语：会话、确定性纠错、用户确认、错题复习、下次安排和桌面/语音提醒成功；
- [x] 投资：资产、持仓、分红、投资理由、关联情报和事实复盘成功；
- [x] 所有验收临时数据已清理；
- [x] 三条浏览器闭环的控制台错误、页面异常、失败请求和错误响应均为 0。

## 本轮验收结果

- 自动测试：47 项通过；
- Ruff、TypeScript、ESLint：通过；
- Alembic：`20260729_0010 (head)`，没有遗漏的数据结构变更；
- 真实恢复验证：35 张表，数据结构 `20260729_0010`；
- 设置页显示 2 份本地恢复点，两份均已通过恢复验证；
- 数据保护浏览器验收：控制台错误、页面异常、失败请求和错误响应均为 0；
- 验收截图：
  - `artifacts/data-protection-verified.png`
  - `artifacts/intelligence-brief-verified.png`
  - `artifacts/english-coach-verified.png`
  - `artifacts/investment-positions-verified.png`

## 已知边界

- `backups/` 当前与数据库位于同一台电脑；它可以防止误操作和逻辑损坏，不能抵御整块硬盘损坏；
- 后续应由用户选择移动硬盘目录，再增加加密的异盘副本；
- 恢复脚本已经实现安全门槛，但本轮没有对当前正式数据库执行破坏性覆盖恢复；
- OpenClaw、Obsidian 和 n8n 都不进入当前运行依赖。

## 下一阶段

- [ ] Sprint 10：完整发布验收、安全检查、恢复演练说明和作品集材料；
- [ ] 在不改变现有数据的前提下整理可交付版本；
- [ ] OpenClaw 继续延期，不作为 Sprint 10 的完成条件。
