---
name: hd2-in-game-panel
description: 仅使用引擎的 Gui.rect 原语在《Helldivers 2》里绘制一个可点击的 mod 面板 —— 保留式屏幕 GUI 生命周期、分级建立、z 图层与原生屏幕失效、区域命中、带位置保存的面板拖拽，以及 4x5 点阵字体（外加打包的 CJK 位图），使文本不需要引擎字体或材质。适用于构建或修复游戏内 mod UI，尤其是在 Gui.text / 材质不可用或会让游戏崩溃的时候。
---

# HD2 游戏内面板（纯 rect、保留式 GUI）

> **置信度:** 来自自定义护甲模组的源码与日志(读来的);本仓库未重建或运行。

[English](https://github.com/YC426/HD2-Agent-Skills/blob/main/skills/hd2-in-game-panel/SKILL.md) / 简体中文

一个能正常工作的游戏内面板，**没有引擎字体、没有材质、没有 Gui.text** —— 每一个像素，包括中文字符，都是一个 `Gui.rect`。来源：`Custom Armor Kit 2.5.10`（`mods/custom-armor-kit/work/standalone/multi_perk.lua`）。

**为什么是这种形态：** 在引擎构建完它的字体/材质库之前调用 `World.create_screen_gui`，会在**原生**层面出错 —— `pcall` 不抓原生崩溃。证据：日志停在 `building the panel`，进程每隔几秒抛出 `ntdll 0xc0000026`，帧回调一直是死的。rect 不带有这种依赖。

> 配套阅读：[`docs/hd2-mod-failure-catalog.md`](../../docs/hd2-mod-failure-catalog.md)
> —— §1（`pcall` 抓不到的原生崩溃）、§2（引擎构建时机）和 §3（保留式面板变不可见的三个
> 原因），正是本技能围绕其塑形的失败模式。

---

## 1. 硬性前置条件（四条全部满足，否则整帧延后）

```lua
local function ui_frame(conf_data, frames)
    if not M.ship_ok then return end                  -- 飞船守卫 / 原生屏幕守卫
    if not M.ship_world then return end               -- world 已解析（约第 600 帧）
    local sr = rawget(_G, 'stingray')
    if type(sr) ~= 'table' or type(sr.Gui) ~= 'table' then return end
    if not (M.ui_font and M.ui_material) then return end
    local okr, rw, rh = pcall(sr.Gui.resolution)
    if not okr or rw < 640 or rh < 480 then return end
    ...
end
```

- 在飞船 world 存在之前，永远不要调用 `create_screen_gui`。有一次面板在错误的时机被启用，
  结果面板自身的创建杀死了帧回调。
- **每一帧**都要重新检查 `stingray.Gui` —— 在某些状态下它并不存在。
- `Gui.resolution()` 是唯一有权威的布局依据；使用之前先校验数值是否合理。

## 2. 分级建立 —— 每步一个引擎里程碑，并记录日志

不要在一次调用里做“创建 + 绑定 + 文本 + 绘制”。每一步都返回 `ok, why`，阶梯只在成功时前进，
因此一次失败会点明出错的正是哪个引擎调用：

```lua
local LNAMES = {'create gui','bind material','dance (off)','dance (off)','dance (off)',
                'draw panel','text (off)','finalize'}

if n == 1 then
    local okg, gui = pcall(sr.World.create_screen_gui, PANEL.world, 'scale', 1, 1)
    if not okg or gui == nil then return false, 'create: ' .. tostring(gui) end
    PANEL.gui = gui
    PANEL.draw_guis = {{world = PANEL.world, gui = gui}}
    return true
end
if not PANEL.gui then return false, 'gui lost before step ' .. n end
if n == 2 then
    -- 绑定只证明该 id 能解析；ink 是有意不使用的
    local oki, ink = pcall(G.material, PANEL.gui, material_id64)
    if not oki then return false, 'G.material error: ' .. tostring(ink) end
    return true
end
if n == 6 then panel_draw(conf_data, rw, rh) return true end
```

第 3-5 步和第 7 步是 `return true, 'skipped (...)'` —— 即便 id64 已经验证过，材质参数那一套 dance
仍然在原生层面出错。**设计上就跳过的步骤，在日志里也必须诚实**；不要悄悄把它丢掉。

## 3. 保留式 GUI：必须刻意让它失效

引擎会一直保留某个屏幕 GUI 的图元，直到那个 GUI 被重建。所以面板**不是**每帧重建；
由一个签名决定保留的那份副本是否已经过期：

```lua
if PANEL.sig ~= sig then
    PANEL.sig = sig
    PANEL.gui = nil                 -- 强制下一帧重建
    PANEL.ladder, PANEL.ladder_done = 1, false
    panel_clear()                   -- 销毁本面板拥有的每一个 GUI
end
```

在以下情况使其失效：面板打开/关闭、语言改变、绘制图层改变（配置里的 `layer=`）、
原生屏幕改变、分辨率改变，以及任何会改变布局的状态。

两个陷阱都会造成“点击毫无反应”：

- **图层。** 保留式 GUI 会按它原来的图层重绘，所以 `layer=` 改变时*必须*重建。
- **盖在你上面的原生屏幕。** 军械库会绘制它自己的全屏图层，而在军械库打开之前建好的面板
  会永远留在它**下面**。盯住原生屏幕 id，一旦改变就重建：
  ```lua
  local screen = (M.gate_info and M.gate_info.ui and M.gate_info.ui.screen) or 0
  if screen ~= M.ui_screen then
      M.ui_screen = screen
      if PANEL.armed and M.ship_ok then PANEL.sig = nil end   -- 重绘，不要只是记日志
  end
  ```

## 4. 拆除 —— `panel_clear()` 必须彻底

```lua
local function panel_clear()
    local sr = rawget(_G, 'stingray')
    if sr then
        if PANEL.draw_guis then
            for _, entry in ipairs(PANEL.draw_guis) do
                pcall(sr.World.destroy_gui, entry.world, entry.gui)   -- 每一个 world 副本
            end
        elseif PANEL.gui and PANEL.world then
            pcall(sr.World.destroy_gui, PANEL.world, PANEL.gui)
        end
    end
    PANEL.gui, PANEL.draw_guis, PANEL.sig = nil, nil, nil
    PANEL.regions, PANEL.font, PANEL.material, PANEL.ink = {}, nil, nil, nil
    PANEL.bounds, PANEL.move_x, PANEL.move_y, PANEL.drag = nil, nil, nil, nil
    PANEL.ladder_done = false
    PANEL.ladder, PANEL.lnext, PANEL.lfail = 1, 0, 0
end
```

- **销毁你在每一个 world 里创建的每一个 GUI。** 军械库那条路径会构建一份副本。
- 重置阶梯，这样从菜单返回时会重新跑一遍分级建立。
- 永远不要在你并不拥有的 world 里分配 GUI —— 那次实验导致了原生崩溃。
- 离线测试：统计两帧前后的存活 GUI 对象数并断言恰好是一个，然后 `panel_clear()` 并断言
  集合为空（`mods/custom-armor-kit/work/standalone/test_armor_ui.py` 用 `lupa` 做了这件事）。

## 5. 几何与布局

```lua
local scale = math.min(rw / 1920, rh / 1080)          -- 全局只有一个缩放系数
local pw    = 560 * scale                             -- 面板宽度
local px    = rw - pw - 20 * scale                    -- 停靠在右下角
local rowh  = 54 * scale; local titleh = 78 * scale; local hint = 30 * scale
local content = titleh + hint + #cards * rowh + rowh   -- 高度由内容推导
local x, y = px, rh - 94 * scale - content
if y < 10 then y = 10 end
```

- **Gui 的原点在左下角。** 所谓“标题在顶部”，其实位于 `y + h - titleh`。
  一个字形位图的第 1 行是它的**顶部**，所以它落在最高的 y 上：
  `rect(x + col*zcell, y + (bm.h - r)*zcell, ...)` —— 把这个搞反，文字就会镜像。
- 每种模式的高度都由内容推导；并夹取到视口之内。
- 保存 `PANEL.bounds = {x=, y=, w=, h=, title=}` —— 命中测试和拖拽都需要它。

### 在不重建面板的前提下移动它

对保留式 GUI 使用 `Gui.move`，并从目标位置计算出一个**增量**：

```lua
local function panel_offset(sr, rw, rh)
    local b = PANEL.bounds
    if not b then return 0, 0 end
    local s = math.min(rw / 1920, rh / 1080)
    local x, top = b.x, b.y + b.h
    if PANEL.place then x, top = PANEL.place.x * s, PANEL.place.top * s end
    x   = math.max(0, math.min(rw - b.w, x))
    top = math.max(b.h, math.min(rh, top))            -- 让整个面板留在视野内
    local dx, dy = x - b.x, top - b.y - b.h
    if PANEL.gui and (dx ~= PANEL.move_x or dy ~= PANEL.move_y) then
        local ok, why = pcall(sr.Gui.move, PANEL.gui, dx, dy)
        if not ok then return PANEL.move_x or 0, PANEL.move_y or 0 end
        PANEL.move_x, PANEL.move_y = dx, dy
    end
    return dx, dy
end
```

- **增量没变时永远不要调用 move** —— 静止的面板必须执行零次原生调用（在测试里断言这一点）。
- 拖拽从**标题条**（`y >= b.y + b.h - b.title`）开始，跟随光标直到按键释放；释放时把 `x/top`
  持久化到 `panel_position.txt`，并保持绘制位置不变。
- 拖拽过程中也要夹取，不能只在加载时夹取。

## 6. 点击处理：针对本帧构建的区域做按下沿判定

`panel_draw` 每次绘制都会从头重建 `PANEL.regions`，而输入处理会消费它们 ——
因此命中测试始终与**本**帧屏幕上的内容一致。

```lua
PANEL.regions = {}
-- ... 绘制过程中 ...
PANEL.regions[#PANEL.regions+1] = {x=bx, y=by, w=bw, h=bh, action='save', index=i}

-- ... 在输入处理中 ...
if not dragging and input and input.down and not PANEL.was_down then
    for _, r in ipairs(PANEL.regions) do
        if input.x >= r.x and input.x < r.x + r.w
           and input.y >= r.y and input.y < r.y + r.h then
            -- 按 r.action / r.index 分发
        end
    end
end
```

- **只取按下沿**（`down and not PANEL.was_down`）—— 按住不重复触发，释放时也不会有幽灵点击。
- 一次拖拽会吞掉这次点击；先检查 `dragging`。
- 每一个输入采样都走 `pcall`；一次采样出错绝不能杀死这一帧。
- 尽量让同一个动作也能从**非鼠标**路径触达（armor kit 也支持用数字键分发到行），
  这样即使遇到拒绝显示指针的场景，面板依然能用。

## 7. 没有引擎文本 API 时的文本

### 4x5 ASCII 点阵字体，用唯一被验证过的原语绘制

```lua
local GLYPHS = {}
local defs = { A='0110 1001 1111 1001 1001', B='1110 1001 1110 1001 1110', ... }
for ch, def in pairs(defs) do
    local rows = {}
    for row in def:gmatch('%d+') do rows[#rows+1] = row end
    GLYPHS[ch] = rows
end

local function asciirun(x, y, s, c, cell)
    local cx = x
    for i = 1, #s do
        local g = GLYPHS[s:sub(i,i)]
        if g then
            for r = 1, 5 do
                local row = g[r]
                for col = 1, 4 do
                    if row:sub(col,col) == '1' then
                        rect(cx + (col-1)*cell, y + (5-r)*cell, cell, cell, c)
                    end
                end
            end
        end
        cx = cx + 5*cell
    end
    return cx
end
```

- 单元格尺寸要与 CJK 字形高度匹配，让中英混排读起来整齐：
  `acell = max(2, floor((16*zcell)/5 + 0.5))`。
- 把所有 ASCII 都转成大写 —— 然后在测试里断言每个标签用到的**每一个**字符都存在于
  `GLYPHS` 中。缺失的字形会静默地什么都不渲染。

### 打包的 CJK 位图

把 CJK 以**打包字符串**的形式发布，而不是一个巨大的 Lua 表构造器：LuaJIT 每个函数
65535 条字节码指令的上限会把大构造器变成 `function too long`，而加载器会**静默跳过整个
mod**。在首次绘制时惰性解析：

```lua
-- ZH_PACK：每个字形一行，"hexkey,w,h,row.row.row..."，其中各行是十六进制半字节
local function zh_init()
    if zh_inited then return end
    zh_inited = true
    local hc = {}
    for b = 0, 255 do hc[string.format('%02x', b)] = string.char(b) end
    for line in ZH_PACK:gmatch('[^\n]+') do
        local kh, w, h, rows = line:match('^(%x+),(%d+),(%d+),(.+)$')
        if kh then
            local key = {}
            for i = 1, #kh, 2 do key[#key+1] = hc[kh:sub(i,i+1)] end
            local r = {}
            for row in rows:gmatch('[^.]+') do r[#r+1] = row end
            ZH[table.concat(key)] = {w = tonumber(w), h = tonumber(h), r = r}
        end
    end
end
```

- 先按**短语**索引字形（打包的短语胜过逐字符打包），然后回退到逐字符，最后回退到空推进。
- 遍历 UTF-8 字符串：由首字节推导长度
  （`>=0xF0 → 4`、`>=0xE0 → 3`、`>=0xC0 → 2`，否则为 1）。不要假定是 3。
- 字符不在打包字体里时只记**一次**日志（`M.zh_miss`）—— 一行，而不是每帧一行。

### 一个能处理全部三种情况的文本入口

```lua
local function txt(x, y, s, c, acell_)
    if type(s) == 'table' then                 -- 预打包位图
        if s.r then return zhdraw(x, y, s, c) end
        return x
    end
    local bm = ZH[s]
    if bm then return zhdraw(x, y, s, c) end   -- 整个打包短语
    s = tostring(s):upper()
    if s:find('[\128-\255]') then              -- 混排：拆成 CJK / ASCII 段
        ...
    end
    return asciirun(x, y, s, c, acell_ or acell)
end
```

混排字符串是最容易踩的 bug：`L('[ 打开 ]')` 和 `'已选 3'` 以前就在 ASCII 回退里丢掉了
它们的中文那一半。按 `byte(i) >= 128` 把字符串切成最大的连续段，每一段用正确的路径渲染，
并把 x 光标向前带。

### 中文位图缩放

```lua
local zcell = math.max(1, math.floor(1.15 * scale + 0.5))     -- 每个字体像素 1 个单位
```
`zhdraw(x, y, bm, c)` 会遍历 `bm.r`，通过 `W8 = {8,4,2,1}` 位测试把每个十六进制半字节展开成
4 个像素，并返回 `x + (bm.w + 2) * zcell`，好让下一个字形正确推进。

## 8. 让隐藏面板可诊断的日志

每次状态变化记一行，受阻时每 N 帧再加一次心跳 —— 绝不要每帧都记：

```lua
local changed = (M.gate_phase ~= phase) or (M.gate_last_reason ~= reason)
if changed or frames - M.gate_last_frame >= 600 then
    log('ui gate ' .. phase .. ': ' .. tostring(reason) .. ' frame=' .. frames
        .. ' world=' .. tostring(world) .. ...)
end
```

至少要记录：GUI 是否存在、`Gui.is_visible`、阶梯步号、分辨率、world 身份（用一个弱键的
序号映射 —— 对每个 world 来说 `tostring(world)` 都是 `[World]`），以及按名称给出的阻塞
原因。没有原因的 “blocked” 会白白耗掉几个小时。

## 9. 离线测试夹具（不启动游戏也能验证 LuaJIT 行为）

没有办法对引擎做单元测试，但你可以在引擎边界上测试*你自己*的代码。`lupa`（CPython 里的
LuaJIT）加上一个假的 `stingray` 表，统计 `create_screen_gui` / `destroy_gui` / `Gui.move`
的调用，可以抓到：

- 保留式重建泄漏（两帧必须恰好创建一个 GUI），
- `panel_clear()` 漏销毁了某个东西，
- 静止的面板调用了 `Gui.move`，
- 拖拽夹取越出视口，
- 分级建立在八帧之内完成且**没有任何固定等待**，
- cards 分支为两个共享同一个 armor id 的卡片绘制出不同的标签。

把它作为常规测试套件的一部分来跑；这比在实机里找同一个 bug 便宜得多。

---

## 证据 / 来源

- `mods/custom-armor-kit/work/standalone/multi_perk.lua` —— `ui_frame` (L2593-2740)、
  `panel_draw` (L2035-2398)、`ladder_step` (L2402-2447)、`panel_clear` (L1713-1730)、
  `panel_offset` (L1737-1760)、`panel_drag` (L1761-1787)、`GLYPHS` (L1814-1849)、
  `zh_init` (L1862-1880)、`ui_resources` (L1414-1487)、屏幕变化重绘 (L3026-3037)。
- `mods/custom-armor-kit/work/standalone/test_armor_ui.py`、
  `test_armor_controls.py` —— 离线的生命周期 / 拖拽 / 字体覆盖断言。
- `mods/custom-armor-kit/RETIREMENT-FINDINGS.md` —— 关于在引擎资源库存在之前创建 GUI
  所导致的原生崩溃的记录。

## 那些实实在在耗掉时间的易踩的坑

| 症状 | 原因 / 修复 |
|---|---|
| `ntdll 0xc0000026`，帧回调死亡，日志停在 "building the panel" | 在引擎的字体/材质库存在之前调用了 `create_screen_gui`。用飞船 world + 资源做守卫；`pcall` **不会**救你。 |
| 面板建好了却看不见 | 保留式 GUI 位于某个原生屏幕（军械库）之下，或者 `layer` 不对。在原生屏幕 / 图层变化时重建。 |
| 点击毫无反应，但 UI 看起来正常 | 针对**本**帧的 `PANEL.regions` 做命中测试，消费按下沿，并在拖拽期间忽略采样。 |
| 文字渲染成了镜像 | 位图第 1 行是字形顶部；把它画在最高的 y 处（`bm.h - r`）。 |
| mod 静默地完全不加载 | 表构造器过大 → LuaJIT 报 `function too long`。把数据打包成待解析的字符串。 |
| 中英混排标签丢掉了中文那一半 | 对整个字符串套用了 ASCII 回退。按 UTF-8 段拆分。 |
| `Gui.move` 堆栈不断堆积 | 只在增量变化时 move；断言静止时调用次数为零。 |
