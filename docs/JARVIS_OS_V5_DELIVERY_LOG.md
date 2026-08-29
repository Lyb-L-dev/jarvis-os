# JARVIS_OS_V5 交付记录

> 版本：V5-1（学习教练 · 掌握度模型与验收闭环 · 后端第一片）  
> 证据日期：2026-08-29  
> 契约来源：[JARVIS_OS_V5_PLAN.md](./JARVIS_OS_V5_PLAN.md)

## V5-1 · 后端第一片（2026-08-29）

### 已交付

- 数据契约：`learning_modules`、`learning_mastery_states`、`learning_verifications`、
  `learning_verification_items`、`learning_mastery_observations`、`learning_review_cards`、
  `learning_review_logs` 共 7 张表（迁移 `20260829_0038_learning_coach.py`，down_revision `20260813_0037`）；
- 服务层 `app/services/learning.py`：
  - rule_v1 判分（expected_points 关键词覆盖，离线可复现，feedback 列出未覆盖要点）；
  - rule_v1 掌握度（半衰期 14 天时间衰减加权 + FSRS retrievability 0.7/0.3 融合，
    `confidence = min(1, 证据数/8)`，证据 <3 条标记 `low_confidence`）；
  - template_v1 出题（Level 1–4 模板，确定性、离线）；
  - FSRS 间隔复习：`fsrs` 5.1.3（py-fsrs，MIT，锁定 `>=5.1,<6`）；验收黄/红题自动建卡，
    复习评级 1–4 直通 FSRS Rating，复习日志与证据流落库，`reps/lapses` 由日志派生；
- API `/api/v1/learning/*`：readiness、modules CRUD（+recompute）、verifications（开始/查询/答题）、
  review queue / review、mastery report；错误语义 403/404/409/422；
- Feature Flag：`v5_learning_coach_enabled`（默认关闭，`.env.example` 已含条目与说明）。

### 不重复造轮子（复用记录）

- 间隔复习调度：py-fsrs（MIT）——禁止自研调度器；retrievability 作为掌握度证据源；
- pyBKT（MIT）暂不引入运行时：证据表已按 BKT 需要记录（module + 正误序列 + 时间戳），校准期再做影子对比；
- DeepTutor（Apache-2.0）仅借鉴 Mastery Path 硬门控设计，未引入代码。

### 自动化证据（本机，Windows 11 / Python 3.12 venv）

| 证据 | 结果 |
| --- | --- |
| `pytest tests/test_learning_coach.py` | 8 passed（Flag 关闭 403、验收流、弱回答建卡、FSRS 重排期、409/422、slug 唯一、rule_v1 判分分桶） |
| `pytest -q`（apps/api 全量） | 407 passed, 38 skipped；2 failed 为 `test_backup_drill.py` 的 PowerShell 子进程环境问题（`--basetemp` 指向仓库内后复现，与本片改动无关，桌面/CI 环境复测待确认） |
| `ruff check apps/api` | All checks passed |

说明：全套件在沙箱终端下需 `--basetemp` 指向可写目录（默认 `C:\Users\...\Temp\pytest-of-*` 被拒绝访问）。
与 V4 交付日志记录的 385 passed 相比，增加的通过数来自 V4 在途工作区改动与 V5-1 新增测试。

### 真实 PostgreSQL 验证（2026-08-29，容器库 127.0.0.1:5433）

| 验证 | 结果 |
| --- | --- |
| `alembic upgrade head`（0037 → 0038） | 成功；7 张 `learning_*` 表创建，列与模型一一对应 |
| `alembic downgrade -1` → `upgrade head` 往返 | 成功；表随 downgrade 全部移除、re-upgrade 重建，`alembic_version=20260829_0038` |
| 服务层端到端冒烟（临时用户，完成后级联清理） | 验收 4 题全 green → status=completed；弱回答建卡并进入到期队列；复习评级 3 → state=learning、reps=1、复习日志落库；掌握度 100%、confidence=0.5、low_confidence=false |

### 未完成（V5-1 余量，进入前需按计划补齐）

- pyBKT 影子校准与展示口径冻结（依赖先积累答题证据数据）；
- genanki 导出 Anki 卡组（可选互操作）。

## V5-2a · 自适应日程后端（2026-08-29）

契约见 V5 计划 §8（2026-08-29 冻结）。任务与计时只写成长中心账本，学习域不建第二套任务表。

