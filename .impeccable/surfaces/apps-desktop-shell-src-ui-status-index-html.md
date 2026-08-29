---
version: 1
slug: "apps-desktop-shell-src-ui-status-index-html"
primary_target: "apps/desktop-shell/src-ui/status/index.html"
related_targets: ["apps/desktop-shell/src-ui/status/status.css","apps/desktop-shell/src-ui/status/status.js"]
---

## Scope and mode

- Surface: Jarvis OS V4 Windows desktop runtime status center
- Mode: Operate
- Approved comp: `.impeccable/mocks/v4-status-ledger.png`
- Approval record: `.impeccable/mocks/v4-status-ledger.json`

## Audience and job

Jarvis OS 的系统所有者需要在启动异常、能力降级或日常核查时，迅速判断系统是否可用、具体哪一项发生了什么、证据来自哪里，以及当前允许采取哪些安全恢复动作。

## Primary task and evidence

状态中心是一份来自 Runtime Supervisor 的运行证据台账，不是装饰性健康仪表盘。首屏先给出整体结论与最后检查时间，再将必需运行组件和可选能力分组列出；每行同时呈现状态、归属、版本、检查时间、直接原因和恢复建议。选择证据行后，右侧判断区显示完整详情，操作区只提供与当前运行事实相关的白名单动作。

读取失败时清除陈旧证据并进入明确的不可用状态，不能继续展示可能过期的“正常”结果。导出的脱敏诊断只包含结构化状态和日志元数据，不包含 Token、Cookie、Prompt、日志正文或私人文件内容。

## Direction contract

- **THESIS:** 运行状态是可核对的证据台账；故障判断不能被装饰性指标卡替代。
- **OWN-WORLD:** 延续 Jarvis 的近黑分层表面、细边界和紧凑数据行。青色只标识焦点与主操作，状态色保持字面语义。
- **STORY:** 先确认整体结论，再逐项核对必需/可选组件，最后只执行与当前事实相关的白名单恢复动作。
- **FIRST VIEWPORT:** 顶部是整体结论；左侧宽幅证据台账，右侧窄幅判断与操作；“重新检查”是唯一主操作。
- **FORM:** “运行证据台账”构图；结构候选 6，seed `f25839f8`。批准稿为 `.impeccable/mocks/v4-status-ledger.png`。
- **FINISH:** `unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, and DESIGN.md`

## Approved composition

批准稿固定以下构图承诺：52px 顶部应用栏；其下是整体状态结论与最后检查时间；主体为宽证据台账加窄操作侧栏；底部保留版本、Schema 和操作反馈。主按钮使用高对比青色实心处理，其他动作保持深色次级按钮。细边界、平坦近黑表面和高密度行式信息构成主要材料语言，不引入图表、总分或同尺寸指标卡。

实际构建可用真实 Runtime Supervisor 数据替换稿内示例组件、版本和时间。实现中在右栏操作上方加入“当前所选证据”详情，是为了让键盘/指针选行产生明确的上下文结果，属于可访问且符合任务的适配。批准稿是构图与层级依据，不是运行数据、权限或恢复语义的事实源。

| Visible ingredient | Composition commitment | Implementation medium |
| --- | --- | --- |
| Application bar | Brand, window name, runtime mode; quiet 52px top strip | Semantic HTML, CSS, authored inline SVG |
| Overall verdict | One status dot, one plain-language conclusion, one explanatory sentence, last-check time | Semantic heading/text, runtime data, CSS status tone |
| Evidence ledger | Dominant wide region; required and optional groups; sticky header; dense selectable rows | ARIA table roles, DOM rows, CSS grid, Runtime Supervisor data |
| Selected evidence | Full reason and recovery guidance for the current row | Live DOM text synchronized to row selection |
| Primary action | “重新检查” alone receives solid cyan emphasis and an `F5` hint | Native button, inline SVG, keyboard shortcut |
| Secondary actions | Restart Core, open logs, export diagnostics remain visually quieter | Native buttons, Tauri commands, inline SVG |
| Privacy boundary | Persistent explanation beside the actions, not hidden behind help | Semantic text and inline SVG |
| Footer feedback | Release, schema revision, and latest operation result | Mono metadata and polite live region |

