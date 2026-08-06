# Sprint 28：Mem0 Shadow Evaluation

## 状态

已完成，2026-08-02。

## 目标

在不改变 Jarvis 正式记忆事实源、不把私人内容默认发送到云端、也不让新引擎自动进入聊天上下文的前提下，真实比较现有规则、本地 Qwen 与 Mem0 的记忆候选质量。

## 核心边界

- `memories` 继续是唯一正式记忆表；
- 正式上下文继续只读取 `active + user_confirmed` 记忆；
- Mem0 只能写入独立的本地派生向量表 `jarvis_mem0_shadow`；
- Jarvis 影子运行与候选分别存入 `memory_shadow_runs`、`memory_shadow_candidates`；
- 没有“将影子候选写入正式记忆”的 API 或界面按钮；
- `V2_MEM0_CHAT_SHADOW_ENABLED=false`，不会在每次聊天后自动消耗本地算力；
- Mem0 故障只使单个影子引擎失败，规则、Qwen、聊天和记忆中心继续可用；
- 关闭 `V2_MEM0_SHADOW_ENABLED` 后，正式系统完整可用。

## MemoryEngine Adapter

三套引擎实现相同的候选提取契约：

- `RuleMemoryEngine`：复用现有确定性规则和敏感信息拦截；
- `QwenMemoryEngine`：通过 Jarvis Model Gateway 显式调用本机 Ollama；
- `Mem0MemoryEngine`：延迟导入 Mem0，使用本机 Ollama LLM、本机 BGE-M3 和本机 PostgreSQL pgvector。

每条候选记录：

- 引擎；
- 记忆类型；
- 内容或敏感拦截占位符；
- 固定评测来源；
- 内容指纹；
- 自动匹配分；
- 人工“正确 / 部分正确 / 错误”判断；
- Mem0 派生记录 ID（仅 Mem0 候选）。

人工判断只标注评测结果，不提供候选转正能力。

## Mem0 本地配置

锁定并审计：

- `mem0ai==2.0.12`；
- `ollama==0.6.2`；
- LLM provider：`ollama`；
- Embedding provider：`ollama`；
- Vector provider：`pgvector`；
- Embedding：`bge-m3:latest`，1024 维；
- PostgreSQL：现有 Jarvis PostgreSQL 17；
- pgvector：精确检索，`diskann=false`、`hnsw=false`；
- `MEM0_TELEMETRY=false`；
- Mem0 工作目录：项目 `.data/mem0`；
- Mem0 历史库：项目 `.data/mem0-shadow-history.db`；
- Ollama 地址必须是本机回环地址；
- 模型缺失时直接停止，禁止 Mem0 自动下载模型；
- 配置完成后再次检查 Mem0 实际 LLM、Embedding 和 Vector provider，任何偏离均拒绝运行。

Mem0 通用安装包会安装 OpenAI、PostHog 和 Qdrant 客户端依赖，但 Jarvis 不向 Mem0 提供云端 provider、云端地址或 API Key，运行时实际 provider 校验为 Ollama / Ollama / pgvector，遥测实测为关闭。

## 16K 本地专用模型

Mem0 2.0.12 的完整提取提示在实测中约为 8,144 tokens，而 Ollama 默认上下文为 4,096。第一次真实运行因此被本地模型主动拒绝，没有产生正式写入。

解决方式：

- 基于已经安装的 `qwen3:4b-instruct-2507-q4_K_M` 创建 `jarvis-memory-qwen:latest`；
- `num_ctx=16384`；
- `num_predict=1000`；
- 别名复用已有模型层，创建过程明确显示 `using existing layer`，不重新下载 2.5 GB 模型；
- 日常聊天仍使用原 Qwen 模型，不被 Mem0 上下文设置影响。

Modelfile：`infra/ollama/JarvisMemory.Modelfile`。

新电脑可在手动安装 Qwen 与 BGE-M3 后运行
`scripts/setup-mem0-shadow.ps1`。脚本只检查并创建本地别名，缺少模型时停止，
不会自动下载。

## 本地多语言评分

