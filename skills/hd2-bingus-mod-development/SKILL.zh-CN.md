---
name: hd2-bingus-mod-development
description: 开发、验证并打包一个基于 Bingus/MDL 加载器的 Helldivers 2 Lua 模组——仓库结构、构建必须跑的 LuaJIT 编译门与 FFI 门、用 lupa 做的离线模拟、模组管理器可导入的信封包 ZIP、部署路径与回退、实机日志取证，以及"未经实机验证就不许称为完成"的发布纪律。用于新建 HD2 模组、给模组加功能、打包发布，或搭建完成这一切的构建流水线。
---

# HD2 Bingus 模组开发

这套流水线产出了本工作区里的全部模组。HD2 模组**不是**"写个 Lua 丢进游戏目录"，而是：

> 独立 git 仓库 → 纯文本 LuaJIT 源码 → 离线沙盒自检 → 信封包 ZIP → 管理器手动部署 → 实机日志取证

它有一条硬发布纪律：任何一条门禁不过，**构建不部署任何东西**；而任何改动只有在真实游戏里跑过
才算完成。

另外两份东西负责"什么会坏"而不是"怎么构建"：
[`docs/hd2-mod-failure-catalog.md`](../../docs/hd2-mod-failure-catalog.md)（症状 → 根因）以及
`hd2-in-game-panel`、`hd2-native-panel-input-lock`、`hd2-game-language-autodetect` 里的代码级技术。
**要搭流水线就读本 skill；要写某个功能再去读那几份。**

---

## 1. 仓库结构

一个模组一个 git 仓库。源码、构建、测试放在一起，构建才能拿测试当门禁。

```text
mymod/
├─ README.md                 中英双语的当前状态：哪些验证过、哪些没有
├─ THIRD_PARTY_NOTICES.md    依赖了什么、哪些不能再分发
├─ work/standalone/          构建放这里（沿用上游约定）
│  ├─ mymod.lua              模组源码：纯文本 UTF-8 Lua，无 BOM
│  ├─ build_mod.py           门禁 + 打包（见 template/build_mod.py）
│  ├─ vendor/bingus/         build_addon.py + archive.py —— 需另行获取
│  ├─ test_*.py              离线测试，一个功能一个文件
│  └─ fixtures/*.lua         测试要复放的参考 Lua 快照
└─ dist/                     产出的 ZIP（只放这个）
```

`vendor/bingus/build_addon.py` 和 `archive.py` 编码了加载器的信封包格式，是**从加载器作者那里
获取的第三方工具，不是你写的、也不是你能再分发的文件**——本工作区就刻意没把它们放进公开快照。
当成构建依赖对待，就跟编译器一样。

Python 侧：`python -m pip install lupa`（CPython 里的 LuaJIT），`requirements-dev.txt` 里钉住版本。

## 2. 源码契约

下面这些是加载器/构建器**强制**的，不是风格偏好。违反它不是构建失败，就是**弄坏别人的模组**：

| 规则 | 原因 |
|---|---|
| 首行是 `-- HD2-Addon: mods/<author>/<entry>` | 构建器按资源名写这行；若已存在则必须完全一致。含换行不超过 256 字节。 |
| 资源名匹配 `mods/[A-Za-z0-9_]+/[A-Za-z0-9_]+(/...)*` | 只允许字母、数字和**下划线**——不能有连字符。`mods/codex/loader` 是保留名。 |
| 纯文本 UTF-8，无 BOM，无 `\0`，非 Lua 字节码 | 构建器会全部拒绝。 |
| **任何 `ffi.cdef` 里都不得声明 `user32` 符号** | LuaJIT 的 C 命名空间是进程级的，且 `ffi.cdef` **保留第一次声明**。用不同的原型声明 `GetCursorPos` 会静默废掉所有先声明它的模组——有个模组因此整局自己禁用了自己。`kernel32`/`bcrypt` 符号照常声明；需要光标就不要重复声明它。 |
| 缓存模组表：`if rawget(_G, KEY) then return rawget(_G, KEY) end` | 加载器可能重跑你的入口；没有这行你会得到两份状态。 |
| 版本号只写一处 | 构建从源码里读 `version='x.y.z'` 并用它命名 ZIP。不要在两处各改一次；构建会断言它读到的那一个。 |

游戏内 README 要**放在源码里**的长括号块中（`[===[My Mod - quick guide ... ]===]`），由构建抽取成
`README.txt`。这样指南永远不会和代码脱节。

模组应使用的运行期路径（自己用 FFI 的 `CreateDirectoryW` 建目录，**绝不**在 update 线程里 spawn
shell）：

```text
%LOCALAPPDATA%\CowboyBingus\Helldivers2\          日志与配置根目录
  Logs\<Mod>.log                                  只追加，跨启动累积
  <Mod>\config.txt                                用户选项
  <Mod>\<Mod>-STATUS.txt                          什么都跑不起来时也会写
```

