# Sprint 4：主动提醒与 Windows Companion

## Sprint 目标

让 Jarvis 在浏览器关闭后仍能可靠地显示 Windows 通知并自动开口，同时保留免打扰、频率限制、延迟、失败重试和完整历史。

## 已完成：持久化调度

- [x] `notification_preferences`、`scheduled_jobs`、`notifications`、`delivery_attempts` 和 `companion_devices`；
- [x] PostgreSQL `20260728_0006` 提醒迁移与 `20260728_0007` 索引对齐迁移；
- [x] 任务可设置 `reminder_at`；
- [x] 任务提醒使用固定幂等键，不重复创建；
- [x] 完成、取消或删除任务时取消待投递提醒；
- [x] 独立提醒创建、列表、延迟、忽略、重试和删除；
- [x] 投递领取与确认协议；
- [x] 领取超时恢复和最多 3 次失败重试；
- [x] 每个渠道单独记录成功或失败。

## 已完成：打扰控制

- [x] 桌面通知与语音独立开关；
- [x] 默认免打扰 22:30–08:00；
- [x] 免打扰时保留桌面文字、禁止自动语音；
- [x] 默认每天最多 12 条提醒；
- [x] 默认每小时最多 3 条语音；
- [x] 延迟 10 / 30 / 60 分钟；
- [x] 暂停 1 小时和立即恢复；
- [x] 投资任务等敏感提醒默认不朗读。

## 已完成：Windows Companion

- [x] 独立 Python 常驻进程，不依赖浏览器；
- [x] 每 10 秒领取提醒并上报设备心跳；
- [x] Windows Toast 桌面通知；
- [x] Windows SAPI 自动语音；
- [x] 自动跳过损坏的系统声音；
- [x] 托盘菜单：打开、暂停、恢复、退出；
- [x] API 暂时离线时继续运行并自动重连；
- [x] `start.ps1` / `stop.ps1` 统一管理 Companion；
- [x] 提供显式的开机自启启用和关闭脚本。

## 已完成：提醒中心

- [x] 后台在线状态；
- [x] 创建独立提醒；
- [x] 即将提醒列表；
- [x] 投递历史和失败原因；
- [x] 延迟、忽略、重试和删除记录；
- [x] 免打扰、上限和语音音量设置；
- [x] 用户确认后才进行语音试听。

## 本轮验收

- 自动测试：27 项通过；
- Ruff、TypeScript、ESLint：通过；
- Next.js 正式生产构建：通过；
- Alembic：`20260728_0007 (head)`，自动差异检查为空；
- API、网页、Companion 三个进程均运行；
- Companion 心跳在线；
- Windows 桌面通知真实投递成功；
- 延迟、忽略、历史、删除和测试数据清理通过；
- 浏览器控制台错误：0；
- 无声语音自检成功生成 WAV；
- 验收截图：
  - `artifacts/reminder-center-online.png`
  - `artifacts/reminder-delivery-history-verified.png`

## 已知本机状态

这台电脑的 `Microsoft Huihui Desktop` 中文系统声音返回 SAPI `0x8004503A`。Companion 已自动跳过它，并使用下一项可用声音完成合成。若希望获得自然中文音色，后续应在 Windows 语言与语音设置中修复或重新安装中文语音包。

## 下一阶段

- [ ] English Coach：文字对话、错误记录和到期复习；
- [ ] 把英语复习任务接入当前提醒队列；
- [ ] 后续在 OpenClaw 阶段增加微信投递渠道；
- [ ] 评估会议、全屏和音频输出设备感知。
