# MIGRATION_SPRINT_2_AI_PRE_STUDY.md — Sprint 2 预研归档（AI Agent Engineer 产出）

- **文档类型**：Tech Lead 归档（源自 AI Agent Engineer Sprint 1 预研交接，2026-08-06）
- **用途**：Sprint 2（AI 能力落地）实施时的起点方案，落地细节以真实代码为准

---

## 1. Prompt 集中管理（现状扫描结论）

全库 22 处硬编码 prompt 位置；`services/prompts/` 不存在；DB 无 prompt 表；
`prompt_version` 仅存在于 `agent_core/catalog.py` 的 6 个 AgentSpec 声明（无内容存储、无对账）——审计 H4。

### 1.1 系统 prompt 迁移清单（可版本化）

| # | 位置（文件:行） | 用途 | 建议 prompt id |
|---|---|---|---|
| 1 | personality.py:17 | 人格边界 | personality.boundaries |
| 2 | personality.py:24 | 人格声明 | personality.disclaimer |
| 3 | personality.py:29/:35 | 语气表（zh/en） | personality.tones |
| 4 | personality.py:85 | 人格块（build_personality_block） | personality.block |
| 5 | personality.py:131 | Chat 系统 prompt（含档案注入） | personality.chat_system |
| 6 | personality.py:148 | English Coach 人格行 | personality.coach_line |
| 7 | english.py:33 | English Coach 系统 prompt | english.coach |
| 8 | english.py:77 | 会话总结分析 prompt | english.summary_analysis |
| 9 | knowledge_capture.py:31 | 知识草稿捕获 | knowledge.capture |
| 10 | knowledge_insights.py:44 | 洞察候选提取 | knowledge.insight |
| 11 | knowledge_retrieval.py:201 | 知识上下文注入（不可信数据声明） | knowledge.retrieval_context |
| 12 | memory_engines.py:41 | Mem0 影子提取指令 | memory.mem0_instructions |
| 13 | memory_engines.py:50 | Qwen 本地记忆提取 | memory.qwen_extract |
| 14 | conversation_summary.py:44 | 摘要上下文注入 wrapper | summary.context_wrapper |
| 15 | conversation_summary.py:90 | 长对话压缩 prompt | summary.compress |
| 16 | growth_workflow.py:601 | Growth Agent 系统 prompt | growth.agent_system |
| 17 | research_workflow.py:794 | Research Agent 系统 prompt | research.agent_system |
| 18 | intelligence.py:956 | 情报编辑系统 prompt | intelligence.editor |
| 19 | context_engineering.py:150 | 已确认记忆注入 wrapper | memory.confirmed_wrapper |
| 20 | api/routes/evaluation.py:144 | 个人能力测试系统 prompt | evaluation.harness |

### 1.2 用户角色模板（kind="user"，一并纳入）

- growth_workflow.py:664（`_planning_prompt`）
- research_workflow.py:865（`_research_prompt`）
- english.py:345 与 api/routes/english.py:661（「请用正确的英语重写：…」复习模板）

### 1.3 非模型文案（不进注册表，仅记录）

两 workflow 的 DeepSeek 确认载荷（`purpose`/`message`/`alternatives`，growth ~L560、
research ~L750）属用户确认界面文案，如需模板化放 Sprint 2 二期。

## 2. 目录结构设计（Sprint 2 落地）

```text
apps/api/app/services/prompts/
├── __init__.py                          # 导出 PromptRegistry / get_prompt_registry
├── registry.py                          # register/activate/get/render
├── loader.py                            # 模板加载 + 校验 + 缓存
├── schemas.py                           # PromptSpec（Pydantic）
├── versions.json                        # id → 活动版本 + 元数据
└── templates/
    ├── personality/   core-v2.0.0.toml
    ├── english/       coach-v2.0.0.toml / summary-v2.0.0.toml
    ├── knowledge/     capture-v2.0.0.toml / insight-v2.0.0.toml / retrieval-v2.0.0.toml
    ├── memory/        qwen-extract-v2.0.0.toml / mem0-v2.0.0.toml
    ├── research/      research-v2.0.0.toml（system + user）
    ├── growth/        growth-v2.0.0.toml（system + user）
    ├── intelligence/  editor-v2.0.0.toml
    ├── summary/       conversation-v2.0.0.toml
    └── evaluation/    harness-v2.0.0.toml
```

