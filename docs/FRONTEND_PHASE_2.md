# JARVIS OS Frontend Redesign — Phase 2

## 状态

已完成 Command Center 与 Jarvis AI Core 重构。

本阶段没有改动 Conversation、English Coach、Information、Growth、Memory
等专项工作区的内部布局，它们将在 Phase 3–5 分别重构。

## Command Center

首页已从高密度仪表盘改为以 Jarvis Core 为中心的个人 AI 入口：

1. 顶部只保留问候、核心服务状态、时间与手动同步。
2. 中央以 Jarvis Orb 为视觉焦点。
3. 左侧显示基于真实计划与情报生成的当前建议。
4. 右侧显示主模型、未读情报与长期记忆上下文。
5. Talk、Research、Plan 三个快捷行动分别进入真实对话、情报和成长模块。
6. 下方每日情报固定展示事件、影响、与你的关系和建议行动。
7. 个人成长轨迹读取今日任务、英语复习、长期记忆和投资持仓。

## AI Core 状态

`src/components/ai/JarvisOrb.tsx` 支持五种正式状态：

| 状态 | 使用场景 | 视觉反馈 |
| --- | --- | --- |
| idle | 系统正常待命 | 缓慢呼吸与低频轨道运动 |
| thinking | 首次载入或手动同步 | 更活跃的能量与粒子反馈 |
| listening | 语音通道开启 | 扩散式聆听波纹 |
| speaking | Jarvis 语音回应 | 核心动态波形 |
| error | 核心连接中断 | 玫红警示能量与恢复提示 |

动画由 Motion 驱动，只改变 transform 与 opacity，并遵循操作系统的
“减少动态效果”设置。

当前 Command Center 会根据真实状态使用：

- 页面首次同步：`thinking`
- 手动同步：`thinking`
- 正常运行：`idle`
- 后端不可用或降级：`error`

`listening` 与 `speaking` 已完成组件能力，将在 Phase 3 的对话与语音工作区
接入实际交互状态。

## 真实数据连接

Command Center 并未使用演示数据，当前读取：

| 页面内容 | 后端能力 |
| --- | --- |
| 用户问候 | Profile |
| Online / Partial | Readiness |
| MiMo / DeepSeek / Local Qwen | Model Status |
| 当前建议和今日任务 | Growth Overview + Today Plan |
| 英语复习 | English Overview |
| 今日情报卡片 | Intelligence Overview + Daily Brief |
| 长期记忆 | Memory Stats |
| 关注持仓 | Investment Overview |

接口采用独立失败隔离：某一项数据读取失败不会让整个首页白屏；核心连接异常时
Orb 会进入 error 状态。

## 组件结构

```text
src/components/
├── ai/
│   ├── AIStatus.tsx
│   └── JarvisOrb.tsx
└── dashboard/
    ├── GrowthCard.tsx
    └── IntelligenceCard.tsx
```

旧版 `jarvis-core.tsx` 已移除，避免维护两套核心状态模型。

## 验收

- 1600×1000 首屏视觉检查通过。
- 1366×768 桌面布局检查通过。
- 完整页面滚动与每日情报卡片检查通过。
- 实际显示 MiMo 主路由、后端服务状态和真实每日情报。
- TypeScript、ESLint 与 Next.js 生产构建通过。
- 平板专用 `/tablet` 路由与后端接口未改动。

## 下一阶段

Phase 3 将重构 Conversation：

- 从传统聊天窗口改成 AI Workspace。
- 增加 Agent Selector 与共享布局动画。
- 将 reasoning、action、memory update 设计为可审计的工作结果区。
- 连接 Jarvis Orb 的 listening / thinking / speaking 状态。
- 保留现有流式回答、停止生成、自动保存、知识增强、隐私模式与模型路由。
