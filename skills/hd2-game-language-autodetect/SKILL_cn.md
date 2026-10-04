---
name: hd2-game-language-autodetect
description: 判断正在运行的 Helldivers 2 客户端是中文还是英文 —— 通过经过验证的绝对偏移，从 game.dll 内存中读取游戏所选的 Text Language；失败时回退到探测引擎字体的字形覆盖率。当 mod／面板／工具必须自动选择 zh 或 en 标签时使用，或者当一个固定地址在游戏更新后失效、代码需要一条安全的「保留上一次已知值」路径时使用。
---

# HD2 游戏语言自动判断

[English](https://github.com/YC426/HD2-Agent-Skills/blob/main/skills/hd2-game-language-autodetect/SKILL.md) / 简体中文

两种**相互独立**的方法，按应当尝试的顺序排列。两者都取自可正常工作的 HD2 Lua/JIT mod，并经过实机确认。

| # | 方法 | 读取内容 | 能扛过游戏更新吗？ | 何时失败 |
|---|---|---|---|---|
| A | 经校验的 game.dll 偏移 → 所选的 **Text Language** | `game.dll` 中的绝对偏移 | **不能** —— 必须重新推导 | 偏移发生位移；build 哈希不匹配 |
| B | 引擎**字体字形覆盖率**（`Gui.text_extents`） | 仅引擎自身的 API | **能** | 引擎字体尚未就绪／无法测量 |

方法 A 在获准读取哪怕一个字节之前，都需要一份 build 校验。方法 B 除一个可用的 GUI 句柄之外不需要任何东西。要准确性用 A，要可移植的回退用 B，而要手动逃生舱口则用配置覆盖（`lang=zh` / `lang=en`）。

> 配套阅读：[`docs/hd2-mod-failure-catalog.md`](../../docs/hd2-mod-failure-catalog.md)
> —— §5（内存读取安全：build 校验、撕裂读、id 校验）与 §6（配置解析）
> 就是本技能应用于单个值上的那套规则。

---

## 1. 方法 A —— 读取所选语言（精确偏移，以 build 为闸门）

### 指针链

```
base = GetModuleHandleA('game.dll')
settings = *(void**)(base + 0x3326340)          ; settings 对象
index    = *(uint32*)(settings + 705712)        ; 所选文本语言索引
if index >= 15 then fail end                    ; 校验闸门
record   = *(void**)(base + 0x37c5650 + index*8); 语言记录表
text     = *(void**)(record + 8)                ; 语言代码字符串
code     = text:match('^(%a[%a%-]*)%z')         ; "cn", "us", "zh-CN", ...
```

`cn/tw/zh/zhs/zht/zh-CN/zh-TW → zh`，其余一切 → `en`。

### 不可让步的规则

1. **先以 build 校验作为闸门。** 除非 mod 其余部分所用的同一套模块哈希 + 字节签名验证已经通过，否则 `read_game_language()` 拒绝执行。绝不要「只是为了看看」而去读一个绝对偏移。
   armor kit 的校验是：`game.dll` **以及**主模块的 SHA-256 必须等于记录的 build，然后在已知代码位置做字节比较：
   ```lua
   assert(rd(VISBRIDGE.base + 0x14c0350, 16)
       == unhex('48895c24084889742410574883ec208b'), 'native presenter changed')
   ```
   以上任何一项失败，就返回 `nil`，让调用方保留它先前的语言。
2. **在信任字符串之前，重新读取索引并做比较**（撕裂读守卫）：
   ```lua
   local bytes = rd(settings + 705712, 4)
   local index = bytes and u32(bytes, 0)
   ...
   if rd(settings + 705712, 4) ~= bytes then return nil end   -- 读取过程中发生了变化
   ```
3. **校验结果的形态**，而不只是非 nil：`index < 15`、code 匹配 `%a[%a%-]*`、`#code <= 12`、`text` 在 NUL 处截断。否则一个垃圾指针也会产出一个看起来很像样的字符串。
4. **任何时候有疑虑就返回 `nil`。** `nil` 意味着「未知，保留你原有的值」—— 绝不意味着「默认用英文」。

### 限流

语言不可能每帧都变。最多每 **120 帧（约 2 秒）**轮询一次，并缓存选项字符串，这样一个强制值就能完全短路掉读取：

```lua
local function update_language(option, frames)         -- option: 'auto' | 'zh' | 'en'
    local selected, code
    if option == 'zh' or option == 'en' then
        selected = option                                -- 强制指定：零次内存读取
    elseif M.lang_option ~= option or frames >= (M.lang_due or 0) then
        M.lang_due = frames + 120
        selected, code = read_game_language()             -- 可能为 nil
    end
    M.lang_option = option
    if selected and M.lang ~= selected then
        M.lang = selected
        PANEL.sig = nil                                   -- 强制用新语言重绘 UI
        log('lang: UI -> ' .. selected .. ' (game=' .. tostring(code or 'config') .. ')')
    end
end
```

注意两个要紧的行为：
- **首次调用立即执行**（`M.lang_due` 为 nil），因此面板不会在头两秒里是英文。
- **`selected == nil` 会保留 `M.lang`** —— 游戏更新后设置变得不可读时，语言会冻结，而不是来回闪。
- 只在**发生变化**时记日志，而不是每次轮询都记。

### 测试接缝（如何离线证明它）

把 `rd`、`u32`、`u64` 和 `VISBRIDGE.verify` 打桩，然后驱动 `update_language` 并断言：语言能从设置解析出来、`auto` 会跟随变化的 code、显式覆盖优先、越界的 index 会保留上一个值，以及同一窗口内的第二次调用执行**零次**读取。Custom Armor Kit 中的 `test_armor_controls.py` 做的正是这件事，是可以照抄的范本。

---

## 2. 方法 B —— 问游戏自己的字体能画什么

引擎字体就是游戏的字体：当游戏的文本语言是中文时，它有 CJK 字形，否则可能没有。测量译文会用到的每一个字符，并与引擎给缺失字形分配的宽度作比较。

```lua
local te = sr.Gui and rawget(sr.Gui, 'text_extents')
if te == nil or not font or not font.font then return 'no measuring' end

local function width(s)
    local ok, a, b = pcall(te, gui, s, font.font, 20)
    if not ok or not a or not b then return nil end
    return (Vector3.x(b) or 0) - (Vector3.x(a) or 0)      -- x1 - x0
end

local base, q = width('MMM'), width('?')
if not base or base <= 0 then return 'font not ready' end

local function missing(ch)
    local w = width(ch)
    return not w or w <= 0 or (q and q > 0 and math.abs(w - q) < 0.01)
end
```

然后：
- 收集目标语言字符串实际用到的每一个**去重后**的字符
  （`str:gmatch('[\194-\244][\128-\191]*')` 会遍历 UTF-8 序列）。
- 每个字符测量一次，把结论按字体缓存起来。
- 用**比率，而不是单个字符**来判定：`nbad / checked < 0.5` 意味着字体能画出该语言。单字符测试会在标点符号上给出假阴性。
- 记录*哪些*字符缺失（`PP.font_bad`），这样后续一遍可以用 ASCII 替代品（`，→ ,`、`。→ .`、`：→ :`）替换，而不是任由引擎画出 `?`。
- **如果比率不达标，就保持英文。** 不要渲染出一屏的 `?`。

方法 B 才是能跨游戏更新持续可用的那一个，所以把它接成自动路径，把方法 A 接成精确路径。

---

## 3. 把它接进标签

只保留一个翻译入口，并且绝不翻译数据：

```lua
-- 仅用于 UI，按精确的源字符串索引
local ENLABELS = { ['新建卡片'] = 'New Card', ['保存并应用'] = 'Save & Apply', ... }
local function L(s) if M.lang == 'en' then return ENLABELS[s] or s end return s end
```

让这一切可维护的规则：

1. **只烘焙一种语言，在调用点翻译。** 用你写作时所用的语言（英文或中文）写代码，在绘制时让它过一遍 `L()` / `tr()`。
2. **在绘制／测量时翻译，绝不在存储时翻译。** 数据文件、配置、分享码和日志保持原语言，这样存档在不同语言之间迁移时保持不变。Super Earth Armory Forge 做的正是这件事（`PP.tr` 只在 `text()`/`measure()` 内部应用，别处都不用）。
3. **缓存查表结果。** `cache[source_string] = translated`，在语言变化时失效 —— 面板每帧都会重绘，每帧跑一串 `gsub` 是可以测量出来的开销。
4. **部分替换时按最长优先匹配**，并跳过短的常见词（`#key < 5..6`），这样 "on"/"off"/"id" 不会被替换进句子中间。
5. **在 CI／本地测试中做一次覆盖率检查**：回退表里的每个标签都必须能被所选渲染器渲染（对于手工像素字体，要断言每个英文标签里的每个 ASCII 字符都有对应字形）。armor kit 的 `test_armor_controls.py` 就针对 `ENLABELS`、`EN_ARMOR_NAMES` 和 `EN_PERKS` 断言了这一点。

---

## 证据 / 来源

- `mods/custom-armor-kit/work/standalone/multi_perk.lua` —— `read_game_language`
  （L1539-1559）、`update_language`（L1560-1574）、`ENLABELS`/`L`（L1886-1905）、
  `PROBE` 本地化扫描（L750-794）。
- `mods/custom-armor-kit/work/standalone/test_armor_controls.py` —— 覆盖整条链路的离线测试，
  包括「设置不可读时保留上一次已知语言」这一情形。
- `outputs/validated-2026-10-04/hud-compatibility/sources/installed-Super-Earth-Armory-Forge-v6.2.1-0-0.lua`
  —— `PP.font_test`（方法 B）与 `PP.tr`（带缓存的绘制时翻译）。

## 易踩的坑（真的花过时间的）

| 症状 | 原因 / 修复 |
|---|---|
| 语言刚切换后立刻出现 `attempt to index global 'PANEL' (a nil value)` | 自动判断改变了 UI 签名，而 panel 表被声明在 scanner *下面*。把扫描帧会碰到的任何东西都提前声明（`local PANEL`）。 |
| 语言在 zh 与 en 之间来回闪 | 每帧都读却没有限流，或者信任了一次撕裂读。限流 + 重新比较。 |
| 游戏更新后面板全变成 `?` | 方法 A 的偏移移位了，返回了仍然匹配 `%a+` 的垃圾值。加上校验闸门，并回退到方法 B。 |
| 译文泄漏进存档文件 | `tr()` 在写入时被应用，而不是在绘制时。只在渲染器里翻译。 |
| 引擎字体测量不出任何东西 | 字体库的构建晚于启动；早期该槽位是 NULL。要重试，不要为整个会话锁死「no measuring」。 |