Mem0 内置模板可能把中文事实输出为英文。单纯中文关键词会把语义正确的候选误判为失败，因此评分采用：

1. 可解释的关键词匹配；
2. 本机 BGE-M3 多语言余弦相似度；
3. 记忆类型匹配；
4. 敏感信息和安全负例硬性扣分。

真实示例中，英文候选与中文原场景的本地相似度为 `0.7334`，综合匹配分为 `0.762`，正确通过；没有调用云端评分模型。

## 个人记忆评测集

`evals/memory_shadow_cases.json` 共 10 项：

- 回答风格偏好；
- 长期职业目标；
- 教育背景；
- 已完成经历；
- 英语学习弱项；
- 投资记录偏好；
- 明确不要记忆；
- 合成凭据安全边界；
- 临时闲聊过滤；
- 稳定学习习惯。

其中 3 项为零候选安全负例。

## 实测结果

| 引擎 | 已测场景 | 平均 F1 | 安全违规 |
| --- | ---: | ---: | ---: |
| 现有规则 | 10 / 10 | 50% | 0 |
| 本地 Qwen | 10 / 10 | 100% | 0 |
| Mem0 Shadow | 10 / 10 | 100% | 0 |

升级门槛：

- 覆盖全部 10 项；
- Mem0 平均 F1 不低于 80%；
- 敏感信息与安全负例违规为 0。

当前门槛已达到。达到门槛只表示 Mem0 值得保留为影子评测引擎，不代表获得正式记忆写入权；转正必须另立阶段并由用户单独批准。

## 数据库迁移与隔离证据

已完成：

```text
20260802_0022 -> 20260802_0023
```

迁移后 PostgreSQL 共 58 张 public 表。

验收时数据：

- `memory_shadow_runs`：14；
- `memory_shadow_candidates`：18；
- `jarvis_mem0_shadow` 派生向量：9；
- `memories.source_type LIKE 'memory_shadow%'`：0。

## 前端

Evaluation Center 新增 Memory Shadow Lab：

- 显示本地隔离状态；
- 显示云模型、遥测、正式记忆写入和聊天自动运行边界；
- 显示三引擎覆盖率、平均 F1 和安全违规；
- 逐项运行三引擎盲测；
- 对影子候选做人工质量标注；
- 显示升级门槛，但不提供正式记忆写入入口。

浏览器验收：

- 影子实验室可见；
- 本地隔离就绪；
- 10 个场景入口可用；
- 最近结果可见；
- 浏览器错误 0；
- 失败请求 0；
- 截图：`artifacts/memory-shadow-sprint28-evaluation.png`。

## 工程验收

- Python Ruff：通过；
- 后端完整回归：146 项通过、1 项跳过；
- 前端 ESLint：通过；
- TypeScript：通过；
- Next.js 正式生产构建：17 个页面通过；
- Python `pip check`：依赖一致；
- Python 与前端生产依赖审计：0 个已知漏洞；
- API Live / Ready：通过；
- Evaluation 页面：HTTP 200；
- 服务已重新启动。

## 恢复点

- 文件：`backups/jarvis-20260802T054315Z-380dad57.dump`；
- SHA-256：`d08dd051ccc90b0bca9cdfe1172f5fceb764d997de7f246e2161f345bf23baaf`；
- 恢复验证：58 张表；
- Schema：`20260802_0023`。

## Feature Flags

代码默认安全关闭：

```text
V2_MEM0_SHADOW_ENABLED=false
V2_MEM0_CHAT_SHADOW_ENABLED=false
MEM0_TELEMETRY=false
```

当前个人环境在迁移、本地模型和安全评测完成后显式启用 `V2_MEM0_SHADOW_ENABLED=true`；聊天自动影子仍保持关闭。

## 架构决策

- [ADR-0008：Mem0 只能作为可熔断的本地影子记忆引擎](adr/0008-mem0-local-shadow-boundary.md)

## 下一阶段

Sprint 29：Tool Gateway 与 Approval Center。Mem0 继续保持影子模式，不进入正式上下文。
