# Jarvis OS 前端 V3 改造方案（Jarvis Design Language 2.0）

> 版本：2026-08-04 · 状态：方案稿（未改代码）
> 配套文档：[开源项目调研与优化报告](./OPENSOURCE_RESEARCH_REPORT_20260804.md)

---

## 0. 方案摘要

**目标**：在不改业务逻辑、不动数据库、不动权限体系的前提下，把 Jarvis 前端从"功能齐全但风格靠堆叠"升级为"有明确设计语言、科技感强、内容简洁、与后端数据严格对应"的 V3 界面。

**一句话设计语言**：小米的"深空科技感 + 数据仪表"做底色，苹果的"排版克制 + 大留白 + 玻璃质感"做骨架，Jarvis 自己的"青色能源色 + J-Core 状态核心"做灵魂。

**总览（9 个阶段，每阶段独立可交付、可回滚）**：

| 阶段 | 名称 | 主要工具 | 产出 | 后端配合 |
|---|---|---|---|---|
| Phase 0 | 品牌核心（最高优先） | 自研 SVG | J.A.R.V.I.S 黑白圆环字标 + favicon/PWA 替换 | 无 |
| Phase 1 | 设计基座 | Tailwind v4 @theme / CSS 变量 | 设计令牌（色/字/距/角/阴影/动效） | 无 |
| Phase 2 | 字体与排版 | 本地中文字体 + next/font | 中文字体、字号阶梯、数字对齐 | 无 |
| Phase 3 | 布局壳层 | 自研 Sidebar/Header + motion | 精简导航、页面容器、顶部状态条 | 1 个聚合接口 |
| Phase 4 | 通用组件库 | shadcn 扩展 + 自研组件 | StatCard / GlassPanel / Skeleton 等 | 无 |
| Phase 5 | 数据可视化 | Apache ECharts + 自研 SVG | 投资/成长/成本/观测图表 | 4 个时序接口 |
| Phase 6 | 情报可视化 | globe.gl / deck.gl / MapLibre | 情报中心全球视图（默认离线） | 1 个字段扩展 |
| Phase 7 | 动效与质感 | motion + Magic UI（少量） | 统一动效体系 + 呼吸球五态 | 无 |
| Phase 8 | 页面逐项改造 | 前面所有成果 | 19 页按规范重排 | 分页/SSE |
| Phase 9 | 平板与 PWA | 触控规范 + 聚合接口 | 平板终端体验 | 1 个聚合接口 |
| Phase 10 | 性能与无障碍 | next/dynamic + Lighthouse | 性能达标、可访问 | 无 |

**推荐节奏**：Phase 0–4 为"第一轮：品牌与地基"（品牌先行，每 Phase 半天到一天）；Phase 5–7 为"第二轮：上能力"；Phase 8–10 为"第三轮：全量落地与验收"。每轮结束都跑一次完整回归（构建 + 169 项测试 + 页面走查），确保系统一直可用。

---

## 1. 设计语言：Jarvis Design Language 2.0

### 1.1 参考拆解：苹果与小米官网各借鉴什么

| 来源 | 借鉴点 | 落到 Jarvis 的规则 |
|---|---|---|
| 苹果官网 | 超大标题 + 大量留白；一屏只讲一件事 | 每页顶部一个 Display 级大标题，首屏信息不超过 5 个模块 |
| 苹果官网 | 玻璃拟态（backdrop-blur）+ 细描边 | 面板统一"半透明 + 1px 内描边 + 柔和阴影" |
| 苹果官网 | 动效克制、有缓动曲线、不喧宾夺主 | 动效只用于状态变化与进入动画，默认遵守"减少动态效果" |
| 小米官网 | 深色科技感、霓虹渐变、光晕 | 保留近黑背景 + 青色能源光晕（Jarvis 已有，继续强化） |
| 小米官网 | 数据仪表感、大数字、模块化卡片 | 数据一律用大号等宽数字 + 单位小标签，一眼可读 |
| 小米官网 | 分段导航、分类清晰 | 导航分组保留 CORE / SPECIALISTS / SYSTEMS，但精简文案与间距 |

### 1.2 设计原则（六条，写进后续所有页面）

1. **数据优先**：一个数字能说清楚的事，不用一段文字；数字用 tabular-nums 对齐。
2. **少即是多**：每页只保留"我要看的"和"我要做的"；装饰元素不超过画面 15%。
3. **状态可见**：J-Core 五态（待命/聆听/思考/执行/警报）是视觉锚点，全局可感知。
4. **玻璃分层**：背景 → 光晕 → 玻璃面板 → 内容，四层结构，不再堆叠第三种背景。
5. **动效即反馈**：动效必须解释"发生了什么"（数据更新、状态切换、审批流转），否则不做。
6. **本地优先**：任何视觉效果不依赖第三方在线服务；地图等默认离线可降级。

### 1.3 视觉规范（Design Tokens）

#### 色彩