## 3. 门禁（构建必须拒绝什么）

本 skill 的 `template/build_mod.py` 已实现全部四条；改 CONFIG 块，不要自己重写一遍。

| 门禁 | 检查 | 它防住的事故 |
|---|---|---|
| **LuaJIT 编译** | `lupa.luajit21.LuaRuntime().compile(src)` | 单函数 65535 指令上限会让加载器**静默跳过**过大的模组，而普通 Lua 编译却说 OK。这是真实发生过的"装上了但什么都不做"。 |
| **无 user32 声明** | 扫每个 `ffi.cdef` 块里的 user32 符号集 | 顶掉别人的声明（见 §2）。 |
| **调用 ⊆ 声明** | 每个 `k.Foo(` / `u.Foo(` 都有声明 | `missing declaration for symbol 'X'` 是调用点的硬错误；它曾经以"点击卡片没反应"的形式发布出去。 |
| **README 块存在** | `[===[...]===]` 标记存在 | 发布一个没有游戏内指南的包。 |

每次保存都跑 `--validate-only`，它在打包前就停。

```powershell
python -B work/standalone/build_mod.py --validate-only
```

## 4. 离线测试：模拟引擎，不是模拟游戏

你没法给游戏写单元测试。但可以针对**引擎边界**测你的代码，而贵 bug 就住在那儿。`lupa.luajit21`
给你真正的 LuaJIT：

- **伪造引擎表**（`stingray`）并统计关键调用（`create_screen_gui`、`destroy_gui`、`Gui.move`）。
  断言**次数**，不只是"没报错"：两帧必须恰好建一个 GUI。
- **复放抓来的 Lua 快照。** `work/standalone/fixtures/*.lua` 保存模组要适配的参考函数（例如某个
  游戏 UI 消费方）；测试让原实现和你的适配器跑同一份合成状态，比对结果和读取次数。
- **差分测试在这里是最强的形式。** "原实现：189 次原生读取；适配器：53 次；所有观测字段一致"
  是你能离线验证的结论。就这么写，并把快照纳入版本管理。
- **测失败路径**：选项关闭、排除名单、未知函数指纹、读取异常、重载。只在顺利路径上能正确还原
  的模组会把用户卡死。
- **断言你将来要引用的观测量**：回调次数、每个返回值（含末尾的 `nil`）、分配量差值，以及
  **静止**面板执行了零次原生调用。

然后把测试清单写明确，每次构建都跑：

```powershell
python -B work/standalone/test_sb2.py
python -B work/standalone/test_sb3_autopause.py
python -B work/standalone/test_sb5_interdict.py
python -B work/standalone/ffi_audit.py work/standalone/mymod.lua
```

**坏了好几个月的测试比没有测试更糟。** 本工作区就背了两个（`test_smoothboot.py` 有 6 项已知失败，
`test_sb4_writerhold.py` 要求另一个版本），规矩是**明说**，而不是悄悄当成通过。修不好的过期测试，
在 README 里标注为"已知失败 + 原因"。

## 5. 打包：信封包

`build_addon.py` 把源码变成加载器读取的归档，再包成管理器可导入的 ZIP：

```text
<Display-Name>-<version>.zip
├─ manifest.json                       Version、Guid、Name、Description、Options[Include:["Addon"]]
├─ Addon/9ba626afa44a3aa3.patch_0      Lua 归档（文件头 + 资源条目）
├─ Addon/9ba626afa44a3aa3.patch_0.stream          （空）
├─ Addon/9ba626afa44a3aa3.patch_0.gpu_resources   （空）
├─ icon.webp                           只有你真的有图标时才在
└─ README.txt                          从源码抽取
```

要紧的规则：

- **一个 GUID 用到底。** `Guid` 是管理器识别"这是升级而不是第二份安装"的依据。同一个模组的每次
  发布都复用同一个 UUID。
- **归档里绝不能有散落的 `.bat`**——模组站点会隔离脚本文件。需要辅助脚本就在运行时写到
  `config.txt` 旁边（SmoothBoot 的日志收集器就是这么做的，并在 `THIRD_PARTY_NOTICES.md` 里说明）。
- **不要发布**代码托管自动生成的 "Source code" ZIP；它不是模组包，管理器不会导入。
- manifest 里引用了图标，归档里就必须有那个文件。悬空的 `IconPath` 会显示空白条目。

```powershell
python -B work/standalone/build_mod.py                 # -> dist/<Name>-<version>.zip
python -B work/standalone/build_mod.py --with-source   # 只用于代码评审交接
```

## 6. 部署、实机验证，并且要能回退

部署是刻意动作，绝不是副作用。有的构建脚本把它放在显式开关后面（`build_armor.py --deploy`），契约是：

> **任何一条门禁不过的构建，不部署任何东西。**

文件落在哪：

