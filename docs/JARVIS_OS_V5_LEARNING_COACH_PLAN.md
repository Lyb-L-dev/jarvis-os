# JARVIS_OS_V5_PLAN — 学习教练（Learning Coach）开发计划

> 版本：v0.1（2026-08-29）  
> 状态：V5-1 契约冻结，开发进行中  
> 上游文档：[未来愿景与优先级](./JARVIS_OS_FUTURE_VISION_NOTES.md)（P1–P4）、[V4 计划](./JARVIS_OS_V4_PLAN.md)  
> 任务跟踪：GitHub Issues（本文件只冻结契约与边界）

V5 是「自适应日程与学习教练」方向的版本代号，对应未来愿景的 P1–P4 优先级，映射为：

| 阶段 | 内容 | 对应愿景优先级 | 状态 |
| --- | --- | --- | --- |
| V5-1 | 掌握度模型 + 验收闭环（后端第一片） | P1 | ✅ 后端+前端+判分/出题影子（见交付记录 V5-1～V5-1.7）；pyBKT 校准数据门控中 |
| V5-2 | 自适应日程（作息建模、每日计划生成、Minimum Day） | P2 | ✅ 后端（V5-2a，schedule_rule_v1 写入成长账本）；前端今日任务页为 V5-2b |
| V5-3 | 上下文通知与当前任务页 | P3 | 未开始 |
| V5-4 | 反馈闭环与复盘 | P4 | 未开始 |

V5 不阻塞也不依赖 V4 Stable 门禁的时间顺序，但不复用其未提交改动；V5 全部工作默认关闭（Feature Flag），Stable 发布纪律不变。

## 1. V5-1 范围与不在范围内

**范围内**：知识模块、掌握度状态、验收会话与题目、掌握度证据流、FSRS 间隔复习卡与复习日志、规则判分（rule_v1）、模板出题（template_v1）、全部 `/api/v1/learning/*` 接口与测试。

**不在范围内（后续阶段）**：pyBKT 实际拟合（先由证据流攒数据，校准期再启用）；genanki 导出（可选互操作）；自适应日程；任何主动提醒；对外部资源 URL 的抓取。判分影子（V5-1.5）、前端第一版（V5-1.6）与出题影子（V5-1.7）已于 2026-08-29 交付，见交付记录；LLM 出题默认仍为模板（template_v1），影子候选需人工采纳后经 `include_accepted` 才进入验收。

## 2. 不重复造轮子（复用决策）

| 能力 | 决策 | 依据 |
| --- | --- | --- |
| 间隔复习调度 | 引入 `fsrs`（py-fsrs，MIT），锁定 `>=5.1,<6`；实测 5.1.3 API：`Scheduler.review_card(card, rating) -> (card, review_log)`、`card.get_retrievability()`、`card.to_dict()/from_dict()` | Anki 现行算法，禁止自研调度器；retrievability 同时作为掌握度证据 |
| 掌握度估计 | 本阶段用 rule_v1（可解释加权），**不引入 pyBKT 运行时**；证据表已按 BKT 需要记录（skill/module + 正误序列 + 时间戳），校准期再引入 pyBKT（MIT）做影子对比 | pyBKT 依赖较重；先攒校准数据，避免未校准就改变展示口径 |
| 验收门控范式 | 借鉴 DeepTutor（Apache-2.0）的 Mastery Path 硬门控设计，不引入其代码 | 平台类项目不整体引入 |
| 错题导出 | 后续可加 genanki（MIT）导出 Anki 卡组 | 互操作出口，非本阶段 |

## 3. 数据契约（PostgreSQL 为唯一事实源）

新增 7 张表（迁移 `20260829_0038`，遵循既有命名约定与 `UUIDPrimaryKeyMixin/TimestampMixin`）：

