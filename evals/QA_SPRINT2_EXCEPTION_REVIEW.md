# Sprint 2 授权例外复核结论（QA & Reliability）

- **日期**：2026-08-06
- **依据**：`docs/MIGRATION_SPRINT_2.md` §2（QA 属主文件授权例外）与 §6.4（Sprint 3 复核）
- **范围**：AI Engineer 在 QA 属主目录的 7 个文件
- **复核方式**：逐文件通读 + 实际运行（非仅静态检查）

---

## 1. 复核结论

**通过。** 7 个文件均未发现断言弱化、未发现测试造假、未发现为通过而绕过真实
逻辑的行为；覆盖与 Sprint 2 验收声明一致。附 5 条非阻塞改进建议（见 §4），
不影响合入。

## 2. 复核证据

```powershell
& .venv\Scripts\python.exe -m pytest `
    apps/api/tests/test_prompts_registry.py `
    apps/api/tests/test_router_consistency.py `
    apps/api/tests/test_runtime_registry_dual.py `
    apps/api/tests/test_policy_reading_point.py `
    apps/api/tests/test_workflow_registry_audit.py -q
# → 29 passed in 2.61s

& .venv\Scripts\python.exe scripts/evaluate-prompts.py
# → cases 25 / passed 25 / failed 0
```

## 3. 逐文件结论

| 文件 | 断言强度 | 造假风险 | 结论 |
|---|---|---|---|
| `test_prompts_registry.py`（12 例） | 强：集合包含、`pytest.raises`、逐字相等（registry 渲染 == 原函数 fallback）、版本 pin、flag 默认关 | 无（全部走真实 registry/渲染/原函数） | 通过 |
| `test_router_consistency.py`（5 例） | 强：真实 `RouterV2`/`ModelRouter` 路由 + `resolve_route`，inert record 语义、mismatch 记录、metadata 键集合精确断言 | 无 | 通过 |
| `test_runtime_registry_dual.py`（4 例） | 强：双 Runtime 注册、flag 关闭抛错、DIRECT runtime 真实执行事件 | 无（WORKFLOW 仅注册未执行，由既有 workflow 测试覆盖） | 通过 |
| `test_policy_reading_point.py`（4 例） | 强：R1/R3 决策 ref 精确断言；R3 四类动作禁止执行 | 无 | 通过 |
| `test_workflow_registry_audit.py`（5 例） | 强：AgentSpec 身份（agent_id/version/runtime）落库断言；policy_gate 步骤开/关双向断言、`output_refs` 精确相等 | 使用 `monkeypatch` 替换 `_invoke`（跳过图执行），属合理接缝：被测对象是身份/审计记录而非图执行 | 通过 |
| `scripts/evaluate-prompts.py` | 强：contract 用例按 `id@version` 从 registry 取文并校验版本漂移；新增 5 条 live parity 逐字锁定（exact/prefix 双模式）；prompt_render 校验 contains + excludes | 无 | 通过 |
| `evals/prompt_policy_cases.jsonl` | 强：路由/记忆/注入红线/渲染占位符/投资交易护栏，期望值均为真实行为契约，非自证式 | 无 | 通过 |

## 4. 非阻塞建议（Tech Lead 可择机消化，不影响本轮）

1. `test_prompts_registry.py` 中 flag 开关用例使用桩 Settings；Sprint 2 已由
   Tech Lead 落地 `config.py` flag 字段，建议后续改真实 `Settings`，与
   `test_router_consistency.py`/`test_policy_reading_point.py` 保持同构。
2. `test_runtime_registry_dual.py` 建议在后续 Sprint 补 WORKFLOW runtime 的
   执行事件断言（当前由既有 growth/research 流程测试间接覆盖）。
3. `test_workflow_registry_audit.py` 的 `_stub_invoke` 接缝建议加注释说明
   与被替换真实实现的关系，降低未来误读为“造假”的风险。
4. `evaluate-prompts.py` 的 `prompt_render` 分支把 expected `excludes` 编码为
   空列表（实际语义正确），建议改为显式比较，提升可读性。
5. 复核确认 `test_router_consistency.py` 的 `resolve_route` 断言依赖
   `mimo_api_key="test-key"` 的最小配置，无网络调用；建议在文件头注明
   “无外部网络”以保证后续维护不引入真实 key。

## 5. 边界说明

- 本复核仅限上述 7 个 QA 属主文件；AI Engineer 的 `services/**`、`chat.py`
  冻结区改动由 Tech Lead 另行验收（MIGRATION_SPRINT_2.md §2）。
- 未执行任何 git 写操作。
