# Persist Directory Guidance

根 [`AGENTS.md`](../../AGENTS.md) 继续生效，本文件只追加 `src/persist/` 目录的局部约束。

## 事实源与边界划分

- **Schema 事实源：** `src/persist/snapshot.rs` 仅是 session/session-history 快照结构与 `SNAPSHOT_VERSION` 的事实源；`src/persist/io.rs` 负责快照文件的读写，`src/persist/restore.rs` 负责恢复编排。
- **Plugin Registry 独立性：** `src/persist/plugin_registry.rs` 独立持久化 `plugins.json`，其 schema 来自 API 定义，有独立文件锁，不受 session snapshot version 机制管辖。
- **结构与 History 解耦：** session 拓扑元数据 (`session.json`) 与 pane history 滚动缓冲 (`session-history.json`) 物理分离，避免输出膨胀拖慢会话保存。
- 架构拓扑详见 [`../../docs/development/architecture.md`](../../docs/development/architecture.md)。

## I/O 行为、版本与现场风险

- **写入与串行化：** 当前 session/history 保存通过固定临时文件写入后执行 rename，依赖 app session writer 串行化，**不存在文件锁，亦非跨文件事务**（仅 plugin registry 有独立锁）。禁止将文件锁或事务性写为既有事实。
- **Future Version 现有风险：** 当前不可识别的未来版本（future snapshot）会被 parse 拒绝，但 server 随后会按“无快照”状态启动，退出保存可能覆盖或删除原快照文件。修改持久化时必须显式将此作为既有风险进行保护和测试，禁止声称“已保护现场”。
- **身份与 ID 重映射：** 严格区分公共显示 ID、持久化 raw ID 与运行期 `TerminalId`。restore 期间必须安全重建 ID 映射，禁止假设 ID 连续或与内部数组索引绑定。
- **恢复模式分流：** 明确区分 cold restore（恢复窗口/pane 结构并在需要时新建 shell）、native agent resume 与 Unix live handoff。严禁假定所有恢复 pane 都会在 restore 时立即启动运行时。

## 验证要求

- 改动前使用 [`../../docs/development/templates/high-risk-change.md`](../../docs/development/templates/high-risk-change.md) 规划验证矩阵。测试根据改动面针对性选择（不将 session 快照契约机械套用到 plugin registry）：
  1. 修改 session schema 时：提供 round-trip 测试、legacy 缺失字段默认值补齐测试、future version 拒绝以及退出保存可能覆盖或删除原文件的风险测试；
  2. 修改 restore/identity 时：使用 `Workspace::assert_invariants_for_test()` 与 adversarial fixtures 覆盖恢复映射；
  3. 修改 plugin registry 时：验证独立锁、读写并发与 API 序列化契约。
