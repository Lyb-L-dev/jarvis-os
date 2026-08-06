# Sprint 1：工程基础与首次启动

## Sprint 目标

在第一周得到一个可以本地启动、能够显示 Dashboard、能够连接数据库并保存首次启动信息的 Jarvis OS。

预计投入：7 天 × 每天约 4 小时。

## 完成定义

- 后端和前端可以独立启动；
- PostgreSQL 可以通过本地配置连接；
- `/api/v1/health/live` 返回正常；
- Dashboard 能展示系统连接状态；
- 可以创建、更新和完成首次启动 Session；
- 完成后生成用户档案和偏好；
- MiMo、DeepSeek、Ollama 状态可见，但不暴露密钥；
- 自动化测试通过；
- `.env` 不进入版本控制；
- 技术设计和 ER 图与代码一致。

## Day 1：工程与架构

时间预算：4 小时

- [x] 建立 `apps/api`、`apps/web`、`apps/desktop`；
- [x] 建立 `docs`、`infra`、`scripts`；
- [x] 创建 `.gitignore` 和 `.env.example`；
- [x] 创建 FastAPI 与 Next.js 骨架；
- [x] 创建 PostgreSQL Compose；
- [x] 确认模型和渠道边界。

当天验收：

- 目录职责清楚；
- 没有真实密钥；
- 技术栈与 PRD 一致。

## Day 2：配置与数据库

时间预算：4 小时

- [x] Pydantic Settings；
- [x] SQLAlchemy Async Session；
- [x] `users`；
- [x] `user_profiles`；
- [x] `user_preferences`；
- [x] `onboarding_sessions`；
- [x] Alembic 初始迁移；
- [x] 用 PostgreSQL 实际执行 `upgrade head`；
- [ ] 在保留真实资料的前提下验证 downgrade。

当天验收：

- 开发和测试配置分离；
- 数据库迁移可以重复执行；
- 用户档案关系正确。

## Day 3：首次启动 API

时间预算：4 小时

- [x] 创建 Onboarding Session；
- [x] 更新步骤与答案；
- [x] 获取 Session；
- [x] 完成 Onboarding；
- [x] 生成档案与偏好；
- [ ] 增加必填字段和步骤校验；
- [ ] 增加 API 集成测试。

当天验收：

- 中断后可以继续；
- 完成后不能继续修改原 Session；
- 完成数据能正确写入档案。

## Day 4：Dashboard 与首次启动 UI

时间预算：4 小时

- [x] Dashboard 视觉骨架；
- [x] 侧边导航；
- [x] 健康状态组件；
- [x] 模块占位页面；
- [x] 首次启动分步页面；
- [x] 表单状态保存；
- [x] 完成后跳转 Dashboard。

当天验收：

- 后端离线时页面仍可打开；
- 页面明确显示连接状态；
- 首次启动流程可以刷新恢复。

## Day 5：Model Gateway 基础

时间预算：4 小时

- [x] `standard / deep / local / auto`；
- [x] MiMo 默认路由；
- [x] DeepSeek 深度路由；
- [x] 本地隐私路由；
- [x] Provider 状态接口；
- [x] OpenAI Compatible Provider；
- [x] Ollama Provider 端到端连通性测试；
- [ ] MiMo 与 DeepSeek Provider 连通性测试（等待 API Key）；
- [ ] 调用日志表设计。

当天验收：

- 路由规则有单元测试；
- Token Plan `tp-` 不进入自定义后端；
- 未配置 Provider 有明确状态。

## Day 6：质量与异常处理

时间预算：4 小时

- [x] 后端 Ruff；
- [x] 后端 Pytest；
- [x] 前端 TypeScript；
- [x] 前端 ESLint；
- [ ] Onboarding 错误场景；
- [ ] PostgreSQL 不可用场景；
- [ ] Ollama 不可用场景；
- [x] 配置检查。

当天验收：

- 自动检查命令一次通过；
- 错误提示不包含敏感信息；
- 数据库或模型离线不会造成空白页面。

## Day 7：真实使用验收

时间预算：4 小时

- [x] 在当前 Windows 电脑完整启动；
- [x] 完成一次真实首次启动；
- [x] 检查数据库记录；
- [x] 重启前后端后验证数据保留；
- [ ] 导出当前配置摘要；
- [ ] 修复验收问题；
- [ ] 冻结 Sprint 1 数据模型；
- [ ] 编写 Sprint 2 任务清单。

当天验收：

- 从零启动流程可复现；
- 能看到非空个人 Dashboard；
- 准备进入 Chat 与真实模型调用。

## 当前下一动作

1. 增加 Onboarding 必填字段、步骤校验与集成测试；
2. 增加数据库与 Ollama 离线场景测试；
3. 设计模型调用日志表；
4. 用户填入 MiMo 按量付费 Key 与 DeepSeek Key 后验证云端 Provider；
5. 导出 Sprint 1 配置摘要并冻结数据模型；
6. 编写 Sprint 2 的 Chat、记忆与模型路由实现清单。
