# ADR-0014：V3 UI 事件投递与可靠续传

## 状态

已接受，2026-08-09。

## 背景

V3-0 使用进程内 asyncio 广播队列、连接快照、周期 `data_version` 检查和 SSE 心跳建立了对话事件基座。该实现适合单用户单 worker，但服务重启会丢事件，连接 ID 会重新从 1 开始，服务端也不能依据 `Last-Event-ID` 重放历史。

V3-2 的可恢复编排和 V3-3 的主动建议需要可靠地把状态变化通知前端，同时不能把私人正文复制到事件系统，也不希望为单用户本地部署引入 Redis。

## 决策

1. V3-0 当前能力只承诺 snapshot、心跳、版本检查和浏览器自动重连，不宣称可靠续传；
2. V3-1.5 在 PostgreSQL 中增加轻量 UI 事件日志或 Outbox，不引入 Redis；
3. 业务状态表仍是事实源，事件记录只包含：
    - 单调递增事件 ID；
    - 事件类型；
    - 聚合类型与引用；
    - `data_version`；
    - 创建时间和保留期限；
4. 事件不得保存对话、记忆、草稿、文件或邮件正文；
5. 状态变更与事件写入使用同一数据库事务或 Outbox 转发；
6. UI Event Feed 对外提供：

```text
publish(event_type, aggregate_ref, data_version) -> event_id
stream(after_event_id) -> EventStream
snapshot() -> UiSnapshot
```

7. 生产使用 PostgreSQL 适配器，自动化测试使用内存适配器；
8. 服务端读取 `Last-Event-ID`，重放保留期内的后续事件；
9. ID 过期、缺失或版本不一致时发送完整 snapshot；
10. 慢消费者可以丢中间通知，但必须通过最新版本或 snapshot 最终收敛；
11. 审批决定、主动建议状态、Agent Run 状态变化必须推进版本；
12. PG 事件日志通过重启和多连接测试前，API 保持单 worker。

## 结果

- API 重启后可以恢复 UI 通知，不再依赖进程内队列；
- 不需要增加常驻 Redis 服务；
- 事件系统不会成为私人正文副本；
- 前端可以用一个稳定接口消费审批、运行、提醒和主动建议状态；
- V3-1.5 需要补充 Outbox、保留策略、重放、过期回退和慢消费者测试。

## 未采用方案

- 继续把 EventSource 自动重连等同于可靠 `Last-Event-ID` 续传；
- 用 Redis Pub/Sub 作为单用户本地部署的必需基础设施；
- 在 SSE payload 中直接发送私人正文；
- 只依赖 10 秒轮询支撑可恢复编排。