1. `learning_modules` — 知识模块：`user_id`、`name`、`slug`（user+slug 唯一）、`description`、`parent_id`（自引用，支持子技能）、`status`（active/paused/archived）、`core_concepts`（JSON 字符串数组，模板出题的输入）、`sort_index`。
2. `learning_mastery_states` — 当前掌握度（物化，可重建）：`module_id`（唯一）、`mastery`（0–1）、`confidence`（0–1）、`method`（`rule_v1`）、`evidence_count`、`computed_at`。
3. `learning_verifications` — 验收会话：`module_id`、`status`（in_progress/completed/aborted）、`mode`（`template_v1`）、`item_count`、`completed_at`。
4. `learning_verification_items` — 验收题目：`verification_id`、`module_id`、`level`（1–4）、`prompt`、`expected_points`（JSON 字符串数组）、`answer`、`grade`（green/yellow/red）、`grader`（`rule_v1`）、`grade_score`、`feedback`、`answered_at`。
5. `learning_mastery_observations` — 掌握度证据（append-only）：`module_id`、`source`（verification/practice/review/interview/manual）、`grade`、`score`、`weight`、`reference_type`、`reference_id`、`detail`（JSON）、`created_at`。
6. `learning_review_cards` — FSRS 复习卡：`module_id`、`verification_item_id`（可空、唯一，错题来源）、`question`、`answer_hints`（JSON）、`fsrs_card`（`Card.to_dict()`）、`state`（new/learning/review/relearning）、`due_at`、`last_review_at`、`reps`、`lapses`、`retrievability`。
7. `learning_review_logs` — 复习日志（append-only）：`card_id`、`rating`（1–4）、`review_log`（`ReviewLog.to_dict()`）、`reviewed_at`。

掌握度只允许从证据流重建（`learning_mastery_states` 是缓存，不是事实源）；删除模块级联清理其状态、验收、证据、复习卡。

## 4. API 契约（`/api/v1/learning`，全部需要 `v5_learning_coach_enabled`）

| 方法与路径 | 语义 |
| --- | --- |
| `GET /learning/readiness` | `{enabled, reason}`；Flag 关闭时 `reason=feature_disabled`（不读用户数据） |
| `GET /learning/modules` | 模块列表 + 掌握度摘要（`mastery_percent`、`confidence`、`evidence_count`） |
| `POST /learning/modules` | 创建模块：`name`、`description?`、`parent_id?`、`core_concepts: string[]` |
| `GET /learning/modules/{id}` | 详情 + 最近证据 + 到期复习卡数 |
| `POST /learning/modules/{id}/recompute` | 从证据流重算掌握度 |
| `POST /learning/verifications` | 开始验收：`module_id`、`levels?: int[]`（默认 1–4）；模板出题；已有进行中的会话返回 409 |
| `GET /learning/verifications/{id}` | 会话与全部题目（含判分结果） |
| `POST /learning/verifications/{id}/items/{item_id}/answer` | 提交回答：`answer: string`；rule_v1 判分 → 写证据 → 黄/红自动建复习卡 → 重算掌握度 |
| `GET /learning/review/queue` | 到期复习卡（`due_at <= now`，按到期时间排序，`limit` 默认 20） |
| `POST /learning/review/cards/{id}/review` | 提交复习评级：`rating: 1–4`（FSRS Again/Hard/Good/Easy）；写复习日志 + 证据 + 重算掌握度 |
| `GET /learning/mastery` | 全模块掌握度汇总（供仪表盘/未来计划生成读取） |
| `POST /learning/verifications/{id}/items/{item_id}/shadow-grading` | V5-1.5：本地 LLM 影子判分一条已回答题目（幂等；每题一行证据，失败也落库） |
| `GET /learning/grader-shadow/summary` | V5-1.5：影子一致性汇总（total/agreed/disagreed/failed/agreement_rate） |

错误语义：Flag 关闭 → `403 v5_learning_coach_disabled`；对象不存在 → 404；重复开始验收 / 回答已答题目 → 409；出题无可用核心概念 → 422。

## 5. 算法契约（可解释，先校准再升级）

**rule_v1 判分**：把 `expected_points` 逐条与回答做关键词覆盖（子串 + 词匹配），`score = 覆盖点数/总点数`；`score ≥ 0.8` 且回答长度达标 → green；`≥ 0.4` → yellow；否则 red；`feedback` 列出未覆盖点。判分完全离线、可复现，后续 LLM 判分（V5-1.5）必须与 rule_v1 并行影子运行后再接管。

**rule_v1 掌握度**：对证据做半衰期 14 天的时间衰减加权（green=1.0、yellow=0.6、red=0.0；来源权重 verification/interview=1.0、practice=0.8、review=0.6），再与该模块复习卡的 FSRS retrievability 均值按 0.7/0.3 融合；`confidence = min(1, 证据数/8)`。无证据时 mastery=0、confidence=0。百分比展示 = mastery×100，保留 1 位小数；证据不足 3 条时 API 返回 `low_confidence=true`。

**FSRS 映射**：验收黄/红题目自动建卡（新卡 state=new）；复习评级 1–4 直通 FSRS Rating；红/黄题目答对复习（Good 及以上）同样回流为 review 证据。

