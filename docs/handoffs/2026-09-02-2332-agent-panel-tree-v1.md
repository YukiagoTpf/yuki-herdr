# Handoff — agent-panel-tree v1

## 1. 目标

**目标**：为展开态 Agents 侧栏新增可折叠的 Workspace → Tab → Agent 树形排列，降低多项目、多 Agent 场景下的识别成本。

**验收标准**：排序标签按 `grouped → tree → priority → grouped` 循环；树形模式不重复 Workspace/Tab 文本；Workspace、Tab 可独立折叠；点击标签和 Agent 叶子可正确聚焦；父节点汇总最高关注级状态；普通 shell pane 不产生空分支；配置可持久化；原有 grouped、priority、自定义 API Agent 视图、收起态和移动端行为不回归；`just check` 与 `just bench-render-scale` 通过。

**约束**：遵守纯渲染边界；树的折叠状态只属于 TUI 展示层，不进入服务端协议；不改变 Agent 检测权威来源；渲染热路径需验证 1 个与至少 15 个 pane 的伸缩表现。

## 2. 当前状态

**进度**：4/6 子任务完成。

**阶段**：测试。

**可运行**：实现已完成且通过静态检查，开发机安装仓库要求的 Rust 1.96.1、Zig 0.15.2、Just 和 cargo-nextest 后可运行；见第 8 节。

### 已完成 ✅

- 树形投影：复用现有 Agent 条目，按 Workspace、Tab 生成一行式树节点和叶子。
- 交互：实现折叠/展开、父节点聚焦、Agent 叶子聚焦以及外部聚焦时自动展开祖先。
- 状态与兼容：父节点按关注优先级汇总状态；自定义 Agent 视图、收起态和移动端继续使用原有扁平投影。
- 配置与文档：新增 `ui.agent_panel_sort = "tree"`，更新默认配置说明、配置参考和 next 文档。
- 测试覆盖：增加配置解析、排序循环、树投影、状态汇总、折叠、点击命中、聚焦和渲染快照级断言。

### 进行中 🔧

- 完整验证：本机缺少常驻 Rust/Zig 工具链，且用户决定转到开发机继续，因此尚未完成 `just check`、伸缩 benchmark 和真实 TUI 手工验收。

### 未开始 ⬚

- 真实多 Workspace、多 Tab、多 Agent 的交互验收。
- 固定几何下 1/15+ pane 的渲染伸缩对比。

## 3. 关键决策

| # | 决策 | 理由 | 被排除的方案 |
|---|------|------|-------------|
| D1 | 折叠集合保存在 `AppState`，使用稳定 Workspace ID 与 Tab number 标识 | 这是纯 TUI 展示状态，不应加深 server/client 耦合；稳定标识不受列表索引变化影响 | 写入服务端或 wire protocol：没有跨客户端共享价值，并引入协议兼容成本；使用数组索引：重排后语义漂移 |
| D2 | 在现有 `AgentPanelEntry` 之上增加 `AgentPanelRow` 投影 | 保留检测、排序、token 解析的单一事实来源，只新增树形展示层 | 为树模式复制 Agent 收集逻辑：会产生两套排序和检测语义 |
| D3 | 树形 Agent 叶子固定为单行，仅显示状态与 Agent 名 | 目标是高密度浏览，Workspace/Tab 信息已由祖先表达 | 沿用可配置多行 Agent 卡片：重新引入重复项目文本并破坏层级密度 |
| D4 | 自定义 API Agent 视图、收起态和移动端保持扁平 | 自定义视图已有自己的过滤/排序契约，小尺寸表面没有稳定树宽度 | 强制所有表面树形化：改变 API 投影语义并降低窄屏可用性 |
| D5 | 仅点击 chevron 切换折叠，点击节点文字执行聚焦 | 同一行同时提供导航和结构控制，命中语义明确 | 整行切换折叠：无法直接从父节点导航到 Workspace/Tab |

## 4. 失败路径

| 尝试 | 失败原因 | 教训 |
|------|---------|------|
| 使用官方下载的 Zig 0.15.2 在当前 macOS 26.3 完成原生链接测试 | vendored libghostty-vt 的 Zig build runner 链接系统符号失败；因此只能在临时副本跳过原生构建步骤完成 Rust 类型检查和 Clippy | 不要把临时副本中的静态检查当作完整测试；在开发机使用项目 dev shell 或兼容的 Zig 0.15.2 包重新跑 `just check` |
| 在当前机器通过 Homebrew 安装完整依赖 | 下载 LLVM 过程中用户决定转到开发机，安装被显式中止 | 不继续修复当前机器；相关 Formula 均未安装，本次 bottle、manifest 和 `.incomplete` 缓存已精确删除 |

