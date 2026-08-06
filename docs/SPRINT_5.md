# Sprint 5：English Coach

## Sprint 目标

把英语练习做成可长期使用的闭环：真实对话发现问题，用户确认后写入错题本，按间隔复习，并通过现有 Windows Companion 主动提醒。

## 已完成：对话训练

- [x] 自由对话、主题练习、面试模拟和技术英语四种场景；
- [x] A1–C2 学习级别；
- [x] 即时纠错、温和纠错和结束总结三种节奏；
- [x] 标准路线由 MiMo 主导，当前 Token Plan 不可直连时明确降级到本地 Qwen；
- [x] 可以强制只用本地 Qwen；
- [x] English Coach 不提供 DeepSeek 自动升级或付费入口；
- [x] 模型调用限制输出长度，45 秒未完成时使用本地规则回复与纠错兜底；
- [x] 每条回答记录目标 Provider、实际 Provider、模型、降级原因、耗时与 Token；
- [x] 浏览器英语语音转写，发送前可编辑；
- [x] 已发送的用户原句仍可修改并标记“转写已修改”；
- [x] 会话自动保存、恢复、完成总结和软删除。

## 已完成：错题本

- [x] 保存用户原句、正确表达、错误类别、解释、上下文和 CEFR；
- [x] 保存首次出现、最近出现、累计次数和下次复习时间；
- [x] 同类错误按标准化指纹聚合，句末标点差异不会重复计数；
- [x] 已删除的同类错误再次出现时安全恢复，不触发唯一键冲突；
- [x] 模型纠错默认是 `pending`，用户确认前不会安排复习；
- [x] 搜索和状态筛选；
- [x] 修改正确表达与解释；
- [x] 确认、忽略、标记掌握、解释有误、恢复和删除；
- [x] “解释有误”会暂停后续复习，修改后可重新确认。

## 已完成：间隔复习

- [x] 高频和最近重复错误优先；
- [x] 使用用户自己的原句作为复习题；
- [x] 先作答、再显示参考表达；
- [x] 没记住、有点难、记住了、很轻松、已经掌握五档反馈；
- [x] 根据反馈自动计算 1 天、困难放缓、正常扩展、简单加速等间隔；
- [x] 标记掌握后降低到至少 30 天一次；
- [x] 展示今日到期和后续复习计划；
- [x] 重复提交已经完成的复习会被拒绝。

## 已完成：主动提醒

确认错题后：

```text
english_mistakes
  → english_reviews
  → scheduled_jobs（english-review:{review_id}）
  → notifications
  → Windows Companion
  → desktop + voice
```

- [x] 首次复习默认安排在次日 19:00；
- [x] 每次评分后自动安排下一次复习；
- [x] 复习完成、解释有误或删除错题时取消旧提醒；
- [x] 提醒使用固定幂等键，不重复投递；
- [x] 继续服从免打扰、每日上限和每小时语音上限。

## 数据与 API

新增 PostgreSQL 迁移：`20260728_0008_english_coach.py`。

新增实体：

- `english_sessions`
- `english_messages`
- `english_mistakes`
- `english_reviews`

主要端点：

```text
GET    /api/v1/english/overview
GET    /api/v1/english/sessions
POST   /api/v1/english/sessions
GET    /api/v1/english/sessions/{id}
DELETE /api/v1/english/sessions/{id}
POST   /api/v1/english/sessions/{id}/messages
POST   /api/v1/english/sessions/{id}/complete
PATCH  /api/v1/english/messages/{id}
GET    /api/v1/english/mistakes
PATCH  /api/v1/english/mistakes/{id}
POST   /api/v1/english/mistakes/{id}/confirm
POST   /api/v1/english/mistakes/{id}/reject
POST   /api/v1/english/mistakes/{id}/master
POST   /api/v1/english/mistakes/{id}/dispute
DELETE /api/v1/english/mistakes/{id}
GET    /api/v1/english/reviews/due
GET    /api/v1/english/reviews/upcoming
POST   /api/v1/english/reviews/{id}/result
```

## 本轮验收

- 自动测试：31 项通过（API 27 项、Windows Companion 4 项）；
- Ruff、TypeScript、ESLint：通过；
- Next.js 正式生产构建：通过；
- Alembic：`20260728_0008 (head)`；
- 真实本地 Qwen 接口约 4.3 秒完成一次英语回复与纠错；
- 真实浏览器完成“创建会话 → 对话 → 纠错 → 人工确认 → 到期复习 → 评分 → 下次提醒”；
- 桌面与语音提醒同时入队；
- 浏览器控制台错误、页面异常、失败请求和错误响应：均为 0；
- 验收数据自动清理；
- 验收截图：
  - `artifacts/english-coach-verified.png`
  - `artifacts/english-review-verified.png`

## 下一阶段

- [ ] Information Intelligence：RSS、信息去重、主题筛选和每日情报；
- [ ] 投资与国际动态使用可追溯来源，不让模型虚构实时信息；
- [ ] 每日情报接入现有桌面、语音提醒；
- [ ] 后续 OpenClaw 阶段增加个人微信投递渠道。
