# yuki-herdr 开发入口

这组文档服务于在仓库内工作的 coding agent 和开发者，不是 Herdr 用户手册。根 `AGENTS.md` 保存跨任务不变量；这里负责把任务路由到真实代码入口和验证证据。

## 十分钟入场

1. 读取根 `AGENTS.md`，检查当前分支、工作区和 `origin` / `upstream`
2. 按下表读取任务相关文档，不一次加载所有资料
3. 用代码、测试和当前 CLI help 验证文档中的事实；文档与代码冲突时先判断哪一方过期
4. 开发中跑最窄检查，交付前按风险扩大验证并记录结果

编译 Herdr 需要仓库固定的 Rust toolchain、Zig 0.15.2 和目标平台的构建工具。在 Unix/macOS 运行验证入口还需要 `just` 与 `cargo-nextest`；完整 `just check` 会使用 Bun 执行 integration asset 与 plugin marketplace 测试。Windows 原生 `just check` 使用 `just`、PowerShell 和 Rust/Zig 工具链，不要求 Bun 或 nextest。具体版本以 `rust-toolchain.toml`、`.github/workflows/ci.yml` 和 lockfile 为准；`flake.nix` 提供 Rust、Zig、just 与 nextest，但当前不包含 Bun。

## 任务路由

| 改动 | 先读 | 主要入口 | 重点证据 |
| --- | --- | --- | --- |
| 默认启动、server/client 生命周期 | [architecture.md](architecture.md) | `src/main.rs`, `src/server/autodetect.rs`, `src/server/headless.rs`, `src/client/mod.rs` | 启动路径测试、真实 attach/session 行为 |
| CLI 或公共 JSON API | [architecture.md](architecture.md) | `src/cli.rs`, `src/cli/`, `src/api/`, `src/app/api.rs`, `src/app/api/` | schema/handler 测试、CLI JSON 输出、共享事实归属 |
| workspace/tab/pane、状态动作 | [architecture.md](architecture.md) | `src/app/state.rs`, `src/app/actions.rs`, `src/workspace.rs`, `src/workspace/`, `src/pane/state.rs` | 无 PTY 单测、identity invariants、adversarial fixture |
| PTY、terminal、输入或渲染 | [architecture.md](architecture.md) | `src/terminal/`, `src/pane.rs`, `src/pane/`, `src/pty/`, `src/input/`, `src/ui.rs`, `src/ui/` | 行为测试；热路径改动补 scaling profile |
| TUI 私有 wire / 客户端 frame | [architecture.md](architecture.md) | `src/protocol/`, `src/client/`, `src/server/client_transport.rs`, `src/server/render_stream.rs` | protocol compatibility、最终 frame/input 行为 |
| 持久化、恢复、handoff | [architecture.md](architecture.md) | `src/persist.rs`, `src/persist/`, `src/handoff_runtime.rs`, `src/server/handoff.rs` | round-trip、legacy fixture、失败与平台行为 |
| Windows、ConPTY、named pipe、原生输入、installer | [windows.md](windows.md) | Windows surface map 中列出的文件 | 按风险选择 native smoke/probe/package/ARM64 |
| Agent detection manifest | 根 `AGENTS.md` 专项边界 | `src/detect/`, `src/detect/manifests/`, `src/pane/agent_detection.rs` | 隔离 session 的 detection read + explain |
| Agent integration 安装资产 | [architecture.md](architecture.md) 与根 [AGENTS.md](../../AGENTS.md) 的专项边界 | `src/integration/`, `src/integration/assets/` | `just integration-assets-test` 与目标 agent 实测 |
| 配置或用户文档 | 本页“文档路由” | `src/config/`, `docs/next/website/src/content/docs/` | config reference check、翻译 parity、必要 website build |
| vendored terminal/PTY | [`vendor/libghostty-vt.patches.md`](../../vendor/libghostty-vt.patches.md) 与 [`vendor/portable-pty.patches.md`](../../vendor/portable-pty.patches.md) | `vendor/libghostty-vt/`, `vendor/portable-pty/` | patch maintenance tests + 受影响平台验证；上游快照内的 `AGENTS.md` 仅作源码构建参考，非工作流权威 |

## 三条真实运行路径

- 普通 `herdr`：自动发现或启动 headless server，再作为 thin TUI client 连接
- CLI/API：CLI 通过换行分隔 JSON API 控制 server；这不是 TUI 的 bincode 私有 wire
- `--no-session`：单进程逃生路径，不代表持久 server/client 架构，也不启用正常 session persistence