| Token | 值 | 用途 |
|---|---|---|
| `--bg-0` | `#07070A` | 页面底色（比现在略深，增加对比） |
| `--bg-1` | `rgba(255,255,255,0.03)` | 玻璃面板底 |
| `--bg-2` | `rgba(255,255,255,0.06)` | 悬浮/激活面板底 |
| `--line` | `rgba(255,255,255,0.08)` | 常规描边 |
| `--energy` | `#22D3EE` | 主色（青），延续现有 |
| `--energy-hot` | `#A5F3FC` | 高亮/焦点 |
| `--energy-soft` | `rgba(34,211,238,0.10)` | 选中底色/辉光 |
| `--violet` | `#6366F1` | 辅助色（思考/研究） |
| `--blue` | `#3B82F6` | 信息色（执行） |
| `--green` | `#62E4AA` | 成功/已确认 |
| `--amber` | `#F6BD68` | 警告/待确认 |
| `--danger` | `#FF667A` | 错误/需处理 |
| `--text-0` | `#F4F4F5` | 主文字 |
| `--text-1` | `#A1A1AA` | 次级文字 |
| `--text-2` | `#63667A` | 辅助说明/时间戳 |

状态色映射（J-Core 五态）：

| 状态 | 颜色 | 视觉形态 |
|---|---|---|
| 待命 IDLE | `--text-1` | 静态圆点 |
| 聆听 LISTEN | `--energy` | 呼吸光晕 |
| 思考 THINK | `--violet` | 旋转/波形 |
| 执行 EXECUTE | `--blue` | 脉冲环 |
| 警报 ALERT | `--amber` / `--danger` | 闪烁 + 抖动（仅高优先级） |

#### 字体与字号阶梯

- 英文与数字：Geist（已有）；中文：**MiSans 或思源黑体（Noto Sans SC）**，本地子集化 woff2，经 `next/font/local` 加载。
- 阶梯（苹果式层级，全局统一）：

| 层级 | 字号/行高 | 字重 | 用途 |
|---|---|---|---|
| Display | 40–56 / 1.05 | 600 | 页面大标题（每页一个） |
| Title | 24–28 / 1.2 | 600 | 区块标题 |
| Heading | 18–20 / 1.3 | 600 | 卡片标题 |
| Body | 14–15 / 1.6 | 400 | 正文 |
| Caption | 12 / 1.4 | 400 | 辅助说明 |
| Micro | 10–11 / 1.3 | 500，字母间距 0.08em | 标签/时间戳 |

- 所有数字、指标使用 `tabular-nums`；货币、百分比、时间戳统一格式（后端只给原始值，前端格式化）。

#### 间距 / 圆角 / 阴影 / 模糊

- 间距：4pt 基准（4/8/12/16/24/32/48/64/96），页面左右留白桌面 32px、平板 20px。
- 圆角：卡片 16–20px、按钮 12px、输入 12px、胶囊标签 999px。
- 玻璃面板：`background: rgba(255,255,255,0.03)` + `backdrop-filter: blur(20px)` + `1px rgba(255,255,255,0.06) 内描边`。
- 阴影：常态 `0 1px 0 rgba(255,255,255,0.03) inset`；悬浮 `0 20px 60px rgba(0,0,0,0.45)` + 青色底部辉光。

#### 动效

| 场景 | 时长 | 缓动 |
|---|---|---|
| hover / 反馈 | 150ms | ease-out |
| 面板展开 / 布局 | 300ms | `cubic-bezier(0.32, 0.72, 0, 1)`（苹果式） |
| 首屏 hero 入场 | 500ms | 同上，带 20px 位移 + 淡入 |
| 状态脉冲 | 1.6s 循环 | 呼吸光晕（仅核心状态） |

#### 品牌图形（J.A.R.V.I.S 黑白圆环字标）

- 品牌图形只使用 JarvisLogomark 组件与导出的静态 mark；图形为"白色等宽单线正圆环（左右开口）+ 居中 J.A.R.V.I.S 字标"，不再使用字母 J 单标。
- 色彩规范：仅两种颜色——背景纯黑 `#000000`，图形与文字纯白 `#FFFFFF`；无阴影、无发光、无渐变、无外描边，扁平矢量。
- 规格：圆环为正圆（左右 9 点钟/3 点钟开口，开口位于文字高度）；圆环线条与文字笔画等粗（4px @ 512）；字标水平居中穿过圆心，字距均匀。
- 尺寸规范：侧边栏 28–32px、平板 40px、聊天头像 28px、favicon 16px（小尺寸自动简化细节）。
- 五态动画（仅限应用内交互态）：待命 = 4.2s 缓慢缩放；聆听 = 呼吸加快；思考 = 静止；执行 = 轻微脉冲；警报 = 不变形、仅页面级红色提示。logo 本身始终保持黑白扁平。

所有动效受 `MotionConfig reducedMotion="user"` 控制（已有），并在设置页提供"关闭装饰动效"选项。

---

## 2. 现状盘点（改造前基线）

**技术栈**：Next.js 16（App Router）+ React 19 + Tailwind CSS v4（CSS-first）+ motion + lucide-react + Geist 字体 + shadcn/ui（button/card/tooltip 三个基础组件）+ `apps/web/src/lib/api.ts`（约 130KB 的类型化 API 客户端）。

**页面（19 个）**：`/`（Command Center）、`/chat`、`/english`、`/intelligence`、`/monitoring`、`/growth`、`/career`、`/memory`、`/observatory`、`/cost`、`/approvals`、`/investment`、`/knowledge`、`/notifications`、`/evaluation`、`/onboarding`、`/settings`、`/tablet`、`/[module]`。

**组件**：每个模块一个大型组件（dashboard / chat-workspace / growth-center / intelligence-center / investment-center / observatory 等），部分已有视觉亮点（JarvisOrb、MemoryGalaxy、system-icon、command-telemetry）。