## 5. 关键文件

| 路径 | 职责 | 状态 |
|------|------|------|
| `src/app/state.rs` | 新增 Tree 排序枚举、稳定节点 ID 和临时折叠集合 | 修改 |
| `src/app/mod.rs` | 从配置初始化 Tree 模式与折叠状态，覆盖启动/保存测试 | 修改 |
| `src/app/actions.rs` | 通过 Agent 导航聚焦时自动展开对应 Workspace/Tab | 修改 |
| `src/app/config_io.rs` | 将 Tree 模式持久化为 `tree` | 修改 |
| `src/app/input/mouse.rs` | 排序三态循环及树节点鼠标动作分发 | 修改 |
| `src/app/input/sidebar.rs` | 树行命中测试、折叠和聚焦交互测试 | 修改 |
| `src/config/model.rs` | 配置枚举、序列化字符串与解析测试 | 修改 |
| `src/main.rs` | 默认配置注释增加 Tree 说明 | 修改 |
| `src/ui.rs` | 导出统一的 Agent 行、尺寸和命中类型 | 修改 |
| `src/ui/sidebar.rs` | 树投影、状态汇总、滚动几何、渲染及单元测试 | 修改 |
| `docs/next/website/src/content/docs/configuration.mdx` | 用户侧行为和配置说明 | 修改 |
| `docs/next/website/src/data/config-reference.json` | `ui.agent_panel_sort` 枚举参考 | 修改 |
| `docs/handoffs/2026-09-02-2332-agent-panel-tree-v1.md` | 开发机续接上下文 | 新增 |

## 6. 已知问题

- [ ] 当前提交尚未完成仓库要求的 `just check`，不可据此判定 CI 已绿。
- [ ] 尚未运行 `just bench-render-scale`；树投影位于 pane-scaled 渲染/布局路径，必须记录 1 与 15+ pane 的伸缩差异。
- [ ] 尚未在真实 TUI 验证窄侧栏截断、长名称、滚动到底部、父节点聚焦以及多客户端配置重载体验。

## 7. 下一步

1. **[P0]** 在开发机进入仓库 dev shell并运行第 8 节的针对性测试与 `just check`；若失败，优先修复而非缩窄检查范围。
2. **[P0]** 运行 `just bench-render-scale`，比较 1 与至少 15 个已填充 pane；若 Tree 模式明显放大每帧分配，复用一次计算出的 `AgentPanelRow` 投影，避免在 metrics/render 中重复构造。
3. **[P0]** 用隔离命名会话完成手工验收：至少 2 个 Workspace、每个 2 个 Tab、每个 Tab 2 个 Agent，并覆盖折叠、状态汇总、聚焦和滚动。
4. **[P1]** 验收通过后，根据开发机最新 `origin/master` 处理 rebase，再继续后续提交或 PR 流程；只向个人 fork 推送，当前账号不具备 upstream maintainer 权限。

## 8. 启动命令

```bash
# 冷启动：仓库提供 Rust 1.96.1、Zig 0.15.2、Just、cargo-nextest 等依赖
cd /path/to/yuki-herdr
nix develop

# 针对性测试
just test-one tree_agent_panel
just test-one clicking_agent_panel_toggle_cycles_grouped_tree_and_priority
just test-one tree_agent_rows_toggle_groups_and_focus_leaf_panes
just test-one focusing_tree_agent_expands_its_ancestors
just test-one agent_panel_sort_config_parses_alias_and_defaults

# 完整检查与渲染伸缩验证
just check
just bench-render-scale

# 从现有 Herdr 内启动新构建时，清除稳定 server 的 socket 继承
env -u HERDR_SOCKET_PATH -u HERDR_CLIENT_SOCKET_PATH cargo run -- --session tree-sidebar-test
```

若开发机也在 Herdr 会话内且默认禁止嵌套，请依照 `.agents/skills/herdr-throwaway-repro/SKILL.md` 创建临时配置和唯一命名会话，不要连接或停止默认会话。
