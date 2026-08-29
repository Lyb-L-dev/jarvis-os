# Jarvis OS V4-0 技术 Spike 报告

> 日期：2026-08-13  
> 平台：Windows 11 x64（10.0.26200）  
> 决策：通过，进入 V4-1～V4-3 工程化  
> 关联：ADR-0015、`JARVIS_OS_V4_PLAN.md`、`JARVIS_OS_V4_PRD.md`

## 结论

采用 Tauri 2 + Next.js 静态资源 + PyInstaller one-directory Sidecar。PostgreSQL/pgvector、Docker Desktop 与 Ollama 保持可见外部依赖；Rust 壳不承载业务逻辑，FastAPI 继续是业务边界，PostgreSQL 继续是唯一事实源。

桌面版不需要 Node Server，不占用 3000 端口。安装态 API 与 Companion 使用同一套 Python 发行资源但保持独立进程角色；两者由 Windows Job Object 监管。源码/PWA 入口继续保留作为开发与恢复路径。

## 实测矩阵

| 能力 | 结果 | 证据 |
|---|---|---|
| V3-4b 主工作台 | 通过 | Tauri 主窗口显示 Online 与真实历史对话 |
| SSE/流式请求 | 通过 | API SSE 回归 4 项；桌面 fetch SSE 支持 `Last-Event-ID` 重连 |
| 麦克风 | 通过 | WebView2 `getUserMedia` 返回 live track，非麦克风权限默认拒绝 |
| 单实例 | 通过 | 第二实例退出且恢复隐藏主窗口 |
| 托盘/退出 | 通过 | 关闭隐藏；`--quit` 完全退出；Docker/Ollama 保持运行 |
| 静态导出 | 通过 | `/chat`、`/onboarding` 等 26 个路由全部预渲染 |
| 无 Node | 通过 | Bundled 模式无 `node.exe`，3000 未监听 |
| 无系统 Python | 通过 | 受限 PATH 下 API、Alembic、Companion 三入口通过 |
| 动态连接 | 通过 | Bundled API 使用系统分配端口；启动前注入 WebView |
| 桌面会话认证 | 通过 | 无令牌业务请求 401；WebView 带令牌显示 Online |
| 正常回收 | 通过 | 完全退出后 API/Companion 均不存在 |
| 崩溃回收 | 通过 | 强制终止 Tauri 后 Job Object 回收两个 Sidecar |

## 基线

| 项目 | 实测值 |
|---|---:|
| Bundled 冷启动（Docker/PG 已运行） | 18.06 秒 |
| Sidecar one-directory | 146.43 MiB / 2056 文件 |
| 静态 UI | 17.81 MiB / 260 文件 |
| Debug Desktop Shell | 24.31 MiB |
| Node Server/3000 | 0 个 / 未监听 |

启动数据包含数据库幂等迁移、Core readiness 和 Companion 拉起。当前值是开发机构建基线，不等同于 Release/NSIS 最终预算；V4-7 必须重新测量 Release 安装包、稳定空闲工作集和真实对话后的工作集。

## 安全边界

- Tauri Command 使用按窗口拆分的显式白名单：启动/状态窗口只获得 Supervisor、配置、更新与诊断所需命令，主业务窗口不获得通用 Shell、文件或进程能力；
- 主窗口只能导航到内嵌 App Origin，HTTP/HTTPS/mailto 外链由系统打开；
- Bundled Core 只监听 `127.0.0.1` 动态端口；
- 启动生成 256-bit 随机会话令牌，通过 WebView 初始化脚本注入，不写运行记录；
- FastAPI 配置令牌后，除预检、根路径与 liveness 外均要求 `X-Jarvis-Desktop-Session`；
- 不提供任意命令、任意文件读取或任意进程终止接口；
- Docker Desktop、PostgreSQL 容器与 Ollama 不进入 Job Object。

## V4-0 之后的实现状态

- Runtime 状态中心、DPAPI 配置、快速窗口、托盘、通知、文件接入、按住说话、开机启动与签名清单更新已实现；
- 本机普通用户已完成 beta.1 首装、beta.2 覆盖升级、120 秒健康超时自动回退和卸载保留数据；
- 当前 beta.3 安装包与 CycloneDX SBOM 已生成；npm/OSV/RustSec 只有上一轮审计记录，最终联网复审仍待显式授权，不得冒充当前证据；
- Defender/SmartScreen 与 Authenticode 只能在生产证书签名包上验收；干净 Windows 11、24 小时待机与 7 天观察仍是 Stable 阻断门禁。

## 回滚

设置 Source profile 或继续使用 `启动 Jarvis.cmd`。回滚不执行数据库 downgrade；Sidecar 与静态 UI 可从安装包移除而不改变 PostgreSQL 业务数据。
