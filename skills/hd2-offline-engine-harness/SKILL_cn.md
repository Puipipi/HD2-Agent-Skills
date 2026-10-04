---
name: hd2-offline-engine-harness
description: 通过在真实 LuaJIT 上用 lupa 伪造引擎边界，离线测试《Helldivers 2》的 Lua mod —— 统计 GUI 的创建/销毁，驱动一次分级建立过程依次经过 no-engine / no-world / full-engine / failing-body 状态，演练帧错误预算，并断言那些否则要付出一次实机运行代价的不变量。适用于为某个 mod 添加离线测试，或者想在不部署的情况下抓住启动顺序或拆解（teardown）缺陷的时候。
---

# HD2 离线引擎测试台

[English](https://github.com/Puipipi/HD2-Agent-Skills/blob/main/skills/hd2-offline-engine-harness/SKILL.md) / 简体中文

> **置信度:** 已在本地针对真实 LuaJIT 上的伪造引擎验证过；它找出了两个真实缺陷。它证明的是你的控制流，而不是引擎的行为。

`scripts/test_panel_skeleton.py` 是一个现成的测试台：24 项检查，**不需要游戏**，
一秒内跑完，针对 `template/panel_skeleton.lua`。

你无法对引擎做单元测试。你*可以*针对**引擎边界**来测试自己的代码，而昂贵的缺陷正住在
那里 —— 在世界存在之前创建的 GUI 会以原生方式出错，`pcall` 抓不到它，所以要找出这一类
缺陷，唯一廉价的办法就是在测试中控制这条边界。

## 前置条件

| 需要 | 原因 | 缺失时 |
|---|---|---|
| Python 3.8+ | 驱动程序 | — |
| **`lupa`**（`pip install lupa`） | 提供带 `ffi` 的真实 **LuaJIT 2.1**，而不是普通的 Lua 5.1 | 测试台无法运行；装上它，不要用 Lua 5.4 替代 |
| 被测的 Lua 源码 | 这还用说 | — |
| 别的什么都不需要 | 不需要游戏、不需要加载器、不需要网络 | 它会写出一个临时日志目录 |

测试台会在自己的目录下写一份伪造的 `LOCALAPPDATA`，这样 mod 的日志就不会污染真实的那个。
请把这个目录排除在版本控制之外。

## 模式

1. **伪造 `stingray`，并统计真正重要的那些调用。**
   ```python
   PRELUDE = """
   CREATED = 0
   WORLD = { name = 'ship' }
   stingray = { Gui = { resolution = function() return 1920, 1080 end },
                World = { create_screen_gui = function() CREATED = CREATED + 1; return {} end },
                Application = { main_world = function() return WORLD end } }
   """
   ```
   然后断言**计数**，而不只是“没有报错”：两帧必须恰好创建一个 GUI。

2. **驱动四种引擎状态，并断言它在哪里停下。**
   | 状态 | 断言 |
   |---|---|
   | 完全没有引擎 | 不创建任何 GUI；它会说出自己按兵不动的理由 |
   | 有引擎，但没有飞船世界 | 在 GUI 阶段之前停下；`CREATED == 0` |
   | 完整引擎 | 到达最后一个阶段；记录分辨率；至多创建一个 GUI |
   | 每帧函数体会抛错 | 在恰好 `FAIL_LIMIT` 次失败之后停下，留下一个原因，不再调用那段坏掉的工作 |

3. **暴露接缝，让失败路径可达。** 骨架调用 `MOD.work(...)`，测试则替换 `MOD.work` 以强制抛错。
   替换整个帧函数体会绕过被测的那个闸门本身 —— 本测试台的第一个版本就是这么做的，
   结果让一个坏掉的预算“通过”了。

4. **把日志指向一个用完即弃的地方**，做法是覆写 `os.getenv`，然后再把它读回来：
   ```python
   rt.execute(f"os.getenv = function(n) "
              f"if n == 'LOCALAPPDATA' then return [[{scratch}]] end end")
   ```
   然后断言诊断文件*说出了发生了什么*（骨架的 STATUS 文件必须显示它实际到达的阶段）。

5. **也测试工具链**：在同一个测试台里跑静态 FFI 审计，并断言源码能在 LuaJIT 上编译通过。
   这些过不了的 mod 就不该走到实机运行。

## 它发现了什么 —— 这是它值得做的证据

针对骨架写这个测试台，找出了代码评审漏掉的两个真实缺陷：

- 一个 `local` 声明在使用它的函数**下方**，于是该引用静默地编译成了全局 `nil`，
  而 `0 >= nil` 在第一帧就抛错；
- `local ok, a = pcall(fn, ...)` 丢掉了第一个之后的所有返回值，于是每个返回两个值的引擎
  调用第二值总是 `nil`，针对它的每个闸门都永远失败。

这两个都读不出来。而在测试台里都是一瞬间的事。

## 局限

- 伪造的引擎证明的是**你的**控制流，而不是引擎的行为。在这里通过，并不构成该功能在游戏里
  可用的证据。
- 测试夹具会漂移：如果真实 API 多了一个返回值或一个字段，伪造件会一直保持旧形状，直到有
  人更新它。请把伪造件当作受审代码的一部分。
- 它抓不到“在错误时机调用真实 API”造成的原生崩溃；在你所模拟的状态下，它只能抓到你的代码
  *试图*这么做。

## 延伸阅读

`hd2-bingus-mod-development` §4 讲这些测试如何嵌入构建循环，
`docs/hd2-mod-failure-catalog.md` §9，`writing-mod-tools`。
