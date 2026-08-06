# Sprint 12：Obsidian Knowledge Bridge 第一阶段

日期：2026-07-29

## 目标

把 Obsidian 作为 Jarvis 的本地知识层接入，同时保持 PostgreSQL 为任务、记忆、
情报、投资和提醒的唯一事实来源。

## 已完成

- 自动识别当前 Obsidian Vault；
- 连接 `F:\obsidian\NewHub\NewHub`；
- 仅允许访问 Vault 下的 `Jarvis/`；
- 创建 9 个受限知识目录；
- 拒绝非 Vault 路径、驱动器根目录、符号链接、重解析点和越界路径；
- `.obsidian` 不参与扫描或索引；
- 扫描最大 5000 篇、单篇最大 2 MB 的 UTF-8 Markdown；
- 保存标题、类型、相对路径、内容哈希、修改时间、大小和扫描时间；
- 支持关键词、标题、路径和类型筛选；
- 支持通过 Obsidian URI 打开笔记；
- 文件修改后更新索引，删除后软删除索引记录；
- 新增知识库页面、设置入口和侧边栏入口；
- Vault 不可用时不影响 Jarvis 其他模块。

## 验证

- 自动测试：55/55；
- Prompt 与策略评测：13/13；
- TypeScript、ESLint、Ruff：通过；
- Next.js 生产构建：通过；
- 数据库版本：`20260729_0012 (head)`，无遗漏迁移；
- 知识库页面：HTTP 200；
- 真实 Vault：已连接；
- 首次扫描：0 篇，未写入演示笔记；
- 新恢复点：恢复验证通过，共 38 张表。

## 下一步

第二阶段实现受控归档：

1. 已确认长期记忆归档到 `Jarvis/Memory/`；
2. 每日情报归档到 `Jarvis/Intelligence/Daily/`；
3. 周复盘、英语和投资研究采用手动确认归档；
4. 加入幂等键、内容冲突检测、待审核区和归档审计；
5. 首版不自动覆盖用户在 Obsidian 中修改过的文件。