## 3. 版本注册表 schema

```toml
[prompt]
id = "knowledge.capture"        # 全局唯一 {domain}.{name}
version = "2.0.0"               # semver
kind = "system"                 # system | user | wrapper
agent_id = "jarvis_core"
purpose = "对话 → 知识草稿捕获"
status = "active"               # active | draft | deprecated
content_ref = "templates/knowledge/capture-v2.0.0.toml"
variables = []                  # 渲染变量白名单（防注入）
safety_tags = ["untrusted_input", "no_injection", "no_external_facts"]
created_at = "2026-08-06T00:00:00Z"
```

API：`register` / `activate` / `get` / `render` / `list_active`；`get_prompt_registry()`
lru_cache 单例。模板内容视同代码，不经用户/外部输入拼接；渲染变量必须显式白名单。

## 4. 评测挂接方式

1. `scripts/evaluate-prompts.py` 由 import 具体函数改为按 prompt id + 版本从注册表取内容；
2. `evals/prompt_policy_cases.jsonl`（16 例）每例加 `prompt_version` 字段，漂移即 fail；
3. 新增 `prompt_render` 评测类型（固定变量渲染，断言安全片段包含/排除）；
4. 灰度期支持 active 与 draft 版本 diff；
5. 对账：AgentSpec.prompt_version 必须存在于注册表（消除 H4 假版本号）；
6. 模型级行为仍用 `evals/personal_benchmark_cases.json`，变更后 QA 重跑。

## 5. Router v2 接入 chat 真实路由（4 阶段灰度）

现状核实：`routes/chat.py:227` 有唯一 RouterV2 调用点 `shadow_agent_route()`
（`v2_router_shadow_enabled` 默认 True，产出 `AgentRouteDecision` 随响应返回并写入
assistant message metadata，不保存用户正文副本）；真实链路与影子链路互不关联；
DeepSeek 拦截由 `require_paid_call_confirmation`（chat.py:215，409 语义）独立完成。

| 阶段 | 开关 | 行为 | 验收 |
|---|---|---|---|
| 0（现状） | `v2_router_shadow_enabled=True` | 影子分类+展示+metadata | 现有 63 个 agent/router 测试全绿 |
| 1（Sprint 2） | 新增 `v2_router_enforcement_enabled=False` | 影子决策与真实 ModelRouter 做一致性校验，不一致记 shadow run，仍走原链路 | 校验不影响响应；可一键关 |
| 2（Sprint 2） | `v2_policy_enforcement_enabled=True` | Policy（R0-R3）决策写 Agent Run Step 审计，Tool Gateway 前置校验 | 不改变执行结果；R3 仍禁止 |
| 3（后续） | `v2_router_enforcement_enabled=True` | selected_provider 参与真实 route；WORKFLOW 建议仅引导用户进专业模块，不在 chat 隐式启动 LangGraph | DeepSeek 未确认仍 409；可回滚 |

关键原则：Router 先达评测门槛再获执行权；`require_paid_call_confirmation` 409 逻辑只读；
新增 flag 属 config.py 契约变更，需 Tech Lead 批准并同步 `.env.example`。

## 6. 死 flag 清单（M5，Sprint 2 处理）

- `v2_agent_core_enabled` / `v2_shadow_runs_enabled` / `v2_mem0_chat_shadow_enabled`：无读取点，
  清理需 Tech Lead 批准（config.py 与 .env.example 由 Tech Lead 落）；
- `v2_policy_enforcement_enabled`：无读取点但 Sprint 2 将接为强制入口（不清理，接线）。
