---
name: hd2-offline-data-workflow
description: 离线定位并解码《地狱潜者 2》的游戏数据表 —— 从 FileDiver 的明文镜像和游戏自身的 typelib 入手，在运行任何东西之前先算出类型哈希、字段偏移和记录布局，然后只做最少的游戏内验证。当你需要某张数据表的内容、偏移或签名，或者你正准备把一次游戏内运行花在本来可以在磁盘上解决的扫描上时，使用本技能。
---

# HD2 离线数据工作流

[English](https://github.com/Puipipi/HD2-Agent-Skills/blob/main/skills/hd2-offline-data-workflow/SKILL.md) / 简体中文

一次机器会话的代价是一次游戏重启，而 Bingus Shared Loader 没有热重载，所以每一个你能在磁盘上回答的问题，都是你不该去问正在运行的游戏的。明文镜像加上 typelib 能回答其中大部分问题。**先离线工作，最后才进游戏。**

本文面向 Lua 注入类 addon（由 Bingus Shared Loader 加载、运行在游戏 LuaJIT VM 内的 addon）。替换 `data/` 资源的资源替换型 mod 属于另一条流水线。运行时写入这一侧在此是有意排除在外的。

## 来源与置信度 —— 先读这一节

**本文件没有任何内容在本仓库执行过或重新测量过。** 它是对一位贡献者工作笔记的重组,取自
[`junze0910/junze-hd2-lua-mod`](https://github.com/junze0910/junze-hd2-lua-mod)(MIT)。作者说过:
其中并非所有内容都测试过,有些还需要别人来测。下面每一条都当作**据来源报告、本仓库未独立验证**。

有两个例外,因为那两条是在本仓库核对的,而不是照搬的:

- **「磁盘上的 `game.dll` 无法离线扫描」** —— 已独立复现。磁盘镜像哈希与加载器的门禁常量一致,但其主节
  的节名被抹空、熵约 7.9998、且找不到已知代码签名;见 `docs/hd2-mod-failure-catalog.md` §5。
- **资源名→哈希的函数,以及归档的 magic/类型常量** —— 已用加载器自己发布的测试向量核对,核对者是
  `hd2-addon-package-inspector`;不一致就非零退出。

有一条**无法**在本仓库核对,已在「注意事项」中标出:`generated_entities.dl_bin` 在内存中的镜像与磁盘
文件逐字节相同这个断言 —— 本工作区没有这个文件。

| 下文使用的标记 | 含义 |
|---|---|
| *(作者已在实机验证)* | 来源称其在真实运行中观察到了。但仍然只是**一台机器、一个 build**。 |
| *(据来源报告)* | 来源如此陈述,但没有描述任何测试。未验证。 |
| *(受版本约束)* | 该值属于某一个游戏 build、模组版本或日期,不可移植,请重新推导。 |
| *(未解决)* | 来源中两处陈述互相矛盾且未调和。两者都保留。 |

不要把这里的任何内容当作既定事实引用。需要确定性就自己去推导,并说明你是怎么推导的。


## 离线优先循环

1. **离线找到明文** —— 数据表的字节和类型库，都在磁盘上。
2. **离线算出偏移和取值** —— 类型哈希、字段偏移、记录布局，以及候选取值本身。
3. **在游戏内做最小验证** —— 一次只读遍历，确认签名就在你算出的位置，布局就是你解码出来的样子。
4. 只有到这时才写入。

机器上的侦察是昂贵的一步；明文镜像消除了对它的绝大部分需求。

## 明文数据从哪来

FileDiver 的 `datalibrary` 用 `//go:embed` 把明文数据（含 typelib）打包进 Go module。运行 `go mod download github.com/xypwn/filediver`（或克隆源码树）；文件位于 `<GOMODCACHE>/github.com/xypwn/filediver@<ver>/datalibrary/`：

| 文件 | 内容 |
|---|---|
| `generated_entities.dl_bin` | **45 MB**；全部实体/组件数据 —— 武器、挂架、装备、库存、战略配备 |
| `generated_projectile_settings.dl_bin`（及同级文件） | projectile / damage / explosion / surface 设置表 |
| `dl_library.dl_typelib` | 游戏自身的类型库 |
| `*.go` | 每个组件字段的名称和注释，由 typelib 生成 |

这个镜像是明文数据表的唯一来源，这也是它出现在本工作流里的原因：安装目录中随游戏发布的 `data/game/generated_*.dl_bin` 文件是加密的（熵 **7.9998 bit/byte**；`LDLD` 在 45 MB 文件里出现 **0** 次；该文件通常只比明文镜像大 **48 字节**）。它们无法被解码，也不在流水线之内 —— 不要试图编辑它们。

**把 typelib 转储成 JSON：** 把 `tools/dump_typelib/` 放进 FileDiver 源码树的 `cmd/` 下，然后运行 `go run ./cmd/dump_typelib -o typelib_all.json`。`-o` 不是可选项 —— PowerShell 的 `>` 重定向会写出 UTF-16，Python 读不了。产物 `typelib_all.json` / `typelib_names.tsv` 带有全部 **约 1177** 个类型的字段偏移 / 大小 / 成员名，以及类型哈希 ↔ 名称的对应关系；当社区结构体与当前版本不一致时，它是权威的偏移来源。

## 定位一张数据表：靠签名，而不是靠地址

**ASLR 会让每次运行之间的一切都移位。** 绝对地址在每次启动时都不同，所以唯一可行的方案是"先按签名定位，再施加相对偏移" —— 硬编码的绝对运行时地址会悄悄成功一次，然后在重启后失效。

### LDLD 块头

一个数据表块是 `LDLD` + u32 version（= **1**）+ u32 type hash + u32 size。离线解析和内存内普查都以这个签名为键。

### 类型哈希 = 末尾减去 5381 的 djb2

`dlsum(name)`：`r = 5381`；对每个字符 `r = (r * 33 + ord(c)) & 0xFFFFFFFF`；返回 `(r - 5381) & 0xFFFFFFFF`。示例：`"HellpodRackComponentData"` → `0xA98BB156`。`typelib_names.tsv` 中的每个名称都以这种方式映射到它的 LDLD 数据表签名，这正是让你不借助游戏就能从类型名走到签名的原因。

### 资源名哈希是另一个函数

资源名用 `MurmurHash64A(name, seed=0)` 做哈希。这两个哈希看起来相似，但彼此无关；在本该用资源名哈希的地方用了类型哈希（或反过来）会悄无声息地什么都找不到 —— 一连串 "not found"，却没有任何报错。

### 数据起始位置有两种可能的布局 —— 按内容验证，绝不猜测

| 数据表族 | 实例数据起始于 |
|---|---|
| `generated_*_settings.dl_bin` | magic **+40** |
| `generated_entities.dl_bin` | magic **+24** |

单个硬编码的数据起始位置会把其中一族数据表解错。用内容来验证：一条解码出的记录应当有说得通的字段 —— count ≤ **8**、speed 在 **1~5000**、item hash 能在资源名列表里解析出来。

### 并非每张数据表都是 LDLD 块

`StratagemSettings` 是一个 **16 字节**的容器，其成员是一个 ARRAY；真正的记录是 `StratagemInfo`，`size = 400`，偏移 `+0` type、`+4` id、`+80` uses、`+104 / +108` cooldown float（success / fail）、`+152 / +160` payload[2]、`+168` package、`+176` icon、`+196` depends_on、`+200` additional_stratagem、`+204` max_in_loadout。**先**从 typelib 里拿到记录类型和字段偏移，然后再选择扫描策略 —— 假设每张数据表都是 LDLD 块，曾让战略配备相关的表完全找不到。

作为对照，战略配备指针数组的一条 AOB 路径记录布局（`StratagemCooldown 2.1.5`）读取的是 **0xB0** 字节的记录：`+0x00` id、`+0x04` hash、`+0x10` name 字符串指针、`+0x50` uses（int32，`-1` = 无限）、`+0x68` cooldown（float）、`+0xC8` AOB 自身访问的那个字段，对应 `additional_stratagem`。

### 它是连续数组吗？去测，不要假设

对于连续记录，步长 `S`，`package` 字段位于 `+P`：`base = addr(pkg) - P - (id-1)*S`。如果若干已知记录得出同一个 base，且它们的 icon 全部吻合，那它就是连续数组；否则不要硬套 `base + (ID-1)*S`。实测：全部 **7** 个 `StratagemInfo` package 都被定位到了，但不存在公共 base —— 这些记录并不是一个按 ID 排序的连续 400 B 数组（更像是指针 / 分散分配），所以每条记录只能按它的 package 内容去定位。

### 字段里存的是枚举值，不是数组下标

记录字段存的是**枚举值**，不是数据表下标。按记录自身的 type 字段去查：`for i = 0, count-1 do if u32(rec + 0) == WANTED_TYPE then ... end end`。查"数组下标 371"什么都没返回；"枚举值 371"找到了正确的记录。

### 社区结构体不是基准事实

由 typelib 生成的 `datalibrary/*.go` 文件 —— 也就是带字段注释的那些 —— 对当前版本是可信的；FileDiver 里手写的 Go 结构体则未必。拿不准时，去读 `typelib_all.json` 里的偏移，或直接读 `dl_library.dl_typelib`。一个与版本脱节的社区结构体曾把一次解码带到了错误的路上。

## 扫描器

### 把扫描放进一个服务里

不要给每个 mod 各写一个私有的 `VirtualQuery` + `ReadProcessMemory` 全量扫描。在把工作收敛进 `Scanner` 之前，七个 mod 各自在全量扫描 9 GB：

```lua
HD2Scanner.scan_request{
  id = 'exo_strat_pkg',
  patterns = { {key='a', bytes=...}, {key='b', bytes=...} },
  budget = 8 * 1024 * 1024,
  on_hit = function(key, addr) ... end,
  on_done = function(hits) ... end,
}
HD2Scanner.scan_cancel(id)
HD2Scanner.scan_status(id)
```

它内部枚举可读的已提交区域，以 **256 KB** 的块加重叠来分块（这样模式不会跨边界断开），强制执行每帧 `8 * 1024 * 1024` 的预算，跳过自身的模式，对多个请求排队，并把结构验证和写入留给消费者。消费者只做验证和写入；如果正在运行的构建里的 Scanner 缺少 `scan_request`，就保留一个自扫描兜底。

### 分时到每步 ≤8 ms CPU

每帧 64 MB 会把游戏饿死，它会卡在加载界面。使用 `os.clock() + 0.008` 的截止时间（**每步 ≤8 ms** CPU），按**尺寸降序**扫描区域（更大的块更可能装着数据表），并把扫描推迟到第 **120** 帧。

### 扫描会找到扫描器自己的模式串

模式串存在于 Lua 堆里，所以内存扫描会命中它们。取每个模式自身的地址 —— `tonumber(ffi.cast("uintptr_t", ffi.cast("const char *", pattern)))`，放在 `pcall` 里调用，因为这个强制转换可能失败 —— 把它们全部收集起来，并跳过落在任一自身地址 **±4096** 字节内的任何命中。曾有一次扫描"成功"完成，但它只匹配到了自己的模式数据。

要注册**每一个**模式，而不只是主签名，例如 `local SELF_PATTERNS = { SIGNATURE, pkg_le_1, pkg_le_2, icon_le_1, ... }`。v1.2 SSProbe 只为 `LDLD + typeHash` 注册了自身地址，于是每个候选都是它自己那份 `SIGNATURE` 拷贝、`size=0` —— 看起来像是找到了目标，其实是探针自身。

### 结构验证是第二道过滤器

LDLD 候选必须有一个说得通的 `magic + ver + typeHash + size`；`StratagemInfo` 候选必须满足 `+8` icon 和 `+28` / `+36` 等于 `0`。

### 给每一层循环都套上 `pcall`

区域读取失败和模式扫描失败都必须被捕获并跳过。每一层循环都需要自己的 `pcall`；否则单次故障就会浪费掉整个回合。

### 把转储读取钳制在区域基址内

一个 LDLD 块可能位于分配基址 **+4** 处。从 `magic-64` 开始转储会读到区域之外，`ReadProcessMemory` 返回 **0 字节**，转储文件里就只剩一个头部。把读取起点钳制到区域基址，失败时把起点往前挪一点再重试。

### 稳定的区域内偏移可以完全取代扫描

Scanner 的设计笔记记录：区域内偏移在会话之间是稳定的，这样无需扫描就能定位一张数据表，代价是 **1.1 MB / 117 ms** —— 比 7 个 mod 各自全量扫描 9 GB 便宜约 **7500 倍**。反复的全量扫描才是主导成本。

### AOB 路线：快、优先，但永远不是契约

`StratagemCooldown 2.1.5` 的 AOB 对是 `49 8B 84 C7 ?? ?? ?? ?? 44 8B 80 C8 00 00 00 8B C2 45 85 C0` —— 即 `mov rax, [r15 + rax*8 + disp32]` / `mov r8d, [rax + 0xC8]` / `mov eax, edx` / `test r8d, r8d`。算法：

1. 取 `game.dll` 的基址和映像大小；
2. 以 **1 MB** 分块、**0x40** 重叠扫描该映像；
3. 要求该 AOB 对是**唯一**的（0 个匹配 = 失败，>1 个 = 有歧义）；
4. 命中处就是 `consumer`；
5. `disp = i32_at(consumer + 4)`；
6. 向上回溯最多 **0x1000** 字节找 `4C 8D 3D`（`lea r15, [rip + disp32]`）；
7. `r15_base = lea_addr + 7 + lea_disp`；8. `table_base = r15_base + disp`；
9. `slot_ptr(id) = u64_at(table_base + id*8)`；10. `rec = read_at(slot_ptr(id), 0xB0)`。

游戏更新可能改变函数、寄存器分配、指令编码或相邻代码，把唯一匹配变成 0 个匹配或若干个有歧义的匹配 —— 也可能 AOB 仍然匹配，而 `disp` / `lea` / 指针数组结构已经移位。因此始终要检查匹配唯一性、检查 `sane_ptr` 范围、验证 `slot_ptr(id)` 和记录字段（id / name / uses / cooldown 是否说得通），失败时**自动回退到全内存的 package 内容搜索**，并把 AOB 解析失败和回退原因显式记进日志。只做 AOB 的实现会在一次更新之后悄无声息地失效。

### 你无法离线扫描随游戏发布的 `game.dll`

`data/game/game.dll`（15.5 MB）在磁盘上是加壳的。证据：前 8 个节名被抹空；这些节的熵是 **8.000**（饱和），而 `kernel32.dll` 是 **6.338**；节的 VSize `0x210FA93` 对 RawSize `0x850800`（内存映像约为磁盘映像的 4 倍）；`.winlice` 节的 RawSize = **0**（只在运行时填充）；导入表 `.idata` / 导出表 `.edata` 各自只有 **0x200** 字节；而最常见的函数序言 `48 89 5C 24 08` 在该文件里命中 **0** 次（在 `kernel32.dll` 里命中 4104 次）。

后果：对磁盘文件做任何离线签名扫描或反汇编都不可能 —— 永远是 **0 次命中**。这也是 MDL 每次启动都要重新扫描签名的原因：它根本没有可离线查询的副本。

### 反作弊边界

反作弊是 **nProtect GameGuard**（安装目录 `bin/GameGuard`）。不要从外部进程用 Python / ctypes 配合 `OpenProcess` + `ReadProcessMemory` —— 那是最容易被检测到的动作，而且与常见的 Cheat-Engine 式附加并扫描的习惯相冲突。只有游戏内的只读 addon 是可接受的。

## 侦察 addon：一次性的只读遍历

写一个**绝不调用 `WriteProcessMemory` / `VirtualProtect`** 的 addon：

1. 分时内存扫描，按 `LDLD + version + type hash` 定位数据表；
2. 同时在内存里搜索唯一 ID 哈希（资源名哈希）并转储 **±512** 字节的上下文，这样即使数据表头始终没出现，对象也能被定位；
3. 十六进制转储到 `%LOCALAPPDATA%/<your dir>/`；
4. 附带一份内存中每个 `LDLD` 块的**普查**（地址 / 类型 / 大小 / 样本）。

永远只读优先。加载器只在**启动时**需要一次 addon，而且没有热重载，所以哪怕只改一行也意味着关闭并重启游戏 —— 这就是为什么第一版必须被做成"就算出了岔子，磁盘上也留有产物"。曾有一次侦察运行以崩溃告终，什么都没写下来。

### 一次性运行的日志纪律

- 每 N 帧周期性刷新，而不是只在扫描结束时刷新；出错时也要刷新。
- 给每行加 `[frame N]` 前缀，这样随飞船加载的数据和只在任务内部存在的数据可以区分开。
- 对重复的报错打印做限流，免得日志被淹没。
- 每条断言旁边都记录**期望值**，这样不匹配时能立刻读成"签名没找到"或"找到了但布局变了"；没有它，这两种情况是分不清的。
- 批量诊断输出不能走有环形上限的日志历史 —— 让它走一个直接写盘的独立 `dump()`，否则 **400** 行的上限会把它吃掉。
- 加载器只接受 `.log` 名字：`if type(name) ~= 'string' or not name:match('^[%w_-]+%.log$') then return nil end`。`.txt` 会返回 `nil`，而调用方外层的 `pcall` 会把它变成一个悄无声息缺失的文件。每次转储都用 `.log`，例如 `SSProbe_dump.log` / `SSProbe_table.log`；文件没出现时，先检查命名规则，再去怀疑扫描。共享日志目录是 `%LOCALAPPDATA%/CowboyBingus/Helldivers2/Logs`。

### 先普查，再规划

先用 `LDLD` 签名普查，然后再选策略。实测：设置类表（projectile / damage / explosion）是常驻的；实体 blob 内部的组件表在飞船上不一定存在，但一旦进入任务就会存在（Leveller 挂架表只在**第二轮**扫描时才被找到）。在飞船上只扫一轮，就得出"该表不存在"的结论。要为多轮扫描预留预算。

### 在没有离线机器码可比对时验证解码器

没有可对照的 `game.dll` 离线副本时，唯一可用的参照就是在同一进程内的第二份实现：找另一个已经在这台机器上跑通的 mod（例如 MDL），从它的日志里抄下它解码出的数字；在你自己的实现首次成功运行时记录同样的那十几个数字；逐项比较 —— 全部相等说明解码器正确，有一处不同就能定位到那个具体的错误 `disp32`。

由 MDL **1.4.2** 在 **2026-09-24** 版本上解码出的已知良好取值，可用作该比对的基线（受版本约束，不是可移植的偏移）：

| 解码器区域 | 取值 |
|---|---|
| native menu state | `MenuSystem +0x347ce38`、open 字节 `+2185`、**36** 种屏幕类型 |
| native tab | bar `+1248`、count `+57448`、labels `+57320`、text `+8296`、`set_labels +0x17aac50`、`set_arg +0x143c950`、labels `0xd876b36e 0x78934e12 0x8c02bd80` |
| native font slots | font `+0x3772268`、atlas `+0x3772ee8`、material `+0x37c5478` |

（现已退役的）ESC 菜单面板设计对 `game.dll` 本身用了同样的思路：一个"签名 + 自检，不匹配就禁用自己"的例程、三层惰性判定、在**第 4 / 第 5** 个菜单槽位之间做运行时决策，以及与 MDL 的互操作。不变式在退役之后依然成立 —— 当菜单宿主所针对的版本已经改变时，它绝不能破坏游戏。

## UI 集成

`_G.ModOptionsMenu`（`mom.register_option`）只支持 `toggle`、`choice`（**2–16** 个固定选项）和 `slider`。它**不**支持自由文本输入、任意按钮 / Action 行、动态只读状态行，也不支持在注册之后修改 `choice` 列表。由此得出的做法：左和右需要各自独立的 `choice` 池（左槽只列左侧条目，右槽只列右侧条目）；由玩家触发的动作（开始扫描 / 初始化）由一个 `toggle` 承载 —— Apply 触发回调，做完事之后要么立刻 `menu.set(id,false)` 弹回，要么在操作结束时弹回；任何在选择变化后必须重算的东西都用 `menu.set` 同步回去；Scanner 本身在 MODS 页用了 3 行（状态 / AOB / 诊断），可以直接照抄。

整个 `_G.HD2Menu` / `HD2MenuQueue` 页面系统已退役（**2026-10-04**）：渲染宿主 `ui.lua` 自 **2026-10-03** 起就不在发布包里了，所以页面从来无法显示；而在 2026-10-04，`registry.lua` 也随之一并被删除。新的 mod 不得写 `menu.register{...}`，也不得往 `HD2MenuQueue` 里排队 —— `rawget(_G,'HD2Menu')` 现在是 `nil`。搭在已退役宿主上的页面从未渲染过，白白浪费了整块 mod 功能。

## 工具与工作流

### 做任何机器操作之前先验证版本

在碰机器之前，先检查 `helldivers2.exe` 的版本和 SHA-256。**版本未变意味着旧的转储、偏移和普查全都依然有效**，这能省下一整轮侦察；在未变的版本上重跑侦察是浪费一整个周期。

### 工具清单

| 路径 | 用途 |
|---|---|
| `references/ldld.py` | **LDLD 数据表解析器** —— `dlsum` / 查找实例 / 解码记录 |
| `tools/projectile_settings.py` | `generated_projectile_settings.dl_bin` 解析器 |
| `tools/dump_typelib/` + `tools/go/` | typelib → JSON（在 FileDiver 源码树内运行）；可移植 Go，只为此需要 |
| `tools/inspect_patch.py` | 归档结构查看 + 自动往返校验 |
| `tools/hd2_archive.py` / `tools/build_addon.py` | `.patch_N` 读/写（往返已验证）/ `.lua` → 可安装 ZIP |
| `_baseline_<build>/` | 机器上的内存转储基线，供更新后比对 |
| `tools/ljd/` —— **第三方** | LuaJIT 字节码反编译器，用来读别人的 mod |
| `tools/filediver/` + `filediver-src/` —— **第三方** | 解包工具 + **明文 datalibrary 与字段名 Go 源码** |

### 靠差分求解，而不是靠发明

用明文镜像里的 `dlsum` 按类型名找到目标数据表并解码全部记录；字段偏移取自 `typelib_all.json`，字段含义取自 `datalibrary/*.go`；然后找出**同族对照**并做 diff —— 这比点对点狙杀更快、更扎实。当时的任务是"Leveller 每次空投只投下一个"，而 EAT-17 和 EAT-700 都投两个，于是把三条挂架记录并排放在一起，差异字段就自己跳出来了（`slot1` 为空 + `SpawnPayloadSize`）。比起发明数值，更应优先复制一个已经在游戏里跑通的配置：最后那 **64 字节**与 EAT-17 的 slot1 **逐字节相同**，只有一处 **8 字节**的 item hash 不同 —— 这证明复现出来的行为就是引擎既有的行为，而发明出来的数值则是未验证的。然后离线验证：用脚本解析转储，确认偏移和取值范围；如果内存布局与文件映像一致，这一步就是纯粹的验证，一次便宜的自检，省掉一个机器往返。

### 与社区 wiki 交叉验证

`helldivers.wiki.gg` 的 "Detailed Weapon Statistics" 给出精确数字；把它们与一张数据表逐项对齐，多项同时命中就锁定了那条记录。示例：按 wiki，Eruptor 的撞击爆炸是 `225 damage / 30 fragments / inner radius 4 m / outer radius 7 m / demolition 20 / stagger 35 / push 40 / Medium armor penetration`，而在 **413** 条爆炸条目里**只有一条**同时匹配这 8 项。Wiki 的行为性描述（例如*"sent two at once like typical EAT-17"*）可以直接引向同族对照。多项字段的 wiki 匹配无需机器扫描就能钉住那条记录。

### 用 `lupa` 加类型严格的桩离线模拟

用 `lupa`（`pip install`）在 Python 里跑 Lua，配一个**假的内存空间**。桩必须是类型严格的，否则它抓不住这一类 bug：在本该传指针的地方传了一个裸 Lua number（`cannot convert number to const void *`）：

```lua
function ffi.cast(ctype, v)
    if ctype:find("%*") then
        if type(v) == "number" then return { __ptr = v } end   -- 指针是特殊对象
        if type(v) == "table" and v.__ffi then return { __ptr = v } end
        error("ffi.cast(" .. ctype .. "): cannot cast " .. type(v))
    end
    return v
end
function kernel.ReadProcessMemory(proc, address, buf, size, count)
    address = as_pointer(address, "ReadProcessMemory")       -- 传 number 会立刻报错
    ...
end
```

一个宽松的桩曾让指针类型 bug 一路跑到机器上。

### 变异测试与夹具

修好一个 bug 之后，把它改回去，确认测试**确实失败** —— 当某个变异没被抓到时，先怀疑夹具再怀疑代码（`SpawnPayloadSize` 那个变异逃掉了，因为夹具自己把诱饵挂架放在了错误的偏移上）。夹具要从真实的捕获内存转储来构建，这样偏移是对真实字节检查的；并加入刻意的诱饵：一张看起来合法但关键字段错误的数据表（测试你的验证逻辑），以及一块包含你自己模式串的假堆区域（测试自检测）。注意扫描顺序 —— 区域按**尺寸降序**扫描，所以如果某个诱饵必须先触发，就把它做大一些。

### `lupa` 疑难排查

| 现象 | 原因 / 修复 |
|---|---|
| `cannot open ...: Illegal byte sequence` | Lua 的 `fopen` 打不开含中文字符的路径；把夹具文件放到 `%TEMP%`（纯 ASCII） |
| `too many registers (limit is 255)` | 一次 `string.char(...)` 调用带了数万个参数；按 **200** 分块 |
| 读回时 `UnicodeDecodeError` | lupa 默认按 UTF-8 解码 Lua 字符串，遇到二进制就会出错；让 Lua 侧返回**十六进制字符串** |

### 参考笔记与负面结果

`hd2-eruptor-dominator-案例.md` —— R-36 Eruptor 弹体打到 JAR-5 Dominator 上（纯内存内的 projectile 表编辑）。`hd2-leveller-double-案例.md` —— EAT-411 Leveller 每次空投投下两个（完整离线求解 + 一次机器侦察 + **64 字节**补丁）。`hd2-ac8-rack-backpack-设计.md` —— AC-8 背包替换 v6（内容锚点法）。`hd2-scanner-设计定稿.md` —— 在写新 mod 或修改扫描/查表逻辑之前先读。`hd2-stratagem-settings-笔记.md` —— StratagemSettings / StratagemInfo 笔记（非 LDLD 的 400 B 记录、package 内容搜索、Scanner memscan 服务、ModOptionsMenu 能力边界）。`hd2-strat-unlock-设计定稿.md` —— "让某个战略配备可选"先读这个。`hd2-supply-custom-设计定稿.md` —— 补给 / 挂架改动先读这个。载具参数笔记 —— **未找到**：`+296`、`+300`、…… 每一个都试过并被否掉。负面结果也是数据：不要重跑已经穷尽的搜索。

值得离线放在手边的组件布局：`HellpodRackComponent` 是 **568 B** = `RackAttach[8]`（每个槽 **64 B**）+ 一个尾部，其中 `spawn_payload_size` 位于 `+0x22C`；AC-8 那个案例通过 LDLD + 类型哈希 + 记录内相对偏移来定位 `HellpodRackComponentData`（即"内容锚点"法）。相对于某条记录的 `package` 字段地址 `c`：`c+32` = `additional_stratagem`、`c-88` = `use`、`c-64` = `cooldown_duration_success`、`c-60` = `cooldown_duration_fail` —— 这些目标分布在 package 指针周围，而不在固定的记录偏移上。

## 注意事项：未解决、未验证与已退役

- **内存映像逐字节相同 —— 由来源报告，本文档未证实。** 来源称 `generated_entities.dl_bin` 的内存内副本与文件逐字节一致，因此离线算出的相对偏移可以直接在运行时使用。该说法在本工作区中**无法**独立验证，因为文件不存在。请把它当作"由来源报告"，在基于它构建之前先用只读探针确认。真正被独立证实的是它的推论：绝对地址每次运行都不同（ASLR），所以"先按签名定位，再施加相对偏移"是唯一可行的方案。
- **未解决的冲突 —— 菜单能承载动态只读状态行吗？** 一种说法是 `ModOptionsMenu` **不**支持动态只读状态行；另一种说法是，把 `label` 或 `description` 做成**函数**就能得到只读状态，MOM 会在每次 ESC 菜单打开时重算它。**来源没有把这两者调和。** 两者都记录在案；请在你的版本上实测来确定。
- **未解决的冲突 —— `.patch_N` 描述符。** 在磁盘上，资源数组描述符持有的是相对偏移；归档一旦加载，同一个结构会被改写成绝对指针。来源把它称作一个"必然踩到"的坑；这两种读法没有被调和，所以无论按哪种读法都不要硬编码绝对运行时地址。
- **存在的数据表并不总在内存里，内存里的数据表也并不总在飞船上。** 先普查；Leveller 挂架表需要第二轮扫描。
- **唯一字节模式的命中不一定属于游戏** —— 它通常是你自己的模式串。注册每一个模式的自身地址。
- **数值字段不是序数下标。** 匹配记录自身的 type 字段，而不是"下标 N"。
- **受版本约束的取值。** MDL 1.4.2 / 2026-09-24 的基线取值和 `StratagemCooldown 2.1.5` 的 AOB 都绑定在那些版本上；来源没有说明它们在别处是否成立，本工作区里也没有任何东西能证实或推翻这一点。它们是比对基线，永远不是可移植的偏移。
- **已退役（2026-10-04）。** `_G.HD2Menu` / `HD2MenuQueue` 页面系统和 ESC 菜单面板设计都已退役；定位例程的不变式在上面被保留下来，但不要复活页面系统。第三方来源（`tools/ljd/`、`tools/filediver/`、`filediver-src/`）的标记保持原样。
