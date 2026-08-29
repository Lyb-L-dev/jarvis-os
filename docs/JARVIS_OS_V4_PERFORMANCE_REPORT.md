# Jarvis OS V4 Windows 性能与体积报告

> 候选版本：`4.0.0-beta.3`  
> 当前安装器 SHA-256：`96CDAAD867F8588EC5BDE37DF4BAF0F238F4F5E76FA8E2C9A3955D75D195CD68`  
> 测试平台：Windows 11 x64 `10.0.26200`，中文用户名开发机

## 当前最终产物

| 指标 | 实测值 | 证据范围 |
|---|---:|---|
| NSIS 安装器 | 69,499,831 bytes | 当前最终哈希 |
| 安装后目录 | 168,164,797 bytes | 当前最终覆盖安装 |
| 安装后文件数 | 2,069 | 当前最终覆盖安装 |
| Desktop Shell EXE | 14,126,592 bytes | 当前最终覆盖安装 |
| Sidecar 目录 | 153,511,356 bytes / 2,059 文件 | 当前最终覆盖安装 |
| 静态路由 | 26/26 | 当前代码生产构建 |
| SBOM | 1186 components | 当前资源清单 |

当前更新机制分发完整 NSIS 安装器，不实现二进制差分，因此 beta.3 的“更新下载体积”按完整安装包约 69.49 MB 计算。安装后程序目录与 `%LOCALAPPDATA%\Jarvis OS` 用户数据目录分离，表中不包含用户数据库 volume、日志、备份或模型权重。

## 启动与工作集证据

| 场景 | 结果 | 是否绑定当前最终哈希 |
|---|---:|---|
| V4-0 Bundled 冷启动，Docker/PG 已运行 | 18.06 秒 | 否，架构 Spike 基线 |
| 快速窗口 20 次唤起 | P50 39.8 ms / P95 139 ms | 否，beta.3 前一构建 |
| 安装版 50 次原生反馈 | P50 23.6 ms / P95 37.8 ms | 否，beta.3 前一构建 |
| 空壳宿主空闲工作集 | P50/P95 28,196,864 bytes | 否，beta.3 前一构建 |

这些结果证明当前架构具备可行基线，但不能替代最终哈希的性能验收。最终安装包仍需重新执行 50 次启动/完全退出循环，并补测：

- 热启动到主工作台的 P50/P95；目标分别不高于 8 秒和 15 秒；
- 冷启动各阶段耗时，包括 Docker/PG 已运行与 Docker 需启动；
- Tauri/WebView2、Core、Companion、PostgreSQL、Ollama 的独立工作集；
- 启动峰值、稳定空闲值、一次真实对话后的工作集与 CPU；
- 24 小时待机、至少两次睡眠恢复后的进程数、CPU、内存和日志增长。

## 语音基线

既有 Windows CPU 语音基准：STT 30 次 P50 148.37 ms / P95 400.56 ms；TTS 15 次 P50 709.18 ms / P95 991.13 ms；STT 冷启动 1014.50 ms，中英语音双模型冷启动 1536.46 ms，完整语音进程峰值工作集 512.96 MB。该数据来自独立语音基准，不代表 WebView2 权限弹窗或完整对话链路延迟。

## 结论

当前最终产物的包体积、安装体积、文件数和组件清单已有可复现数据；启动时延与工作集只有前一构建或架构 Spike 基线。由于最终 50 次生命周期测试尚未获授权、24 小时/7 天观察尚未完成，本报告不能支持 Stable 性能结论。

关联证据：`.runtime/release-evidence/desktop-quick-20-source-final.json`、`.runtime/release-evidence/desktop-lifecycle-50-final-strict.json`、`.runtime/release-evidence/desktop-resources-final.json`、[V4-0 Spike](./JARVIS_OS_V4_0_SPIKE_REPORT.md)。
