# Sprint 37：受控 Computer-use（阶段 1–2）

## 状态

已完成。Jarvis 现在可以“只读查看”电脑屏幕元数据与沙箱文件，并能把用户指令转成可解释的操作计划供预览；写文件与外部账号仍被阶段拦截。永久禁区（投资交易、支付、数据删除、凭据操作）继续保持 R3 最高风险等级，不注册任何 Agent 工具。

## 目标

- 按风险逐级开放电脑操作能力，而不是一次性放开自主控制；
- 当前开放：只读查看（阶段 1）+ 操作计划与预览（阶段 2）；
- 阶段 3（确认后修改）与阶段 4（外部账号）保留开关，默认关闭；
- 永远不自动执行交易、支付、凭据操作和不可恢复删除。

## 已交付

### 后端

- `services/computer_use.py`：
  - 屏幕只读：显示器数量、分辨率与窗口标题等元数据，不采集画面内容；
  - 沙箱文件只读：限定 `.data/tool-sandbox`，返回内容与内容哈希；
  - `build_plan`：把自然语言指令解析为步骤列表（工具、动作、风险级别、是否需要审批、预览提示、是否被当前阶段拦截），文件写入类步骤在阶段 2 被标记 `blocked_by_stage=true`。
- 新工具 `computer.screen.info`、`computer.file.read`：均为 R0 只读，已登记到 jarvis_core 与 local_document 的 Agent 白名单，由 Tool Gateway 统一校验、幂等与审计。
- `schemas/computer.py` + `api/routes/computer.py`：
  - `GET /api/v1/computer-use/status`：返回四级阶梯（只读查看 → 计划与预览 → 确认后修改 → 外部账号）、当前阶段、每级是否启用、沙箱根目录、永久禁区和各工具开关；
  - `POST /api/v1/computer-use/plan`：根据指令生成操作计划，含当前阶段提示。
- 配置项 `computer_use_stage=2`，可通过 `.env` 调整。

### 前端

- 新增 `/computer` 页面与侧边栏 SYSTEMS 入口（Computer Use）；
- 展示当前阶段阶梯、只读工具状态、永久禁区、沙箱边界与操作计划生成器；
- 风格沿用 Cinematic Jarvis 设计。

### 顺带修复：生产版全站水合警告

- 问题：生产构建下所有页面控制台报 React error #418（服务端渲染文本与客户端不一致）；
- 根因：顶部栏时钟、首页问候/时间、平板端时钟等组件把 `new Date()` 作为初始状态，静态页面在构建时把时间写死在 HTML 里，浏览器打开时重新计算，两边文字不一致；
- 修复：时钟与日期改为挂载后再填充；投资页三个“今天”日期默认值和提醒页“十分钟后”默认时间同样处理；
- 结果：22 个页面生产控制台零错误。

## 安全边界

- 阶段 1–2 只开放 R0 只读工具，不产生任何文件、日历、邮件或账号变更；
- 永久禁区沿用 `PERMANENTLY_BLOCKED_ACTIONS`：`investment_trade`、`payment`、`delete_data`、`credential_operation`，不注册 Agent 工具、不生成执行步骤；
- 屏幕只返回元数据，不采集画面；文件读取限定沙箱根目录；
- 阶段 3（确认后修改）开启前必须经过预览与审批中心，保持 R2 三阶段流程；
- 微信/OpenClaw 继续延期，不安装到当前主系统。

## 当前验收

- API 回归：220 项通过、1 项按环境跳过（新增 12 项 Computer-use 测试）；
- 桌面端测试：6 项通过；
- Python Ruff、TypeScript、ESLint：全部通过；
- Next.js 生产构建：25 个页面通过（新增 `/computer`）；
- 浏览器验收：22 个页面控制台 0 错误，截图归档 `artifacts/computer-use-sprint37.png`；
- 真实接口验收：
  - `GET /computer-use/status`：`stage=2`，阶梯 1–2 启用、3–4 关闭，`permanent_blocks` 4 项，写文件工具 `workspace.file.write=false`；
  - `POST /computer-use/plan`：对“读取沙箱笔记并整理要点”生成只读屏幕元数据计划，R0、无需审批、不被阶段拦截；
  - Tool Gateway 真实执行：`computer.screen.info` 返回 1920×1080、1 显示器与真实窗口标题；`computer.file.read` 读取沙箱笔记并返回内容与哈希。

## 设计说明

- 按风险逐级开放：只读 → 计划与预览 → 确认后修改 → 外部账号；
- 当前停留在“计划与预览”，任何写操作都还没有打开；
- 后续升级只需调整配置并注册对应工具，不改变 Agent 与 Tool Gateway 架构；
- 操作计划默认可解释、带风险级别与预览提示，为阶段 3 的确认流程做准备。

## 后续

- 阶段 3：用户确认后修改文件、日历或邮件（仍需预览 + 审批）；
- 阶段 4：外部账号逐项授权；
- 永不开放自动交易、支付、凭据操作和不可恢复删除。
