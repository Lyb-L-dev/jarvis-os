# JARVIS OS Frontend Redesign — Phase 1

## 状态

已完成并通过视觉、构建和后端连接检查。

本阶段只建立新的设计系统和全局应用框架。Command Center、Conversation、
English Coach、Information、Growth 与 Memory 的页面内容将在 Phase 2–5
分别重构，避免一次性替换造成视觉与功能回归。

## 设计基础

- 默认背景：`#09090B`，辅以低对比度 cyan / blue / purple 环境光。
- 主色：`#22D3EE`；蓝色：`#3B82F6`；紫色：`#6366F1`。
- 字体：本地打包的 Geist Sans 与 Geist Mono，不依赖运行时网络字体。
- 浮动侧栏：280px、半透明玻璃材质、26px 圆角与柔和阴影。
- 动效：统一使用 Motion，默认遵循系统的“减少动态效果”设置。
- 图标：统一使用 Lucide React，保持一致的线宽和尺寸。

## 组件基础

```text
src/components/
├── motion/
│   └── animations.ts
├── ui/
│   ├── button.tsx
│   ├── card.tsx
│   └── tooltip.tsx
├── providers.tsx
└── sidebar.tsx
```

`components.json` 已加入，后续 shadcn/ui 组件将继续以源码形式纳入项目，
而不是引入封闭组件库。

## 导航与真实功能映射

| 新导航名称 | 路径 | 保留的真实能力 |
| --- | --- | --- |
| Command Center | `/` | 今日任务、系统状态、模型与个人信号 |
| Conversation | `/chat` | 流式对话、模型路由、知识增强、自动保存 |
| English Coach | `/english` | 英语对话、纠错与复习 |
| Information | `/intelligence` | 情报抓取、分析与行动建议 |
| Growth | `/growth` | 目标、任务、计时与复盘 |
| Memory | `/memory` | 长期记忆确认、搜索和管理 |
| 投资 | `/investment` | 资产、持仓、交易、理由与情报关联 |
| 知识库 | `/knowledge` | Obsidian 索引、检索与归档 |
| 提醒 | `/notifications` | 桌面与语音提醒 |
| 评测 | `/evaluation` | 模型与提示词评测 |
| Settings | `/settings` | 模型、隐私、备份与语音设置 |

侧栏的 Online 状态来自 `/api/v1/health/ready` 对应的真实后端检查，
不是静态演示状态。`/tablet` 保持独立全屏布局，不显示桌面侧栏。

## Phase 1 验收

- TypeScript 检查通过。
- ESLint 检查通过。
- Next.js 生产构建通过，共 16 个路由成功生成。
- 后端 69 项测试通过。
- 16 项 Prompt / 路由 / 安全策略评测通过。
- 安全检查通过；保留一项既有提示：Windows 共享账户不应读取 `.env`。
- 1600×1000 桌面首页与对话页完成视觉检查。
- 1240×800 平板专用页完成回归检查，布局与后端连接未受影响。

## 下一阶段

Phase 2 只重构 Command Center 与 Jarvis AI Core：

- 建立新的 `JarvisOrb.tsx`，实现 idle / thinking / listening / speaking /
  error 五种有语义的状态。
- 将当前高密度仪表界面收敛为“AI 核心 + 今日情报 + 快捷行动”的个人 AI
  入口。
- 继续读取真实任务、情报、成长、记忆、投资和模型状态，不使用假数据。
