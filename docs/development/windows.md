# Windows 开发与验证

Windows 是本 fork 的重点平台，但它不是一个孤立的 `src/platform/windows.rs` 文件。一次 Windows 改动可能跨越 client 原生输入、私有 wire、server、named pipe、ConPTY、vendor、installer 与 CI；本页用于找到完整链路并选择足够的原生证据。

用户可见的支持范围和限制以 `docs/next/website/src/content/docs/windows-beta.mdx` 及其 `zh-cn` 版本为准。文件名保留 `beta` 是历史路径，当前正文把 Windows 描述为 generally available；不要根据文件名推断产品状态。

## Surface map

| 表面 | 主要位置 | 关键边界 |
| --- | --- | --- |
| Win32/process/filesystem/daemon/IME | `src/platform/mod.rs`, `src/platform/windows.rs`, `src/platform/windows/` | OS API 与实质行为集中在平台层 |
| IPC | `src/ipc.rs`, `src/api/client.rs`, `src/server/client_transport.rs` | Windows 使用 named pipe；路径文件是 identity/stale marker，不是 Unix socket endpoint |
| server accept/readiness | `src/server/headless.rs`, `src/server/autodetect.rs` | 独立 accept thread；readiness 需真实 JSON status/client Hello，不靠路径存在 |
| PTY/ConPTY | `src/pty/mod.rs`, `src/pty/actor.rs`, `src/pty/backend.rs`, `src/pane.rs` | vendored `portable-pty`，Windows reader/writer/input/control threads |
| 原生控制台输入 | `src/client/input/windows_vti.rs`, `src/client/input.rs`, `src/client/mod.rs` | `INPUT_RECORD` 保留 physical key、repeat、release、focus、mouse |
| 输入 wire 与 fallback | `src/protocol/wire.rs`, `src/server/client_transport.rs`, `src/raw_input.rs`, `src/input/model.rs`, `src/app/input/terminal.rs`, `src/platform/windows.rs` | `WindowsConsole` record 穿过 client/server，再编码到 ConPTY |
| shell/command quoting | `src/platform/windows.rs`, `src/pane.rs`, `src/integration/`, `vendor/portable-pty/` | PowerShell 与 `cmd.exe /d /c` 语义不同；raw command tail 有本地 patch |
| screen/history/render | `src/pane/terminal/windows_recent_fallback.rs`, `src/protocol/render_ansi.rs` | main/alternate screen、recent fallback 与 Windows cursor 有专门退化逻辑 |
| remote/update | `src/remote.rs`, `src/remote/`, `src/update.rs` | Windows 可作 SSH client，不作 remote host；update 走 installer，无 live handoff |
| package/install | `packaging/windows/`, `scripts/package_windows_conpty.*`, `scripts/windows_*.ps1`, `website/install.ps1` | 正式 zip 必须包含 `herdr.exe` 与受控 app-local ConPTY |
| CI/release | `.github/workflows/ci.yml`, `.github/workflows/windows-arm64.yml`, `.github/workflows/preview.yml`, `.github/workflows/release.yml` | native checks、package、installer、ARM64 fallback 各自独立 |

## 实现不变量

- 严禁将 Unix 的 path-exists、unlink、nonblocking accept、signal、process group 或 shell quoting 等假设套用到 Windows
- named pipe 的 marker、owner-only DACL、stale detection 和 client Hello 是安全/生命周期契约，修改其中一项要检查整条连接路径
- Windows input 改动沿完整链路检查 repeat、release、Esc、Shift+Enter、modifier、Kitty/native/legacy source 与 ConPTY fallback；只测 crossterm 或单个 `INPUT_RECORD` 不够
- shell 命令使用现有 platform helper。路径、argv 与用户编写的 shell text 分开处理，不用字符串拼接模拟 Windows quoting
- Win32 UTF-16 边界使用 `OsStr`/`OsString`/`Path` 与现有转换；禁止无理由提前将路径转换为 lossy UTF-8 字符串
- client cursor/window/IME 是 presentation；PTY 内容、process、terminal state 和共享尺寸是 server/runtime。先分类再加字段或 protocol message
- Windows session persistence 表示 server 继续运行或普通 snapshot restore，不等于 Unix live handoff
- `HERDR_WINDOWS_CONPTY=system` 是故障诊断与兼容恢复开关，不是正常打包路径

## ConPTY 与 vendor 供应链

`Cargo.toml` 使用 `vendor/portable-pty/`。修改 PTY、ConPTY loader 或 Windows command builder 前必须读取：

- `vendor/portable-pty.patches.md`
- `vendor/patches/portable-pty/`
- `packaging/windows/conpty.json`

当前本地 patch 同时保护两件事：受控加载 hash-verified app-local ConPTY，及保留 `cmd.exe /d /c` 的 raw command tail。patch、vendored source、索引、package hash、license/notice、installer 与移除条件必须一起维护。

裸 debug `herdr.exe` 没有 sibling bundle 时可能使用 system ConPTY；它不能证明正式 zip 的 loader、hash、OpenConsole 路径或 installer 正确。

