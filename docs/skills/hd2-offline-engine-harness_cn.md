---
name: hd2-offline-engine-harness
description: "用 lupa 在真 LuaJIT 上离线测试或对比 HD2 Lua mod：假引擎边界、GUI 计数、分阶段启动、帧错误预算。加离线测试时用。"
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

## 比较热路径的离线成本

控制流测试回答“代码做了什么”；基准测量“这部分工作花了多久”。两者不能互相替代。可参考 [AutoChat build 10
基准说明](https://github.com/Puipipi/HD2-AutoChat/blob/4445596a76ed387edc3c09d0d25aa9d06ffd5b11/docs/PERFORMANCE-OFFLINE-1.0.0.md)
和
[`bench_frame_performance.py`](https://github.com/Puipipi/HD2-AutoChat/blob/4445596a76ed387edc3c09d0d25aa9d06ffd5b11/work/standalone/bench_frame_performance.py)。以下命令要在
AutoChat checkout 根目录运行，不是在本技能仓库：

```powershell
python -B work/standalone/bench_frame_performance.py --source-ref 5237d9b --runs 3 --frames 12000 --warmup 1200
python -B work/standalone/bench_frame_performance.py --runs 3 --frames 12000 --warmup 1200
```

加载同一个生产入口（本例为 `_G.update()`），对比固定旧 ref 与当前源码，并记录两者 SHA-256。每轮使用全新的 LuaJIT runtime，先预热，再在 Lua 内用 QPC
收集样本，减少 Python/Lua 跨边界调用对逐帧计时的干扰。样本存放在 Lua table；曾有独立夹具扩展 FFI 采样数组时失败，这只是测量夹具失败，不能归因于游戏或引擎。GUI stub
只统计绘制/测量调用，不保留每次 draw 的文本和图元，避免夹具数组及 GC 污染计时。

分开报告稳定帧和周期工作。当前案例每种场景使用三个 fresh runtime 并报告 median：稳定帧 mean、周期 poll mean 与 p99、所有帧 overall mean、p99 与 max。评估
**0.05 ms** 目标时，mean、p99、max 都要查看；overall mean 不代表逐帧上界。AutoChat 每 30
帧做一次周期观察，这是该模组的场景，不是建议其他模组降低检查频率。记录任务数、角色、enabled/done/due 状态和调用计数。100/1000 条“未来任务”必须确实属于活动角色，且
enabled、未完成、尚未到期。

一个安全的调度优化例子是先检查是否有 enabled、未完成、可重试并已到期的任务；活动/默认角色选择与生产保持一致。检查发生在构造并排序任务数组快照之前，没有到期项就跳过该快照分配；每日任务也必须沿用相同日期条件。发现到期项后，保留完整任务快照与排序、逐项动态判断，以及发送、保存、重试等副作用。不要为了改善数字降低检查频率，也不要在没有状态失效机制时增加跨帧 deadline 缓存。

调用次数变少不等于实测更快：AutoChat 曾试用 wrapped-text 缓存，但没有得到稳定收益，随后撤回。默认 open/redraw
场景只绘制短提示，不代表长文本、中英混排或大量规则的重绘压力。要优化这些场景，应加入代表性输入并确认确实发生重绘；布局正确性断言与计时分开。伪引擎、字体 mock 和离线 QPC
数据都不是实机延迟证据，也不能保证游戏每帧低于 0.05 ms。

### 如实测量缓存或 renderer 改动

基线和候选必须使用同一个生产闭包、场景输入、帧序列和计数器。分别构造每个测试场景；不要用多层
字符串替换只改其中一侧，否则两边可能不止目标改动不同。记录 LuaJIT 版本、`jit.status()`、GC 模式和
源码修订。每个场景用新的进程/runtime，在 Lua 内用 QPC 计时；限制假 native/UI stub 的保留数据量，避免
采样数组或 JIT trace 日志成为主要 GC 负担。预热要走与计时相同、有界的批次路径。若计时期间 JIT
trace 仍在增长，应称为 cold-to-warm，而不是 steady-state。QPC 墙钟耗时不等于线程 CPU 时间。

统计量名称要与实际采样对象一致。callback 批次均值的分位数是批次分位数，不是逐帧 p99。要在相同输入
分组下展示缓存 rebuild、hit、population 和剩余工作；相同总量可能掩盖某条路径漏测。离线数字是在该
夹具下的观察，不是受控的实机结果，也不能证明达到游戏每帧目标。

按工作层级分别计数：源数据/输入扫描、cache key 构造、几何展开与复制、数学对象构造、GUI stub 事件、原生提交。面数不等于原生调用数。基于身份的缓存可能复用输出，但构造 key 时仍扫描每条源数据；在声称减少遍历前，单独统计这项扫描。除调用/复制计数外还要比较耗时；如果候选只降低了一个计数器，实测没有节省时间，就应拒绝它。

每个实机采样窗口都记录 reset/start/end 边界、样本数、分母及已确认的目标实例/类型状态。普通弹丸或效果标记不能证明目标角色数量。窗口增量与 profiler 累积计数分开记录；短阶段均值既不是整次调用均值，也不是逐帧 p99。

可复用几何缓存时，先沿真实引用关系核对所有权。某个 LuaJIT renderer 的复制缓存槽位持有的是三个批次
wrapper 内数组的引用，而不是 wrapper 表本身。它用每次新建的外层 batch 数组身份作为 cache miss 信号，
不会比较被复用展开行的身份。只有在这个已核实的契约下，且 native line 提交会把端点值复制到自己的 buffer，
才复用最终展开行与端点表。每次 rebuild 都新建外层 cover 或 dash 集合。若消费者通过行身份判断变化，池化这些
行前必须另有 revision 或失效证据。没有证明生命周期和身份契约允许前，不池化 raw flow 输入、GUI face 输入
或静态展开几何。
释放 pool 所有权链接时，不要改写仍被当前提交或缓存持有的行与点。保留 same-bucket no-op 仍需要的有效展开
状态，并为绕过常规 pair helper 的内联清理路径单独 detach。覆盖首次、相同和变化 bucket、重建失败与重试、
world/style/toggle 变化、trim 和空 guide。以上是要核对的所有权与失效问题示例，不是可复用 API 契约。

实机确认前，先确认运行进程，再核对启动版本 banner、已部署产物 hash 和本次 session epoch，避免把旧日志
归给候选版本。对已部署的 instrumentation 记录原始日志尾部 hash、实际 copy offset 和字节数。严格校验预期
日志 schema/version；遇到 `profile_unavailable` 等有界提前停止时，不能声称完成了目标采样数。若停止点靠近
guide 边界，证据只支持粗略时序，不能证明精确根因。分组 hit/rebuild/population 数量只有在运行控制了这些
条件时才是受控结果，否则应称观察数据。若单枚项目的人评信号清楚，可能无需截图；不要添加无法回答问题的
捕获步骤。

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
- 如果同 build 证据表明引擎数学构造器返回帧/临时 arena userdata，就在所属帧内同步构造并消费；除非该 build 的生命周期契约明确证明安全，否则不要把它保存在 controller 或跨帧复用。伪引擎复制对象来断言 Lua 状态没有保留它们，只能验证控制流，不能证明真实引擎对象的生命周期。
- 伪造的 `Gui.text_3d` 边界可以验证资源闸门、参数顺序和清理，不能验证原生调用是否接受、文字外观、遮挡或性能。`Application.can_get == true` 只表示该 API 认为资源可用，不证明文字路径会绘制。未经目标 build 实机视觉检查，未运行的 text 原型必须明确保持实验状态。
- 只记录输入的 `Gui.text` stub 不会模拟原生 markup 解析或光栅化。若需求是字面显示 markup，
  增加仅用于测试的 markup-aware shim，检查单次绘制调用是否收到完整 tag；再断言生产 renderer
  会拆分调用，且可见 source span 按顺序拼接后等于预期文本。这只验证调用边界，不验证原生
  renderer。交互式文字应通过生产鼠标/键盘 reducer 和绘制路径驱动；断言实际发出的文字/选区
  矩形、viewport offset 与保留式重绘。一个长标记可能跨多个调用，所以按 source span 顺序验证，
  不要要求每个标记或每行都由单次调用绘完。离线耗时与实机延迟结论分开报告。

## 延伸阅读

`hd2-bingus-mod-development` §4 讲这些测试如何嵌入构建循环，
`docs/hd2-mod-failure-catalog.md` §9，`writing-mod-tools`。
