# Sprint 33：Cost Center

## 状态

已完成。Cost Center 提供 MiMo、DeepSeek 与本地模型的 Token、调用次数、耗时和估算费用统计；DeepSeek 单独统计已确认付费的部分；本地模型展示进程 CPU、内存与显存占用。所有费用都是本地估算，明确标注不代表供应商账单。

## 目标

- 展示 MiMo、DeepSeek、本地模型的 Token 和调用次数；
- 单独统计经过确认的 DeepSeek 费用；
- 本地模型显示耗时、CPU、显存等资源指标；
- 不把估算费用伪装成供应商账单。

## 已交付

### 统计 API（`/api/v1/cost`）

- `GET /cost/overview?days=30`：总调用、成功调用、总 Token、DeepSeek 估算费用（全部/仅已确认）、按供应商统计（调用、Token、平均耗时、输出速度、估算费用）、每日序列、本地资源状态与单价表；
- `GET /cost/calls?limit=50`：最近模型调用明细，统一合并聊天调用与工作流模型调用（标注来源）。

### 数据来源

- 聊天调用：`model_call_logs`（请求/实际供应商、Token、耗时、首字延迟、Token/秒、`user_confirmed`）；
- 工作流调用：`agent_runs`（`provider_used`、Token、`paid_model_confirmed`），避免只统计聊天而漏掉 Growth/Research 的模型调用；
- 本地资源：Ollama `/api/ps`（已加载模型、显存占用）+ 轻量 Windows 进程读取（CPU 平均占用、工作集内存），零新增依赖。

### 费用估算

- DeepSeek 按本地估算单价计算：输入 ¥4/百万 Token、输出 ¥16/百万 Token（可在 `.env` 调整，见 `.env.example`）；
- MiMo 走 Token Plan 套餐内，不计费；Ollama 本地模型不计费；
- 页面与 API 都带明确的“估算 ≠ 供应商账单”声明，价格规则完整可见；
- 估算只统计成功调用；失败调用不产生估算费用。

### Cost Center 页面

- 侧边栏 SYSTEMS 分组新增入口，地址 `/cost`；
- 指标卡：总调用、总 Token、DeepSeek 估算（全部）、已确认付费（仅确认过）、本地引擎状态；
- 按供应商统计面板：MiMo（套餐内）、DeepSeek（估算 + 已确认次数）、Ollama（本地 + 耗时 + 输出速度）；
- 本地运行时面板：进程 CPU、内存、已加载模型与显存；
- 每日用量图：近 7/30/90 天切换，Token 用量与 DeepSeek 估算费用双柱图；
- 最近调用明细：来源（对话/工作流）、模型、Token、耗时、已确认付费标记、估算费用；
- 15 秒自动刷新 + 手动刷新；
- 视觉验收截图：`artifacts/cost-center-sprint33.png`。

### 稳定细节

- 本地进程指标使用 ctypes 直接读取 Windows API，不引入 psutil 等新依赖；
- 进程 CPU 采用“自启动以来的平均占用”，避免单次采样失真；时间基准换算已正确处理 FILETIME（1601 纪元 → Unix 时间戳）与时长字段的区别；
- 时间窗口以 UTC 日期划分，跨日统计稳定；
- 工作流调用在响应中标记来源，避免与聊天调用混淆。

## 当前验收

- API 回归：174 项通过、1 项按环境跳过（新增 4 项 Cost Center 测试，含进程指标守护测试）；
- 桌面伴侣：6 项通过；
- Browser Worker Node 安全测试：5 项通过；
- Prompt/策略评测：16/16 通过；
- Python Ruff、TypeScript、ESLint：通过；
- Next.js 生产构建：21 个页面通过（新增 `/cost`）；
- 浏览器视觉验收：控制台错误 0，截图归档 `artifacts/cost-center-sprint33.png`；
- 真实数据验收：14 次调用正确聚合（MiMo 1 / DeepSeek 1 / Ollama 12），DeepSeek 估算 ¥0.0007 且未确认部分单独标注，本地引擎在线并返回 CPU 0.1%、内存 26.5 MB。

## 设计说明

- 估算单价与货币统一从配置读取，前端只做展示，避免硬编码漂移；
- “已确认付费”与“全部估算”分开展示，DeepSeek 只有在用户确认后才会被调用；
- 所有费用值保留到小数点后 4 位并带货币符号，明示本地估算性质；
- 资源指标读取失败时优雅降级为“离线/—”，不影响其余统计。

## 后续

[Sprint 34 Context Engineering](SPRINT_34.md)：按任务只加载需要的记忆与 Obsidian 文档，为不同 Agent 建立独立上下文预算，进一步降低 Token 消耗。
