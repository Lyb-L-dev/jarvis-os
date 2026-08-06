# Tool & Automation — 交接说明 1/3：Computer-use 阶段 3（确认后沙箱文件修改）

- **产出**：Tool & Automation Agent（Sprint 2 只读预研）
- **日期**：2026-08-06
- **类型**：设计交接说明（含现状证据行号），待 Tech Lead 审核后归档 `docs/`
- **对应任务**：MIGRATION_ROADMAP.md Sprint 5 L161「Computer-use 阶段 3：确认后沙箱文件修改（保持 R2 预览-批准-执行）」
- **本轮改动**：无（不改任何产品文件；本文件仅为设计交接）

---

## 0. 结论摘要

1. 阶段 3 的本质是把已注册的 R2 工具 `workspace.file.write` 从「计划层提示」升级为「网关层强制执行」：
   复用现有 Tool Gateway 的预览-批准-执行三阶段，增量补齐 handler 级阶段门禁、写后校验与备份回滚。
2. 现状发现一个**安全缺口**：`workspace.file.write` 的执行 handler 不检查 `computer_use_stage`，
   阶段开关目前只存在于计划生成与状态展示层（见 §1 证据 4、5）。若 `v2_tool_gateway_enabled` 与
   `v2_approval_center_enabled` 均已开启，阶段 2 下仍可能绕过计划层直接提交写工具。
   阶段 3 必须把门禁下沉到 handler/gateway 执行路径。
3. 沙箱写入边界维持 ADR-0009 #13 现状（仅 `.data/tool-sandbox`、`.md/.txt/.json`、≤20_000 字符），
   不扩大到用户任意文件；删除仍属 R3，永不注册工具。

---

## 1. 现状证据（文件:行）

| # | 事实 | 证据 |
|---|---|---|
1 | 当前阶段为 2（只读 + 计划/预览） | `apps/api/app/core/config.py:132` `computer_use_stage: int = 2` |
2 | 沙箱根为 `.data/tool-sandbox`，TTL 30 分钟，单文件上限 20_000 字符 | `config.py:88-90` |
3 | 阶段阶梯定义：阶段 3 = 受控工作区文件写入（需审批） | `apps/api/app/api/routes/computer.py:22-27`（STAGE_LADDER） |
4 | 阶段 2 下 `build_plan` 对写步骤给出 `blocked_by_stage: True` 的提示 | `apps/api/app/services/computer_use.py:168-191`（尤其 L180-190） |
5 | `build_plan` 的 stage 门禁仅影响计划输出；`handle_workspace_file` 本身**不检查** `computer_use_stage` | `computer_use.py:169` vs `apps/api/app/services/tool_catalog.py:539-544` |
6 | 只读能力：`read_workspace_file` 做绝对路径拒绝、resolve+`is_relative_to` 包含校验、后缀白名单、截断与 sha256 | `computer_use.py:21`（后缀）、`:106-132` |
7 | 写工具定义：`WorkspaceFileWriteInput`（relative_path ≤240、content ≤20_000、overwrite 标志） | `tool_catalog.py:42-45` |
8 | 写边界校验：沙箱包含校验、后缀白名单、目录拒绝、已存在文件必须 `overwrite=true` 且重新预览 | `tool_catalog.py:244-269`（`resolve_workspace_target`） |
9 | 预览构建：operation（create/replace）、before/after sha256、size、内容前 4_000 字符、警告 | `tool_catalog.py:280-297`（`workspace_file_preview`） |
10 | 原子写实现：临时文件 + fsync + `os.replace`；产出 before/after sha256 副作用证明 | `tool_catalog.py:494-536`（`_write_workspace_file`） |
11 | 工具注册：`workspace.file.write` action_kind=`MODIFY_FILE`（→R2），allowed_agents={LOCAL_DOCUMENT}，handler 已挂 | `tool_catalog.py:738-753`；风险映射 `apps/api/app/services/agent_core/policy.py:30-36` |
12 | R2 审批管线：提交 → 预览入库 → pending_approval → 批准 → 单独执行；批准后校验参数哈希与权限 | `apps/api/app/services/tool_gateway.py:377-536`（提交）、`:488-528`（审批创建）、`:594-654`（决定）、`:657-669`（执行） |
13 | 执行前复核：approval 必须 approved、参数哈希一致、执行参数与入库哈希一致 | `tool_gateway.py:260-297` |
14 | 执行失败/成功：状态机 + `side_effect_proof` 入库 + 审计事件 | `tool_gateway.py:320-374`；`apps/api/app/db/models/tool.py:28-93`（execution）、`:96-140`（approval） |
15 | 前端契约已具备提交/执行/改提案/批准/拒绝/审批中心端点 | `apps/api/app/api/routes/tools.py:131-152`、`:170-190`、`:193-215`、`:218-263`、`:266-366` |
16 | 红线来源：R2 必须预览-批准-执行；当前文件写入只允许受控沙箱；未来 Computer-use 必须沙箱/VM 运行 | `docs/adr/0009-tool-gateway-human-control-boundary.md:18-19`（#6/#7）、`:25`（#13）；`docs/JARVIS_OS_V2_ARCHITECTURE_MIGRATION_PLAN.md:771`（§12.3） |