**后端**：FastAPI，按模块提供接口：chat 流式、growth、english、intelligence、investment、memory、observatory、cost、approvals、monitoring、notifications、career、knowledge、evaluation、system、health。前端直接并行 `Promise.allSettled` 拉取，无统一请求缓存层。

**当前痛点**：
1. 没有统一设计令牌，页面之间样式靠手写 CSS 堆叠（如 approval-page 大段自定义类）。
2. 排版层级不统一，缺少"页面大标题 + 留白"的骨架，信息密度偏高。
3. 无图表库，数据多为数字和列表，缺少趋势/分布可视化。
4. 情报中心没有地图/全球视野；monitoring 只有事件列表。
5. 侧边栏条目多、分组文案密集，平板/窄屏体验一般。
6. 无统一请求缓存/轮询策略（首页一次性并行 10 个请求）。

---

## 3. 阶段实施计划（Step by Step）

### Phase 0 —— 品牌核心：J.A.R.V.I.S 黑白圆环字标（最高优先级）

**为什么放在第一位**：品牌是用户第一眼看到的东西。J 字母图标缺乏辨识度；按用户最终规格，品牌定稿为：**纯黑背景 + 白色等宽单线正圆环（左右开口）+ 居中 J.A.R.V.I.S 字标**，极简扁平、赛博工业风。

**定稿规格（用户确认版）**：
- 背景：纯黑 `#000000`，无渐变、无噪点、无纹理。
- 圆环：一条等粗白色单线正圆环，无填充；**左侧开口**（9 点钟方向，位于文字高度）与**右侧开口**（3 点钟方向，位于文字高度）；环线被横向文字从中穿过。
- 字标：`J.A.R.V.I.S`，字母间用英文句点分隔；水平居中穿过圆心；几何硬朗无衬线字体（Bahnschrift / Geist 600）；笔画与圆环同为 4px（@512）、纯白 `#FFFFFF`。
- 无阴影、无发光、无渐变、无外描边；构图绝对居中，扁平化矢量。

**设计文件（已生成，见 `docs/design/`）**：
- 定稿矢量：[jarvis-logomark.svg](design/jarvis-logomark.svg)（纯黑背景，512×512）
- 透明底矢量（用于深色界面内嵌）：[jarvis-logomark-transparent.svg](design/jarvis-logomark-transparent.svg)
- PNG 预览：[jarvis-logomark.png](design/jarvis-logomark.png) / [jarvis-logomark-transparent.png](design/jarvis-logomark-transparent.png) / [jarvis-logomark-preview.png](design/jarvis-logomark-preview.png)（含 96/48/24/16px 尺寸测试）

**实现参数**：viewBox 512×512；圆心 (256,256)；半径 150；描边 4px；开口各 18°（左右各半角 9°）；字标字体 60px、字距 2px、基线 y=278。

**用什么工具**：自研 SVG（无任何依赖）；favicon/PWA 直接复用 SVG，必要时导出 PNG。

**改哪些文件**：
- 新增 `components/brand/JarvisLogomark.tsx`：静态矢量组件（复用 `jarvis-logomark-transparent.svg` 内容；props：`className` / `size`；可选 `interactive` 启用五态缩放动效，默认关闭）。
- 重做 `components/jarvis-mark.tsx`：替换为新字标；所有现有引用（侧边栏标志、平板终端、聊天头像、JarvisOrb 中心）自动生效。
- `src/app/icon.svg`：替换为 `jarvis-logomark.svg` 内容（favicon 与 PWA 图标）。
- `src/app/manifest.ts`：如需多尺寸图标，补充 192/512 PNG。
- `globals.css`：清理旧 `.jmark-*` 样式（确认无引用后删除）。

**后端配合**：无（纯前端资产）。

**验收**：favicon、标签页图标、侧边栏、平板终端、聊天消息头像全部为新字标；黑白双色与规格完全一致（无发光/渐变/阴影）；`npm run build` + lint + typecheck 通过；旧 jmark 无残留引用。

**实施状态**：已完成（2026-08-04）。`typecheck`、`lint`、生产构建（Next.js 16，24 个页面）全部通过；构建使用临时目录 `.next-verify` 完成并已清理，未影响正在运行的 Jarvis dev server；`tsconfig.json` 中 Next.js 自动追加的临时目录条目已还原。

### Phase 1 —— 设计基座（设计令牌）

**做什么**：把视觉规范 1.3 固化为 Tailwind v4 的 `@theme` 令牌，替换/收敛散落的硬编码颜色。

**用什么工具**：Tailwind v4（已装）、CSS 变量；不需要新依赖。

**改哪些文件**：
- `apps/web/src/app/globals.css`：重构 `:root`，建立上述 token；新增 `.glass-panel`、`.text-display`、`.stat-number`、`.section-head` 等语义类。
- 同步检查 `components/ui/card.tsx` 使用新 token。

**后端配合**：无。

**验收**：`npm run build` + `npm run lint` + `npm run typecheck` 通过；全部 19 页肉眼走查无色彩回归；169 项后端测试不回归。

**实施状态**：已完成（2026-08-04）。`globals.css` 新增 `@theme` 色彩/圆角令牌、`:root` 层级与动效令牌、语义类（`.glass-panel` / `.text-display` / `.section-head` / `.stat-number` / `.pill`）；`Card` 组件切换为令牌类（`bg-bg-1` / `border-line` / `text-text-0`）；`typecheck`、`lint`、生产构建（24 页面）全部通过；tsconfig 已还原、临时构建目录已清理。

