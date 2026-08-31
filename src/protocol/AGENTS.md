# Protocol Directory Guidance

根 [`AGENTS.md`](../../AGENTS.md) 继续生效，本文件只追加 `src/protocol/` 目录的局部约束。

## Wire 边界与职责划分

- **私有 Wire 承载范围：** 本目录下的长度帧 bincode wire 用于 interactive client 与 headless server 之间的通信，除 presentation 与 input 外，亦承载连接私有的模式与控制（如 terminal 的 attach/observe/control 状态）。
- **双向边界防跨界：** 共享 session/runtime 事实与公共自动化操作必须走中性 JSON API。禁止将连接私有的交互状态误暴露为公共 API，亦严禁将共享业务能力塞入私有 wire。
- 详细架构拓扑与 API 边界见 [`../../docs/development/architecture.md`](../../docs/development/architecture.md)。

## 编码、布局与不可信输入防范

- **字段顺序与 Enum 变体：** bincode 序列化严格依赖字段声明顺序与 enum tag 索引。严禁调整已有字段顺序或删除已有变体；任何 wire 结构改动必须同步更新双端单元测试与冻结测试 fixture。
- **帧边界与 Payload 防护：** 解码 framing 必须严格校验 payload 上限，防范超大包导致内存耗尽或拒绝服务；妥善处理 trailing bytes 与畸变数据，防止 panic 崩溃服务端。
- **双端同步演进：** wire 协议变更必须保证 client 与 server 在握手协商、版本拒绝及消息解包逻辑上对称演进，严禁出现单端升级导致静默丢包或挂起。
- **Render ANSI 性能：** ANSI 渲染与帧转换位于每帧 fanout 乘法热路径，严禁在解析与序列化过程中引入无必要内存分配、I/O 或全局锁。

## 验证要求

- 协议与序列化改动属于高风险边界，改动前使用 [`../../docs/development/templates/high-risk-change.md`](../../docs/development/templates/high-risk-change.md) 明确兼容风险与版本策略（遵循根 `AGENTS.md` 的 `PROTOCOL_VERSION` 发布判定）。
- 必须提供双端序列化 round-trip 测试、legacy/mismatched 版本拒绝测试，以及真实 client/server 联调验证。
