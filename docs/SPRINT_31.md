# Sprint 31：Read-only Browser Research 与职业机会雷达

## 状态

Sprint 31 已完成。代码、数据结构、界面、数据库迁移、自动化测试和真实进程验收全部通过；用户已手动建立本地 HMAC 签名凭据，Browser Worker 已启用并处于只读就绪状态。

## 目标

在不控制个人浏览器、不接入账号、不上传简历和不自动投递的前提下，为 Jarvis 增加可追踪的公开岗位研究与个人档案匹配能力。

## 已交付

### 隔离 Browser Worker

- 独立进程：`apps/browser-worker/server.cjs`；
- 固定监听：`127.0.0.1:5690`；
- HMAC-SHA256、60 秒时效、随机 nonce、正文哈希和重放拒绝；
- 每次研究使用新的 Microsoft Edge 进程和非持久 BrowserContext；
- JavaScript、Service Worker、下载和浏览器网络全部关闭；
- 远程页面由受限 HTTPS 读取器获取，浏览器只解析已经取得的静态 HTML；
- 精确域名白名单、DNS 公网地址校验、跳转逐次复核；
- robots 默认拒绝、2 MB 单页上限、最多 5 页、1.5 秒域内节流；
- 不支持登录、Cookie 复用、上传、下载、表单或申请提交。

### Prompt Injection 防护

- 页面正文固定视为不可信数据；
- 检测忽略指令、系统提示词索取、角色覆盖、工具执行、凭据和上传请求；
- 信号只写入证据账本，不进入 Agent 指令；
- 内置 `career_prompt_injection_v1` 安全演练同时包含结构化岗位和恶意页面指令；
- Node 安全单测覆盖公网/私网 IP、域名白名单、robots 最长匹配和 Prompt Injection。

### Tool Gateway

- 新工具：`browser.jobs.research`；
- 风险：R0，只读公开来源；
- Agent：Research、Growth；
- 输出二次校验 `read_only=true`、`isolated_context=true`；
- 强制检查凭据、表单、上传、下载和持久会话均为 false；
- `browser.submit` 仍不可用，没有自动投递入口。

### 数据与匹配

- `career_sources`：用户确认的精确域名来源；
- `career_research_runs`：每次研究和 Tool Execution 关联；
- `career_evidence_pages`：来源、时间、HTTP 状态、文本、注入信号、内容和截图哈希；
- `career_opportunities`：结构化岗位、首次/最近发现时间和匹配结果；
- 当前只接受 JSON-LD `JobPosting`，不从不完整正文臆造岗位；
- 匹配由职业目标、已有技能、地点和教育背景的确定性规则构成；
- 不调用 DeepSeek，不产生模型费用；匹配理由和待补技能可解释。

### Career Radar 界面

- Browser Worker 在线与安全边界状态；
- 一键建立和运行本地 Prompt Injection 演练；
- 手动添加官方招聘入口与精确主机白名单；
- 来源运行状态、岗位数量和注入信号；
- 岗位匹配分数、依据、技能差距和原始来源；
- 证据时间、内容哈希和完整性校验后的本地截图；
- 页面明确标记不登录、不上传、不下载、不提交。

## 旧求职项目复用结论

保留了网络策略、逐跳复核、robots、限速、岗位字段和不可信页面提示词等设计思想。没有复制旧项目的数据文件、配置、API Key、用户简历、投递记录或自动申请能力，也没有修改旧项目的脏工作区。

## GitHub 参考结论

- Playwright 的隔离 Context 与截图能力适合作为底层；
- Browser Use 的 `allowed_domains` 和 IP 阻断适合作为设计参考；
- JobSpy 的统一岗位 Schema 有参考价值，但当前不需要引入抓取依赖；
- AIHawk 的自动申请路线不符合 Jarvis 安全边界；
- 通用 Playwright MCP 明确不是安全边界，因此没有直接暴露给 Agent。

## 当前验收

- Browser Worker Node 安全测试：5 项通过；
- API 与桌面伴侣完整回归：169 项通过、1 项按环境跳过；
- Prompt/策略评测：16 项通过；
- Python Ruff、TypeScript、ESLint：通过；
- Next.js 生产构建：19 个页面通过；
- Career 页面本机 HTTP 200、浏览器错误 0、失败请求 0；
- 视觉验收截图：`artifacts/career-radar-sprint31.png`；
- 运行开关：`V2_BROWSER_RESEARCH_ENABLED=true`；
- 本地签名凭据：已由用户手动建立（`.data/browser-secrets/webhook_secret`）；
- 数据库迁移：已应用 `20260803_0025`；
- 最终恢复点：`jarvis-20260804T024832Z-6637c48e.dump`；
- 恢复验证：65 张表，schema `20260803_0025`，临时库恢复演练通过；
- 真实 Worker 签名验收：有效签名 200；缺失、篡改、超时（90 秒）、重放同一 nonce 均返回 401；
- Prompt Injection 安全演练：`career_prompt_injection_v1` 完成，识别 3 类注入信号（忽略指令、系统提示词索取、上传请求），信号只进入证据账本；
- 岗位提取与档案匹配：提取 1 个结构化 JobPosting，确定性匹配 42 分/中等级，匹配理由与缺失技能清单可解释；
- 证据截图：本机 PNG 生成成功，SHA-256 与数据库记录一致，接口完整性校验后返回 `image/png`；归档于 `artifacts/career-radar-sprint31-evidence.png`。

## 完成记录

2026-08-04：用户手动执行 `配置 Jarvis 职业雷达.cmd` 建立签名凭据后，开发流程完成以下步骤：

1. 启用 `V2_BROWSER_RESEARCH_ENABLED=true` 并重启 Jarvis 全栈；
2. Browser Worker 真实进程上线，`/healthz` 安全不变量全部符合；
3. Node 安全测试 5/5、API 回归 163 项、桌面伴侣 6 项通过（合计 169 通过、1 项按环境跳过）；
4. Prompt/策略评测 16/16 通过；
5. 签名/超时/重放验证、Prompt Injection 演练、岗位提取与证据截图验收全部通过；
6. 创建并验证最终恢复点 `jarvis-20260804T024832Z-6637c48e.dump`（65 张表）。

Sprint 31 正式结束。

## 手动启用步骤

凭据操作永不由 Agent 自动执行。用户需要在项目目录手动运行：

```powershell
.\scripts\setup-browser-worker.ps1
```

也可以直接双击项目根目录的 `配置 Jarvis 职业雷达.cmd`。

脚本只会生成 Jarvis 内部进程之间的随机签名密钥和本地证据目录，不配置任何网站账号、浏览器档案或简历。完成后再由开发流程启用 Feature Flag、重启 Jarvis、运行安全演练和完整验收。

## 架构决策

- [ADR-0011：Browser Worker 只执行隔离、只读的公开岗位研究](adr/0011-isolated-read-only-browser-research.md)