| 目标 | 路径 |
|---|---|
| 游戏 patch 槽位 | `...\Helldivers 2\data\9ba626afa44a3aa3.patch_<slot>` |
| 模组管理器库 | `%LOCALAPPDATA%\hd2arsenal\mods\<ModDir>\Addon\9ba626afa44a3aa3.patch_0` |

**先搞清哪个槽位是你的。** 靠层内声明（`-- HD2-Addon: mods/<author>/<entry>`）判断。`data\` 里其他
一切、以及管理器库里别人的每个条目，都属于游戏或其他作者：不读、不改、不依赖。有的构建脚本会同步
两处；如果你的会，之后仍要两处都核对。

**做实验之前先备好回退点。** 留一份你**亲眼见过不崩**的构建，记下字节数和哈希前缀，并且知道两个
路径怎么覆盖回去。实验构建一旦让游戏崩，两处都还原再重启——不要在坏掉的安装上继续调。

端到端循环：

```powershell
# 1. 改 work/standalone/mymod.lua
# 2. 门禁 + 测试
python -B work/standalone/build_mod.py --validate-only
python -B work/standalone/test_sb2.py
# 3. 打包
python -B work/standalone/build_mod.py
# 4. 显式部署，然后验证
Start-Process 'steam://rungameid/553850'      # 约 15-25 秒到船上
#     观察 60-120 秒，然后读日志
```

搜构建输出前先重定向到文件——测试运行器的噪音混在 stdout/stderr 里，直接管道会误导你。

## 7. 实机取证

没有日志的模组无法调试，没有日志的结论不算结果。

- **每次状态变化一行日志**，卡住时加一条心跳——绝不每帧。
- **写 `-STATUS.txt`**，加载时和心跳时都写，这样"面板从没打开"也留下一个能发出去的文件。
- **日志跨启动累积且是 UTC。** 判断"这一轮"要按时间戳筛（UTC+8 时区下 `12:xx:xxZ` = 本地
  20:xx），不要按文件位置。这已经造成过真实误读。
- 先读 `BingusSharedLoader.log`：它告诉你加载器到底有没有加载你的入口。然后再读你自己的日志。
- 日志里要**按名字**写清任何跳过或挂起的原因。"blocked" 要花几小时；"held: ship world not
  resolved" 只要几秒。

## 8. 发布纪律

这是让项目保持诚实的那部分，而且很便宜：

1. **把"离线验证过"和"实机验证过"分开。** 本工作区每份 README 都写明白哪个是哪个。模拟结果永远
   不是帧率或行为结果。
2. **没亲眼观测到的实机结论就不要宣称。** 明确写出待办（"实机验收仍未完成"）。
3. **候选版就保持是候选版。** dev ZIP 不是稳定发布。
4. **说清你没修什么。** 已知失败的测试、未解决的反馈、没测过的边界。
5. **离开时让游戏处于你见过能用的状态。** 收尾前确认它能启动、不崩。
6. **只碰自己的模组。** 不碰游戏本体，不碰别人的文件。
7. **不要改动用户已经确认过的行为**（显示时机、热键、默认值），除非被要求。只修被要求修的东西。

## 工作流

1. 复制 `template/build_mod.py`，填 CONFIG 块（源码路径、资源名、GUID、显示名、README 标记）。
2. 把 `build_addon.py` + `archive.py` 放进 `work/standalone/vendor/bingus/`。
3. 源码从本 skill `template/` 目录的 `panel_skeleton.lua` 起步（分级建立、取值守卫、帧错误预算、
   STATUS 文件、可测接缝）——它是不依赖特定打包格式的模组骨架。
4. 写功能时对照对应的代码级 skill。
5. 每次保存跑 `--validate-only`；每个功能配一份离线测试。
6. 打包、显式部署、实机观察、读日志。
7. 宣称完成之前，先更新 README 里"已验证 / 未验证"的划分。

## 参考

- `template/build_mod.py` —— 含全部四条门禁、图标处理和 README 抽取的构建脚本。改 CONFIG 块即可
  直接运行。
- `hd2-in-game-panel`、`hd2-native-panel-input-lock`、`hd2-game-language-autodetect` —— 功能侧：
  绘制、输入/光标、本地化。
- [`docs/hd2-mod-failure-catalog.zh-CN.md`](../../docs/hd2-mod-failure-catalog.zh-CN.md) —— 出问题时：
  症状 → 根因 → 修法，包括那些不抛异常的坑。

## 哪些**没有**验证

流水线结构、门禁行为和打包格式取自本工作区里的模组，且此处的构建脚本已端到端跑过（门禁通过、
打包产出合法信封、user32 声明被正确拒绝）。但**上面的部署路径、槽位号和日志位置是本工作区观测到的
值**——请从你自己安装里的 `-- HD2-Addon:` 声明重新推导槽位，不要照抄数字。
