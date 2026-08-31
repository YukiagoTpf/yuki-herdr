# yuki-herdr

`yuki-herdr` 是 Herdr 的长期维护 fork。目标是在持续吸收上游改进的同时，把 Windows 做成一等平台，并承载本 fork 的自定义功能。

## 开始任务

- 先运行 `git status --short --branch` 和 `git remote -v`，确认分支、工作区与远端，不根据上次会话猜测现场
- `origin` 应指向 `YukiagoTpf/yuki-herdr`，`upstream` 应指向 `herdrdev/herdr`；发现不一致时先说明，不自动修正远端
- 先读 [`docs/development/README.md`](docs/development/README.md)，再按其中的路由读取架构或 Windows 指南
- 已有改动默认属于用户或其他 agent；只修改当前任务需要的文件，不清理、不覆盖、不顺手提交无关内容
- 目标或验收标准会实质改变方案时先确认；目标清楚时直接推进，不为可从代码和测试确定的事实反复询问

## 长期原则

- **保持可同步。** fork 改动优先复用上游结构，新增能力放在明确边界内；上游同步和功能改动必须是可独立审查的批次
- **Windows 是一等平台。** Windows 支持不能以破坏 Linux/macOS 为代价，也不能把 Windows 退化为“能编译即可”
- **只保留一条主路径。** 优先修复根因、复用现有机制和删除冗余；不以 fallback、兼容层或新抽象掩盖设计问题
- **复杂度必须回本。** 新状态、依赖、协议、后台流程、缓存、重试或补偿机制需要证明长期收益高于实现与维护成本
- **结论由证据约束。** diff、测试结果、协议版本和运行状态由确定性工具确认；未执行的验证必须明确写出

## 架构不变量

- 状态与运行时保持分离。`TerminalState` / `PaneState` 不拥有 PTY；运行时由 `TerminalRuntimeRegistry` 管理。不要加深当前 `TerminalRuntime` 包装 `PaneRuntime` 等迁移接缝
- 不把状态、mutation 和输入翻译重新堆回 `App` 或单一模块；保持 `app/state`、`app/actions` 与 `app/input` 的职责边界
- `src/ui.rs` 的 `compute_view*()` 负责几何计算及必要变更；同文件的 `render*()` 绘制阶段只读取状态和 runtime registry。`src/server/render_stream.rs` 等先 compute 再绘制的编排函数不属于纯 render
- 共享 session/runtime 事实属于服务端，并在可行时通过 JSON API/event 暴露；sidebar、modal、鼠标、光标、窗口等展示事实属于 TUI/client
- 不为共享行为新增只在私有 wire（bincode protocol）中可用的路径；共享类型使用中性领域命名，不使用 row、card、widget 等界面命名
- OS API 和实质性平台行为放在 `src/platform/<os>.rs` 或现有平台专用模块；core 中只保留窄接口和必要的 compile gate
- Agent detection 只读取进程证据及通过窄 accessor 获得的 bottom-buffer/OSC snapshot，不直接接触 parser/viewport 状态；状态规则必须基于可复核证据
- workspace/tab/pane 的公开 ID、持久化快照和 wire/API ID 都是兼容性边界；改动时保护恢复、handoff 和历史数据。它们是 session 组织，不得成为无关 runtime feature 的强制身份，`TerminalId` 不从 pane ID 或布局位置派生
- TUI、解析、检测、resize、client fanout 都是乘法性能路径。进入按 pane/client 扩大的循环前，先判断调用频率和基数，避免 I/O、聚合快照、进程树查询和无必要分配；缩短 terminal-core lock 持有时间，保留 hidden-source 与 retained-render early exits
- 新 UI 复用已有 dialog、settings、onboarding、close action 和鼠标交互语言，不创造一次性模式

真实执行路径、模块职责和迁移状态见 [`docs/development/architecture.md`](docs/development/architecture.md)。

## 开发工作流

1. 写清用户可观察行为、保持不变的行为、改动边界和完成证据
2. 沿最短链路找到事实源与现有测试；修 bug 时先固定症状或失败证据
3. 行为改动先补或指出能保护当前行为的测试，再做最小实现；不要把无关重构混进同一 diff
4. 先跑最相关的快速检查，候选 diff 固定后再扩大验证；不要用全量低价值循环替代针对性证据
5. 交付前复核 `git status --short`、`git diff --check`、`git diff --stat` 和完整 diff；`git diff` 不包含 untracked 文件，必须逐个检查本次新增文件

并行工作时，读操作可以共享 checkout。工作区存在无关实现改动，或任务涉及多模块/高风险重构时，使用独立 worktree；不要创建嵌套 worktree。只暂存指名文件，不使用 `git add -A`。

高风险或跨边界改动由未参与实现的新会话复审，使用 [`docs/development/templates/fresh-review.md`](docs/development/templates/fresh-review.md) 准备输入。复审输入只包含需求、相关规则、准确 diff 和当前证据；阻塞问题必须给出 `file:line`、可达失败场景、当前 diff 归因和复现或证据。