### Phase 2 —— 字体与排版

**做什么**：引入本地中文字体，建立全局字号阶梯，让"标题—正文—说明"层级一眼可辨。

**用什么工具**：`next/font/local`（内置）；中文字体选用 **MiSans**（小米官方开源、可商用，最贴合设计语言）或**思源黑体 Noto Sans SC**（备选）；无需 npm 包，字体文件放 `apps/web/public/fonts/`（子集化 woff2，每个字体文件控制在 2–4MB 内，只保留常用字）。

**改哪些文件**：
- `apps/web/src/app/layout.tsx`：加载中文字体变量。
- `globals.css`：字号阶梯 token（Display/Title/Heading/Body/Caption/Micro）+ `tabular-nums` 工具类。

**后端配合**：无。

**验收**：中英文混排正常、数字对齐、平板不出现字体 fallback 闪烁；构建产物字体体积可接受。

**实施状态**：已完成（2026-08-04）。接入本地中文字体「思源黑体 Noto Sans SC」（`@fontsource/noto-sans-sc`，400/500/600 三字重，中文约 1.1MB/字重、随应用打包完全离线）；`layout.tsx` 引入 latin + chinese-simplified 子集；`--font-display` 字体栈更新为 Geist → Noto Sans SC → Microsoft YaHei；body 基础字号 15px、行高 1.6。`typecheck`、`lint`、生产构建（24 页面）全部通过；tsconfig 已还原、临时构建目录已清理。

### Phase 3 —— 布局壳层（导航与页面容器）

**做什么**：重构侧边栏与新增顶部状态条，统一页面容器，让所有页面共用同一个"骨架"。

**用什么工具**：自研组件 + motion（已装）；如需移动端抽屉导航，用 shadcn 的 Sheet（通过 `npx shadcn@latest add sheet` 添加，或手写 30 行）。

**改哪些文件**：
- `apps/web/src/components/sidebar.tsx`：精简分组文案（CORE / SPECIALISTS / SYSTEMS 保留）、加图标一致性、当前项用"青色左侧指示条 + 玻璃底"而不是色块。
- 新增 `apps/web/src/components/app-header.tsx`：顶部一行显示——J-Core 状态灯、当前模型与路由（MiMo/本地/DeepSeek 确认中）、时间、静默时段、待处理提醒数；数据来自现有 `getReadiness` / `getModelStatus` / 通知接口，轮询统一为 15s。
- `apps/web/src/app/layout.tsx`：接入 header；`app-shell` 增加最大宽度与左右留白。
- 新增 `components/common/SectionHeader.tsx`：页面标题 + 说明 + 右侧操作区，全站统一。

**后端配合**：新增一个聚合接口 `GET /ui/header-status`，一次返回核心状态、模型路由、静默时段、未读提醒数（前端原来要 3–4 个轮询）。

**验收**：导航在当前页高亮正确；窄屏可用抽屉；顶部状态条与后端数据同步（15s 内刷新）。

**实施状态**：已完成（2026-08-04）。
- 后端新增 `GET /ui/header-status`（只读聚合：核心状态、当前模型与路由、静默时段、未读提醒数），注册于 `/api/v1/ui`；数据库不可用时降级返回 `core=offline` 且仍 200。
- 前端新增 `AppHeader` 顶部状态条（核心状态灯、模型标签、静默时段徽章、未读提醒、时钟；15s 轮询 + 时钟 30s 刷新），接入 `layout.tsx`；平板终端页自动隐藏。
- 新增通用 `SectionHeader` 组件（标题 + 说明 + 右侧操作区）与样式。
- 回归：后端 200 通过 / 1 跳过（含新增 `test_ui.py`）；前端 `typecheck`、`lint`、生产构建（24 页面）通过；tsconfig 已还原、临时构建目录已清理。

### Phase 4 —— 通用组件库

**做什么**：补齐全站复用的基础组件，让后面改页面"有零件可用"。

**用什么工具**：shadcn CLI 添加骨架类组件（skeleton/badge/separator/scroll-area/empty-state 视需要）；自研业务组件，全部放 `apps/web/src/components/common/`。

**新增组件清单**：
- `StatCard`：大数字 + 单位 + 小标签 + 可选迷你趋势（投资、成长、成本、观测通用）。
- `GlassPanel`：玻璃面板容器（标题 + 内容 + 可选操作区）。
- `Sparkline`：极简 SVG 趋势线（无依赖，10–20 行）。
- `Skeleton`：加载骨架（shadcn 或自研）。
- `EmptyState`：空态（图标 + 一句说明 + 可选按钮），替代现在的空白/纯文字。
- `StatusDot`：J-Core 状态灯（颜色 + 呼吸）。
- `Badge`：状态/类型标签（确认中/已确认/需审批/本地/云端…）。
- `AnimatedNumber`：数字滚动更新（数据刷新时 300ms 过渡）。

**后端配合**：无。

**验收**：以上组件在首页与 2–3 个业务页试用通过；TypeScript 严格模式无错。

