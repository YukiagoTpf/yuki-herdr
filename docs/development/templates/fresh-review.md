# 独立复审输入模板 (Fresh Review)

> **使用说明：** 高风险或跨边界改动由未参与实现的新会话进行独立复审。
> **原则：** 复审输入仅包含需求、相关规则、准确 diff 和确定性证据；**严禁向独立 reviewer 塞入完整会话历史或长篇主观自证**。
> 请逐字保留各字段前的机器标记 `<!-- agent-field: ... -->`。

---

<!-- agent-field: review-requirement -->
### 1. 原始需求与验收标准
- **目标任务：** [一句话说明本次改动要解决的核心问题]
- **验收标准：** [用户可观察行为的具体预期]

---

<!-- agent-field: review-rules -->
### 2. 相关仓库规则与架构不变量
- [列出当前任务必须遵守的根 AGENTS.md 条目、局部 AGENTS.md 约束或架构不变量]

---

<!-- agent-field: review-diff -->
### 3. 待审候选与 Diff 详情
- **仓库根路径 (repo/root)：** `<填写仓库绝对路径或工作区根路径>`
- **Base Commit：** `<填写 baseline commit/branch>`
- **HEAD Commit：** `<填写当前分支 HEAD commit/branch>`
- **审查候选类型：** [ ] 已提交 Range (`<base>...<head>`) / [ ] 工作区 Dirty Candidate
- **Git 现场状态 (`git status --short`)：**
  ```text
  <粘贴 git status --short 输出>
  ```
- **1. 已提交 Committed Range Diff (若适用)：**
  ```diff
  <粘贴 git diff <base>...HEAD 输出>
  ```
- **2. 已暂存 Staged Diff (`git diff --staged`)：**
  ```diff
  <粘贴 git diff --staged 输出；若无则填“无暂存改动”>
  ```
- **3. 未暂存 Unstaged Diff (`git diff`)：**
  ```diff
  <粘贴 git diff 输出；若无则填“无未暂存改动”，禁止用 HEAD...HEAD 掩盖工作树改动>
  ```
- **4. Untracked 新增文件清单与完整内容：**
  - [逐个附上本次新增 untracked 文件的完整内容或可复现 patch/bundle，禁止仅罗列文件名；若无则填“无新增文件”]

---

<!-- agent-field: review-evidence -->
### 4. 验证执行记录与证据
| 执行命令 | 运行环境 (Host/OS) | 结果 (Exit Code) | 能证明的事实 | 不能证明的范围 |
| --- | --- | --- | --- | --- |
| `<填写命令，如 cargo test ...>` | `<填写环境>` | `<填写 Exit Code>` | `<填写直接证明的事实>` | `<填写不能证明的范围>` |
| `<填写命令>` | `<填写环境>` | `<填写 Exit Code>` | `<填写直接证明的事实>` | `<填写不能证明的范围>` |

---

<!-- agent-field: review-exclusions -->
### 5. 范围排除、未执行验证与已知风险
- **Out-of-Scope 明确排除项：** [列出明确不在本次审查范围内的周边模块或已有逻辑]
- **未执行的验证项：** [明确写出受环境、工具链或测试资源限制未运行的检查与测试]
- **已知剩余风险：** [客观说明当前改动在极端边界或未覆盖环境下的潜在风险]

---

<!-- agent-field: review-output-contract -->
### 6. Reviewer 输出契约
> 请独立 Reviewer 遵循以下契约输出审查结论：
> 1. **阻塞性问题（Must-Fix）：** 逐条给出 `file:line`、可达失败场景、当前 diff 归因以及确定性复现证据；
> 2. **非阻塞建议（Optional）：** 明确标出优化建议及理由；
> 3. **既有问题：** 与当前 diff 无关的已有代码缺陷单列，不阻碍当前任务交付；
> 4. 若无阻塞问题，明确回复“通过”。
