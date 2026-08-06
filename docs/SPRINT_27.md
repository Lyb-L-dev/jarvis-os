# Sprint 27：Semantic Memory with pgvector

## 状态

已完成，2026-08-02。

## 目标

在不改变正式记忆确认规则、不增加独立向量数据库、也不把私人内容默认发送到云端的前提下，为已确认长期记忆和 Obsidian 文档增加本地语义召回。

## 核心设计

### 事实源与派生索引

- `memories.content` 与 `knowledge_documents.content` 继续是唯一事实源；
- `semantic_index_entries` 只保存来源标识、内容哈希、片段位置和向量；
- 向量表不复制正文，任何时候都能从 PostgreSQL 正文完整重建；
- `semantic_index_states` 保存模型、维度、版本、覆盖数量和最近错误；
- 当前个人数据规模使用 pgvector 精确余弦距离检索，不启用 HNSW；
- 数据规模和实测延迟达到门槛后才评估近似索引。

### 本地 Embedding

- 复用本机已安装的 Ollama `bge-m3:latest`；
- 实测输出为 1024 维；
- Embedding 接口被硬限制为 `localhost`、`127.0.0.1` 或 `::1`；
- 不配置、不调用云端 Embedding；
- 1600 字符分片、200 字符重叠，批次上限 12；
- 模型或 pgvector 不可用时不阻断聊天，自动保留关键词路径。

### 混合检索

- 知识库分别计算关键词排名与语义排名；
- 使用 Reciprocal Rank Fusion 合并两组排名；
- 语义检索没有结果或本地模型故障时，记录原因并回退关键词；
- 检索审计增加 `retrieval_mode`、索引版本、语义结果数和回退原因；
- 长期记忆按当前问题做语义、关键词和重要度联合排序；
- 对话接口与前端无须暴露模型选择。

### 权限与删除一致性

- 未确认、停用、拒绝、过期和软删除记忆不会参与语义检索；
- `retrieval_enabled=false` 的知识文档同步移出索引；
- 内容修改先使旧索引失效，再尝试构建新索引；
- 每次检索都将向量结果重新关联到当前正文和当前内容哈希；
- MiMo / DeepSeek 路线再次检查当前 `cloud_allowed`，索引不能绕过授权；
- 派生索引失败不回滚用户对正式记忆或文档权限的修改。

## 前端

Memory Galaxy 与 Knowledge Center 共用语义索引状态面板，显示：

- 本地模型是否可用；
- 已确认记忆和知识文档覆盖率；
- 向量片段数量；
- 索引版本和最近构建时间；
- 是否正在使用关键词安全回退；
- 手动“重建语义索引”入口。

重建只删除并重新生成派生向量，不修改、删除或覆盖正式记忆和 Obsidian 文件。

## 数据库迁移

已完成迁移：

```text
20260802_0021 -> 20260802_0022
```

新增：

- PostgreSQL `vector` 扩展；
- `semantic_index_entries`；
- `semantic_index_states`；
- `knowledge_retrieval_logs` 的混合检索审计字段。

PostgreSQL 保持 17 主版本，Docker 镜像切换为官方 `pgvector/pgvector:pg17`，继续复用 `jarvis_postgres_data` 命名卷。

## Feature Flag

代码安全默认关闭：

```text
V2_SEMANTIC_MEMORY_ENABLED=false
```

当前个人 Jarvis 环境已在 pgvector 迁移和本地模型验证成功后显式启用。

## 验收结果

- 本机 Ollama：`0.32.5`；
- 本地模型：`bge-m3:latest` 已安装；
- 实际 Embedding：1024 维，单条调用成功；
- Python Ruff：通过；
- Sprint 27 修改后的完整后端回归：140 项通过、1 项跳过；
- 语义边界专项测试覆盖本机地址限制、分片重叠和 SQLite 安全关闭；
- Alembic 单一 Head：`20260802_0022`；
- 迁移前备份：`jarvis-20260802T041506Z-a554afe7.dump`；
- 备份 SHA-256：`4d35110c61cd31123c2fb9e133a6ae81707470b5780035d7e82dff0590066347`；
- 备份已真实恢复验证：53 张表，版本 `20260802_0021`；
- PostgreSQL 镜像：`pgvector/pgvector:pg17`，PostgreSQL `17.10`；
- 镜像摘要：`sha256:7ae6051efd0e60444282c27c7e141af07f322ce033300e727a49c3dd11075e38`；
- 迁移前原数据卷核对：53 张表、版本 `20260802_0021`，完整保留；
- 迁移后数据库：55 张表、版本 `20260802_0022`、pgvector `0.8.6`；
- 首次索引重建：4 篇知识文档、8 个片段、100% 覆盖、无回退；
- 本地实际余弦检索：返回 4 个候选，无回退原因；
- 当前所有 4 篇文档的云端授权均为关闭；
- 前端 TypeScript 与 ESLint：通过；
- Next.js 正式生产构建：17 个页面通过；
- API Live / Ready、Memory 与 Knowledge 页面：HTTP 200；
- 浏览器验收：两个语义面板均就绪，浏览器错误 0、失败请求 0；
- 视觉验收截图：`artifacts/semantic-memory-sprint27-memory.png`、
  `artifacts/semantic-memory-sprint27-knowledge.png`；
- 迁移后恢复点：`jarvis-20260802T044001Z-c63445ff.dump`；
- 迁移后 SHA-256：`973a770293e0dfc673a799588cff3a37bb0f07764fd2d24f5b50dd02e3735c9e`；
- 迁移后恢复点已真实恢复验证：55 张表、版本 `20260802_0022`；
- Jarvis Core、Web、Windows Companion 与自动备份服务已重新启动。

## 安全结论

- 本阶段不调用 MiMo 或 DeepSeek；
- 本阶段没有新的付费模型路径；
- 读取和派生索引可以自动进行；
- 正式记忆仍必须使用原有确认流程；
- Obsidian 写入规则没有改变；
- 不提供投资交易、支付、数据删除或凭据操作入口；
- 语义索引无权执行文档内的指令。

## 本阶段明确不实现

- Mem0；
- 独立 Qdrant / Chroma；
- HNSW 近似索引；
- 云端 Embedding；
- Personality Layer；
- Context Engineering Layer；
- Proactive Engine；
- Agent Observatory；
- Cost Center。

## 架构决策

- [ADR-0007：本地语义索引与权限一致性](adr/0007-local-semantic-index-and-permission-consistency.md)

## 下一阶段

Sprint 28：Mem0 Shadow Evaluation。Mem0 只生成影子候选，不拥有正式记忆，也不自动写入正式记忆。
