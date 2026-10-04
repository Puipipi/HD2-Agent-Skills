---
name: hd2-lua-forward-declarations
description: 修复 Lua 中「函数在定义之前就被调用」的失败——此时调用点解析为 nil 并静默失败，也就是「我改了设置却什么都没发生」背后的模式。当某个回调、rescan 或 refresh 没有任何报错却毫无作用时，当某个功能在一次重构之后静默失效时，或者当你在写一个 mod 而其中一个函数调用了文件更靠下处定义的另一个函数时使用。
---

# Lua 前向声明：什么都不报告的 bug

[English](https://github.com/Puipipi/HD2-Agent-Skills/blob/main/skills/hd2-lua-forward-declarations/SKILL.md) / 简体中文

```lua
local function rescan() ... end   -- defined at line 900

register_option('x', { on_change = function(v) rescan() end })  -- registered at line 300
```

注册时闭包被构建出来；到了**调用**时才会去查找 `rescan`。如果定义尚未执行，这个 upvalue 里
保存的是 `nil`，而 `rescan()` 就是一次对 nil 值的调用——而且发生在框架往往会吞掉异常的回调里。
选项渲染出来了，玩家点击了，值移动了，却什么都没发生。没有任何错误到达用户那里。

## 来源与置信度

这不是假设。在 `mods/stratagem-cooldown` 中，删掉 `mom_rescan` 的定义却留下它的调用点，
产生的正是这个结果：游戏内的改动完全无效，而那个“每 10 秒重写一次”的循环从未运行过一次。
这一个缺陷解释了 3.0.0 到 3.7.0 的**全部**症状。它是通过把调用点与定义清单做比对发现的，
而不是靠读症状发现的。

## 规则

**在任何东西可能捕获它之前先声明这个 local；在函数体自然所属的位置给它赋值。**

```lua
-- near the top, before any closure that might call it
local rescan

-- ... registration and other code that references rescan ...

-- where the implementation belongs
function rescan()
    ...
end
```

`local rescan` 创建绑定；后面的赋值把它填上。闭包捕获的是**绑定**，不是值，所以在赋值之后的调用
能正常工作，而在赋值之前的调用会以你能看见的原因失败。

## 给每一个可能提前运行的调用点加防护

前向声明修的是你能控制的顺序。它修不了你控制不了的顺序：框架回调、定时器，或另一个 mod 的钩子
可能在你的赋值之前触发。

```lua
if type(rescan) == 'function' then rescan() end
```

并且，比起悄悄跳过，更倾向于把防护的拒绝记录下来：

```lua
if type(rescan) ~= 'function' then
    log('rescan not ready yet (configuration changed before init finished)')
    return
end
```

## 为什么这一类 bug 代价高昂

- **它在调用时失败，而不是在定义时失败**，所以文件能干净地编译和加载。
- **错误落在框架可能用 pcall 包住的回调里**，所以它永远到不了日志或弹窗。
- **它看起来像设置没有被读取**，于是自然的下一步是去调试配置解析器或内存写入——完全错误的子系统。
  这正是它所造成的绕路。
- **它出现在重构之后**，当某个定义被移到它的第一个调用者下面时。其他什么都没变，
  所以读起来就像是“这个功能自己坏了”。

## 如何找到它，而不是猜

不要从症状出发（“设置没有生效”）。要从**调用图**出发：

```powershell
# every local function definition, with line numbers
Select-String -Path src\*.lua -Pattern '^\s*local function (\w+)' |
  ForEach-Object { "{0,5}  {1}" -f $_.LineNumber, ($_.Matches[0].Groups[1].Value) }

# every call to one of them
Select-String -Path src\*.lua -Pattern 'rescan\s*\(' |
  ForEach-Object { "{0,5}  {1}" -f $_.LineNumber, $_.Line.Trim() }
```

如果某个调用点的行号**小于**唯一定义的行号，并且这次调用可能在文件执行完之前发生，那就是这个
bug。完全缺失的定义会表现为一个被调用却从未被定义的名字——也要查这种情况，因为“定义被删掉、
调用点留下来”是同一个失败、不同的成因。

廉价的机械检查，值得在每一轮测试之前跑一遍：

```lua
-- offline: assert that everything the mod calls exists by the time it is called
for _, name in ipairs({'rescan', 'apply', 'refresh'}) do
    assert(type(_G[name] or _ENV[name]) == 'function', name .. ' is not defined')
end
```

## 推广

这是同一个项目学了两次的、一条更普遍规则的其中一个实例：**一个无法报告自身失败的关卡，
会被读成否定结果。** 一次 `nil` 调用、一个返回 `false` 却没人检查的 `pcall`、
一次返回了原因却没人记录日志的注册——这三者从外面看完全一样：“这个功能不工作”，
而且没有任何线索指向是哪一层拒绝了。

当一个功能静默地什么都不做时，在用户动作与效果**之间**的那一层加上探针，让它说出自己拒绝了什么
以及为什么。要在重读逻辑之前做这件事，因为逻辑通常没问题。
