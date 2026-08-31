# 架构与改动地图

本文记录当前代码事实和新改动应遵守的目标边界。代码现状与目标边界并不完全一致：Herdr 正从复用单进程 `App` 的实现迁移到 server-owned runtime，文档会明确标出过渡接缝，避免把目标架构误写成已经完成的事实。

## 运行拓扑

```text
普通 TUI
用户输入 -> thin client -> 私有 bincode wire -> headless server
                                           -> App / shared state
                                           -> terminal runtime -> PTY -> agent/shell
server -> 每客户端虚拟 render frame -> thin client -> 宿主终端

自动化 / CLI
CLI 或外部工具 -> 换行分隔 JSON API -> headless server -> 同一 shared state/runtime
```

### 启动入口

- 总入口：`src/main.rs::main`
- 默认 `herdr`：`server::autodetect::auto_detect_launch` 检查服务端，必要时启动 `herdr server`，然后调用 `client::run_client`
- `herdr server`：`src/server/headless.rs::run_server`，拥有共享状态、PTY、检测、JSON API 和 client 连接
- `herdr client`：只连接已有 server
- `--no-session`：本地创建 `App` 的单进程逃生路径，不启用正常 session persistence；不要用它证明 server/client 改动完整

## 状态与运行时

| 概念 | 当前事实 | 主要位置 |
| --- | --- | --- |
| `AppState` | workspace/tab/pane 组织、terminal 元数据、UI 模式、几何结果和请求标志 | `src/app/state.rs` |
| `TerminalState` | cwd、agent、hook authority、label、title、启动 argv 等纯终端状态 | `src/terminal/state.rs` |
| `PaneState` | viewport/pane 状态，通过 `attached_terminal_id` 引用 terminal | `src/pane/state.rs` |
| `App` | 包裹 `AppState`，拥有 channel、deadline、后台任务、持久化 writer 与 runtime registry | `src/app/mod.rs` |
| `TerminalRuntimeRegistry` | 在 `AppState` 外按 `TerminalId` 管理 PTY/parser/detector/channel | `src/terminal/runtime_registry.rs` |
| `TerminalRuntime` | 当前仍包装旧 `PaneRuntime`，是迁移适配层 | `src/terminal/runtime.rs` |
| `PaneRuntime` | 持有 terminal/parser、PTY actor、child PID、检测任务和同步原语 | `src/pane.rs` |

目标是让状态可以不依赖真实 PTY 与 async runtime 测试，但当前对象图尚未完全纯化：`Workspace -> Tab` 仍间接包含 event sender、notify 和 render signal。新代码禁止扩大这条接缝，亦不得借“纯化”之名顺手做与当前任务无关的重构。

状态变更优先落在可测试的 `src/app/actions.rs`。TUI 发起的共享 mutation 通过 `src/app/runtime_mutations.rs::dispatch_runtime_mutation` 复用中性的 JSON API `Method`，不要新建只从某个 UI 手势可达的共享路径。

## 布局与渲染

- `src/ui.rs::compute_view*` 计算几何并执行必要的 PTY resize，因此可以修改状态
- `src/ui.rs::render_with_runtime_registry` 只读取 `&AppState` 和 runtime registry 并绘制
- `src/server/render_stream.rs` 为 client 生成虚拟 frame；其编排函数会先调用 `compute_view*()`，随后进入只读的 `ui::render_with_runtime_registry`
- `src/server/headless.rs` 按 client 尺寸渲染。前台 App client 控制共享布局与 PTY 尺寸；TerminalAttach client 会直接 resize 所附 terminal 并持有 `direct_attach_resize_locks`，TerminalObserve client 不会
- client 自身的尺寸、主题、focus、input framer、frame baseline 与 graphics cache 位于 `src/server/clients.rs::ClientConnection`，不是共享 session fact
- `src/server/client_transport.rs` 的 control message 使用可靠队列；普通 render 是容量 1 的可丢弃槽，槽满时拒绝新 frame 并安排后续 full render，不为慢 client 累积历史 frame

任何进入 render、view computation、PTY parse、detection、background resize 或 client fanout 的新工作，都要按“每事件 × panes/tabs/workspaces × clients”评估成本。隐藏 pane 仍解析输出，但不能为了更新内部状态触发无意义的 presentation work。

## 公共 API 与私有 wire