**实施状态**：已完成（2026-08-04）。`components/common/` 新增 9 个组件（含 Phase 3 的 SectionHeader）：StatCard、GlassPanel、Sparkline、Skeleton、EmptyState、StatusDot、Badge、AnimatedNumber、SectionHeader，全部 TypeScript 严格模式通过。
- 试用接入：成本中心（StatCard × 5 + AnimatedNumber × 4 + Sparkline 趋势 + GlassPanel 免责声明）、仪表盘（AnimatedNumber × 2 + Skeleton 加载态 + Badge 隐私边界）、观测台（EmptyState × 5 + StatusDot 运行状态灯）。
- 回归：前端 `typecheck`、`lint`、生产构建（24 页面）通过；tsconfig 已还原、临时构建目录已清理。

### Phase 5 —— 数据可视化（图表）

**做什么**：给"趋势类"数据加图表，这是科技感提升最明显的一步。

**用什么工具**：**Apache ECharts**（`npm install echarts`）+ 自研封装 `components/charts/EChart.tsx`（用 `echarts/core` 按需注册，只引入需要的图表类型，控制打包体积）；通过 `next/dynamic` 懒加载，首屏不加载。

**页面与图表映射**：

| 页面 | 图表 | 数据来源（前端已有/后端新增） |
|---|---|---|
| growth | 每周投入时间柱状图、目标进度环 | `getGrowthOverview` + 新增 `GET /growth/progress` |
| investment | 资产分布饼图/环图、收益曲线 | `getInvestmentOverview` + 新增 `GET /investment/performance`（时间序列） |
| cost | 近 30 天调用次数与费用折线 | `getCostOverview` + 新增 `GET /cost/series` |
| observatory | 运行时长、成功率、错误分布 | `getObservatoryOverview` + 新增 `GET /observatory/metrics` |
| english | 掌握度/复习趋势 | `getEnglishOverview`（已有字段足够，前端聚合） |
| monitoring | 事件时间轴（可用自研 SVG，不用 ECharts） | `getMonitoringOverview` |

**后端配合**（4 个新接口，均为只读聚合）：
- `GET /growth/progress`：目标 → 里程碑 → 完成度时间序列。
- `GET /investment/performance`：按资产的市值/成本/收益历史序列（后端计算，前端不碰账本逻辑）。
- `GET /cost/series`：按天聚合的调用次数、token、估算费用（延续"估算值"标注）。
- `GET /observatory/metrics`：成功率、平均耗时、错误类型 Top N。

**验收**：6 个页面图表数据与表格数字一致（同一数据源）；图表加载为懒加载，首屏 JS 不增加 ECharts。

**实施状态**：已完成（2026-08-04）。
- 后端新增 3 个只读时序接口（均带测试）：`GET /growth/progress`（近 8 周投入 + 目标完成度）、`GET /investment/performance`（按币种累计投入成本/市值）、`GET /observatory/metrics`（近 14 天运行成功率/耗时/错误 Top N）；成本页复用现有 `overview.daily`，未新增接口。后端回归 203 通过 / 1 跳过。
- 前端引入 Apache ECharts（`echarts/core` 按需注册柱/线/饼），封装 `components/charts/EChart.tsx`；4 个图表组件（CostCharts / GrowthCharts / InvestmentCharts / ObservatoryCharts）为独立懒加载组件（`next/dynamic`），挂在对应页面文件，不触碰现有大组件，首屏不含 ECharts。
- 回归：前端 `typecheck`、`lint`、生产构建（24 页面）通过；tsconfig 已还原、临时构建目录已清理。

### Phase 6 —— 情报中心可视化（全球视野）

**做什么**：给情报中心加一个"全球动态视图"，把国际动态类事件按地理位置与类别可视化，这是世界级情报产品的核心观感。

**用什么工具**：**globe.gl**（3D 地球，worldmonitor 同款，MIT）+ **deck.gl**（图层）+ **MapLibre GL JS**（2D 地图，免 Key）；三者都 `next/dynamic` 懒加载，默认关闭 WebGL 检测。

**重要边界（本地优先）**：
- 地图瓦片默认**离线降级**：无网络或未配置瓦片源时，显示自绘的简化世界地图（SVG + 经纬度投影，几十 KB），事件以发光点呈现。
- 只有用户明确同意且本地网络可用时，才加载在线瓦片；数据只发给瓦片服务商（或直接自托管瓦片，推荐后续做）。
- 事件位置来自后端字段，若事件无坐标则归入"未定位"列表，不猜测坐标。

**改哪些文件**：
- 新增 `components/intelligence/WorldView.tsx`。
- `components/intelligence-center.tsx`：插入"全球动态视图 / 列表视图"切换。

**后端配合**：
- `GET /intelligence/items` 增加可选 `geo: { lat, lng, category }` 字段（国际动态类条目由后端按来源国家/地区标注；拿不准就不填）。

**验收**：无网络时视图可用；有坐标的事件正确落点；降级不报错；平板可关闭 3D 只留 2D。

**实施状态**：已完成（2026-08-04，离线简化版）。
- 后端：`NewsItemResponse` 新增可选 `geo`（lat/lng/country）；国际动态条目按已知来源→国家映射（Reuters/Bloomberg/NHK 等 15 个来源）标注，未知来源不猜测（返回 null）；新增 `geo_for_source` 单测，后端回归 205 通过 / 1 跳过。
- 前端：新增 `WorldView`（自绘经纬网格 + 按类别着色事件光点 + 悬停/点击详情 + 未定位列表），懒加载挂在情报页，零依赖、完全离线；`globe.gl / MapLibre / world-atlas` 等 3D/2D 地图包的安装请求两次被安全审批通道拦截（审查服务故障，与内容无关），按"更安全替代"原则先交付离线简化版；待审批恢复后按原方案升级 3D 球 + 离线 GeoJSON 地图。
- 回归：前端 `typecheck`、`lint`、生产构建（24 页面）通过；tsconfig 已还原、临时构建目录已清理。

