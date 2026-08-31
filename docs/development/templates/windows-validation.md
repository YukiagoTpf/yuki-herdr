# Windows 原生验证记录模板

> **使用说明：** 本模板用于记录 Windows 平台的真实验证证据。验证策略与执行要求以 [`../windows.md`](../windows.md) 为唯一依据，本文件仅作为记录槽位。
> 请逐字保留各字段前的机器标记 `<!-- agent-field: ... -->`。

---

<!-- agent-field: windows-build -->
### 1. 构建与版本信息
- **Commit / HEAD：** `<填写 git rev-parse HEAD 输出>`
- **工作区状态：** [ ] Clean Commit / [ ] Dirty Candidate
- **源码身份与改动证据 (Dirty Candidate 必填)：**
  - Tracked / Staged Diff 及相关 Untracked 内容 (或记录可复现 evidence bundle 标识及其 SHA-256 哈希；注意：仅二进制 artifact hash 不能代替源码身份)
- **编译产物路径与 SHA-256：** `<填写产物绝对路径及哈希值>`

---

<!-- agent-field: windows-environment -->
### 2. 验证环境
- **操作系统：** Windows 版本及 CPU 架构（如 Windows 11 x86_64 / ARM64）
- **Shell 环境：** PowerShell 版本（如 5.1 / 7.x）
- **工具链版本：** Rust target（如 `x86_64-pc-windows-msvc`）、Zig 版本（0.15.2）

---

<!-- agent-field: windows-artifact -->
### 3. 产物形态
- [ ] 裸 Debug 可执行文件 (`target/debug/herdr.exe`)
- [ ] System ConPTY 测试环境 (`HERDR_WINDOWS_CONPTY=system`)
- [ ] 当前待验证候选 Package (`herdr-windows-x86_64.zip` 解压目录)
- [ ] Current Installer 在 ARM64 安装已发布的 preview x86_64 fallback (仅限 Tier 6)

---

<!-- agent-field: windows-conpty-source -->
### 4. ConPTY 加载源与路径
- **实际加载源：** [App-Local Hash-Verified ConPTY / System ConPTY]
- **OpenConsole 实际路径：** `<记录 loader 解析出的真实 OpenConsole.exe 绝对路径>`

---

<!-- agent-field: windows-results -->
### 5. 执行命令与结果
| 验证层级 | 完整执行命令 (含必填参数) | Exit Code | 关键输出摘要 / 日志路径 |
| --- | --- | --- | --- |
| Tier 2 (原生快速门禁) | `powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/windows_check.ps1` | `<填写>` | `<填写测试输出摘要>` |
| Tier 3 (基础 Smoke) | `powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/windows_smoke_conpty_path.ps1 -ExePath <path-to-herdr.exe>` | `<填写>` | `<填写 Smoke 输出摘要>` |
| Tier 4 (增强输入 Probe) | `powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/windows_conpty_enhanced_input_probe.ps1 -ExePath <path-to-herdr.exe> [-ExpectedConsoleHostPath <path-to-OpenConsole.exe>]` *(注：仅当断言 app-local OpenConsole 时传入 expected path)* | `<填写>` | `<填写 Probe 输出摘要>` |
| Tier 5 (Package 安装测试) | `powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/windows_install_conpty_package_test.ps1 -ArchivePath <path-to-herdr-windows-x86_64.zip>` | `<填写>` | `<填写 Package 测试输出摘要>` |
| Tier 6 (ARM64 Fallback CI) | Workflow Run URL / ID: `<填写>`<br>Workflow Commit: `<填写>`<br>实际安装的 Published Preview 版本: `<填写>` | `<填写>` | `<注：本层级仅证明 current installer 对已发布 preview 的 x86_64 fallback 安装路径；不能证明当前候选 package，亦不能证明原生 ARM64 binary>` |

---

<!-- agent-field: windows-evidence -->
### 6. 运行证据与会话状态
- **测试层级：** [Tier 1 ~ Tier 6]
- **Session / Pane 标识 (若相关)：** `<填写测试过程中的 session_id / pane_id>`
- **Detection / Screen Evidence (若相关)：** `<捕获的 bottom-buffer detection text 或 ANSI>`
- **环境清理确认：** [ ] 已清理测试过程生成的临时 session、测试目录及后台进程 / `<填写清理状态或遗留项>`

---

<!-- agent-field: windows-unverified-risk -->
### 7. 未验证范围与剩余风险
- **未执行 / 失败层级：** [列出未执行的层级，如 Tier 4/5/6]
- **不能证明的事实：** [明确说明当前测试无法保证的范围，如未证明 Win32 原生输入捕获、未证明 client→server 私有 wire]
- **已知剩余风险：** [客观记录遗留风险]
