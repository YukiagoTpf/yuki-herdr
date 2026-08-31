# 高风险改动设计与验证模板

> **使用说明：** 本模板用于广泛重构、持久化 snapshot、协议/API ID、workspace/tab/pane identity、restore/handoff、检测权威或 UI/input projection 等高风险改动。
> 模板为可复制填写的脚手架，填写结果记录于会话、review 输入或 `.local/`，日常常规修复无需填写。请逐字保留各字段前的机器标记 `<!-- agent-field: ... -->`。

---

<!-- agent-field: observable-behavior -->
### 1. 目标行为与问题症状
- **需求与背景：** [说明改动来源、关联 issue 或目标场景]
- **当前失败证据：** [贴出当前行为的失败日志、复现命令或错误现象]
- **目标可观察行为：** [清晰描述改动完成后，用户/CLI/API 可观察到的预期行为]

---

<!-- agent-field: scope-boundary -->
### 2. 改动范围与执行边界
- **In-Scope：** [本次必须修改的模块与最短代码路径]
- **Non-Goals：** [明确排除的无关改动与禁止顺带重构的范围]
- **真实执行路径：** [标明涉及的运行路径：普通 TUI / CLI / headless server / 平台专用层]

---

<!-- agent-field: protected-invariants -->
### 3. 受保护的行为与不变量
- **保持不变的行为：** [列出改动过程中绝对不能破坏的现有能力与契约]
- **Characterization Tests：** [用于保护现有行为的基准测试集]
- **Adversarial Invariants：** [如涉及 identity/state，标明使用的 `assert_invariants_for_test()` 及 adversarial fixtures]

---

<!-- agent-field: compatibility-risk -->
### 4. 兼容性与跨维度风险
- [ ] **Identity / Layout：** 是否影响 workspace/tab/pane 的公开 ID 或内部映射？
- [ ] **Snapshot / Restore：** 是否影响旧版本读取、未来版本拒绝或缺失字段默认值？
- [ ] **Public API / Private Wire：** 是否影响 `PROTOCOL_VERSION` 或 JSON API schema？
- [ ] **Agent Detection：** 是否触碰 detection text 提取、manifest 优先级或 hook authority？
- [ ] **Platform / Windows：** 是否涉及 named pipe、ConPTY、Win32 输入或 UTF-16 边界？
- [ ] **Vendor / Patches：** 是否影响 `portable-pty` 或 `libghostty-vt` 补丁？
- [ ] **乘法性能路径：** 是否引入 render/layout/parse 循环内的分配、I/O 或进程查询？

---

<!-- agent-field: evidence-plan -->
### 5. 验证矩阵与证据规划
| 验证类别 | 命令 / 方法 (待填写) | 预期证据与覆盖面 (待填写) |
| --- | --- | --- |
| 定向测试 | `<填写命令，如 just test-one <filter>>` | `<填写核心覆盖逻辑与预期证据>` |
| 跨平台静态检查 | `<填写命令，如 just lint / just windows-lint>` | `<填写 all-target clippy 与条件编译预期>` |
| 架构/性能回归 | `<填写命令，如 just test / just bench-render-scale>` | `<填写无 PTY 架构测试或伸缩基准预期>` |
| 平台原生验证 | `<填写 Windows 原生脚本或 CI 工作流>` | `<按 windows.md 阶梯填写真实运行证据预期>` |

---

<!-- agent-field: rollback-and-residual-risk -->
### 6. 失败恢复与剩余风险
- **失败恢复 / 回滚策略：** [若改动出现未预期行为时的回滚或降级方案]
- **未覆盖范围与剩余风险：** [明确指出由于环境或条件限制未执行的验证项及潜在风险]

---

<!-- agent-field: open-decisions -->
### 7. 待决决策（Open Decisions）
- [列出实质性影响实现方案、仍需与用户确认的关键决策点；若无则填“无”]
