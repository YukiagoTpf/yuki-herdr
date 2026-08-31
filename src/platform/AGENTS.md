# Platform Directory Guidance

根 [`AGENTS.md`](../../AGENTS.md) 继续生效，本文件只追加 `src/platform/` 及其子目录的局部约束。

## 平台层边界与现有合法模块

- **平台代码分布：** 主要 OS 抽象与系统 API 集中在 `src/platform/<os>.rs` 及平台子目录；同时承认 [`../../docs/development/windows.md`](../../docs/development/windows.md) surface map 中列出的现有合法专用模块（如 `src/ipc.rs`、`src/client/input/windows_vti.rs`、`src/pty/` 等），禁止要求将这些合法边界机械搬迁回 `platform/`。
- **Compile Gate 与接口收窄：** 向 core 仅暴露跨平台窄接口与抽象。平台特有代码必须使用 `#[cfg(windows)]`、`#[cfg(unix)]` 或 target 宏进行精确条件编译，禁止将 OS 细节泄漏进上层业务代码。
- 架构分层详见 [`../../docs/development/architecture.md`](../../docs/development/architecture.md)。

## 原生资源、编码与进程契约

- **路径与编码转换：** 对不透明的文件系统路径和 argv，在无需 Unicode 文本语义时保持 `Path` / `OsStr` / `OsString`；API 边界所需的显式转换必须是可失败、非 lossy 的（禁止粗暴 lossy 转换导致路径截断或损坏），严禁无理由提前将 UTF-16 转为 UTF-8。
- **资源 Ownership 与释放：** Win32 `HANDLE`、named pipe 与进程句柄必须遵循所有权管理与 RAII 及时 `CloseHandle`，防止句柄与文件锁泄漏。
- **安全与 DACL：** Windows named pipe 与 IPC 必须严格维护 owner-only DACL、identity marker 与 stale 连接检测，修改连接握手必须验证整条生命周期。
- **Shell 与 Quoting：** 区分 PowerShell、`cmd.exe /d /c` 与 POSIX shell 的转义语义差异；路径、argv 与用户输入必须分开处理，禁止用字符串拼接模拟 Windows 命令转义。
- **避免高频进程查询：** 进程树查询、快照采集和 I/O 属于昂贵操作，严禁在 render、layout 或 client fanout 等乘法热路径中无缓存高频调用。

## 验证要求

- **宿主针对性验证：**
  - Unix/macOS 环境：运行 `just lint` 与 `just windows-lint` 提前拦截条件编译与 cross-clippy 错误；
  - Windows 原生环境：运行 `just check` 执行原生筛选测试与构建验证；
- 涉及 Windows 深度原生行为时，按 [`../../docs/development/windows.md`](../../docs/development/windows.md) 阶梯补齐原生证据，未覆盖部分必须明确记录为剩余风险。
