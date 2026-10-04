---
name: hd2-ffi-audit
description: 静态检查一个 Helldivers 2 Lua mod 调用的每个 C 符号是否都已声明，以及是否有任何声明会与另一个 mod 可能做过的声明冲突 —— 因为 LuaJIT 的 ffi.cdef 保留第一条声明，一个错误的原型会静默地让另一个 mod 失效。在打包任何使用 ffi 的 mod 之前使用，或者在某个 mod 能加载但某个动作抛出 "missing declaration for symbol" 时使用。
---

# hd2-ffi-audit —— FFI 声明静态审计

> **置信度:** 扫描器能跑,但其规则是读来的,不是从加载器重新推导的。已知盲区见下。见[验证状态](../../docs/verification-status.md)。

[English](https://github.com/YC426/HD2-Agent-Skills/blob/main/skills/hd2-ffi-audit/SKILL.md) / 简体中文

`scripts/ffi_audit.py` 把 Lua 源码当作文本来读取，并报告两类都曾在这个生态中发布出去的
破坏：

1. **被调用但未声明。** 没有匹配 `ffi.cdef` 的 `k.VirtualAllocEx(...)` 在调用处就是硬
   错误。它曾经以*「点击卡片没有任何反应」*的形式发布出去。
2. **被别的 mod 以不同方式声明。** LuaJIT 的 C 命名空间是进程全局的，而 `ffi.cdef`
   **保留第一条声明**。一个声明了 `GetCursorPos(int32_t*)` 的 mod 顶掉了另一个 mod 的
   `HD2CS_POINT*` 形式，于是那个 mod 在整个会话中把自己禁用了。

## 前置条件

| 需要 | 原因 | 缺失时 |
|---|---|---|
| Python 3.8+ | 该脚本 | — |

没有别的：**不需要 LuaJIT，不需要 lupa，不需要游戏，不需要网络。** 它是对文本做正则扫描，
并且不写入任何东西。

## 使用

```powershell
python -B scripts/ffi_audit.py path\to\mod.lua
python -B scripts/ffi_audit.py work\standalone\*.lua      # 每个文件一份报告
```

退出码 0 = 每个被调用的符号都已声明；非零 = 至少有一个缺失，并列出其首次调用的行号。

它能识别这个生态中使用的全部三种声明风格：

- `ffi.cdef[[ ... ]]` 块
- `pcall(ffi.cdef, 'int Foo(void*);')` 单行式
- `bind('int (*)(int32_t *)', 'GetCursorPos')`（通过 `GetProcAddress` 解析）

## 它做不到什么

在你信任它之前请知悉：

- 它是**基于正则的**，因此通过宏、typedef 或计算出的名称到达的符号不会被看到。
- 它检查的是某个符号*在某处被声明过*，而不是原型**正确**。user32 规则
  （`hd2-addon-build`）之所以存在，正是因为一个看起来合理的错误原型才是危险的情形，而
  只有白名单能抓住它。
- 它对其他 mod 的声明一无所知；它能告诉你某个声明*可能*冲突（该符号在已知的 user32
  集合中），但不能说它*确实*冲突。
- 它对于该符号是否存在于已加载的库中什么也说明不了。

对于运行时那一半 —— 一个正则接受、但带有拼写错误的 `cdef` 字符串 —— 请记录该失败而不是
把它吞掉：

```lua
for _, d in ipairs(FFI_LIST) do
    local ok, err = pcall(ffi.cdef, d)
    if not ok then log('ffi.cdef FAILED for: ' .. d .. ' -- ' .. tostring(err)) end
end
```

## 另见

`hd2-addon-build` 把一项等价的检查作为构建门禁来运行（外加 user32 拒绝）；
`writing-mod-tools` 说明了为什么上面这些局限写在这里，而不是留给用户去发现。
