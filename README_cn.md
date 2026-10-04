# HD2 Agent Skills

[English](https://github.com/YC426/HD2-Agent-Skills/blob/main/README.md) / 简体中文

在 Windows 上**无人值守**驱动 **Helldivers 2** 的 agent skills —— 以及构建、验证、打包那些让自动化成为
可能的模组。这里的每个坐标、每个按键序列、每个失败模式都来自真实运行。

游戏没有提供自动化 API：agent 只能穿过窗口聚焦、合成输入、游戏内菜单和模组日志。这些 skill 存在的
意义，就是让下一个人不必把这些重新发现一遍。

**写模组（而不是驱动游戏）？** 先读[踩坑清单](docs/hd2-mod-failure-catalog_cn.md)——它按症状组织，
第一节就是最花时间的那条规则（`pcall` 不抓原生崩溃）。然后拿
[模组骨架](template/SKELETON_cn.md)：一个最小 addon，把那三条最贵的规则写对了，并附带一个不需要游戏
就能跑的离线测试台（`hd2-offline-engine-harness`）。

## Skills

每个 skill 只讲一件事。工具类 skill 自带工具本体，并把前置条件写清楚。任何文档旁边的 `_cn` 文件
就是它的中文版。

### 流程与技术

| Skill | 中文 | 用途 |
|---|---|---|
| [`hd2-bingus-mod-development`](skills/hd2-bingus-mod-development/SKILL.md) | [中文](skills/hd2-bingus-mod-development/SKILL_cn.md) | Bingus/MDL Lua 模组的完整流水线：仓库结构、加载器强制的源码契约、构建门禁、离线模拟、信封包 ZIP、部署路径与回退、实机日志取证，以及发布纪律。 |
| [`hd2-mission-entry`](skills/hd2-mission-entry/SKILL.md) | [中文](skills/hd2-mission-entry/SKILL_cn.md) | 从冷启动到落地：启动、跳过片头、确认舰船就绪、星图选任务、简报配装、部署，以及每一步的验证证据。自带带聚焦校验的键鼠工具，并列出该流程依赖的模组。 |
| [`hd2-in-game-panel`](skills/hd2-in-game-panel/SKILL.md) | [中文](skills/hd2-in-game-panel/SKILL_cn.md) | 只用 `Gui.rect` 在游戏内画出可点击的面板——保留式 GUI 生命周期、分级建立、图层/原生界面失效、区域命中、拖拽，以及 5×4 点阵字体与打包的中文字形。 |
| [`hd2-native-panel-input-lock`](skills/hd2-native-panel-input-lock/SKILL.md) | [中文](skills/hd2-native-panel-input-lock/SKILL_cn.md) | 用热键（F7）打开面板、解锁鼠标，并在面板打开时让游戏收不到键鼠——raw input 注销、窗口过程过滤、坐标换算、滚轮格数、安全归还。 |
| [`hd2-game-language-autodetect`](skills/hd2-game-language-autodetect/SKILL.md) | [中文](skills/hd2-game-language-autodetect/SKILL_cn.md) | 自动判断客户端是中文还是英文——经 build 校验的 `game.dll` 偏移，带引擎字体字形覆盖率回退，标签只在绘制时翻译。 |

### 工具（每个自带脚本）

| 工具 skill | 脚本 | 用途 |
|---|---|---|
| [`hd2-addon-build`](skills/hd2-addon-build/SKILL.md) | `scripts/build_mod.py` | 把模组打成管理器可导入的 ZIP；源码过不了门禁就拒绝打包。 |
| [`hd2-addon-package-inspector`](skills/hd2-addon-package-inspector/SKILL.md) | `scripts/inspect_package.py` | 读产出的 ZIP：manifest、归档头、名字→哈希映射、声明的图标，以及包里装的是不是你构建的那份源码。 |
| [`hd2-ffi-audit`](skills/hd2-ffi-audit/SKILL.md) | `scripts/ffi_audit.py` | 静态检查：每个被调用的 C 符号都已声明，且没有和别的模组的声明冲突。 |
| [`hd2-bingus-toolchain-setup`](skills/hd2-bingus-toolchain-setup/SKILL.md) | `scripts/fetch_bingus_tools.py` | 在本机找到那套第三方打包工具，放到构建期望的位置。 |
| [`hd2-offline-engine-harness`](skills/hd2-offline-engine-harness/SKILL.md) | `scripts/test_panel_skeleton.py` | 用假引擎边界在真 LuaJIT 上离线测模组——GUI 次数、分级状态、错误预算。 |
| [`hd2-bilingual-doc-verify`](skills/hd2-bilingual-doc-verify/SKILL.md) | `scripts/verify_translations.py` | 让 `X.md` / `X_cn.md` 成对保持诚实：代码块、标题结构、链接、frontmatter。 |
| [`hd2-live-memory-probe`](skills/hd2-live-memory-probe/SKILL.md) | —（模式 + 骨架） | 写一个只读探针跑在运行中的游戏上，验证地址链，不必再打一局。 |
| [`hd2-mod-log-analysis`](skills/hd2-mod-log-analysis/SKILL.md) | —（模式 + 骨架） | 把"模组没反应"变成具名阶段，并写出说清这件事的分析器。 |
| [`writing-mod-tools`](skills/writing-mod-tools/SKILL.md) | — | 怎么把这些工具写好：前置条件与优雅降级、默认只读、退出码、`--json`、dry-run、自检、**实机前先验证判据**、诚实写出做不到什么。 |

`hd2-mission-entry` 另外自带 `scripts/hd2_window.py`、`hd2_verified_input.py`、`hd2_click.py`——
按 pid 定位窗口并校验前台，以及在游戏自己移动光标时仍然能点准的点击器。

## 报告

| 报告 | 中文 | 摘要 |
|---|---|---|
| [`docs/hd2-mod-failure-catalog.md`](docs/hd2-mod-failure-catalog.md) | [中文](docs/hd2-mod-failure-catalog_cn.md) | HD2 Lua 模组的死法：症状 → 根因 → 修法。含 `pcall` 抓不住的原生崩溃、引擎库时序、保留式 GUI 不可见、LuaJIT 的静默上限、纯 Lua 的作用域/元数陷阱、读内存安全、配置处理、日志，以及已验证的死路。 |
| [`template/SKELETON.md`](template/SKELETON.md) | [中文](template/SKELETON_cn.md) | 最小且契约正确的模组骨架；配合 `hd2-offline-engine-harness` 使用。 |
| [`tests/probe-build/`](tests/probe-build/README.md) | — | 流水线探针：唯一无法用模拟覆盖的"导入并加载"步骤，附一分钟验证流程。 |
| [`docs/c4-quick-actions-performance-feedback-2026-10-04.md`](docs/c4-quick-actions-performance-feedback-2026-10-04.md) | — | HD2 C4 Quick Actions 1.11 的稳态读取次数与 FPS 实测；已作为 [issue #1](https://github.com/etxp/HD2-C4-Quick-Actions/issues/1) 提交上游。 |

## 使用

把 `skills/` 指向你的 agent/skill 加载器，或把某个 skill 目录复制进你的 skill 目录。每个 skill 都是
自包含的 `SKILL.md`，带 frontmatter（`name`、`description`）；加载器只认 `SKILL.md`，所以旁边的
`SKILL_cn.md` 不会冲突。

## 检查

以下全部不需要游戏、也不需要加载器的第三方工具即可运行：

```powershell
python -B tests/probe-build/test_probe.py                                    # 探针能到达 PIPELINE OK
python -B skills/hd2-offline-engine-harness/scripts/test_panel_skeleton.py   # 24 项检查
python -B skills/hd2-bilingual-doc-verify/scripts/verify_translations.py     # 所有文档对
python -B skills/hd2-ffi-audit/scripts/ffi_audit.py template/panel_skeleton.lua
python -B skills/hd2-addon-package-inspector/scripts/inspect_package.py <zip>
```

`verify_translations.py` 锁住翻译**不该改**的东西——代码块剥掉注释后一致、译文里的 Lua 仍能在 LuaJIT
上编译、标题结构一致、链接不丢、frontmatter 完好——同时把目录树和散文围栏当作文档处理。改动任何一侧
之后都跑一遍。

## 约定

- 坐标是 1707x1067 布局上的**逻辑像素**（游戏跑在非 100% DPI 缩放，物理 = 逻辑 × 缩放）。
- 游戏内面板使用引擎的 **Gui** 坐标系：原点在左下、y 向上，尺寸取自 `Gui.resolution()`，按
  `min(w/1920, h/1080)` 缩放。Win32 客户区像素换算：
  `gui_y = height - y * height / client_h`。
- 输入注入**永远先确认目标窗口在前台**再发送。
- 每一步都有**日志证据或截图**来确认它确实发生了。
- skill 记录的是**技术**，不是别人的代码：参考实现按文件与行号引用。若被引用实现的代码是 copyleft，
  skill 会说明，并给出独立编写的等价实现——见 `hd2-native-panel-input-lock` 的来源一节。

## 许可

MIT