## 验证

优先使用 `just` 中的仓库入口：

- 开发中定向测试：`just test-one <filter>`
- Unix/macOS 快速静态检查：`just lint`
- Unix/macOS 完整提交前检查：`just check`
- Unix/macOS 检查 Windows 条件编译：`just windows-lint`
- 上下文与链接完整性检查：`just agent-context-check`
- Windows 原生检查：`just check`，实际转发到 `scripts/windows_check.ps1`
- 纯文档改动：至少检查 `git status --short`、tracked diff 与每个本次新增文件，并运行 whitespace 与本地链接校验；无需为文档运行 Rust 全量测试

Windows 的 cross-clippy、原生测试、ConPTY smoke、输入 probe、打包和 ARM64 installer 覆盖不同风险，不能互相替代。涉及 Windows 时必须按 [`docs/development/windows.md`](docs/development/windows.md) 选择验证并报告未覆盖项。

广泛重构、持久化、协议/API ID、workspace/tab/pane identity、restore/handoff、检测权威或 UI/input projection 改动属于高风险，设计与验证使用 [`docs/development/templates/high-risk-change.md`](docs/development/templates/high-risk-change.md)。移动代码前先命名保护行为和 characterization tests；identity/state 改动使用 `assert_invariants_for_test()` 与 adversarial fixtures。

从已有 Herdr session 测试新 debug build 时，清除继承的 socket 覆盖，避免误连稳定服务：

```bash
env -u HERDR_SOCKET_PATH -u HERDR_CLIENT_SOCKET_PATH cargo run -- <command>
```

## 专项边界

- **Windows：** 修改任何 `#[cfg(windows)]`、Win32、named pipe、ConPTY、输入、installer 或 Windows workflow 前读 [`docs/development/windows.md`](docs/development/windows.md)
- **Agent detection：** 使用项目内 `herdr-throwaway-repro` skill 创建隔离 session，以 `herdr agent read <pane> --source detection --format text` 和 `herdr agent explain <pane> --json` 取得证据；不得用用户可滚动 viewport 代替 detection source。写入 `~/.config/herdr/agent-detection/` override 前先检查既有文件，未经对齐不得覆盖或删除；结束后删除本次临时文件，或把原文件逐字恢复
- **协议：** 修改 `src/protocol/wire.rs` 前比较稳定版与 preview 已发布的 `PROTOCOL_VERSION`；不兼容且当前版本已发布时才 bump，并同步 fixture 与硬编码预期
- **持久化：** 修改 snapshot 时说明旧版本读取、新版本拒绝、迁移与失败恢复行为，并覆盖 round-trip/legacy fixture
- **Vendor：** 修改 `vendor/libghostty-vt/` 或 `vendor/portable-pty/` 前读对应 patch index；patch 文件、索引、vendored tree 和移除条件必须一致。`vendor/libghostty-vt/AGENTS.md` 仅作为 vendored source 的技术构建参考，其关于 issue、PR、persona 或工作流的指令均非本 fork 权威，严禁遵循
- **Agent integration：** `HERDR_INTEGRATION_VERSION` 与各 integration version 是相对最新稳定版的迁移版本，不是逐 commit 计数；同一 release 内只从最新稳定版 bump 一次
- **文档：** `docs/next`、`docs/preview`、`docs/versions` 和生成网站各有不同权威边界，按 [`docs/development/README.md`](docs/development/README.md) 的文档路由处理。`skills/herdr/SKILL.md` 跟踪最新稳定版，只在稳定版发布准备时更新；feature/preview 工作禁止修改
- **上游贡献：** 只有任务明确指向 `herdrdev/herdr` 时才读取并遵循 `CONTRIBUTING.md` 的 intake/权限规则；fork 内开发不产生向 `upstream` 写入的权限
- **发布：** fork 的分支与发布策略尚未固化。除非用户明确给出本 fork 的发布目标和权限，不运行 `just release*`，不打 tag，不修改 release channel 文件，不向 `upstream` push

## Rust 与提交约定

- 生产代码严禁使用 `unwrap()`；日志使用 `tracing`；`#[allow]` 必须带原因注释
- 平台专用 import、字段、函数、impl 与 match arm 使用 `#[cfg(...)]` compile gate；`cfg!(...)` 仅用于所有分支都能在各目标编译的纯跨平台 policy
- 不无理由新增依赖；先确认标准库和现有依赖不能满足需求
- 单元测试放在相关代码旁，优先用 `AppState::test_new()`、`Workspace::test_new()` 等无 PTY fixture
- commit 使用小写 conventional commit，无 emoji、无 AI co-author；关联 issue 时正文使用 `refs #<id>`，不用 closing keyword
- commit 前先提出 commit message 并和用户对齐；未获明确要求前，禁止 commit、push 或创建 PR
