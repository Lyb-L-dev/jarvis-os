# ADR-0011：Browser Worker 只执行隔离、只读的公开岗位研究

## 状态

已接受，2026-08-03。运行开关保持关闭，等待用户手动建立本地签名凭据后验收启用。

## 背景

Jarvis 需要从公开招聘页面发现岗位并与个人档案建立联系，但网页内容可能包含 Prompt Injection、恶意跳转、内网探测、账号诱导、上传或提交指令。通用 Browser Agent 或直接控制个人浏览器会把网页登录状态、文件与 Tool Gateway 权限混入不可信页面环境。

旧求职项目提供了有价值的安全设计：凭据 URL 拒绝、私网/IP 拒绝、逐跳重验、robots 规则、限速、正文上限、短生命周期浏览器上下文和岗位字段模型。本次只借鉴设计，不复制其数据库、账号、简历、配置或自动投递逻辑。

## 决策

1. Browser Worker 是独立 Node 进程，只监听 `127.0.0.1:5690`；
2. Jarvis Core 只能通过固定 `/v1/research` 路径、HMAC-SHA256、时间戳、nonce 与正文哈希调用；
3. Worker 只接收最多 8 个精确 DNS 主机名，不允许通配符、IP、URL 用户名/密码或疑似凭据查询参数；
4. 每个请求和每次跳转都执行 HTTPS、精确白名单和 DNS 公网地址校验；
5. `robots.txt` 无法安全确认时默认拒绝；页面限制为 HTML、单页 2 MB、单次最多 5 页；
6. 远程页面由 Node HTTPS 客户端读取，使用固定 DNS 地址连接，浏览器不直接访问远程网络；
7. HTML 进入 JavaScript 禁用、Service Worker 禁用、所有网络请求中止的一次性 Playwright BrowserContext；
8. 每次任务启动全新 Edge 进程和 Context，结束后关闭，不复用个人浏览器配置，不保存 Cookie、LocalStorage 或会话；
9. 当前只从 JSON-LD `JobPosting` 提取岗位，避免用模型从任意页面正文臆测字段；
10. 页面文本只作为不可信数据，Prompt Injection 规则只生成信号，不改变 Agent 指令或 Tool 权限；
11. 证据截图由本地净化后的证据页生成，并保存来源 URL、抓取时间、内容哈希和截图哈希；
12. `browser.jobs.research` 是 Tool Gateway 的 R0 工具，只允许 Research 与 Growth Agent；
13. JD 与个人档案匹配使用本地确定性规则，不调用 MiMo 或 DeepSeek；
14. `browser.submit` 保持不可用的 R2 预留工具；没有登录、上传、下载、表单或投递工具；
15. Browser Worker 离线只影响求职雷达，不影响 Jarvis Core；
16. 真实来源默认不存在，必须由用户手动确认只读范围并加入精确域名白名单；
17. 本地签名密钥属于凭据操作，不由开发 Agent 自动创建；用户需手动运行设置脚本。

## 参考项目的取舍

- Playwright：采用一次性 BrowserContext、截图与网络拦截；
- Browser Use：采用域名白名单、IP 阻断和凭据域边界思想，不引入其通用 Agent 执行面；
- JobSpy：采用统一岗位字段和多来源适配思想，不引入代理、反限流或抓取依赖；
- AIHawk：明确拒绝自动申请路线；
- Playwright MCP：不直接接给 Agent，因为其自身文档说明它不是安全边界，域名配置也不能覆盖重定向安全。

## 后果

- JavaScript 动态渲染且没有 JSON-LD 的招聘页面，第一版可能识别不到岗位；
- 跨域 ATS 必须由用户明确加入第二个精确域名；
- 严格 robots 默认拒绝会降低覆盖率，但避免未经确认地采集；
- 页面截图是可审计的净化证据，不是远程页面的像素级原貌；
- 未来若增加动态渲染，仍不得开放登录、上传、下载或提交，必须另立安全评审。

## 被拒绝的方案

### 把通用 Playwright MCP 直接交给 Agent

拒绝。工具能力过宽，域名设置不是完整安全边界，页面跳转与工具权限容易混合。

### 复用用户的 Edge/Chrome 个人配置

拒绝。会暴露 Cookie、登录态、扩展、下载目录和外部账号。

### 使用自动投递项目

拒绝。上传简历、填写表单和提交申请超出 Sprint 31 的只读授权。

### 使用 DeepSeek 判断每个岗位

拒绝作为默认路线。岗位初筛可以用可解释的本地规则完成；复杂职业规划仍按原有流程说明 DeepSeek 作用并逐次确认。

