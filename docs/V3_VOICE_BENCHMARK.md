# V3-4a 本地语音基准

> 采样日期：2026-08-10
>
> 设备：Windows 11，Intel64 Family 6 Model 154，16 逻辑处理器
>
> 运行时：Python 3.13.3，CPU provider

## 冻结基线

- STT：`sherpa-onnx-streaming-zipformer-small-bilingual-zh-en-2023-02-16`，int8 encoder/joiner；
- 中文 TTS：`vits-zh-hf-fanchen-wnj`；
- 英文 TTS：`vits-piper-en_US-hfc_male-medium`；
- 模型只在本地按需加载，空闲 300 秒后卸载；不启用常驻唤醒。

选择小型中英双语 Zipformer 是因为 Jarvis 的实际输入会混合中文和英文，而目标设备是 16GB 内存的 CPU 优先设备。安装入口统一为 `scripts/install-voice.ps1`，不从业务请求临时下载模型。

## 固定语料结果

命令：

```powershell
.\.venv\Scripts\python.exe .\scripts\benchmark-voice-loop.py --rounds 5
```

STT 使用模型包自带的 6 个 WAV，每个重复 5 次，共 30 次；TTS 使用固定的中文、英文和中英混合短句，每句重复 5 次，共 15 次。

| 指标 | 样本 | p50 | p95 | 最大值/冷启动 |
|---|---:|---:|---:|---:|
| STT 音频结束到最终文本 | 30 | 148.37 ms | 400.56 ms | 424.37 ms |
| STT 冷加载 | 1 | - | - | 1014.50 ms |
| TTS 请求到完整 WAV | 15 | 709.18 ms | 991.13 ms | 991.13 ms |
| 中英 TTS 双模型冷加载 | 1 | - | - | 1536.46 ms |
| STT + TTS 同进程峰值工作集 | 1 个完整基准进程 | - | - | 512.96 MB |

这些数字只证明固定语料下的延迟和资源量级，不代表真实麦克风环境的识别准确率。

## 冻结验收目标

| 分段 | p95 目标 |
|---|---:|
| STT 音频结束到最终文本（模型已加载） | ≤ 600 ms |
| LLM time-to-first-token（standard 路由） | ≤ 2500 ms |
| TTS 请求到首音（当前完整 WAV 返回口径） | ≤ 1200 ms |
| 麦克风结束到首音的体感延迟 | ≤ 5000 ms |
| STT + TTS 语音进程峰值工作集 | ≤ 650 MB |

本轮已通过 STT、TTS 和语音进程资源目标。LLM TTFT 与体感首音需要已配置的模型路由和真实浏览器音频设备，当前环境未运行，不能记为通过；在 V3-5 性能复采或用户设备验收时补齐。

## 隐私与回滚

- 浏览器将录音在内存中转换为 16kHz 单声道 PCM WAV，只发送到 `127.0.0.1` 的 Jarvis API；
- API 校验最长 60 秒，不写临时音频文件、业务表或事件正文；
- TTS 生成音频同样只在内存中返回；
- 关闭 `v3_voice_loop_enabled` 后，语音端点拒绝执行，原文本聊天保持不变。