| 边界 | 格式与入口 | 应承载的内容 |
| --- | --- | --- |
| 公共控制面 | `src/api/schema.rs`, `src/api/server.rs`, `src/api/client.rs`, `src/app/api.rs`, `src/app/api/`；换行分隔 JSON | pane/agent metadata、process/terminal/session state、事件和自动化动作 |
| TUI 私有传输 | `src/protocol/wire.rs`, `src/client/`, `src/server/client_transport.rs`；长度帧 bincode | input/frame、cursor、IME、window、sound 等 client presentation/control |

修改 wire format 前检查 `PROTOCOL_VERSION` 是否已经通过 stable 或 preview 发布。一个未发布协议上的多次不兼容变更只需要一次版本 bump；版本变化后同步兼容检查、测试 fixture 和硬编码预期。

## 持久化与身份

- snapshot 模型和版本：`src/persist/snapshot.rs`
- 原子写入与读取：`src/persist/io.rs`
- 普通恢复：`src/persist/restore.rs::restore` 恢复组织与元数据；普通 pane 立即新建 shell/PTY，native agent resume pane 先保存 pending plan，待几何与主题就绪后再创建 runtime
- live handoff restore：仅 Unix，位于 `src/persist/restore.rs`, `src/server/handoff.rs`, `src/handoff_runtime.rs`
- dirty session 延迟保存和 shutdown 保存：`src/app/session.rs`

snapshot 改动至少回答：旧版本如何读取、未来版本如何拒绝、字段缺失默认值是什么、失败是否保留可恢复状态。workspace/tab/pane identity 改动使用 `assert_invariants_for_test()` 和 adversarial fixture，避免把数组位置、raw ID、公开 ID 或展示编号混为一谈。

## Agent detection

```text
PaneRuntime detection task
  -> platform foreground process/job evidence
  -> terminal bottom-buffer detection_text
  -> manifest AND/OR rules + OSC evidence
  -> AppEvent
  -> TerminalState 仲裁 screen fallback 与 hook authority
```

主要入口：

- 普通 PTY 的检测任务构造：`src/pane.rs::PaneRuntime::spawn_command_builder`
- Unix live handoff 的检测 helper：`src/pane.rs::spawn_basic_detection_task`
- 检测入口：`src/detect/mod.rs`
- manifest 解析与缓存：`src/detect/manifest.rs`
- bundled rules：`src/detect/manifests/*.toml`
- bottom buffer：`src/pane/terminal.rs::ghostty_detection_text`
- 状态迁移：`src/pane/agent_detection.rs`, `src/terminal/state.rs`

修改 manifest 前必须通过隔离 Herdr session 捕获 detection text；样式、alternate screen 或控制符相关时同时捕获 ANSI。规则只匹配稳定控件与明确的备选特征（AND/OR 门），严禁匹配整屏偶发文本。

## 模块所有权速查

| 领域 | 主要目录 |
| --- | --- |
| CLI 解析与命令 | `src/cli.rs`, `src/cli/` |
| 应用状态、动作、输入编排 | `src/app/` |
| workspace/tab/pane 组织 | `src/workspace.rs`, `src/workspace/`, `src/pane/state.rs` |
| terminal 状态与 runtime registry | `src/terminal/` |
| PTY/parser/pane runtime | `src/pane.rs`, `src/pane/`, `src/pty/`, `src/ghostty/` |
| server、client 与 transport | `src/server/`, `src/client/` |
| 公共 JSON API | `src/api/`, `src/app/api.rs`, `src/app/api/` |
| 私有 TUI protocol | `src/protocol/` |
| layout/render/UI | `src/layout.rs`, `src/ui.rs`, `src/ui/` |
| persistence/handoff | `src/persist.rs`, `src/persist/`, `src/handoff_runtime.rs` |
| platform | `src/platform/` 及现有窄平台专用模块 |
| Agent detection/integration | `src/detect/`, `src/integration/` |
| config | `src/config.rs`, `src/config/` |
| remote attach | `src/remote.rs`, `src/remote/` |

## 高风险改动的保护证据

| 改动 | 最低保护 |
| --- | --- |
| state action | 无 PTY 单元测试，覆盖成功、拒绝和边界状态 |
| identity/layout | invariants + adversarial identity state |
| snapshot/restore | current round-trip + legacy/missing field + invalid/future version |
| JSON API | schema/handler/client 测试与中性命名检查 |
| private wire | 双端 fixture、版本判断和真实 client/server 行为 |
| render/layout 热路径 | deterministic architecture tests；扩大工作量时跑 `just bench-render-scale` |
| detection | live detection source + `agent explain`，Rust 测试只保护规则语义与 reload/cache |
| 跨平台 core | Unix 行为测试 + Windows cross-clippy；涉及 OS 行为再补原生验证 |
