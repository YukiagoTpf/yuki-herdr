# Detect Directory Guidance

根 [`AGENTS.md`](../../AGENTS.md) 继续生效，本文件只追加 `src/detect/` 目录的局部约束。

## 事实输入与架构分工

- **输入解耦：** Agent detection 只读取前台进程/作业证据、终端 bottom-buffer 文本快照与 OSC 事件。严禁读取用户可见的滚动 viewport，亦不得直接接触 terminal parser 状态。
- **边界与仲裁：** 本模块中 detector 判定结果路径仅负责评估规则并输出 `AgentDetection`，由 `src/pane.rs` 中的 pane detection task 负责发布相关 `AppEvent`，最终由 `TerminalState` 统一仲裁 screen fallback 与 hook authority；detector 不得直接修改全局终端主状态。同时承认 `src/detect/manifest_update.rs` 维护流程可合法发布 `AppEvent::AgentDetectionManifestsUpdated`。
- 架构执行路径见 [`../../docs/development/architecture.md`](../../docs/development/architecture.md)。

## Manifest 来源优先级与失败降级

- **有效来源顺序：** 规则加载遵循 `valid local override → 不旧于 bundled 的 valid cached remote → bundled`。
  - 过旧的 remote 规则不得遮蔽新版 bundled 规则；
  - 遇到无效的 local override 时安全回退至有效 remote 或 bundled；
  - 规则版本受 `min_engine_version` 约束，不兼容版本将被忽略。
- **失败语义与原子性：** 网络请求或单个 agent 规则更新失败时，保留 last-known-good cached remote 并记录状态（并非所有网络失败都立即回退 bundled）；仅当磁盘 cached remote 无效、过旧或解析失败时，加载路径才回退至 bundled。远端规则落地必须保证原子 commit。
- **既有 Override 保护：** 进行临时规则验证时，**严禁覆盖或删除用户既有的本地 override 文件**（`~/.config/herdr/agent-detection/<agent>.toml`）；验证完成后必须精准恢复原有文件内容。

## 规则质量与验证流程

- **逻辑门与误报控制：** 规则必须基于稳定控件、按区域（region）及优先级（priority）配置显式的 AND / OR / NOT 逻辑门；严禁匹配整屏偶发文本或高变动字符。
- **隔离验证与调试：** 修改 manifest 必须使用 `herdr-throwaway-repro` 创建隔离 session，通过 `herdr agent read <pane> --source detection --format text`（必要时 `--format ansi`）和 `herdr agent explain <pane> --json` 采集真实匹配证据。
- **测试范围：** 单元测试聚焦于 manifest 解析、规则语义、缓存热重载、`min_engine_version` 校验与回退逻辑，不引入全屏膨胀的偶发测试用例。