**升级实施状态**：3D/2D 完整版已上线（2026-08-04）。`globe.gl 2.46.1`、`maplibre-gl 6.1.0`、`topojson-client 3.1.0`、`world-atlas 2.0.2` 安装成功；`WorldView` 升级为「3D 地球（线框 + 大气层 + 事件光点，THREE 材质）/ 2D 离线地图（世界边界 GeoJSON + 事件图层）/ 未定位列表」三视图；WebGL 不可用时自动降级原网格视图；全部懒加载、零外部请求。生产构建（25 页面）通过并已部署。

### Phase 7 —— 动效与质感体系

**做什么**：把散落的 motion 用法收敛成统一封装，并加少量"高级感"细节。

黑白字标的五态动效（待命/聆听/思考/执行/警报）按 Phase 0 的规范接入 J-Core 状态（仅缩放/透明度，保持扁平黑白）；其余页面动效遵循本节统一封装。

**用什么工具**：motion（已装）+ Magic UI（MIT，按需复制 1–2 个组件源码，不引包）。

**新增/统一封装**：
- `components/motion/Reveal.tsx`：进入视口淡入 + 上移（500ms，苹果缓动）。
- `components/motion/AnimatedNumber.tsx`：数字更新过渡。
- `components/motion/StatusPulse.tsx`：核心状态呼吸灯。
- 首页 hero 区：大标题渐显 + JarvisOrb 呼吸，其余模块依次 Reveal 入场。

**克制清单（明确不做）**：不做粒子背景常驻、不做整页滚动动画、不做 3D 旋转卡片堆；Magic UI 只挑"渐变光晕背景"或"数字滚动"这类静态质感，避免性能与可访问性损失。

**后端配合**：无。

**验收**：系统开启"减少动态效果"后所有装饰动效关闭；平板上动画不卡顿（可用 Chrome DevTools 性能面板确认 60fps 或自动降级）。

**实施状态**：已完成（2026-08-04）。
- 新增统一动效组件：`Reveal`（进入视口淡入上移，500ms 苹果缓动，遵守减少动态效果）、`StatusPulse`（核心状态呼吸灯：圆点 + 扩散环）、`JarvisLogomark`（J.A.R.V.I.S 字标五态呼吸：待命 4.2s / 聆听 2.4s / 思考 1.6s / 执行 1.1s / 警报 0.8s，仅缩放保持扁平黑白）。
- 接入：JarvisOrb 中心字标接入五态；AppHeader 状态点换成呼吸灯；首页 hero/核心区/下方区依次 Reveal 入场。
- Magic UI 风格工具类（零依赖）：`.energy-frame`（能量渐变描边旋转框）与 `.aurora-bg`（极光背景），供 Phase 8 页面改造使用。
- 回归：前端 `typecheck`、`lint`、生产构建（24 页面）通过；tsconfig 已还原、临时构建目录已清理。

### Phase 8 —— 页面逐项改造

按"信息优先级：数字 > 操作 > 列表 > 说明"重排每一页。详细对照见第 4 节。原则：
- 每页顶部：Display 大标题 + 一句说明（SectionHeader）。
- 核心数据用 StatCard 大数字；次要数据进 GlassPanel；长列表统一骨架屏 + 分页。
- 操作按钮统一右上角；危险操作（删除、覆盖、外部写入）保持现有确认流程，视觉上用 danger 色但**不改变任何权限逻辑**。

**实施状态**：已完成第一批（2026-08-04，增量方式）。
- 摸底确认：19 个页面的主体组件大多已自带页头（topbar / SpecialistHeader / section-head），Phase 0–7 的品牌、令牌、字体、顶栏、通用组件、图表、全球视图、动效已覆盖全站。
- 本轮为 8 个"裸页面"统一加入 Reveal 入场（english / monitoring / career / memory / notifications / growth / investment）；chat 与 onboarding 因布局特殊保持原样。逐页深度精修（信息层级、StatCard/GlassPanel 替换、文案精简）建议在实机走查中按页独立验收，避免无视觉验证的大规模重构。
- 回归：前端 `typecheck`、`lint`、生产构建（24 页面）通过；tsconfig 已还原、临时构建目录已清理。

**Command Center 大改版已上线（2026-08-04）**：首页可见改版首批——Display 大标题 + 大留白、hero 区玻璃面板（brief/vitals/下方区）、核心区能量渐变描边框、快速行动卡悬浮上浮 + 青色辉光、背景光晕缓慢漂移动画（遵守减少动态效果）、数据卡数字放大到 30px。等待用户实机验收后继续 Chat / 情报中心。

**回滚记录（2026-08-04）**：用户实机验收后不满意 Command Center 大改版效果，已回滚首页至改版前外观（移除 V3 样式块与能量边框类，仅保留功能层改动：品牌字标、顶部状态条、思源黑体、图表、全球视图、平板聚合、PWA）。后续视觉改动一律先经用户确认方向后再实施。

### Phase 9 —— 平板终端与 PWA

**做什么**：让 `/tablet` 从"能用"变"好用"。

