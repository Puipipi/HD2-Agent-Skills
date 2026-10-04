# template/ —— 一个最小、契约正确的 HD2 模组骨架

[English](https://github.com/YC426/HD2-Agent-Skills/blob/main/template/SKELETON.md) / 简体中文

`panel_skeleton.lua` 是一个刻意无聊的起点。它不画任何有意义的东西；它的存在是为了让那三条
最贵的规则从第一行就是对的，免得后面的功能代码把违规藏起来。

| 文件 | 是什么 |
|---|---|
| `panel_skeleton.lua` | 骨架本体。当成 addon 丢进加载器即可。 |
| `../tests/test_panel_skeleton.py` | 离线测试台：在真 LuaJIT 上、用假引擎跑骨架。 |

> 英文原文：[SKELETON.md](SKELETON.md)

## 它强制的三条规则

1. **守卫是取值判断，不是 `pcall`。** `pcall` 只拦 Lua 错误；空的引擎槽位或错误的指针会原生
   fault，并让帧回调整局死掉。见 `native_ok`、`callable`、`read_mem`。
2. **分级建立，只在拿到正向事实时推进。** 六个具名阶段，每帧重新检查，每次 hold 只把原因记
   一次。没有任何东西会因为一次早期失败就被记成“不可能”——引擎库是晚建好的。
3. **帧错误预算。** 连续五次失败就停掉该功能，并留下具名原因；游戏继续跑。

再加上让它可诊断的配套习惯：状态变化各一行日志、什么都跑不起来时也照样写 `-STATUS.txt`，
以及一个 `MOD.work` 接缝，让失败路径可测。

## 先跑测试

```powershell
python -B tests/test_panel_skeleton.py
```

需要 `lupa`（CPython 里的 LuaJIT）。它**不需要游戏**就能做四件事：

* 跑工作区里的 `ffi_audit.py` 静态检查——你**调用**的每个 C 符号都必须已声明，因为少一条声明
  就是调用点的硬错误；
* 在 LuaJIT 2.1 上编译骨架，并断言没有引擎写入、没有内存分配；
* 用假引擎在四种状态下驱动它——无引擎、有引擎但无舰船 world、完整引擎、以及每帧都失败的
  函数体——断言不会过早创建 GUI、阶段停在正确的位置、错误预算能停掉坏循环；
* 检查加载后 STATUS 文件存在。

提交状态下 24 项检查全部通过。你如果改骨架，请让它们继续通过：这个文件已经出过两个 bug，
都在评审里看不见，在测试台里一目了然。

## 用来写真正的模组

1. 改掉 `KEY`、`MOD.version`，以及日志/状态文件名。
2. 按你的加载器改底部的 `register()` 段。从那里调 `MOD.tick(frames)`，或者把 `MOD.frame` 接到
   加载器的回调——**两条路都要让预算包装留在链路里**。
3. 把你的每帧工作放进 `MOD.work`（或替换 `frame` 里标出的那段）。
4. 任何涉及绘制或输入的东西，先读
   [`../skills/hd2-in-game-panel/SKILL_cn.md`](../skills/hd2-in-game-panel/SKILL_cn.md) 和
   [`../skills/hd2-native-panel-input-lock/SKILL_cn.md`](../skills/hd2-native-panel-input-lock/SKILL_cn.md)
   再加调用。
5. 对结果重跑 `ffi_audit.py`——每个新增的 `ffi.cdef` 符号都要在列表里有声明，而一条错误的
   声明能静默顶掉另一个模组的声明。

## 哪些**没有**验证

骨架在**假引擎**上能正确编译、加载、分级、hold、失败并停止。它**没有**被部署进真实运行的游戏。
阶段边界、帧数和舰船 world 的时序都来自参考模组的日志，不是来自这个文件自己的运行——把它
第一次实机运行当成一次测试，盯住 `stage N (...) held:` 那几行，它会告诉你哪个前置条件此刻
还不成立。