## Evidence ledger behavior

- “必需运行”决定工作台是否可用；“可选能力”失败只造成明确降级，不应伪装成全系统故障。
- 桌面完整列顺序为：组件、状态、归属、版本、最后检查、直接原因/恢复建议。
- 表头在台账内部滚动时保持粘附；真实长标题需要省略或换行而不能破坏列网格。
- 所选行使用淡青底色和内侧 2px 青色标记，同时更新 `aria-selected` 与右栏详情。
- 选择优先级为阻断项、降级项、首项，确保用户先看到最需要处理的证据。
- 空数据与 Supervisor 不可达是不同状态；不可达必须停止展示陈旧行，显示恢复动作与明确错误反馈。

## State semantics

- **就绪 / ready:** 绿色；组件或整体可以按预期提供服务。
- **已降级 / degraded:** 琥珀色；核心任务仍可继续，但必须显示直接原因或恢复建议。
- **已阻断 / blocked:** 红色；必需路径不可用或证据读取失败，不能以成功语气弱化。
- **idle / starting / stopping:** 整体层级按琥珀色过渡态处理，保留正在发生的文字说明。
- **stopped / not_configured:** 行级使用中性灰并写出“已停止”或“未配置”；颜色不能替代状态标签。
- **证据不可用:** 使用阻断语义，清空陈旧列表，将 Runtime Supervisor 与恢复建议显示在判断区。

## Actions and safety

- “重新检查”是唯一主操作，并支持 `F5`。它只重新读取证据，不修改业务数据。
- “重启 Jarvis Core”“打开日志目录”“导出脱敏诊断”是次级白名单操作；不得添加快捷修复、批准或任意命令入口。
- 每个异步动作都设置 `disabled` 与 `aria-busy`，保留稳定标签位置，并在完成或失败后发布反馈。
- Runtime 适配器不可用时禁用不安全或无效的恢复动作；动作完成后重新读取证据，避免结果与当前事实脱节。

## Accessibility requirements

- 页面语言为 `zh-CN`，标题层级与左右区域使用明确的 `aria-labelledby` 关联。
- 证据台账保留 `table`、`rowgroup`、`row`、`columnheader`、`cell` 语义；不可用仅视觉网格替代语义关系。
- 每条证据行进入顺序焦点，支持 Enter 与 Space 选择，并同步 `aria-selected`；指针和键盘必须得到同一结果。
- 所有按钮与可选行使用 2px 可见青色焦点轮廓；焦点不能只靠背景颜色表示。
- 状态必须有完整文字标签；绿色、琥珀色、红色或灰色只能作为冗余线索。
- 刷新和恢复动作使用 `aria-busy`；底部操作反馈保持 `role="status"` 与 `aria-live="polite"`，不得抢占正在输入的辅助技术用户。
- 图标均为辅助性 SVG 并设 `aria-hidden="true"`；可访问名称来自可见按钮文字或区域标签。
- 尊重 `prefers-reduced-motion: reduce`，停用加载动画并把过渡缩短到近乎即时。
- 桌面窗口最小支持尺寸为 880×620；内容区域在内部滚动，不能让核心证据或操作被窗口裁掉。

## Responsive behavior

该表面是 Windows 桌面窗口，不承担手机布局。在 980px 以下，右栏从 286px 收窄到 246px，台账隐藏“最后检查”列并重分配剩余列；状态、原因/恢复建议与可用操作始终保留。窗口不得低于 880px 宽或 620px 高。

## Unresolved decisions

- 当前无视觉或交互未决项；未来新增 Runtime 组件时沿用既有 required/optional、ownership、state、detail 和 recovery 契约，不为新组件增加新的装饰性状态颜色。
