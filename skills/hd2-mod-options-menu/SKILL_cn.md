---
name: hd2-mod-options-menu
description: 用 ModOptionsMenu（MOM）框架为 Helldivers 2 mod 构建游戏内设置页——真实的注册契约、它接受的两种类型、2–16 个选项的上限、以索引为取值的 choice，以及两个控件写同一个设置时的单一主人规则。当 mod 需要面向用户的选项、当选项静默地不出现、或当页面里的值变了但游戏内没有任何反应时使用。
---

# ModOptionsMenu：游戏内设置页框架

[English](https://github.com/Puipipi/HD2-Agent-Skills/blob/main/skills/hd2-mod-options-menu/SKILL.md) / 简体中文

MOM 是 mod 在不附送一个需要手工编辑的配置文件的前提下给玩家提供选项的方式。它的契约很小，
而几乎它的每一部分都**静默**失败——被拒的选项干脆不出现，而一个忽略变更的页面不会记录任何日志。

## 来源与置信度

取自一个能用的 addon 而不是猜测：下面的契约逐字抄自
`mods/stratagem-cooldown/src/vehicle_cooldown.lua` **L1490–1500**，而该处声明它本身抄自
**ExoLoadout v0.8.0**——一个已知可用的 addon。陷阱部分列出的失败是那个 mod 自己记录的事件
（v2.2.2 → 4.1.0，全部在当天复现过）。

**纠正本仓库别处的一个错误：** `hd2-offline-data-workflow` 曾声称 MOM 接受 `slider`。它并不接受，
该说法已被修正——L1494 处的源码注释写着
`spec.type = 'toggle' | 'choice' -- those two are what it really takes`。

## 契约

```lua
local host = rawget(_G,'ModOptionsMenu')   -- rawget, and check it exists
-- host.api == 1

host.register_option(id, spec)
--   spec.type        = 'toggle' | 'choice'      ONLY these two
--   spec.mod         = the mod's display name
--   spec.label       = the row's label
--   spec.description = the row's description
--   spec.choices     = { 'text', ... }          choice: 2 to 16 entries
--   spec.default     = <INDEX into choices>     a NUMBER, not the text
--   (slider: min / max / step)                  asked for, but refused - see traps

host.get(id)                 -- returns the INDEX of the current choice
host.set(id, index)
host.on_change(id, function(value) ... end)
```

最重要的一个后果：**每一个具有两种以上状态的设置都是一个 `choice`，其取值是一个索引。**
`spec.default` 是一个数字；`host.get()` 返回一个数字；回调收到的也是数字。把选项文本传进去，
你得到的是一个能渲染出来、然后什么都不做的行。

选项列表无法表达的取值留在 `config.txt` 里——这份技能的来源 mod 在那里保留了一个自由的
`percent=65` 和 `uses_add=7`，而页面只提供粗粒度的档位。

## 陷阱，每一个都来自真实事件

### `slider` 被拒，而且拒绝是静默的

当请求一个真正的 slider 时，框架拒绝了它。尝试过的那个 mod 的应对方式是在一个回退 id 下注册一个
三项的 `choice`，让该设置仍然可控，并记录：

```
menu: slider refused, the three-entry choice is in charge instead
```

检测方法：那个 mod 自己的尝试显示为 **7 options registered 2**——页面只显示了恰好是 `toggle` 的那两个。
把已注册行数与预期行数做对比是最省事的检查；把它记进日志。要按类型可能不生效来实现回退，
而不是假定它能用。

### 被拒的选项不会出现，而且没有任何日志替你记录

`register_option` 是在 `pcall` 里调用的；一次拒绝会以一个 falsy 结果加上一个原因字符串返回。
如果你不检查它，这个选项就只是从页面上消失了。把每一次拒绝连同它的 key、它的类型和原因都记录下来：

```lua
local ok, res, why = pcall(host.register_option, id, spec)
if not (ok and res) then
  rejected[#rejected+1] = string.format('%s (%s): %s', o.key, o.kind, tostring(ok and why or res))
end
```

一句含糊的“选项不全”的报告，通常就是踩到了某一条硬性框架规则。

### 超过 16 个 choice 会让整行消失

框架拒绝长度超过 16 的列表，日志行会点名这个上限：

```
refused: percent (choice): choices must list 2 to 16 names
```

这一行不会被截断——它会消失。缩短列表（来源 mod 把 counts 改成 7 档、把 Eagle 改成 6 档），
或者把这个设置拆成两个选项。

### 两个控件写同一个设置会互相打架

在试验阶段，一个百分比同时以 `choice` 和 `slider` 的形式存在。两者都注册成功了，两者都写同一个值，
最后被点击的那个获胜。

**单一主人规则：** 某个设置第一个成功注册的主人保留它；该设置的其他控件仍然会渲染，但拒绝生效，
并说明原因。

```lua
if o.kind=='slider' and not mom.slider_owner then mom.slider_owner = o.key end
-- at change time:
local owned = (o.kind=='slider') and (mom.slider_owner==o.key)
              or (o.kind~='slider' and not mom.slider_owner)
if not owned then
  log('menu: '..o.key..' = '..tostring(v)..' (not applied: '..
      tostring(mom.slider_owner or 'the choice')..' owns this setting)')
  return
end
```

静默忽略输家正是这里要防止的失败模式：用户点击一行，看到它移动了，而值没有变。

### 已注册的回调调用了后面才定义的函数

那个 mod “在页面里改了，游戏内毫无反应”的症状还有第二个原因：该函数在调用时本身就是 `nil`。
参见 `hd2-lua-forward-declarations`——这个框架是这类 bug 最糟糕的落脚点，因为选项会正确渲染，
而回调静默失败。

### `config.txt` 解析有两条路径，修好一条还不够

那个 mod 同时以分节和扁平两种方式解析自己的配置。施加在其中一个解析器上的修复被另一个覆盖了。
当你改动配置解析时，先把每一个解析器都找出来，再宣布它被修好。

## MOM 不支持什么

- **自由文本输入。** 列表无法表达的精确数值属于 `config.txt`。
- **任意按钮或动作行。** 由玩家触发的动作需要另一种机制。
- **动态的只读状态行。** 来源材料对此的记述相互矛盾：一条笔记说它不受支持，另一条说把
  `label`/`description` 做成函数就能得到一个只读状态，MOM 会在菜单打开时重新计算它。
  **这一点尚未解决——在依赖其中任何一种说法之前先做实测。**
- **在注册之后更改 `choice` 列表。**

来源 mod 采用的设计后果：给左和右各自独立的 `choice` 池，而不是一个动态列表。

## 管理器一侧，失败方式不同

游戏内页面与 mod 管理器的选项树是两个独立的系统，而且两者都静默失败：

| 症状 | 原因 | 修复 |
|---|---|---|
| 整棵选项树都不出现在管理器里 | 某个子选项用了一个空的 `Include: [""]` 当作“仅供 UI 的条目” | 每个子选项的 `Include` 都必须指向一个真实存在且带有 payload 的目录；照抄一个已知能正确显示的 mod |
| 挂上 payload 后，游戏崩溃或黑屏 | 子选项的 payload 是纯文本 Lua | 用与核心相同的 `build_addon()` 把它包起来，并让打包自检把每个 payload 的头几个字节与核心信封做比对 |
| 导入之后，什么都没有被改动 | 管理器导入时会勾选**每一个** block，而读取器取的是每个 block 的第一项——于是排在最前的“关”被取走了 | 当所有 block 都是关的时候回退到内置配置；更好的做法是，把设置搬进游戏内页面，不随包提供任何管理器配置 |
| 部署时用旧层覆盖了新层 | 管理器库里还躺着一个旧的包 | 部署前重新导入新包，或者只使用已经就位的那一层 |

## 不启动游戏来测试它

一个假 host 验证的是你的逻辑，**而不是**框架的行为——不要把它当作验收。它能做的是抓住上面那些
静默类问题：断言已注册选项的数量等于预期数量、断言每一个 `spec.default` 都是数字、断言每一个被接受的
id 都有 change handler。这三条断言本可以抓住本技能中除 `slider` 被拒之外的每一个陷阱，
而后者需要真实 host 才能测出。

## 验证清单

1. 记录 `registered N of M options` 并核对两个数字是否一致。
2. 把每一次拒绝连同它的 key、类型和原因字符串都记录下来。
3. 记录每一次已生效的变更**以及**每一次拒绝生效，连同主人的名字。
4. 确认每一个 `choice` 的 `spec.default` 都是数字。
5. 在页面里改一个值，并要求日志中给出**数字**证据（来源 mod 的证据形如 `780 -> 273`），
   而不是“现在能用了”。
