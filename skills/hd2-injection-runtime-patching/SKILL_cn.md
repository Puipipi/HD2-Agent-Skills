---
name: hd2-injection-runtime-patching
description: 从 LuaJIT addon 对一个正在运行的 Helldivers 2 进程打运行时补丁 —— 通过特征码与相对偏移定位一张表、安全地打开只读页、正确处理 LuaJIT 的数字、字符串与 FFI cast，并选择何时写入。当某个 mod 通过 FFI 读写 Helldivers 2 的进程内存时使用，或当一次写入静默地什么也没做、破坏了相邻数据、或被一次地图加载抹掉时使用。
---

# HD2 注入：在运行时对内存打补丁

[English](https://github.com/YC426/HD2-Agent-Skills/blob/main/skills/hd2-injection-runtime-patching/SKILL.md) / 简体中文

范围：在游戏的 LuaJIT VM 内部运行、并在运行时通过 FFI 读写 Helldivers 2 进程内存的 addon。
资源替换类 mod（替换 `data/` 资源）属于另一个类别，
本文不涉及。

以下所有内容均转载自本项目经机器验证的笔记。当某个值绑定于某一个 build
或某一个 mod 版本时，文中会说明 —— 永远不要把绑定于 build 的数字
提升为可移植的偏移。

---

## 来源与置信度 —— 先读这一节

**本文件没有任何内容在本仓库执行过或重新测量过。** 它是对一位贡献者工作笔记的重组,取自
[`junze0910/junze-hd2-lua-mod`](https://github.com/junze0910/junze-hd2-lua-mod)(MIT)。作者明确
说过:其中并非所有内容都测试过,有些还需要别人来测。所以下面每一节都当作**据来源报告、本仓库未独立
验证**。

在实际使用中这意味着:

| 下文使用的标记 | 含义 |
|---|---|
| *(作者已在实机验证)* | 来源称其在真实运行中观察到了。但仍然只是**一台机器、一个 build**。 |
| *(据来源报告)* | 来源如此陈述,但没有描述任何测试。未验证。 |
| *(受版本约束)* | 该值属于某一个游戏 build 或某一个模组版本,不可移植,请重新推导。 |
| *(未解决)* | 来源中两处陈述互相矛盾且未调和。两者都保留。 |

不要把受版本约束的数字当成可移植偏移,也不要把这里的任何内容当作既定事实引用。需要确定性就自己去
推导,并说明你是怎么推导的。

---


## 1. 获得一个安全的写入原语

**通过特征码定位，然后施加一个相对偏移。永远不要存储绝对地址。**
`generated_entities.dl_bin` 的内存副本与文件镜像逐字节完全一致，因此
离线计算出的相对偏移可以直接在运行时施加。绝对地址每次运行都不同
（ASLR）。*这能防止的失败：* 一个硬编码的绝对地址会静默地成功一次，然后在
重启后失败。如果一个方案依赖于一个固定的运行时地址，那么这个方案就是错的。

**磁盘与内存持有的指针并不相同。** 在 `.patch_N` 归档中，资源数组
描述符持有的是相对偏移；归档一旦被加载，同一结构就会被重写为
绝对指针。来源将此列为其格式中必须踩过的坑之一。

**只读的目标页会被打开、写入，然后再次关闭。** 使用 `VirtualProtect` 临时
打开该页、写入，然后恢复*原始*的保护属性。这
是首次尝试就在真机上通过的运行时补丁模板的一部分；让该页
保持可写不是一个选项。

**永远不要从外部进程读取游戏内存。** 反作弊是 **nProtect GameGuard**
（安装目录 `bin/GameGuard`）。不要用 Python / ctypes 配合 `OpenProcess` +
`ReadProcessMemory` —— 那是现有最容易被检测到的操作。只有游戏内的只读
addon 是可接受的。*Conflicts:* 这排除了整套 Cheat Engine 风格的附加并扫描
习惯；这不是一个偏好，而是一条边界。

**你无法静态分析随游戏发布的 `game.dll`。** `data/game/game.dll`（**15.5 MB**）在
磁盘上是加壳的。证据：前 8 个节名被抹零；那些节的熵为
**8.000**（饱和），而 `kernel32.dll` 为 **6.338**；VSize `0x210FA93` 对 RawSize
`0x850800`（内存镜像约为磁盘镜像的 4×）；`.winlice` 节的 RawSize =
**0**（仅在运行时填充；该节名逐字转载，来源未作解释）；
导入表 `.idata` 与导出表 `.edata` 各只有 **0x200** 字节；而最常见
的函数序言 `48 89 5C 24 08` 在该文件中命中 **0** 次，在
`kernel32.dll` 中命中 **4104** 次。后果：无法对磁盘文件做离线特征码扫描或反汇编（始终
0 命中）。验证是**在进程内**进行的 —— mod 解码并记录结果，以便与已知
值比对 —— 或用只读探针 dump 内存中的 `game.dll`。这也是
MDL 在每次启动时重新扫描特征码的原因：它根本没有可供离线查询的副本。*Conflicts:* 认为
可以把反汇编器指向已安装的 `game.dll` 这一常见信念是错的；对它做离线扫描
返回了零命中，并产生了不可用的偏移。

**也不要编辑磁盘上的数据表。** 安装目录中的 `data/game/generated_*.dl_bin` 文件
是加密的：熵为 **7.9998 bit/byte**，`LDLD` 在
45 MB 的文件中出现 **0** 次，且该文件通常只比它的明文镜像大 **48 bytes**。它们
无法被解码，也不属于 mod 流水线的一部分 —— 所有表相关的工作都走明文镜像。

---

## 2. 这个 VM 中的 FFI 正确性

**指针参数必须经过 `ffi.cast`。** 在期望指针的位置传入一个裸 Lua number 会
抛出 `cannot convert number to const void *`。只有真正的 FFI 会强制这一点，因此离线
测试桩必须严格检查类型才能捕获它 —— 一个宽松的 double 接受了 number，让指针 bug
溜了过去，结果它们反而在游戏里才暴露。

**获取一个 Lua 字符串自身的地址需要一次指向字符串的 cast**，并用 `pcall` 包裹，因为该 cast
可能失败：

```lua
tonumber(ffi.cast("uintptr_t", ffi.cast("const char *", pattern)))
```

这正是自命中跳过得以实现的原因 —— 没有它，扫描器会匹配到它自己的特征码数据，
而那些数据位于 Lua 堆中；于是扫描“成功”了，却除了它自己什么也没找到。

---

## 3. 会咬人的 LuaJIT 数字与字符串语义

**number 只携带 53 位；一个 64 位 ID 绝不能碰 number。** 把
`0x80F1A156D9FA1E36` 存进一个 Lua number 会得到 `0x80F1A156D9FA2000`，这会破坏搜索
特征码。任何大于 2^53 的 ID 都由十六进制字符对构建：

```lua
local function le_bytes_from_hex(hex)
  return (hex:gsub("%x%x", function(p) return string.char(tonumber(p, 16)) end)):reverse()
end
```

*失败：* 一个被破坏的 64 位特征码会静默地永不匹配。*Conflicts:* 这与把 64 位 ID 写成
Lua 十六进制字面量或 `tonumber('0x…')` 的通常习惯相矛盾。

**`table.concat` 把 number 渲染为十进制文本。** `table.concat({65,66})` 返回 `"6566"`，而不是
`"AB"`。因此，一个混装 number 与字符串的字节表会产生长度错误的字节，并在
写入时破坏相邻数据。构建字节载荷要靠纯字符串拼接。
*Conflicts:* 在一个表中混装 number 与字符串这一常见的字节表惯用法在这里是不安全的。

**Lua 不检查字段类型；永远不要用同一个字段名承载不同类型。** 在同一个表中先使用 `hits = {}`、
之后再使用 `hits = 0`，会让 `hits + 1` 抛出
`attempt to perform arithmetic on field 'hits'`。在观察到的情况中，第一次命中就中止了整轮
扫描，普查结果从未被刷出 —— 一整次侦察运行因为一个集合与一个
计数器之间的重名而丢失。

---

## 4. 何时写、写多频繁

### 4.1 决定一切的是窗口，不是速度

一张表在内存中，并不意味着消费它的那个列表尚未被构建。用
战略配备附加项实测：进入任务之后再写 `additional_stratagem` 可能已经太晚
—— 当前任务的列表已经固定，改动只在回到飞船后或
下一个任务中才出现。扫描速度只决定*地址何时被知道*；决定一次改动
是否生效的，是表加载之后、列表构建之前的那个窗口。加快扫描
不能替代找到那个窗口。*Conflicts:* 认为更早找到地址
就能让写入生效的假设是错的。

### 4.2 运行时补丁模板（一次就在真机上通过）

1. 通过特征码定位该表，并校验一个已知常量，例如 `size`。
2. 通过**唯一 ID** 找到目标记录；要求匹配唯一（多于一个 → 拒绝）。
3. 校验该记录内部的一个预期常量（例如 `SpawnPayloadSize == 2`）。
4. **写入之前把原始字节备份到磁盘。**
5. 检测该补丁是否已经应用（幂等），以免被写入两次。
6. 对于只读页，临时使用 `VirtualProtect`，并在之后恢复原始页保护。
7. **逐字段回读并校验** —— 而不只是“写入成功了”。
8. 每 **~5 秒**重新检查一次，如果被地图重载抹掉就重新施加。
9. 用 `_G.<ModName>` 作为单例守卫，对错误日志做速率限制，并在任何校验不匹配时
   记录日志并拒绝写入。

### 4.3 会把自己锁在门外的写入守卫

**一个只把 {current == target, current == original} 列入白名单的守卫会把自己的写入锁死。**
观察到的症状：对某个挂载槽的第一次写入成功，把它改成另一个物品会被
拒绝，而一个先是载体、后来变成附加项的机甲变得完全无法写入，
因为在第一次成功写入之后，`cur` 是上一个目标值，它不匹配任何一个分支。
按地址同时保存当前目标与原始值这**两者**，并把上一次写入的
值视为合法的来源：

```lua
local last = state.slots[address] and state.slots[address].item

if cur == le(want) then
  state.slots[address] = { item = want, orig = orig, who = who }
elseif force or want == orig or cur == le(other) or (last and cur == le(last)) then
  write(...)
  state.slots[address] = { item = want, orig = orig, who = who }
else
  refuse
end
```

`state.slots[address]` 保存 `item`（当前目标，用于识别下一次切换）与 `orig`
（原始值，用于在初始化期间恢复）。

**把原始值写回去必须始终绕过所有检查。** 2026-10-03 新增（guard dog）：
如果原始值本身被 `cur` 测试挡住，那么从旧版 mod 迁移过来的玩家会被
永久卡住。具体来说：`guard-dog-mg43` 已经写入了 **MG-43**，新 mod 的 `orig` =
**A32621E3BDE13379**，`cur` = MG-43，`last` = nil，因此 `cur` 既不是原始值也不是 `last`，
写入被拒绝 —— 连选择原始值都变得不可能。因此上面片段中有 `want == orig` 这个
条件：只要目标值等于原始值，就完全跳过检查、直接写入。
“把原始值写回去”永远不会比把一个未知值留在原处更糟。
非原始值的物品切换仍然受到保护。这是除 `force` 之外的第二道保障；
`exo_loadout` 与 `guard_dog_loadout` 都实现了它，guard-dog 的离线用例 **13** 固定了它
（内存中保存 MG-43，而 cfg 选择 AR-23P → 必须把原始值写回去）。*Conflicts:*
与广为流传的写入守卫惯用法（只把
{current == target, current == original} 列入白名单）直接矛盾 —— 而那正是这个损坏守卫的形状。

**初始化必须恢复原始默认值，而不是上一次的 cfg。** 复用常规的回写
路径（`apply_all('vanilla')`）会把退出时的配置留在内存中，因为当前值
既不匹配原始值也不匹配目标值，而守卫会静默拒绝。修复：一个 `vanilla_force` 模式 ——
`apply_all('vanilla', true)` —— 它只校验 `node` / `pad` / `recIdx`，并强制写入
原始值。初始化**不**读取 `ExoLoadout.cfg`；退出时的 cfg 是错误的
语义。把它整合为：

```
do_initialize()
  -> cancel Scanner memscan
  -> restore_strat()          -- 恢复原始 additional / use 值
  -> restore_arms_all()       -- 恢复所有被追踪的槽位
  -> apply_all('vanilla', true)
  -> reset_cfg()              -- 回到默认：patriot + none + original
  -> clear strat_addr / strat_hits / strat_pair / scanner state
  -> sync ModOptionsMenu
```

**附加项的默认机体是 `none`。** `CFG = { carry = 'patriot', extra = 'none', arms = {} }`。
新生成的 cfg 使用 `extra=none`，`reset_cfg()` 回到 `extra=none`，附加项的
`choice` 默认为 none，而自检必须接受 `extra='none'`。任何其他默认值都会让
全新安装一开始就已经是被修改过的状态。

### 4.4 附加战略配备写入：只有一个方向

对于携带机甲 A 加附加机甲 B：

| 记录 | 字段 | 动作 |
|---|---|---|
| A | `package+32` `additional_stratagem` | 写入 B 的战略配备 ID |
| A | `package-88` `use` | 写入 `2` |
| B | `package+32` `additional_stratagem` | 不要触碰 |
| B | `package-88` `use` | 写入 `2` |
| A/B | `package-64` / `package-60` cooldown | 不要触碰 |

只写入携带方那一条记录的单个 `additional_stratagem`；双向写入会造成
战略配备嵌套循环。写入之前，校验当前的 `+32` 是 `0` 还是已经是目标值 ——
否则拒绝。

### 4.5 发布纪律

先做只读侦察；写入前校验一个值的范围，写入后再回读；不匹配时拒绝并
记录日志；校验游戏版本（`exe`/`dll` SHA-256），不匹配时拒绝写入。主动
警告用户：在线时改变游戏行为会让客户端与队友不同，
并带有反作弊风险；同时明确说明这些是客户端本地改动，大多数
其他玩家看不到。所有改动都只存在于内存中，因此禁用该 mod 并执行 Purge
即可完全恢复游戏。

---

## 5. 在运行时读取与解读一张数据表

### 5.1 块格式与识别

一个 LDLD 块头是 `LDLD` + u32 version（= **1**）+ u32 type hash + u32 size。这正是
离线解析与内存内普查共同依赖的特征。

**实例数据的起始位置取决于文件族。** 对于 `generated_*_settings.dl_bin`，数据
从 magic **+40** 开始；对于 `generated_entities.dl_bin`，从 magic **+24** 开始。不要猜 —— 要用
内容验证：一条解码后的记录应当有合理的字段（count ≤ **8**，speed 在 **1~5000** 之间，
item hash 能在资源名列表中被解析出来）。单一硬编码的数据起始位置会把其中一个族的
表解码错。

**type hash 是 djb2，最后再减去 5381** —— 这就是你为某个类型名与
块头比对时所用的值：`r = 5381`；对每个字符执行 `r = (r * 33 + ord(c)) & 0xFFFFFFFF`；
返回 `(r - 5381) & 0xFFFFFFFF`。完整示例：`"HellpodRackComponentData"` → `0xA98BB156`。
`typelib_names.tsv` 中的每个名字都以这种方式映射到它的 LDLD 特征。

**资源名哈希是另一个函数：** `MurmurHash64A(name, seed=0)`。这两种哈希
看起来相似，但彼此无关；在需要资源名哈希的地方使用 type hash（或反过来）
会产生一连串 “not found”，且没有其他症状。

**相比手写的 struct，要更信任 typelib 生成的字段数据。** 由
typelib 生成的文件（那些带字段注释的）对当前 build 是可信的；社区手写的
Go struct 可能已经不再匹配。不确定时，读取 `typelib_all.json`，或直接读取
`dl_library.dl_typelib`。*Conflicts:* 这与把社区
struct 定义当作地面真值的常见做法相矛盾 —— 一个过期的 struct 把一次解码带上了错误路径。

### 5.2 并非每张表都是 LDLD 块

`StratagemSettings` **不是**一个 LDLD 块：它是一个 16 字节的容器，其成员是一个 ARRAY，
而真正的记录是 `StratagemInfo`，`size = 400`，偏移为 `+0` type、`+4` id、`+80` uses、
`+104` / `+108` cooldown float（success / fail）、`+152` / `+160` payload[2]、`+168` package、
`+176` icon、`+196` depends_on、`+200` additional_stratagem、`+204` max_in_loadout。先从 typelib
取得记录类型与字段偏移，再选择查找策略；LDLD 只适用于部分
表。*失败：* 假设每张数据表都是 LDLD 块，会让战略配备表
变得无法找到。

**围绕 `package` 字段写入。** 设 `c` = 某条记录的 `package` 字段地址（
来源把这些写成 `package±N` 而未定义参照帧；这里采用姊妹笔记的
定义）：`c+32` = `additional_stratagem`，`c-88` = `use`，`c-64` = `cooldown_duration_success`，
`c-60` = `cooldown_duration_fail`。同样的字段也存在于记录层级：`+200`
`additional_stratagem` 以及 400 B 的 `StratagemInfo` 记录上的 `+104`/`+108` 冷却。写入
目标位于 package 指针附近，而不是固定的记录偏移上。

**在使用公式之前，先测试记录是否构成连续数组。** 在记录连续、
步长为 `S`、且 `package` 字段位于 `+P` 时：`base = addr(pkg) - P - (id-1)*S`。如果若干已知
记录得出相同的 base，且它们的 icon 全部匹配，那它就是一个连续数组；否则不要
强行使用 `base + (ID-1)*S`。实测：**7** 个 `StratagemInfo` package 都被定位到了，但不存在共同的 base
—— 这些记录并不是按 ID 排序的连续 400 B 数组（更像是指针 / 分散
分配），因此退回到按 package 内容逐条定位记录。

**经由 `StratagemCooldown 2.1.5` AOB 路径的按 ID 记录查找。** 该路径读取
`0xB0` 字节的记录：`+0x00` id、`+0x04` hash、`+0x10` name string pointer、`+0x50` uses（int32，`-1` =
无限）、`+0x68` cooldown（float）、`+0xC8` AOB 自身访问的那个字段，对应
`additional_stratagem`。注意这是一个按 ID 的捷径，不是一份契约 —— 通过特征码读取的
内存内表，其可靠性只与它被发现时的那个 build 相当；当布局不再匹配时，任何实现都需要
回退路径（按内容）。

**按 ID 解锁一个战略配备需要三个条件，且必须同时成立**（v1.7 已在
真机上验证）：① `StratagemInfo +0xC0` bit0；② `+0x80` bit1（= 明文数据
表中的 `selectable`）；③ registry 记录 `+0x14 ∈ {2,4}`。早先认为 `+0x14` 不是 owned 位
的结论已被推翻。战略配备指针表是 `*(0x37CB600 + id*8)`。写入必须同时包含
`selectable` 位。*失败：* 双条件写入会让战略配备保持锁定状态；第三个
条件是通过把三者放在一起测试才找到的。

### 5.3 Rack 与补给记录

`HellpodRackComponent` 是 **568 B** = `RackAttach[8]`（每槽 **64 B**）加一个尾部；
`spawn_payload_size` 位于 `+0x22C`。AC-8 案例通过 LDLD +
type hash + 记录内相对偏移来定位 `HellpodRackComponentData`（即“内容锚点”方法）。Rack 编辑需要精确的
每槽步长与尾部字段位置。

一个补给 rack 的 **4** 个已填充槽位决定冷却时间（**30~150 s**）。一次完整的改动要写到
三处：rack 槽位的 `item` / `offset` / `rotation_offset`、战略配备在
`+0x68` 处的 `cooldown_success`，以及战略配备 ID **77** 的三个条件。*失败：* 只写
三处之一，会让游戏内的冷却与 rack 不一致。

### 5.4 在进程内验证一个解码器

当不存在可离线验证的机器码时（见 §1），唯一的地面真值是另一份
已经在这台机器上工作的实现：抄下某个已知可用 mod 从其日志中解码出的
数字，在你第一次成功运行时记录同样那十几个数字，然后逐项比对。全部
相等意味着解码器正确；有一处不同就能精确定位到那个出错的 `disp32`。

已知可用基线，由 **MDL 1.4.2** 在这台机器上解码得到（**2026-09-24 build**）：
`native menu state: MenuSystem +0x347ce38, open byte +2185, 36 screen types`；
`native tab: bar +1248, count +57448, labels +57320, text +8296, set_labels +0x17aac50,
set_arg +0x143c950, labels 0xd876b36e 0x78934e12 0x8c02bd80`；
`native font slots: font +0x3772268 atlas +0x3772ee8 material +0x37c5478`。

这些数字绑定于那一个 build —— 把它们当作比对基线，而**不是**可移植
偏移；游戏更新之后要重新推导它们。