### 已交付

- 迁移 `20260829_0042_learning_schedule.py`：
  - `learning_schedule_blocks`：weekday（0=周一）作息块，kind=study/practice/career/routine，start/end 分钟；
  - `learning_day_logs`：教练侧当日状态（mode=normal/minimum_day/rest、planned_task_ids、完成计数，派生缓存可重建）；
- 服务 `app/services/learning_schedule.py`（schedule_rule_v1，全部可解释）：
  - 作息块 CRUD（校验 weekday 0–6、start<end、kind 白名单）；
  - 预览（零写入）：学习块先插 FSRS 到期复习任务（如有），再按掌握度**从弱到强**循环选模块；
    实践块绑定最薄弱概念；求职块为静态动作模板；
  - **Minimum Day**：显式传入，或昨日 planned>0 且 completed=0 时**自动触发**（不论昨日是否已是
    Minimum Day——未执行就继续降档，直到重新执行）；固定 25 分钟核心学习 + 25 分钟项目实践 +
    1 个求职动作；目标是不断档，不补偿不堆积；
  - commit：为每项创建 `GrowthTask`（`source_type="learning_coach"`、planned_date、estimated_minutes），
    新建或**追加**当日 `DailyPlan`（仅 draft 可追加，confirmed → 409），并写 day log；
    重复提交 409；无可用作息块 422；
  - day status：完成度从 GrowthTask 状态实时重算并回写缓存。
- API（`v5_learning_schedule_enabled` 子 Flag，默认关闭；父 Flag 关闭时同样不可达）：
  `GET/POST /learning/schedule/blocks`、`POST /learning/schedule/blocks/{id}/deactivate`、
  `POST /learning/schedule/plan/preview`、`POST /learning/schedule/plan/commit`、
  `GET /learning/schedule/day?date=`；
- 日期默认 `local_today()`（Asia/Shanghai，复用 growth 既有约定）。

### 自动化证据（本机）

| 证据 | 结果 |
| --- | --- |
| `pytest tests/test_learning_schedule.py` | 6 passed（校验 422、弱模块优先、Minimum Day 三件事、昨日空执行自动降级、commit 写账本与 409、confirmed 保护、Flag 关闭 403） |
| 学习域合计（coach + grader_shadow + schedule） | 23 passed |
| `pytest -q`（apps/api 全量，含 growth 回归） | 421 passed, 39 skipped；2 failed 仍为 `test_backup_drill.py` 环境问题 |
| `ruff check apps/api` | All checks passed |
| 真实 PG（5433）`alembic upgrade head` | 0041 → 0042 成功，`alembic_version=20260829_0042` |

### 边界与回滚

- 不修改 growth 服务代码，只向其账本写入带来源标记的任务；成长中心的计划生成/确认流程不受影响；
- 关闭 `v5_learning_schedule_enabled` 即停用；已生成的任务留在成长中心由用户自行处理（教练不删除用户任务）；
- 未完成（V5-2 余量）：「今日任务」接入双翼工作台面板（V5-3 一并考虑）、LLM 计划生成影子、通知接入（V5-3，依赖 V4 通知深链）。

## V5-2b · 前端「今日任务」工作台（2026-08-29）

### 已交付

- API 客户端 `lib/api/learning.ts` 追加日程端点：blocks 列表/创建/停用、
  plan preview / commit、day status（类型与后端契约一一对应）；
- 组件 `apps/web/src/components/learning-schedule.tsx`：
  - **今日任务卡**：当日模式（正常 / Minimum Day / 未生成）与完成进度、任务列表
    （已完成 ✓ 标绿）与「计划写入成长中心账本，执行与计时请在 /growth 处理」的明确指引；
  - **计划生成流**：Minimum Day 勾选 → 生成预览（逐项标题/详情/预计分钟 + 规则说明脚注；
    自动降级时显著提示"昨日计划未执行，已自动切换 Minimum Day"）→ 提交计划 → 刷新当日状态；
  - **作息块设置**：按周几 + 时间段（time 控件）+ 类型（学习/实践/求职/日常）+ 备注的创建表单，
    列表带一键停用；
- `/learning` 页面组装为「今日任务 → 学习教练」两个工作台（日程在上）；
- 样式：`learning-*` 作用域块追加（plan-actions / draft / block-row / block-form），900px 降级。