---

## 2. 阶段 3 设计

### 2.1 阶段开关与门禁（关键修复）

- 阶段开关：`computer_use_stage` 由 2 提升至 3（`config.py:132`；config.py 属 Tech Lead 冻结面，实施时走变更请求）。
- **强制门禁下沉**：在 `handle_workspace_file`（`tool_catalog.py:539-544`）与 `workspace_file_preview`
  （`tool_catalog.py:280-297`）入口增加 `settings.computer_use_stage >= 3` 校验，低于阶段 3 直接抛
  `ToolCatalogError`，确保「阶段 2 不可写」不再是提示而是强制；`routes/computer.py:48-52` 的 status
  工具表（`workspace.file.write: stage >= 3`）与真实门禁保持一致。
- 阶段 4（外部账号）不随本设计开放；`calendar/email/external.account` 仍保持不可用（见交接 3/3）。

### 2.2 R2 预览-批准-执行三阶段（保留不变）

1. **预览**：`submit_tool` 生成 preview（`tool_catalog.py:280-297`），连同 proposed_parameters、
   parameters_hash、TTL（`config.py:89`）写入 `tool_approvals`（`db/models/tool.py:96-140`）。
2. **批准**：用户可修改提案（`tool_gateway.py:539-591`）、批准或拒绝（`:594-654`）；批准仅置
   `approved` 状态，**不触发执行**。
3. **执行**：`execute_approved_tool` 单独调用（`tool_gateway.py:657-669`）；执行前重新校验
   approval 状态、参数哈希、Agent 白名单与风险上限（`:260-297`、`:88-124`）；批准消费为 `consumed`。

新增约束：预览对象中补充「是否存在备份、恢复将回到哪一版本」字段，让用户在批准前看到回滚信息。

### 2.3 沙箱写入边界

- 根目录：仅 `.data/tool-sandbox`（`config.py:88`），`sandbox_root()` resolve 后校验（`computer_use.py:28-31`）。
- 路径：禁止绝对路径；`resolve()` 后必须 `is_relative_to(root)`；禁止目录目标；禁止以 root 自身为目标。
- 类型与大小：仅 `.md/.txt/.json`；单文件 ≤ `tool_file_max_chars`（20_000，`config.py:90`）。
- 覆盖语义：已存在文件必须显式 `overwrite=true` 并重新生成预览（`tool_catalog.py:267-268`）。
- **TOCTOU 加固**：写入沿用「同目录临时文件 + `os.replace`」原子替换（`tool_catalog.py:503-516`），
  替换后再次 `resolve()` 复核仍在沙箱内；拒绝符号链接/重解析点逃逸（resolve 后包含校验已覆盖常规场景）。
- **写后校验**：`os.replace` 后计算 after_sha256，与预览承诺的 after_sha256 比对，不一致即报错并把
  执行标记为 failed（不允许返回「已写入但哈希不符」的成功结果）。

### 2.4 回滚方式（阶段 3 新增）

- **备份库**：新增沙箱内备份目录（建议 `.data/tool-sandbox/.backups/`，与可写区同根，受同一沙箱边界约束）。
  每次 R2 写入前将原文件字节复制为 `{execution_id}/original.bin`，并落 manifest（path、before_sha256、
  size、execution_id、written_at）；新建文件记录「无原文件」。
- **恢复工具**：新增 R2 工具 `workspace.file.restore`（action_kind=`MODIFY_FILE`，授权仅
  LOCAL_DOCUMENT）：输入 = 目标 execution_id；预览展示目标路径、before/after 哈希与
  「将恢复为写入前内容」；批准后从备份库恢复，恢复后校验 sha256 与 manifest 一致，产出
  `side_effect_proof`。恢复本身是文件修改，必须走同一预览-批准-执行管线。
- **保留策略**：备份默认保留 30 天，由用户或独立运维脚本清理；**Agent 不得自动删除任何文件**
  （删除是 R3，`policy.py:37-42`）。备份清理不得借道恢复工具。