## 验证阶梯

| 层级 | 命令或 CI | 能证明 | 不能证明 |
| --- | --- | --- | --- |
| 1 | Unix/macOS `just windows-lint` | Windows target 能 compile/clippy | Win32、named pipe、ConPTY runtime |
| 2 | Windows `just check` | fmt/clippy、`windows_` 筛选测试、transport、repeat/release、build | 全量 tests、正式 package |
| 3 | `powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/windows_smoke_conpty_path.ps1 -ExePath <herdr.exe>` | server/workspace/pane 与基础 ConPTY happy path 可运行 | stale marker、live collision、跨用户拒绝、增强输入和 installer |
| 4 | `powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/windows_conpty_enhanced_input_probe.ps1 -ExePath <herdr.exe> [-ExpectedConsoleHostPath <OpenConsole.exe>]` | JSON API 注入后 server→ConPTY 下游的 legacy/Kitty/native record 编码、modifier、Esc、repeat/release 和 device response；传入 expected path 时验证 app-local OpenConsole | Win32 `INPUT_RECORD` 采集、client→私有 wire、installer repair/upgrade |
| 5 | package job + `scripts/windows_install_conpty_package_test.ps1` | tampered bundle 拒绝、system override、正式 bundle、PowerShell 5.1 install/repair | ARM64 主机安装 |
| 6 | `.github/workflows/windows-arm64.yml` | Windows ARM64 上用当前 installer 安装已发布 preview 的 x86_64 fallback | 当前候选 package、原生 ARM64 Herdr binary |

<!-- agent-evidence: windows-enhanced-input-probe command=scripts/windows_conpty_enhanced_input_probe.ps1 argv=-ExePath,-ExpectedConsoleHostPath claims=server-conpty-input,app-local-openconsole conditional-claim=app-local-openconsole:-ExpectedConsoleHostPath gaps=win32-input-capture,client-private-wire -->
<!-- agent-evidence: windows-arm64-installer workflow=.github/workflows/windows-arm64.yml artifact=published-preview gaps=current-candidate-package,native-arm64-binary -->

Tier 4 的 enhanced input probe 通过 JSON API 注入输入，只证明 server 到 ConPTY 下游的编码；`app-local-openconsole` 声明只有在显式传入 `-ExpectedConsoleHostPath` 时才成立；它不能证明 client 端的 Win32 原生输入捕获（`INPUT_RECORD` capture）或 client 到 server 的私有 wire 传输。

Tier 6 的 Windows ARM64 workflow 使用当前发布脚本在 ARM64 环境安装已发布的 preview 版本，用于验证 x86_64 fallback 安装路径；它不能证明当前待发布的本地候选 package，亦不代表已提供原生 ARM64 Herdr 二进制。

`scripts/windows_check.ps1` 运行的是有意筛选的原生测试，不是全部 Rust test。交付时不要只写“Windows check passed”，要写清实际层级。

## 按改动选择证据

| 改动类型 | 最低要求 |
| --- | --- |
| 仅共享 Rust 逻辑，含 Windows cfg | 相关单测 + `just windows-lint` + 最终 Windows CI |
| `src/platform/windows.rs` process/path/shell | Windows `just check` + 对应行为的原生测试或手工证据 |
| named pipe/server readiness | Windows `just check` + `cargo test --locked --target x86_64-pc-windows-msvc --bin herdr ipc::tests` + 基础 ConPTY smoke。当前自动化未覆盖 stale marker/live collision 与跨用户拒绝，必须补测试或提供独立原生证据 |
| input/key encoding/wire | Windows `just check` + `just test-one client_input_events_roundtrip` + enhanced input probe；真实 TUI 的 Win32 采集和 client→私有 wire 必须另取证，否则列为未覆盖；不兼容 wire 同时处理 protocol version |
| PTY/ConPTY loader/vendor | portable-pty maintenance test + package job + tampered/system/bundled 三条路径 |
| installer/update/package layout | package/installer test；涉及架构选择时，用 ARM64 workflow 检查当前 installer 对已发布 preview 的 fallback，但不得把它当作当前候选 package 证据 |
| user-facing Windows 行为 | 上述代码证据 + 更新 `docs/next` 的英文与中/日文对应页面 |

无法取得原生 Windows 证据时，可以先交付 cross-clippy 与平台无关测试结果，但必须把 named pipe、ConPTY、input 或 installer 的未验证范围明确列为剩余风险，严禁声称 Windows 已验证。

## 原生验证记录

记录模板使用 [`templates/windows-validation.md`](templates/windows-validation.md)，至少包含：

- Windows 版本与 CPU architecture
- PowerShell 版本、Rust target 与 Zig 版本
- 测试的是裸 debug exe、system ConPTY 还是正式 app-local package
- 完整命令、exit code 与关键输出
- session/pane 标识和必要的 detection/read evidence
- 未执行层级及原因

严禁使用 WSL 测试结果声称 Windows 原生行为通过。Windows VM 或 CI 中的真实 Win32/named-pipe/ConPTY 路径才是运行证据。