改动共享行为时至少沿目标路径走完一次。只改 CLI 输出、API handler 或 TUI 表面，可能遗漏同一事实的其他消费者。

## 验证选择

| 命令 | 适合时机 | 实际覆盖 | 不代表什么 |
| --- | --- | --- | --- |
| `just test-one <filter>` | 开发中的快速回归 | 匹配的 Rust nextest | 全仓或跨平台通过 |
| `just lint` | Unix/macOS 快速反馈 | fmt + all-target clippy | tests、Windows runtime |
| `just test` | 本地行为检查 | Rust nextest、Python maintenance、UI architecture、Bun integration/marketplace | fmt/clippy、Windows cross-clippy |
| `just ci '<filter>'` | 对齐 Unix CI lane | lint、筛选 nextest、UI architecture、Bun checks | maintenance Python 全集、Windows runtime |
| `just windows-lint` | Unix/macOS 提前发现 Windows cfg 问题 | Windows target clippy | named pipe、ConPTY、Win32 input 可运行 |
| `just agent-context-check` | 文档与上下文变更时 | AGENTS、文档链接真实可达性与机器标记完整性 | Rust 代码正确性 |
| `just check`（Unix/macOS） | 提交前 | `ci` + Windows target lint + maintenance tests | Windows 原生 smoke/package |
| `just check`（Windows） | Windows 原生快速门禁 | Windows fmt/clippy、筛选测试、transport/repeat-release、build | 全部 Rust tests、ConPTY package job |
| `just bench-render-scale` | 扩大 render/layout/pane/client 热路径时 | 固定几何下的 pane/workspace scaling | 行为正确性 |

纯文档改动至少检查 `git status --short`、tracked diff 与每个本次新增文件，并执行 whitespace 和本地链接校验。行为改动必须有直接相关测试；运行时或平台行为还需要与失败面对应的真实证据。

## 文档路由

- 根指令单一入口：`AGENTS.md` 为唯一维护的权威正文；根 `CLAUDE.md` 为普通文件，内容仅为 `@AGENTS.md`（通过 Claude Code 相对 import 实现免 symlink 权限的跨平台单一入口，正文只维护 `AGENTS.md`）
- 内部开发文档：`docs/development/`
- 下一稳定版的用户文档草稿：`docs/next/website/src/content/docs/`
- 根 README 的下一版草稿：`docs/next/README.md` 与 `docs/next/README.zh-CN.md`
- active preview snapshot：`docs/preview/`，由 Preview CI 管理，严禁手动修改
- 已发布稳定版：`docs/versions/`，只做明确的已发布事实修正
- `website/src/content/docs/`：构建生成物，严禁手动修改
- 普通 feature/fix 不编辑 `docs/next/CHANGELOG.md`、根 `README.md`、根 `CHANGELOG.md` 或 `website/latest.json`

`website/agent-guide.md` 用于指导 agent 帮助用户使用 Herdr，`skills/herdr/SKILL.md` 用于控制 Herdr；二者都不是仓库开发指南。

## 局部指令与共享模板

高风险目录设有局部 `AGENTS.md`，仅追加该目录的架构契约与边界规则；跨任务协作使用统一模板脚手架：

- **局部指令：**
  - 平台与 Win32：[`src/platform/AGENTS.md`](../../src/platform/AGENTS.md)
  - 协议与私有 Wire：[`src/protocol/AGENTS.md`](../../src/protocol/AGENTS.md)
  - 持久化与快照：[`src/persist/AGENTS.md`](../../src/persist/AGENTS.md)
  - Agent 检测与规则：[`src/detect/AGENTS.md`](../../src/detect/AGENTS.md)
- **共享模板：**
  - 高风险设计与验证：[`templates/high-risk-change.md`](templates/high-risk-change.md)
  - 独立会话复审输入：[`templates/fresh-review.md`](templates/fresh-review.md)
  - Windows 原生验证记录：[`templates/windows-validation.md`](templates/windows-validation.md)

## 当前不自动化的部分

本阶段新增局部指令、模板和确定性静态门禁，但不新增通用 dev skill 或 session hook。提炼新自动化流程的门槛是：至少在 3 次独立真实任务中、跨 2 种 agent 客户端出现同一流程偏离，且模板与静态检查无法解决；禁止为假设中的工作流预建抽象。

fork 的 PR、issue、release、长期分支策略与发布命名仍由用户决定，不新增对应模板。涉及上游同步、重写历史、push、tag 或 release 时，必须先与用户对齐，严禁自行决定策略。