## 6. 验收与回滚

- pytest：模块 CRUD、验收流（出题数量=levels×每级题数、判分、完成状态）、弱回答建卡与到期队列、复习调度推进 due、掌握度重算、Flag 关闭 403、未开始 onboarding 409。
- 迁移 `alembic upgrade head` / `downgrade -1` 双向可执行；测试环境 SQLite `create_all` 与生产 PG 迁移不漂移（迁移列与模型一一对应）。
- 回滚：关闭 `v5_learning_coach_enabled` 即回到原状态；迁移可 downgrade；其他子系统零改动（不触碰 chat/growth/通知）。

## 7. 交付纪律

完成 V5-1 后：交付记录写入 `docs/JARVIS_OS_V5_DELIVERY_LOG.md`（新建）；`check.ps1` 与 ruff 通过；本文件状态改为 V5-1 ✅，并冻结 V5-2 的契约草案。实施边界沿用愿景记录：教练身份不扩大 R2/R3 权限，云端模型调用遵守逐次授权，主动提醒遵守静默与去重纪律（V5-3 起适用）。

## 8. V5-2 契约冻结：自适应日程（2026-08-29）

### 范围

作息建模（weekday 时间块）、规则驱动的每日计划生成（schedule_rule_v1）、Minimum Day 降级、
把生成的任务写入成长中心既有账本。**不在范围**：LLM 计划生成（先规则后影子）、前端今日任务页
（V5-2b）、主动提醒/通知（V5-3）、外部资源抓取。

### 账本纪律（不重复造轮子的核心）

- 任务与计时**只写成长中心**：`GrowthTask`（`source_type="learning_coach"`、`planned_date`、
  `estimated_minutes`）+ `DailyPlan`（按 user+date 唯一，追加/新建 `task_ids`，status=draft 才可追加）；
- 学习域只新增两张教练自有表：`learning_schedule_blocks`（weekday 作息块：kind=study/practice/career/routine）、
  `learning_day_logs`（当天模式 normal/minimum_day/rest + planned_task_ids + 完成计数，派生缓存可重建）；
- 不新建第二套任务表、不复制计时字段。

### 生成规则（schedule_rule_v1，可解释）

1. 读取该 weekday 的 active 作息块（routine 块只作上下文，不生成任务）；
2. 学习块 → 先插入 FSRS 到期复习任务（如有），再按掌握度**从弱到强**循环选模块
   （标题「推进学习：{module}」，详情带核心概念）；
3. 实践块 → 「项目实践：把 {module} 的 {concept} 用在真实代码里」（取该模块最薄弱概念）；
4. 求职块 → 静态求职动作模板（本阶段不耦合 CareerRadar 数据）；
5. Minimum Day（显式传入，或**昨日 planned>0 且 completed=0 时自动触发**并写明原因）：
   固定三件事——25 分钟核心学习（最弱模块）+ 25 分钟项目实践 + 1 个求职动作；
   目标是不断档，不补偿、不堆积；
6. 预览（preview）零写入；commit 才写 GrowthTask + DailyPlan + learning_day_logs；
   当日已有教练计划 → 409，当日计划已 confirmed → 409。

### API（全部要求 `v5_learning_coach_enabled` 且 `v5_learning_schedule_enabled`）

| 方法与路径 | 语义 |
| --- | --- |
| `GET /learning/schedule/blocks` | 作息块列表（按 weekday+start 排序） |
| `POST /learning/schedule/blocks` | 新建作息块（weekday 0–6，start<end，kind 白名单） |
| `POST /learning/schedule/blocks/{id}/deactivate` | 停用作息块 |
| `POST /learning/schedule/plan/preview` | 生成当日计划草稿（零写入；body: plan_date?、minimum_day?） |
| `POST /learning/schedule/plan/commit` | 提交当日计划（写成长账本 + day log） |
| `GET /learning/schedule/day?date=` | 当日模式、任务完成度（从 GrowthTask 状态重算） |

### 验收与回滚

- pytest：作息块 CRUD 校验、预览选弱模块、Minimum Day 三件事、昨日空执行自动降级、
  commit 写账本与 409、day 完成度重算；
- 回滚：关闭 `v5_learning_schedule_enabled`；已生成的任务留在成长中心由用户自行处理（教练不删除用户任务）；
- 时区：日期默认 `local_today()`（Asia/Shanghai，复用 growth 既有约定）。
