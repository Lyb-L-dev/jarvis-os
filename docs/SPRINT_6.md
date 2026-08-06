# Sprint 6：Information Intelligence

## Sprint 目标

把投资、国际动态、AI、职业、技术和英语信息做成一个可长期运行的事实闭环：

```text
公开来源 / 手动链接
  → 安全获取
  → 标准化
  → URL / 正文 / 标题去重
  → 兴趣与目标匹配
  → 3–5 条可追溯简报
  → 收藏 / 忽略 / 转任务反馈
  → 桌面与语音提醒
```

## 已完成：来源与抓取

- [x] RSS、Atom 和手动链接三种首批输入方式；
- [x] 官方白名单来源：OpenAI News、Google DeepMind、GitHub Changelog、NVIDIA Blog、Federal Reserve、United Nations News；
- [x] 来源启用、停用、删除、单独刷新和全部刷新；
- [x] 来源可信度、默认主题、语言、刷新间隔、ETag、Last-Modified 和错误状态；
- [x] 只允许 `http://` 与 `https://`；
- [x] DNS 解析后阻止本机、局域网、链路本地、保留地址和重定向到内网；
- [x] 每次重定向重新执行安全校验，最多 3 次；
- [x] Feed 最大 2 MB，每个来源最多导入 30 条，默认只保留近 30 天；
- [x] 拒绝根节点前的 DTD / Entity 声明，同时允许来源正文里的 HTML 示例；
- [x] 普通网页正文自动抓取暂不开放；手动链接由用户填写已确认的来源摘要。

## 已完成：标准化、去重与筛选

- [x] 去除 `utm_*`、`fbclid`、`gclid` 等追踪参数；
- [x] 用户级规范 URL 指纹唯一约束；
- [x] 标题与来源摘要生成正文指纹；
- [x] 近 3 天标题相似度达到 0.9 时标记为重复事件；
- [x] 重复条目保留审计记录，但不进入信息流默认视图和每日情报；
- [x] AI、职业、技术、英语、投资、国际动态六类主题；
- [x] 官方来源默认主题带分类先验，避免国际动态被单个通用技术词误分类；
- [x] 当前兴趣权重、来源可信度、时效和长期目标共同计算相关度；
- [x] 收藏、忽略和转任务分别产生正向或负向反馈；
- [x] 兴趣权重限制在 1–5，并兼容首次启动阶段的 `high`、`medium_high` 等旧值。

## 已完成：可追溯每日情报

每条卡片明确分成：

1. `来源事实`：RSS 或用户手动提供的原始摘要；
2. `整理摘要`：只对已有来源内容进行中文概括；
3. `AI 分析 · 非来源事实`：说明与兴趣、目标的相关性；
4. `建议行动`：可验证、可转任务、非交易的下一步。

- [x] 每日优先 3–5 条，不足时明确说明且不凑数；
- [x] 同一主题最多优先占 2 条，避免简报被单一类别占满；
- [x] 每条保留来源名、原始链接、发布时间、可信度和模型审计；
- [x] 标准模式请求 MiMo；Token Plan 不支持自建后端时明确降级本地 Qwen；
- [x] 可以强制只使用本地 Qwen；
- [x] 情报接口不接受 `deep`，不会自动调用或消费 DeepSeek；
- [x] 模型只接收已抓取的来源摘要，并明确把来源内容当作不可信数据；
- [x] 模型失败或格式错误时回退到来源摘要与规则分析；
- [x] 英文来源也强制输出简体中文概括，专有名词可保留；
- [x] 投资信息禁止输出买入、卖出、加仓、减仓、仓位和价格预测；
- [x] 持仓关联字段已预留，但在投资模块完成前始终为 `false`。

## 已完成：主动运行与提醒

- [x] 每天上海时间 07:45–12:00 检查一次；
- [x] 当天已有简报时不会重复生成；
- [x] 没有来源内容时不生成空简报，后续轮询仍可重试；
- [x] 自动刷新白名单来源并使用标准 MiMo 优先路线；
- [x] 生成后写入 `daily-brief:{brief_id}` 幂等提醒；
- [x] 同时请求 `desktop` 与 `voice`；
- [x] 继续遵守免打扰、每日上限和每小时语音上限；
- [x] 语音只播报条目数和首要标题，不朗读完整投资细节。

## 数据与 API

新增 PostgreSQL 迁移：`20260728_0009_information_intelligence.py`。

新增实体：

- `news_sources`
- `news_items`
- `news_item_links`
- `daily_briefs`
- `interest_feedback`

主要端点：

```text
GET    /api/v1/intelligence/overview
GET    /api/v1/intelligence/preferences
PATCH  /api/v1/intelligence/preferences
GET    /api/v1/intelligence/sources
POST   /api/v1/intelligence/sources
PATCH  /api/v1/intelligence/sources/{id}
DELETE /api/v1/intelligence/sources/{id}
POST   /api/v1/intelligence/sources/{id}/refresh
POST   /api/v1/intelligence/refresh
GET    /api/v1/intelligence/items
POST   /api/v1/intelligence/items/manual
GET    /api/v1/intelligence/items/{id}
POST   /api/v1/intelligence/items/{id}/read
POST   /api/v1/intelligence/items/{id}/save
POST   /api/v1/intelligence/items/{id}/ignore
POST   /api/v1/intelligence/items/{id}/task
DELETE /api/v1/intelligence/items/{id}
GET    /api/v1/intelligence/briefs/today
GET    /api/v1/intelligence/briefs
POST   /api/v1/intelligence/briefs/generate
POST   /api/v1/intelligence/briefs/{id}/read
```

## 本轮验收

- 自动测试：41 项通过（API 37 项、Windows Companion 4 项）；
- Ruff、TypeScript、ESLint：通过；
- Next.js 正式生产构建：通过；
- Alembic：`20260728_0009 (head)`，`alembic check` 无待迁移差异；
- 6 个官方来源真实刷新：6 成功、0 失败；
- 真实标准路由：请求 MiMo，实际使用本地 Qwen，约 35 秒完成 5 条简报；
- DeepSeek 未调用；
- 中文摘要、事实 / 分析 / 建议分层和投资边界已验证；
- 桌面与语音提醒已入队；
- 真实浏览器完成“今日简报 → 信息流搜索 → 收藏 → 转任务 → 来源状态”；
- 浏览器控制台错误、页面异常、失败请求和错误响应：均为 0；
- 验收任务、验收情报和临时兴趣权重已清理；
- 验收截图：
  - `artifacts/intelligence-brief-verified.png`
  - `artifacts/intelligence-sources-verified.png`

## 下一阶段

- [ ] Investment Assistant：资产、持仓、交易和投资理由；
- [ ] 手动录入持仓与交易，不自动下单；
- [ ] 把情报与资产 / 持仓建立可追溯关联；
- [ ] 区分市场事实、持仓影响分析和行动建议；
- [ ] 重要持仓信息继续接入桌面与语音提醒。
