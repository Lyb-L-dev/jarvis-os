# Sprint 7：Investment Assistant

## Sprint 目标

把用户手动记录的资产、交易、投资理由和已收集情报连接成一个可审计的投资复盘闭环：

```text
资产与初始持仓
  → 买入 / 卖出 / 分红
  → 精确重算数量、成本与已实现收益
  → 手动最新价格
  → 投资理由与关键假设
  → 关联情报
  → 周 / 月 / 手动事实复盘
```

本阶段只负责记录、关联与复盘，不接券商、不自动下单、不提供买卖建议。

## 已完成：资产与持仓

- [x] 手动录入名称、代码、市场、资产类型和币种；
- [x] 可同时录入初始数量、平均成本、建仓日期、风险等级和目标比例；
- [x] 初始持仓自动形成 `opening` 交易，持仓始终能从交易历史重建；
- [x] 最新价格与价格日期由用户手动维护；
- [x] 无最新价格时市值、浮动盈亏和收益率保持为空，不伪造行情；
- [x] CNY、USD 等币种分别展示成本、市值、浮动盈亏和已实现收益；
- [x] 没有汇率来源时不跨币种相加；
- [x] 资产删除为软删除，并同步关闭持仓、交易、理由和复盘；
- [x] 软删除后的同市场同代码资产可恢复录入。

## 已完成：交易账本与精确重算

- [x] 支持初始持仓、买入、卖出和分红；
- [x] 数量、价格、费用、成本和收益全部使用 `Decimal` / `Numeric`；
- [x] 买入把成交金额与费用计入移动平均成本；
- [x] 卖出按卖出前平均成本减少成本基础，并记录扣除费用后的已实现收益；
- [x] 分红增加收入，不改变数量和持仓成本；
- [x] 编辑或删除历史交易后，按交易日期、创建时间和记录标识重新计算后续状态；
- [x] 历史修改导致后续卖出超过可用数量时拒绝保存；
- [x] 当前持仓不足时拒绝超额卖出；
- [x] 存在有效交易后拒绝修改资产币种；
- [x] 交易保留发生时点的数量、平均成本和成本基础快照。

## 已完成：投资理由、情报和复盘

- [x] 记录原始投资理由、当前看法、关键假设、观察事件和失效条件；
- [x] 新理由替代旧版本时，旧版本标记为 `superseded`，原始理由不丢失；
- [x] 每份理由单独记录是否允许未来用于云端分析，默认不允许；
- [x] 情报可手动关联到资产，并保存“为什么相关”的说明；
- [x] 解除关联或删除资产时同步更新情报的持仓关联状态；
- [x] 周复盘、月复盘和手动复盘均从数据库事实生成；
- [x] 复盘快照包含当前持仓、期间交易、当前投资理由和关联情报；
- [x] 用户可确认理由仍成立、部分成立、已失效或暂不确定，并补充笔记；
- [x] 所有复盘固定显示“不构成投资建议”；
- [x] 不自动调用 DeepSeek，不输出买卖、调仓、仓位或价格预测。

## 数据与 API

新增 PostgreSQL 迁移：`20260729_0010_investment_assistant.py`。

新增实体：

- `assets`
- `portfolio_positions`
- `investment_transactions`
- `investment_theses`
- `investment_reviews`

主要端点：

```text
GET    /api/v1/investment/overview
GET    /api/v1/investment/assets
POST   /api/v1/investment/assets
PATCH  /api/v1/investment/assets/{id}
DELETE /api/v1/investment/assets/{id}
GET    /api/v1/investment/positions
POST   /api/v1/investment/positions
PATCH  /api/v1/investment/positions/{id}
GET    /api/v1/investment/transactions
POST   /api/v1/investment/transactions
PATCH  /api/v1/investment/transactions/{id}
DELETE /api/v1/investment/transactions/{id}
GET    /api/v1/investment/theses
POST   /api/v1/investment/theses
PATCH  /api/v1/investment/theses/{id}
DELETE /api/v1/investment/theses/{id}
GET    /api/v1/investment/reviews
POST   /api/v1/investment/reviews/generate
PATCH  /api/v1/investment/reviews/{id}
DELETE /api/v1/investment/reviews/{id}
GET    /api/v1/investment/assets/{asset_id}/news
POST   /api/v1/investment/assets/{asset_id}/news/{news_item_id}
DELETE /api/v1/investment/assets/{asset_id}/news/{news_item_id}
```

## 本轮验收

- 自动测试：43 项通过（API 39 项、Windows Companion 4 项）；
- 投资专项测试覆盖平均成本、买卖、分红、历史重算、超额卖出、币种边界、理由版本、情报关联和软删除恢复；
- Ruff、TypeScript、ESLint：通过；
- Next.js 正式生产构建：通过，`/investment` 已预渲染；
- Alembic 已升级到 `20260729_0010 (head)`；
- 真实浏览器完成资产、持仓、分红、投资理由、情报关联、月度复盘和清理闭环；
- 浏览器控制台错误、页面异常、失败请求和错误响应：均为 0；
- 验收临时资产与情报已清理；
- 验收截图：
  - `artifacts/investment-positions-verified.png`
  - `artifacts/investment-review-verified.png`

## 下一阶段

- [x] Sprint 8 OpenClaw 主机安装延期，并记录恢复开发前的隔离与审计门槛；
- [x] Sprint 9 先完成自动备份、恢复验证、故障降级和跨模块回归；
- [ ] OpenClaw 恢复后先实现白名单身份、只读查询和普通提醒；
- [ ] 投资记录不通过微信直接修改；
- [ ] 外部消息、付费模型和重要动作继续要求确认；
- [ ] Obsidian Knowledge Bridge 与 n8n Automation Gateway 保留在 v1.2 升级计划。
