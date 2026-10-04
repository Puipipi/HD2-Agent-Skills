---
name: hd2-native-panel-input-lock
description: 在 Helldivers 2 中通过热键（F7）打开一个游戏内面板，解锁鼠标使其可以作为指针使用，并在面板打开期间阻止游戏接收键盘/鼠标输入——Windows raw input 注销、可选的 user32 窗口过程过滤、光标显示/裁剪的保存与恢复、客户区像素到 Gui 单位的换算、滚轮格数，以及关闭/失焦时的安全归还。当某个 mod 面板需要一个可用的光标、当点击穿透到面板背后的军械库、或当打字时镜头仍在转动时使用。
---

# HD2 原生面板：热键、鼠标解锁与输入封锁

> **置信度:** 读来的。没有执行任何代码;来源一节说明了哪些部分是 copyleft。

[English](https://github.com/YC426/HD2-Agent-Skills/blob/main/skills/hd2-native-panel-input-lock/SKILL.md) / 简体中文

取自 **Super Earth Armory Forge v6.2.1**（F7 面板）——其注释将此部分归功于
**SHODAN Stat Editor v1.4.1**——并与 Custom Armor Kit 更简单的指针处理做了交叉核对。
**在复制任何内容之前，请先阅读 §6（来源与许可）**；
其血统并不统一，其中一支属于 copyleft。

> 配套阅读：[`docs/hd2-mod-failure-catalog.md`](../../docs/hd2-mod-failure-catalog.md)
> —— §1 与 §8 正是输入路径写得如此防御性的原因（半吊子的输入夺取
> 比完全不夺取更糟）。

一句话概括问题：游戏的镜头与 UI *确实*会响应硬件按键和
鼠标，所以仅在其上绘制一个面板是不够的——你必须在面板打开期间
**把鼠标和键盘从游戏手中取走，然后再原样归还**。

---

## 1. 热键：聚焦状态下的沿检测，每次按下只触发一次

```lua
local function hotkey_pressed(name)
    local vk = VK[name]                                  -- 'F7' -> 0x76
    if not vk then return false end
    local down = input.key_down(vk)                      -- GetAsyncKeyState(vk) < 0
    local was  = keys_was[name]
    keys_was[name] = down
    local focused = input.focused()                      -- 前台窗口就是我们的进程
    if down and not was and name == hotkey() then
        PP.note(focused and 'presses' or 'unfocused')     -- 在丢弃一次非聚焦按下时说明
    end
    return down and not was and focused
end
```

- **用沿，而不是电平**（`down and not was`），并且要求**聚焦**，否则用户在
  另一个应用程序中按下 F7 时面板也会打开。
- `input.focused()` = `GetForegroundWindow()` → `GetWindowThreadProcessId` →
  与 `GetCurrentProcessId()` 比较。绝不要按标题匹配窗口：HD2 的标题
  包含 `™`，按标题子串查找会失败。
- 记录**被丢弃**（非聚焦）的按下。否则「F7 不管用」就无从归因。
- 从 mod 表中取得按键默认值并校验它（`^F%d%d?$` → 存在于 `VK` 中），这样
  手工编辑过的配置文件永远不会让面板变得无法打开。

```lua
panel_tick = function(now)
    if not input or not sr then return end
    if hotkey_pressed(hotkey()) then open_panel(not ui.open) end
    ...
end
```

## 2. 解锁鼠标——两个光标，都必须处理

存在**两个**光标：游戏自身的（`stingray.Window.show_cursor` /
`set_show_cursor` / `set_clip_cursor`）和 Win32 的（`ShowCursor` /
`ClipCursor`）。两者都要处理，并记住它们的状态，以便把鼠标归还回去。

```lua
local cursor = { taken = false }

local function window_fn(name)
    local f = sr.Window and rawget(sr.Window, name)
    return type(f) == 'function' and f or nil
end

local function engine_cursor_shown()
    local f = window_fn('show_cursor')
    if not f then return nil end
    local ok, shown = pcall(f)
    if ok and type(shown) == 'boolean' then return shown end
    return nil
end

local function take_cursor()
    if cursor.taken then return end
    cursor.taken = true
    local set_show, set_clip = window_fn('set_show_cursor'), window_fn('set_clip_cursor')
    cursor.was_shown = engine_cursor_shown()          -- 可能为 nil：未知
    cursor.engine = set_show ~= nil
    if cursor.engine then
        pcall(set_show, true)                         -- 让引擎显示它
        if set_clip then pcall(set_clip, false) end   -- 并停止把它裁剪到中心
    end
    cursor.shows = 0
    while input.show_cursor(true) < 0 and cursor.shows < 20 do cursor.shows = cursor.shows + 1 end
    cursor.shows = cursor.shows + 1
    cursor.clip = input.get_clip()                    -- 保存游戏的裁剪矩形
    input.set_clip(nil)                               -- 释放光标
end
```

**显示计数的陷阱。** `ShowCursor` 使用的是一个按线程计的计数器，而游戏可能已经
调用过它好几次。循环调用 `ShowCursor(true)` 直到它返回 `>= 0`，数出用掉了多少次
调用，然后**精确地**归还同样次数的 `ShowCursor(false)`。恢复
保存的裁剪矩形。如果游戏原本是显示光标的，就把它恢复成原来的样子：

```lua
local function release_cursor()
    if not cursor.taken then return end
    cursor.taken = false
    if cursor.engine and cursor.was_shown == false then
        local set_show, set_clip = window_fn('set_show_cursor'), window_fn('set_clip_cursor')
        pcall(set_show, false)
        if set_clip then pcall(set_clip, true) end
    end
    for _ = 1, cursor.shows or 0 do input.show_cursor(false) end
    if cursor.clip then input.set_clip(cursor.clip) end
end
```

**面板打开期间游戏会不断隐藏光标。** 它会在镜头/画面变化时调用自己的
`set_show_cursor(false)`，所以要每帧重新主张一次——而且要廉价：

```lua
local function keep_cursor()
    if not cursor.taken then return end
    if engine_cursor_shown() == false then
        local set_show, set_clip = window_fn('set_show_cursor'), window_fn('set_clip_cursor')
        if set_show then pcall(set_show, true) end
        if set_clip then pcall(set_clip, false) end
    end
end
```

每帧的调用顺序：`keep_cursor()` → `hold_input()` → 鼠标/点击处理。

### 指针在哪里——用面板绘制所用的单位表示

```lua
function self.cursor()                       -- 相对左上角的客户区像素 + 客户区尺寸
    local window = self.window()
    if not window then return nil end
    if user.GetCursorPos(ffi.cast('void*', point)) == 0
       or user.ScreenToClient(window, ffi.cast('void*', point)) == 0
       or user.GetClientRect(window, ffi.cast('void*', rect)) == 0 then return nil end
    return point[0], point[1], rect[2] - rect[0], rect[3] - rect[1]
end

-- 调用方：像素 -> Gui 单位（Gui 原点在左下角，y 轴向上）
local x, y, cw, ch = input.cursor()
if not x or cw <= 0 or ch <= 0 then return end
local width, height = sr.Gui.resolution()
local sx, sy = x * width / cw, y * height / ch       -- 屏幕像素，原点在左上角
local gui_y  = height - sy                            -- 用于命中测试 / 绘制的 Gui y
```

- 拒绝 `[0,cw) x [0,ch)` 之外的任何值，并拒绝为零的客户区尺寸。
- 引擎的 `Mouse.button` 在菜单状态下不可靠——改从
  Windows 读取按键，并遵循交换按键的系统设置：
  ```lua
  function self.mouse_left()
      local swapped = user.GetSystemMetrics(23) ~= 0          -- SM_SWAPBUTTON
      return user.GetAsyncKeyState(swapped and 0x02 or 0x01) < 0
  end
  ```
- 在**按下沿**点击，在**同一命中区域上释放时**触发（`armed`），
  这正是防止拖拽同时点击下方按钮的原因。

## 3. 阻止游戏接收输入

游戏把**鼠标移动**当作 Windows 的 **raw input** 读取，把**按键、鼠标按钮和
滚轮**当作**窗口消息**读取。两种机制配合使用：

### (a) 取走 raw input 注册（移动 + 镜头）

```lua
PP.gi = { state = 'not yet', saved = nil, next_check = 0 }

function PP.hold_input(now)
    local G = PP.gi
    if not PP.block_on() or G.broken or not (input.raw_list and input.raw_register) then return end
    if not input.focused() then return PP.give_input() end     -- 非聚焦：把输入还给游戏
    local hk = VK[hotkey()]
    if hk and input.key_down(hk) then return end               -- 先让面板键「松开」
    -- ... 只安装一次窗口过滤（见 (b)） ...
    if now < G.next_check then return end
    G.next_check = now + 0.5                                   -- 每秒重新检查两次
    local take, other = {}, false
    for _, d in ipairs(input.raw_list()) do
        if d.page == 1 and (d.usage == 2 or d.usage == 6) then  -- 鼠标 (2) 与键盘 (6)
            if input.raw_ours(d) then take[#take + 1] = d else other = true end
        end
    end
    if other then G.other = true end
    if #take == 0 then
        if not G.saved then
            G.state = other and 'raw input on another thread: left alone' or 'game has no raw input'
        end
        return
    end
    local remove = {}
    for _, d in ipairs(take) do remove[#remove + 1] = { page = 1, usage = d.usage, flags = 0x1, target = nil } end
    if input.raw_register(remove) then                             -- flags 0x1 = 移除
        G.saved = G.saved or {}
        for _, d in ipairs(take) do G.saved[d.usage] = d end       -- 记住最新的注册
        G.state = 'held'
    else
        G.state, G.broken = 'could not take it', true
        log("panel: could not take the game's raw input; it keeps it")
    end
end
```

由此提炼出的规则，每一条都是关键：

- **枚举，不要猜。** 先用 `GetRegisteredRawInputDevices(nil, &count, size)`
  取得数量，加上余量，再读取列表。设备是 `{page, usage, flags,
  target}`、大小为 `RID_DEVICE_INFO` 的记录；用 `void*` 转换可以避免与同一
  Lua 状态中另一个 mod 自己声明的结构体冲突。
- **只碰窗口属于本线程的注册**：
  ```lua
  function self.raw_ours(dev)
      if dev.target == nil then return true end
      return user.GetWindowThreadProcessId(dev.target, nil) == kernel.GetCurrentThreadId()
  end
  ```
  归还另一个线程的注册可能失败，并**让游戏失去鼠标**。
- **每 0.5 秒重新检查**——游戏会在画面切换时重新注册它的设备。
- **保留游戏最新的 flags**，而不是第一次快照，这样归还才是忠实的。
- `other` = 另一个 mod/线程拥有 raw input：不要去动它，并在日志中说明。

### (b) 用窗口过程过滤丢弃按键和鼠标按钮

移除 raw input 并不能阻止窗口消息。安装一个极小的窗口过程钩子
（`SetWindowLongPtrW(window, -4 /* GWLP_WNDPROC */, entry)`），它把一切都转发给
`CallWindowProcW`，除了面板自己拥有的那些按下：

```lua
-- build_input()：钩子的机器码是一个小的字节表加一个数据槽
-- {[0]=enabled,[1]=wheel notches,[2]=keys dropped,[3]=buttons dropped,[4]=held buttons}
local function filter_install(window)
    if window == nil then return nil, 'no game window' end
    local current = user.GetWindowLongPtrW(window, -4)            -- GWLP_WNDPROC
    local call = kernel.GetProcAddress(kernel.GetModuleHandleA('user32.dll'), 'CallWindowProcW')
    local block = kernel.VirtualAlloc(nil, 4096, 0x3000, 0x40)    -- commit+reserve, RWX
    if call == nil or block == nil or current == 0 then return nil, 'no memory for it' end
    -- 写入：原始 wndproc、CallWindowProcW、消息表、机器码，然后
    -- SetWindowLongPtrW(window, -4, entry) 以及 FlushInstructionCache
end
```

- 记录安装时已经按住的鼠标按钮，这样释放消息永远不会被
  吞掉（数据槽中的 `held` 位掩码）。释放一个游戏从未看到
  被按下的按钮，就是卡键 bug。
- **数据槽约定**（机器码与 Lua 侧达成的共识）：一个整数
  数组位于块的开头，`u[0]` = 启用标志，`u[1..3]` = 滚轮格数 / 丢弃的按键数
  / 丢弃的点击数计数器，`u[8]`（字节偏移 32）= 安装时初始化的按住按钮位掩码。
  代码入口点是 `block + 64`，所以头部携带原始
  窗口过程和 `CallWindowProcW`，函数体则附加在其后。
- **绝不要移除过滤器。** 另一个 mod 可能把它的过程链在
  你的后面；改为翻转共享数据槽中的启用标志（`filter_set(on)`）。
- 过滤器还会**统计滚轮格数**——面板需要它们，否则它们
  会随游戏其余输入一起丢失：
  ```lua
  function PP.filter_wheel()
      local G = PP.gi
      if not G.filtering then return nil end
      local total = input.filter_wheel()
      local turned = total - (G.wheel_seen or total)
      G.wheel_seen = total
      G.wheel_rest = (G.wheel_rest or 0) + turned
      local n = G.wheel_rest >= 0 and math.floor(G.wheel_rest / 120)
                                 or -math.floor(-G.wheel_rest / 120)   -- WHEEL_DELTA
      G.wheel_rest = G.wheel_rest - n * 120
      return n
  end
  ```
- 面板通过 `GetAsyncKeyState` / `GetCursorPos` 读取自己的输入，过滤器
  和 raw input 移除都**不会**影响它们。

### (c) 把所有东西都还回去——用一个不会让游戏失声的兜底方案

```lua
function PP.give_input()
    local G = PP.gi
    if G.filtering then pcall(input.filter_set, false); G.filtering = false end
    G.next_check = 0
    if not G.saved then return end
    local list = {}
    for _, d in pairs(G.saved) do list[#list + 1] = d end
    table.sort(list, function(a, b) return a.usage < b.usage end)
    G.saved = nil
    if input.raw_register(list) then G.state = 'given back'; return end
    -- 绝不让游戏失去鼠标和键盘：再试一次，不带窗口
    local plain = {}
    for _, d in ipairs(list) do
        local f = tonumber(d.flags) or 0
        for _, m in ipairs({ 0x100, 0x1000, 0x2000 }) do   -- INPUTSINK、EXINPUTSINK、DEVNOTIFY 需要窗口
            if math.floor(f / m) % 2 == 1 then f = f - m end
        end
        plain[#plain + 1] = { page = 1, usage = d.usage, flags = f, target = nil }
    end
    local ok = input.raw_register(plain)
    if not ok then for _, d in ipairs(plain) do d.flags = 0 end; ok = input.raw_register(plain) end
    G.state, G.broken = 'broken', true                     -- 本次会话剩余时间内关闭封锁
    log('panel: could not give the game its raw input back as it was; registered it again without a window (' ..
        tostring(ok) .. '); game input blocking is off for this session')
end
```

在以下时机归还输入：面板**关闭**时、游戏窗口**失去焦点**时，或封锁路径的
任何一步**抛出异常**时。在一次失败之后就把整个机制标记为 `broken` 并停止
尝试——半吊子的输入夺取远比完全不夺取糟糕。

让它可退出（在面板自己的配置文件中设置 `block_input = off`，并在
Keys 标签页中呈现），并记录一行描述，这样问题报告就能说明发生了什么：

```
game input while open: blocked (held); dropped: 12 key presses, 3 clicks; raw input now: mouse, keyboard
```

## 4. 行之有效的每帧顺序

```lua
local function panel_frame(now)
    pcall(keep_cursor)                                   -- 1. 重新主张光标
    local held, why = pcall(PP.hold_input, now)          -- 2. 获取/刷新输入所有权
    if not held then
        PP.gi.broken = true
        log('panel: game input blocking off for this session: ' .. tostring(why))
        pcall(PP.give_input)
    end
    -- 3. 当 world 集合变化时重新解析绘制世界（军械库会增删 world）
    local main, worlds = sr.Application.main_world(), sr.Application.worlds() or {}
    if not same_worlds(worlds, ui.worlds) or main ~= ui.main then
        ui.worlds, ui.main = worlds, main                -- 重建保留式 GUI
    end
    -- 4. 光标 -> 悬停 -> 按下沿 -> 动作；5. 手柄
end
```

- **在 tick 中用 `pcall` 包裹整个帧**，统计连续错误数，在连续约 5 次之后关闭
  面板并清理 GUI。一个坏的帧绝不能卡死游戏。
- 仅在 `input.focused()` 时接受输入。

## 5. 手柄（可选，但成本很低，而且能摆脱对鼠标的依赖）

通过 `XInputGetState` 使用 Sony 风格手柄（依次尝试 `xinput1_4`、`xinput1_3`、`xinput9_1_0`），Back +
Start 切换面板，D-pad/左摇杆移动焦点框，A 按下，B 返回，
LB/RB 切换标签页，右摇杆滚动。两个细节：

- **很少探测空槽位**（每 60 帧探测一个槽位）——询问一个空槽位很慢。
- **鼠标一旦移动超过约 2 px 就重新接管**：丢弃焦点框
  并递增 `ui.version` 计数器，使面板重绘。

## 6. 来源与许可——复制代码之前请先阅读

本技能描述的是一项技术；其中的代码是为本文档编写的。这一
区分是刻意的，因为参考实现的血统**并不**统一，其中一支属于 copyleft：

| 部分 | 来源 | 状态 |
|---|---|---|
| 光标的取用 / 保持 / 释放（`ShowCursor` / `ClipCursor` / `sr.Window.set_*_cursor`） | **改编自 SHODAN Stat Editor**——它自己的头部说明如此 | **GPL-3.0** |
| 窗口消息过滤的机器码 + 构建它的参数块 | **同一份 SHODAN 代码**，在两个 mod 中逐字节相同（已验证） | **GPL-3.0** |
| 通过 `GetAsyncKeyState` + `SM_SWAPBUTTON` 实现的 `mouse_left` | Armory Forge 自有——SHODAN 中不存在 | Armory Forge |
| raw input 注销 / 归还、`mouse()` / 命中测试 / 点击武装、手柄支持 | Armory Forge 自有——SHODAN 中不存在 | Armory Forge |
| `bd` / `sd` / `bl` / `filters[].u` 数据槽约定 | Armory Forge 自有 | Armory Forge |

**陷阱：** Armory Forge 的 `CREDITS.txt`（以及它的 README）把 SHODAN Stat Editor
v1.4.1 描述为*「public domain / Unlicense」*。而该仓库本身是 **GPL-3.0**——
`LICENSE` 文件和 GitHub 的许可证元数据都这样表明。2026-10-04 验证：

```
GET https://api.github.com/repos/SHODAN-HORAI/SHODAN-Stat-Editor
  license: { "key": "gpl-3.0", "spdx_id": "GPL-3.0" }
GET https://raw.githubusercontent.com/SHODAN-HORAI/SHODAN-Stat-Editor/main/LICENSE
  → "GNU GENERAL PUBLIC LICENSE / Version 3, 29 June 2007"
```

这个 mod 注释是错的，所以**不要把「mod 自称 public domain」当作许可
授予**。一个可公开下载的 mod 与一个以宽松许可授权的代码并不等同，而把
GPL-3.0 文件复制进一个带有不同许可的仓库（本仓库是 MIT），
也不是 mod 作者能够授权的——只有版权持有者可以。

实际后果：

- **你想在自己的 mod 中使用它？** 可以，而且最简单：保留对
  SHODAN 的署名，并把你的 mod 以 GPL-3.0（或 GPL 兼容许可）授权。在此之上
  不需要 Armory Forge 作者的额外许可。
- **把 GPL-3.0 的字节复制进一个宽松许可的仓库？** 不推荐。
  上面的过滤字节正是这种情况。此处其余内容都是这项技术加上
  本文档自己的代码，这也是字节表被刻意省略的原因。
- **在这里做独立的重新实现确实很容易。** Windows ABI 事实不受
  版权保护：`RID_DEVICE_INFO` 大小的 `{page, usage, flags, target}` 布局、
  页 `0x01` 上的 `RIM_TYPEMOUSE = 0` / `RIM_TYPEKEYBOARD = 1` usage 值、`flags = 0x1`
  移除一个注册、`GWLP_WNDPROC = -4` 索引、`CallWindowProcW` 链式调用，以及
  `WHEEL_DELTA = 120` 累加器。根据这些事实实现同样的槽位约定
  以及 §3 中的安全不变量，你就能得到相同的行为而不带那份血统。

如果你特别想要那两个字节表（`FILTER_TABLE`、`FILTER_CODE`），请从
GPL-3.0 源码获取，并同时注明该许可——它们并未在此处重现。

## 证据 / 来源

- `outputs/validated-2026-10-04/hud-compatibility/sources/installed-Super-Earth-Armory-Forge-v6.2.1-0-0.lua`
  —— `build_input()`（L2874-3075）、`PP.hold_input`/`PP.give_input`（L5330-5400）、
  `hotkey_pressed`（L5938-5947）、`mouse()`（L5452-5521）、光标取用/保持/释放
  （L5675-5727）、`panel_frame`（L5745+）、`panel_tick`（L5949-6001）。
  L5267-5279 处的头部注释说明了 raw input 与窗口消息的划分；面板
  来源说明在 L2822-2831。该仓库中的 `CREDITS.txt` 正是关于 SHODAN Stat Editor 的
  （不正确）「public domain」说法出现的地方——见 §6。
- `mods/custom-armor-kit/work/standalone/multi_perk.lua` —— 最小版本：
  `sample_input`（L1791-1810）、`panel_drag`（L1761-1787）。注意它自己的发现：
  *「引擎的 Mouse.button 在菜单状态下报告不可靠，这让军械库中的点击感觉
  像失效了」*——因此使用 `GetAsyncKeyState(0x01)`。
- `mods/custom-armor-kit/work/standalone/test_armor_controls.py` —— 离线拖拽/钳制测试。

## 代价高昂的易踩的坑

| 症状 | 原因 / 修复 |
|---|---|
| 面板打开时镜头仍在转动 | 只取走了 raw input 注册；窗口消息形式的滚轮/按键仍会到达，或者你只取走了 mouse(2)/keyboard(6) 中的一个。 |
| 按键和点击仍能到达面板背后的军械库 | 移除 raw input 并不能阻止窗口消息——你需要 `GWLP_WNDPROC` 过滤器。 |
| 在菜单中点击感觉像失效了 | 从 `sr.Mouse.button` 读取按键。改用 `GetAsyncKeyState`（+ `SM_SWAPBUTTON`）。 |
| 拖拽之后仍然触发了点击 | 没有 `armed` 区域 / 在同一区域上释放时触发的逻辑。 |
| 光标可见但冻结在屏幕边缘 | 游戏重新隐藏或重新裁剪了它；每帧调用 `keep_cursor()`，并清除 `ClipCursor`。 |
| 关闭时光标又不可见，或者游戏有*两个*光标 | `ShowCursor` 是按线程计的计数器。取用时数出调用次数，归还同样的次数；恢复保存的裁剪矩形。 |
| 关闭后游戏失去鼠标 | 归还时使用了需要窗口的 flags（`INPUTSINK`/`EXINPUTSINK`/`DEVNOTIFY`），或者恢复了另一个线程的注册。去掉这些 flags，用不带窗口的方式重试，然后标记为 broken 并停止。 |
| 在另一个应用中按下 F7 时面板也打开 | 沿检测上没有前台窗口检查。 |
| 打开面板后移动/瞄准卡住 | 安装过滤器时按住的一个按钮被吞掉了；初始化按住位掩码。 |
| 面板中滚轮没有作用 | 滚轮是窗口消息；在输入被持有时，统计过滤器中的格数是唯一来源。 |