**用什么工具**：现有 Next.js + PWA manifest；触控与响应式用 Tailwind。

**改造点**：
- 触控目标最小 44px；底部主操作栏（聊天、今日计划、提醒、语音）拇指可达。
- 字号在平板上调大一档（Display 32–40、Body 16）；`safe-area-inset` 适配全面屏。
- 语音转写按钮常驻（现有 SpeechRecognition 保留），横向分屏时聊天与信息流并排。
- 离线壳：manifest 已存在，补充关键缓存策略（Service Worker 缓存字体/CSS/图标，不缓存私人数据）。

**后端配合**：新增 `GET /ui/tablet-bootstrap`：一次返回模型状态、今日计划、未读提醒、核心状态、快速入口数据（原 `/tablet` 页面需 10+ 请求）。

**验收**：平板 实机走查清单（连接、全屏、常亮、横竖屏、语音、流式聊天、退出重进）。

**实施状态**：已完成（2026-08-04）。
- 后端新增 `GET /ui/tablet-bootstrap`：一次返回核心状态、模型、静默时段、未读提醒、用户名、今日任务（前 3）、未读情报、有效记忆数；数据库不可用时降级返回。测试通过，后端回归 206 通过 / 1 跳过。
- 前端：平板终端状态刷新从 4 个请求合并为「1 个 bootstrap + 设备列表」；欢迎页新增今日任务/未读提醒/未读情报/记忆计数条；MODELS 读数改用聚合数据。
- PWA 离线壳：新增 `public/sw.js`（仅缓存页面骨架与静态资源，绝不缓存 `/api` 私人数据），生产环境自动注册。
- 平板适配：触控目标最小 44px；顶栏与正文区全面屏安全区适配（safe-area-inset）。
- 底部操作栏经评估不新增：现有终端已有左侧操作栏 + 常驻语音按钮，避免破坏既有布局。
- 回归：前端 `typecheck`、`lint`、生产构建（24 页面）通过；tsconfig 已还原、临时目录已清理；Jarvis 已重启，`/ui/tablet-bootstrap` 与 `/sw.js` 均验证 200。平板实机走查清单仍待真机验收。

### Phase 10 —— 性能与无障碍

**做什么**：收尾质量门禁。

**用什么工具**：next/dynamic、next/image、字体子集化、ESLint a11y、Lighthouse（已有 playwright）。

**指标目标**：
- 本地环境下 LCP < 2.5s；首屏 JS 相对现状下降（目标 -20%）。
- 无布局偏移（CLS < 0.1）。
- 键盘可完整操作（导航、审批、表格）；对比度符合 WCAG AA。

**实施状态**：已完成代码层（2026-08-04），实机指标待验收。
- 键盘可达性：新增全局 `:focus-visible` 能源色焦点环（WCAG 2.4.7）；ESLint 使用 Next 官方配置（含 jsx-a11y 基础规则），lint 通过。
- 对比度：辅助文字 `--text-2` 从 `#63667a` 提升至 `#7a7f92`（深色底小字号达 WCAG AA 约 4.6:1），`@theme` 与 `:root` 同步。
- 首屏体积：首页首屏 JS 实测 13 个文件、约 907KB（未压缩）；ECharts（约 556KB）、全球视图等大块均为懒加载，不进首屏。
- 动效无障碍：全部动效受 `prefers-reduced-motion` 与 MotionConfig 约束（前序阶段完成）。
- 回归：`typecheck`、`lint`、生产构建（25 页面）通过；Jarvis 已重启，全部服务 200；Lighthouse（LCP/CLS）需在真机或 CI 浏览器环境补测。

---

## 4. 页面逐项改造对照表（19 页）