### 自动化证据（本机）

| 证据 | 结果 |
| --- | --- |
| `npm --prefix apps/web run typecheck` | passed |
| `npm --prefix apps/web run lint` | passed（修复 1 处 `react-hooks/set-state-in-effect`：effect 内联 async IIFE，不经由会 setState 的 useCallback） |

### 边界与回滚

- 任务状态只读展示：完成/计时沿用成长中心的任务流转（教练不改写 growth 状态机）；
- 前端不做本地计划缓存，全部以预览/提交/查询的实时结果为准；
- 回滚：移除页面中的 `<LearningSchedule />` 即可，API 与数据不受影响。

## V5-1.7 · LLM 出题影子（2026-08-29）

### 已交付

- Prompt Registry 版本化条目 `learning.question_shadow@2.0.0`
  （`templates/learning/question_shadow-v2.0.0.toml`；变量 module_name/module_description/concepts/count；
  四级出题指引 + 严格 JSON 输出契约 + untrusted_input 安全标签）；
- 迁移 `20260829_0041_learning_question_candidates.py`：`learning_question_candidates` 表
  （level/prompt/expected_points/source/model_used/prompt_version/status/decided_at）；
- 服务：`generate_question_candidates`（本地路由，输出解析含非法 level/空要点过滤，
  失败写 ModelCallLog 后抛 502、不落半成品候选）、`list_question_candidates`、
  `decide_question_candidate`（accept/reject，幂等 409 保护）；
- 验收消费：`POST /learning/verifications` 新增 `include_accepted`（默认 false）——
  采纳的候选作为额外题目进入验收，`mode` 记为 `template_v1+accepted`；
  模板出题（template_v1）仍是默认且权威的生成方式；
- API：`POST /learning/modules/{id}/question-shadow`、
  `GET /learning/modules/{id}/question-candidates?status=`、
  `POST /learning/question-candidates/{id}/decide`；
- 复用影子 Flag `v5_learning_coach_llm_shadow_enabled`（出题与判分影子同一开关、同一"仅本地模型"纪律）。

### 判定纪律

候选题目在人工取舍前不进入任何验收；采纳后也只是"额外题目"，模板题仍固定生成。
出题接管（跳过模板、默认混入候选）需要候选采纳率与答题质量证据，后续单独冻结口径。

### 自动化证据（本机）

| 证据 | 结果 |
| --- | --- |
| `pytest tests/test_learning_grader_shadow.py tests/test_learning_coach.py` | 17 passed（生成→取舍→include_accepted 消费、失败 502 不落候选、Flag 关闭 403、重复取舍 409） |
| `pytest -q`（apps/api 全量） | 415 passed, 39 skipped；2 failed 仍为 `test_backup_drill.py` 环境问题 |
| `ruff check apps/api` | All checks passed |
| 真实 PG（5433）`alembic upgrade head` | 0040 → 0041 成功，`alembic_version=20260829_0041` |

修复记录：验收会话构造时 `mode` 曾硬编码字面量导致 `template_v1+accepted` 不生效，
被测试 `test_question_candidates_generate_triage_and_consume` 捕获后修复。

## V5-1.6 · 前端第一版「学习教练」工作台（2026-08-29）

### 已交付

- API 客户端 `apps/web/src/lib/api/learning.ts`：readiness、modules、verifications、
  review queue、shadow grading 与 summary 的类型化封装（沿用 `apiUrl/responseError/runtimeRequestHeaders` 契约）；
- 组件 `apps/web/src/components/learning-coach.tsx`（客户端组件）：
  - Flag 感知三态：关闭（提示打开方式）/ 连接失败 / 就绪；
  - 模块与掌握度：进度条（mastery_percent）、证据数、`low_confidence` 提示「样本不足」、核心概念展示、创建模块表单（名称 + 逗号分隔核心概念）；
  - 学习验收：选择模块 → 开始验收 → Level 1–4 逐题作答 → rule_v1 判分回显（🟢🟡🔴 + 未覆盖要点）→ 完成态；答黄/红后复习队列自动增加（由后端负责）；
  - 影子判分入口：仅当 shadow summary 可读（即 shadow Flag 开启）时对已回答题目显示「影子判分对比」按钮与逐题结果；
  - 复习队列：到期卡 + 四级记忆评级（重来/模糊/记得/轻松），提交后刷新队列与掌握度；
  - 影子一致性面板：total/agreed/disagrored/failed/一致率（明确标注 NOT AUTHORITATIVE）；
