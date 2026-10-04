---
name: hd2-mod-log-analysis
description: 分析 Helldivers 2 某个 mod 的运行时日志，回答“它到底做了事没有，又在哪里停下的？”—— 对分阶段日志逐阶段分类、处理跨启动追加与 UTC 时间戳、在一次会话中关联两个 mod 的日志，以及供报告使用的 JSON 输出。当某个 mod 看起来什么都没做、当某个功能静默空转、或当你需要游戏内证据却又不想启动游戏时使用。
---

# HD2 mod 日志分析

[English](https://github.com/YC426/HD2-Agent-Skills/blob/main/skills/hd2-mod-log-analysis/SKILL.md) / 简体中文

> **置信度:** 来自报告。它背后的事故是真实的；这里没有执行任何脚本。

“这个 mod 什么都没做”这个问题，只能从日志来回答。本技能讲的就是怎么读一份日志，以及怎么
写一个替你读日志的工具。

来自本工作区的动机案例：有个 mod **连续 165 次会话保持沉默**，没有留下任何痕迹。把日志改成
分阶段的，并为它写一个分析器（`stratagem-cooldown/tools/analyze_vehicle_cooldown_log.py`），
才把“什么都没做”变成了“停在 `locate failed`”。

## 前置条件

| 需要 | 原因 | 缺失时 |
|---|---|---|
| Python 3.8+ | 分析器 | — |
| mod 的日志文件 | 证据 | 默认用标准路径，并**说出**它看了什么：`%LOCALAPPDATA%\CowboyBingus\Helldivers2\Logs\<Mod>.log` |
| **不**需要游戏 | 读日志不需要游戏 | — 如果文件不存在，打印尝试过的路径并以非零码退出；不要崩溃 |

只读。它绝不触碰游戏、游戏的文件或游戏的内存。

## 首先：日志本身就是交付物

你无法分析一份不存在的日志。在写分析器之前，先让 mod 把日志打对 —— 这一部分决定了分析
到底有没有可能：

1. **每次状态变化一行**，卡住时另有心跳行。绝不逐帧打。
2. **给每个结果命名，包括负面的那些。**`table located at load`、
   `no vehicle records yet`、`ABORTED + rolled back`、`error: ...`。静默的 `return` 在日志里
   是看不见的；命名过的就是一个阶段。
3. **让序列分阶段**，这样读者能判断它*在哪里*停下：
   ```python
   STAGES = [
       ('locate failed',  re.compile(r'STOPPED at load')),
       ('located',        re.compile(r'table located at load')),
       ('installed',      re.compile(r'v([\d.]+) installed')),
       ('gate',           re.compile(r'uptime gate passed')),
       ('records',        re.compile(r'vehicle records appeared')),
       ('no-records',     re.compile(r'no vehicle records yet')),
       ('applied',        re.compile(r'cooldown applied to')),
       ('rollback',       re.compile(r'ABORTED \+ rolled back')),
       ('error',          re.compile(r'error: ')),
       ('heartbeat',      re.compile(r'heartbeat: ')),
   ]
   ```
4. **在旁边写一个状态文件**，这样即使“面板从未打开”也仍有东西可以发出去。

## 然后：分析它

- **日志会跨启动追加。** 要判断“这一次运行”，按时间戳过滤，而不是按文件位置 —— 从这次会话
  里的某个东西（起始标记、加载行）取一个分界点，而不是假设文件是全新的。
- **时间戳是 UTC。** 在 UTC+8，`12:xx:xxZ` 是本地 20:xx。搞错这一点曾真实地误判过某一行
  属于哪次运行。把两者都打印出来，或者说明哪个是哪个。
- **先分类，再计数。** 先报告阶段序列（按顺序发生了什么），再报告每个阶段的计数。一行孤零零
  的 `applied` 被 4000 条心跳包围，与 `locate failed` 是两种不同的缺陷。
- **当失败跨越两个 mod 时，把它们关联起来。** 加载器会介入其他 mod，所以答案可能在两个文件
  里：同时接受 `--log` **和** `--smooth-log`，按时间戳对齐它们，并报告合并后的序列。
- **`--json`**，这样报告可以引用精确数字，而不是转述。
- **绝不用转述抹掉原始行。** 在每个分类旁边附上匹配到的日志行（或它的行号），这样人能自己
  去查。

## 骨架

```python
"""Read <Mod>'s runtime log and report what the addon actually did, stage by stage.

    python -B tools/analyze_<mod>_log.py
    python -B tools/analyze_<mod>_log.py --log <path> --smooth-log <path> --json

Read-only diagnostic: it never touches the game, its files or memory. It exists because
"the mod does nothing" is only answerable from the log, and the 1.5.x family proved that a
mod can stay silent for 165 sessions without leaving a single trace.
"""
import argparse, collections, datetime, io, json, os, re, sys

DEFAULT_LOG = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'CowboyBingus',
                           'Helldivers2', 'Logs', '<Mod>.log')
```

报告形状：阶段序列、每个阶段的计数、第一个和最后一个时间戳、本次运行的行数，以及任何逐字
引用的 `error:` / `rollback` 行。当日志缺失、或在所选窗口内没有任何内容时以非零码退出 ——
空报告不能看起来像通过。

## 局限

- 它只能看见 mod 记录下来的东西。如果 mod 被加载器跳过了，那就根本没有日志 —— 先检查
  `BingusSharedLoader.log`，它会说明该条目是否加载。
- 正则阶段匹配的好坏，取决于日志的自律程度：共享同一条消息字符串的两个功能无法区分开。
- 日志说的是 mod *以为*的事；它不是游戏行为的独立证据。对任何用户可见的东西，都要配一张
  截图或一次游戏内观察。

## 延伸阅读

`writing-mod-tools`（退出码、`--json`、前置条件、诚实的局限），
以及 `docs/hd2-mod-failure-catalog.md` §7 讲一开始该记录什么。