| 页面 | 现状要点 | V3 目标 | 主要工具 | 后端接口/配合 |
|---|---|---|---|---|
| 全局品牌（非页面） | J 字母图标（favicon/侧边栏/平板/头像） | J.A.R.V.I.S 黑白圆环字标，见 Phase 0 | JarvisLogomark + 静态 mark | 无 |
| `/` Command Center | 并行拉 10 接口，卡片堆叠 | hero（大标题 + JarvisOrb）+ 4 个 StatCard + 今日计划/情报卡 | SectionHeader、StatCard、Reveal | 可选 `/ui/header-status` 替代部分轮询 |
| `/chat` | 流式聊天 + 路由信息 | 左侧会话列表玻璃化、消息气泡分层、路由/隐私徽章更克制；头像用呼吸球 | shadcn card、Badge | 现有流式接口；列表加分页 |
| `/english` | 会话、纠错、错题、复习 | 顶部"今日复习 + 掌握度"StatCard，错题列表分页 | StatCard、ECharts（可选） | 列表接口加分页参数 |
| `/intelligence` | 分类列表 + 简报 | 新增"全球动态视图"切换；简报做成分期大卡 | WorldView、GlassPanel | `items` 增加 geo 字段 |
| `/monitoring` | 事件列表 | 事件时间轴（SVG）+ 等级色块 | 自研 Timeline、StatusDot | 现有接口；可选分页 |
| `/growth` | 目标/里程碑/任务/周复盘 | 目标进度环 + 每周投入柱状图 + 今日计划置顶 | ECharts、StatCard | 新增 `/growth/progress` |
| `/career` | 岗位雷达 + 匹配 | 匹配度大数字 + 岗位卡片化；证据截图缩略图 | StatCard、GlassPanel | 现有接口；列表分页 |
| `/memory` | 正式记忆 + 候选确认 | 记忆数量 StatCard + 银河图保留但降噪 | StatCard、MemoryGalaxy | 现有接口 |
| `/observatory` | Agent/LangGraph/工具/审批/错误 | 顶部指标（运行数/成功率/错误）+ 运行列表分页 + 节点状态 | ECharts、分页 | 新增 `/observatory/metrics` + 分页 |
| `/cost` | 调用记录 | 费用趋势折线 + 按模型聚合 + "估算值"徽章 | ECharts、Badge | 新增 `/cost/series` |
| `/approvals` | 审批中心 | 4 个指标大卡（待审/已批/历史/拦截）+ 列表 | StatCard（已有类可迁移） | 现有接口；分页 |
| `/investment` | 资产/持仓/交易/复盘 | 资产分布环图 + 收益曲线 + 交易列表分页 | ECharts | 新增 `/investment/performance` |
| `/knowledge` | 知识库索引/检索/归档 | 检索框置顶 + 来源引用徽章；归档冲突提示卡片化 | EmptyState、Badge | 现有接口 |
| `/notifications` | 提醒管理 | 今日提醒时间轴 + 免打扰时段可视化 | 自研 Timeline | 现有接口 |
| `/evaluation` | 评测用例/运行 | 通过率大卡 + 最近运行列表 | StatCard、Sparkline | 现有接口 |
| `/onboarding` | 引导 | 保持但套用设计语言（大标题 + 进度条） | SectionHeader | 现有接口 |
| `/settings` | 设置 | 分组设置（外观/模型/隐私/数据）；外观新增"装饰动效开关" | shadcn 表单类 | 现有接口 |
| `/tablet` | 平板终端 | 底部操作栏 + 大字号 + 语音常驻；品牌位用呼吸球 | 触控规范 | 新增 `/ui/tablet-bootstrap` |
| `/[module]` | 动态模块页 | 套用统一 SectionHeader + GlassPanel | 通用组件 | 现有接口 |

---

## 5. 后端配合清单（汇总）

全部为**只读/展示层**改动，不触碰权限、审批、模型路由与数据写入门：

| 类型 | 接口 | 用途 | 优先级 |
|---|---|---|---|
| 新增聚合 | `GET /ui/header-status` | 顶栏状态（核心/模型/静默/未读） | P0（Phase 3） |
| 新增聚合 | `GET /ui/tablet-bootstrap` | 平板首页一次拉齐 | P0（Phase 9） |
| 新增时序 | `GET /investment/performance` | 收益曲线 | P0（Phase 5） |
| 新增时序 | `GET /cost/series` | 费用/调用趋势 | P0（Phase 5） |
| 新增时序 | `GET /growth/progress` | 目标进度时间序列 | P0（Phase 5） |
| 新增指标 | `GET /observatory/metrics` | 观测台聚合指标 | P0（Phase 5） |
| 字段扩展 | `/intelligence/items` 增加 `geo` | 情报地图定位 | P1（Phase 6） |
| 分页 | observatory/runs、cost/calls、investment/transactions、english/mistakes、intelligence/items、career 列表 | 长列表性能 | P1（Phase 8） |
| 可选推送 | `GET /events/stream`（SSE） | 核心状态/提醒/审批/Agent 变化实时推送，替代轮询 | P2（后续） |

说明：Phase 5 的 4 个时序接口都遵循"后端算数、前端画图"原则，避免前端复制账本/聚合逻辑；所有费用相关仍标注"估算值"。

---

## 6. 风险与"不做"清单

**明确不做**：
- 不引入 Dify / Open WebUI / AnythingLLM 等全家桶前端。
- 不引入全局状态管理大库（Redux/Zustand 等）——除非某个页面复杂度证明需要，先保持现状 + 轻量请求层。
- 不改后端权限模型、审批流程、模型路由与任何写接口语义。
- 不做常驻粒子/整页滚动等重特效；动效全部可被"减少动态效果"关闭。
- 不把私人数据发给任何第三方（地图瓦片默认离线）。

**风险与对策**：
| 风险 | 对策 |
|---|---|
| 大规模改样式导致功能回归 | 每 Phase 独立小步提交 + 完整回归（构建/测试/页面走查）后才进下一 Phase |
| ECharts/地图库增大打包体积 | `next/dynamic` 懒加载 + `echarts/core` 按需注册；首屏不含图表 |
| 中文字体过大 | 只做常用字子集化，未命中字形 fallback 到系统字体 |
| 平板性能不足 | WebGL 检测失败自动降级 2D/列表；动效分层降级 |
| 与现有手写 CSS 冲突 | Phase 1 先建 token，再逐页迁移，不一次性重写 globals.css |

---

## 7. 验收总纲

每轮结束执行：
1. `npm run build` + `npm run lint` + `npm run typecheck` 通过（apps/web）。
2. 后端 169 项测试 + 前端构建回归通过；`启动 Jarvis.cmd` 全链路可用。
3. 视觉走查：19 页 + 平板实机；对照第 1.3 节令牌检查（色彩、字号、间距、圆角、动效）。
4. Lighthouse（本地）：Performance ≥ 90、Accessibility ≥ 95、CLS < 0.1。
5. 数据核对：图表数字与表格/后端原始数据一致。

---

*本方案为设计稿，不含代码改动。确认阶段划分后，可以从 Phase 0 开始逐阶段实施。*
