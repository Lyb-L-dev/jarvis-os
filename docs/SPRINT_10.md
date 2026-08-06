# Sprint 10：桌面版发布验收与作品集

## Sprint 目标

把前九个阶段的可运行功能收口成一个可长期个人使用、可说明、可演示、可检查、
可备份和可恢复的 Windows 桌面版发布候选。

本阶段不安装 OpenClaw，不用降低安全门槛换取“功能全勾选”。

## 已完成：发布缺口

- [x] 新增全部业务表的本地 JSON 数据导出；
- [x] 导出不包含 MiMo、DeepSeek 或 OpenClaw 密钥配置；
- [x] 首次初始化幂等创建一个首周目标、一个里程碑和 3 个首周任务；
- [x] 新用户的微信提醒默认关闭并明确标记延期；
- [x] 新增 12 项 Prompt 与策略评测；
- [x] 新增不需要私人数据的演示数据创建和精确清理脚本；
- [x] 补齐 Playwright 验收依赖，避免依赖本机偶然安装的包；
- [x] 更新当前架构图，OpenClaw 显示为未安装的未来隔离通道。

## 已完成：安全与依赖

- [x] `.env`、`.runtime`、`backups`、私钥和证书文件进入忽略规则；
- [x] 项目源码未发现高可信 API Key、Token 或私钥；
- [x] API、网页和 CORS 来源均限制在本机；
- [x] `OPENCLAW_ENABLED=false`；
- [x] npm 生产与开发依赖审计均为 0 个已知漏洞；
- [x] Python 依赖审计为 0 个已知漏洞；
- [x] 升级存在已知漏洞的 pip 与 pytest；
- [x] 使用兼容覆盖修复 Next.js 传递依赖中的 PostCSS、Sharp、Minimatch 和 Brace Expansion；
- [x] 全量测试在 pytest 9 与 Starlette 推荐的 httpx2 测试栈通过且无警告。

## 已完成：运行与数据保护演练

- [x] 创建新的 PostgreSQL 恢复点；
- [x] 在独立临时数据库恢复成功：35 张表，结构版本 `20260729_0010`；
- [x] 完整停止 API、网页、Windows Companion 和备份 Worker；
- [x] 确认 3000、8000 端口关闭，运行状态文件被移除；
- [x] 正式重新构建网页并重新启动全部四个 Jarvis 进程；
- [x] 重新启动后 API、网页、导出、提醒与备份 Worker 正常；
- [x] 网页导出入口通过真实浏览器点击验收；
- [x] 没有对正式数据库执行覆盖恢复。

## 发布测试结果

- 自动测试：49 项通过；
- Prompt 与策略评测：12/12 通过；
- Ruff、TypeScript、ESLint：通过；
- Next.js 正式生产构建：通过；
- Alembic：`20260729_0010 (head)`，无遗漏变更；
- 浏览器闭环：
  - 成长目标、任务、每日计划与周复盘；
  - 长期记忆与 DeepSeek 费用确认；
  - Windows 桌面提醒、延迟、忽略、历史与清理；
  - 情报来源、分层简报、收藏与转任务；
  - 英语会话、纠错确认、错题复习与提醒；
  - 投资持仓、交易、理由、情报关联与事实复盘；
  - 备份、恢复状态与个人数据导出。
- 上述浏览器验收的控制台错误、页面异常、失败请求和错误响应均为 0。

## 交付文档

- [x] `README.md`；
- [x] `docs/ARCHITECTURE.md`；
- [x] `docs/USER_GUIDE.md`；
- [x] `docs/DEMO_GUIDE.md`；
- [x] `docs/RELEASE_ACCEPTANCE.md`；
- [x] `evals/prompt_policy_cases.jsonl`；
- [x] `scripts/preflight.ps1`；
- [x] `scripts/security-check.ps1`；
- [x] `scripts/dependency-audit.ps1`；
- [x] `scripts/demo-data.ps1`。

## 明确保留项

- OpenClaw/微信延期，不属于本次主机发布；
- 当前 MiMo 配置是 Token Plan，Jarvis 不绕过提供方限制，因此运行状态是
  DeepSeek 与 Ollama 已配置、MiMo 应用 API 未配置；
- 备份当前仍位于同一块硬盘；
- 正式数据库交换恢复脚本已实现安全门槛，但未对当前数据库执行破坏性演练；
- 安装流程已由明确依赖、预检和当前机器重建验证，尚未在第二台全新电脑实测；
- `.env` 继承 Windows 本地用户组读取权限，不应在多人共用账户下使用真实密钥。

## 发布结论

Jarvis OS v1.1 Desktop Release Candidate 可以继续作为当前电脑上的个人长期使用版本。
原始 PRD 中的微信项没有通过，也没有被伪装成通过；满足隔离安全门槛后再作为独立
通道恢复开发。