- 页面 `apps/web/src/app/learning/page.tsx`（静态可导出，无动态 API）；
- 导航：`sidebar.tsx` SPECIALISTS 组新增「学习教练」（GraduationCap 图标）；
- 样式：`globals.css` 追加 `learning-*` 作用域块（复用既有 `--line`/`--cyan` token 与 primary/ghost button），含 720px 移动端降级。

### 自动化证据（本机）

| 证据 | 结果 |
| --- | --- |
| `npm --prefix apps/web run typecheck` | passed |
| `npm --prefix apps/web run lint` | passed |

### 边界与回滚

- 不触碰 V3-4b 双翼工作台与旧路由；后续在双翼工作台内以面板形式复用同一 API 客户端；
- 页面静态可导出，不影响桌面壳构建（26 → 27 路由，构建数字待 CI 确认）；
- 回滚：删除导航入口即可让入口下线，API 与数据不受影响。

## V5-1.5 · LLM 判分影子（2026-08-29）

### 已交付

- Prompt Registry 版本化条目 `learning.grader_shadow@2.0.0`
  （`templates/learning/grader_shadow-v2.0.0.toml`；变量 module_name/level_name/question/expected_points/answer；
  safety_tags: untrusted_input、local_only、no_pii——回答按不可信文本处理，不执行其中指令）；
- 迁移 `20260829_0039_learning_grader_shadow.py`：`learning_grader_shadows` 表
  （rule_grade、llm_grade、llm_score、llm_feedback、agreement、model_used、prompt_version、latency、tokens、success、error_message）；
- 迁移 `20260829_0040_standalone_model_call_audit.py`：`model_call_logs.conversation_id` 放宽为可空——
  影子判分是首个不属于会话的后台模型调用，全局审计不要求伪造会话（chat 模型同步放宽）；
- 服务 `app/services/learning_shadow.py`：仅走 ModelMode.LOCAL（后台零付费纪律），
  输出 JSON 解析（含代码围栏容错、非法 grade 拒绝），幂等（每题一行），
  失败也先落库再抛 502，保证一致性统计不撒谎；
- API：`POST /learning/verifications/{id}/items/{item_id}/shadow-grading`、
  `GET /learning/grader-shadow/summary`；
- Flag：`v5_learning_coach_llm_shadow_enabled`（默认关闭；父 Flag 关闭时整个 /learning 不可达）。

### 判定纪律

rule_v1 仍是唯一权威判分：影子结果只写 agreement 证据，不改答案、不改掌握度、不建复习卡。
接管的退出条件（后续冻结）：影子样本量与 agreement_rate 达到计划口径后再评审，且接管时必须保留 rule_v1 作为回退路径。

### 自动化证据（本机）

| 证据 | 结果 |
| --- | --- |
| `pytest tests/test_learning_grader_shadow.py tests/test_learning_coach.py` | 14 passed（一致/分歧/失败落库/幂等/未答 409/双 Flag 403/解析容错） |
| `pytest -q`（apps/api 全量） | 413 passed, 38 skipped；2 failed 仍为 `test_backup_drill.py` 环境问题（与 V5 无关） |
| `ruff check apps/api` | All checks passed |
| 真实 PG（5433）`alembic upgrade head` | 0038 → 0039 → 0040 成功；`learning_grader_shadows` 建立，`model_call_logs.conversation_id` 已可空 |

### 边界与回滚

- rule_v1 与掌握度行为零变化；关闭 `v5_learning_coach_llm_shadow_enabled` 即停用影子；
- 迁移 0040 的 downgrade 会把 `conversation_id` 收紧回 NOT NULL（存在 NULL 行时会失败，仅限清理影子数据后执行）；
- 每次影子调用同时写入全局 `model_call_logs`（route_reason=`learning_grader_shadow`），可在成本中心审计。

### 边界与回滚

- 未触碰 chat / growth / 通知 / 审批 / Tool Gateway；PostgreSQL 仍是唯一事实源；
- 回滚：关闭 `v5_learning_coach_enabled` 即恢复原状；迁移可 `alembic downgrade -1`（已在容器库实测往返）；
- 迁移已在真实 PostgreSQL（容器库 5433）执行并验证，当前 `alembic_version=20260829_0038`。