- **审计**：写入与恢复各产生独立 ToolExecutionEvent（`db/models/tool.py:143-161`），
  `side_effect_proof` 记录 before/after 哈希，Approval Center 可见（`routes/tools.py:266-366`）。

### 2.5 与 browser-worker 隔离的关系

文件修改完全由 Jarvis Core 沙箱 handler 完成，不经过浏览器；browser-worker 的 7 层隔离
（`apps/browser-worker/server.cjs:13-14`、`:50-70`、`:117-157`、`:204-214`、`:255-274`、`:471-477`、
`:558-561`）不因阶段 3 有任何削减，浏览器仍无写入/上传/提交路径（ADR-0011:28）。

---

## 3. 与阶段 2 的差异清单

| # | 维度 | 阶段 2 现状 | 阶段 3 设计 | 证据 |
|---|---|---|---|---|
| D1 | 阶段开关 | `computer_use_stage=2` | 提升为 3 | `config.py:132` |
| D2 | 计划层 | 写步骤标记 `blocked_by_stage: True` | 生成可执行 R2 步骤（仍提示需审批） | `computer_use.py:180-190` |
| D3 | 执行门禁 | handler 无 stage 检查（缺口） | handler/preview 强制 `stage>=3` | `tool_catalog.py:539-544` |
| D4 | 状态展示 | `tools.workspace.file.write = stage>=3` | 与强制门禁一致（只读展示） | `routes/computer.py:48-52` |
| D5 | 写入边界 | 包含校验 + 后缀 + 大小 + overwrite | 不变，新增 TOCTOU 复核与写后哈希比对 | `tool_catalog.py:244-269`、`:494-536` |
| D6 | 预览 | before/after sha256、content_preview | 追加备份信息（是否可回滚、恢复目标版本） | `tool_catalog.py:280-297` |
| D7 | 回滚 | 无（仅 before_sha256 证据） | 备份库 + `workspace.file.restore`（R2 管线） | 本节 §2.4 |
| D8 | 审计 | 写入事件 + 副作用证明 | 增加 restore 事件与备份 manifest 审计 | `db/models/tool.py:143-161` |
| D9 | R3 边界 | 删除/凭据/交易/支付禁止 | 不变；恢复≠删除，删除仍无工具入口 | `policy.py:37-42`；ADR-0009:20-21 |
| D10 | 幂等 | 同 key 同参数仅一次副作用 | 不变；restore 同样幂等 | `tool_gateway.py:411-453` |

---

## 4. 红线合规自检

- R2 预览-批准-执行：三阶段保留，且执行前复核全部参数与权限（`tool_gateway.py:260-297`）。✓
- R3 永不自动化：无删除/凭据/交易/支付工具；restore 只回写沙箱内既有备份。✓
- 沙箱写入边界：不扩展到用户任意文件；`.data/tool-sandbox` 外一律拒绝。✓
- browser-worker 7 层隔离不削减：本设计不触碰 browser-worker 任何能力。✓
- 不引入新凭据暴露：本设计无凭据参与。✓

---

## 5. 依赖/契约变更需求（实施时提交 Tech Lead）

1. `apps/api/app/core/config.py:132`（阶段值）与新增备份保留天数配置 → Tech Lead（冻结面）。
2. 新工具 `workspace.file.restore` 属工具注册扩展流程 → 见交接 2/3；`tool_catalog.py` 为我方目录可直接落。
3. 若 `ComputerPlanStep`/status 需展示备份信息 → `apps/api/app/schemas/computer.py` 属 Tech Lead 契约面。
4. 回滚按钮前端展示 → `apps/web/**` 禁止我方修改，需 Frontend Agent 承接。

---

## 6. 风险与回滚

- 风险 1：恢复工具被误用于覆盖新版本 → 预览明示 before/after 哈希，参数哈希复核拦截参数漂移。
- 风险 2：备份库膨胀 → 保留策略配置化 + 独立清理脚本（人工触发）。
- 风险 3：写后校验失败留下半成品 → 原子替换保证目标要么旧要么新；校验失败仅标记 failed 并保留证明。
- 整体回滚：阶段 3 可用 Feature Flag 一键回到阶段 2（`computer_use_stage` 回退）；既有功能零改动。

---

## 7. 交接说明（MULTI_AGENT_TEAM_PLAN §4）

- **修改文件清单**：无（只读预研；本轮未写任何产品文件）。
- **测试结果**：未运行（本轮禁止写代码与执行测试；设计基于静态证据核对）。
- **风险说明**：现状缺口 D3（handler 无阶段门禁）应在 Sprint 5 实施时第一优先修复；恢复工具必须与
  删除边界严格区分（R3）。
- **AI 辅助记录**：未调用付费模型（无 DeepSeek 费用），未发送私人数据。
