# Jarvis Desktop Companion

独立于浏览器运行的 Windows 后台组件。

职责：

- 每 10 秒从 Jarvis Core 领取到期提醒；
- 显示 Windows 桌面通知；
- 优先使用原创离线中文男声和美式英语男声自动播报；
- 自动识别中文、英文与中英混合文本，分段合成后连续播放；
- 所需本地男声不可用时自动降级到 Windows 系统语音；
- 根据提醒类别、优先级和人格生成适合朗读的措辞；
- 向后端上报两个语音引擎的实时可用状态；
- 回传每个渠道的成功或失败结果；
- 提供托盘入口、暂停一小时、恢复和退出；
- API 暂时离线时保持运行并自动重连。

语音自检不会从扬声器播放，而是生成 WAV 文件：

```powershell
python -m jarvis_desktop --tts-self-test .runtime\jarvis-tts-self-test.wav
```

首次安装离线男声：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install-voice.ps1
```

每个离线引擎使用 CPU 和 2 个线程，不占用本地 Qwen 所需的独立显卡显存。
英语模型仅用于个人、非商业场景。
