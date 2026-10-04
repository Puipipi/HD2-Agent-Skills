---
name: hd2-live-memory-probe
description: 针对正在运行的 Helldivers 2 进程编写并运行一个只读实时探针，用来验证某个 mod 的指针链、模块基址、函数签名或字段偏移，而不必再烧掉一次游戏内运行 —— PROCESS_VM_READ 句柄、模块枚举、VirtualQuery 页守卫、版本指纹、双源交叉核对，以及离线分析器日后可以消费的 --json 输出。当某个地址或签名可疑、当探针记录到的全是零、或在发布任何依赖绝对偏移的东西之前使用。
---

# HD2 实时内存探针

[English](https://github.com/Puipipi/HD2-Agent-Skills/blob/main/skills/hd2-live-memory-probe/SKILL.md) / 简体中文

> **置信度:** 该技术来自本工作区中探针的报告；探针骨架本身从未在这里对运行中的游戏跑过。

实时探针只回答一个问题 —— *这条地址链是否就是 mod 以为的那条？* —— 它在游戏运行期间
几秒钟就给出答案，而不是再走一轮部署 + 任务 + 日志。

内容来自本工作区中的探针/校验器组合（`mobility-optimization/tools/*`、
`melee-vehicle-rescue/tools/*`、`stratagem-cooldown/tools/measure_overhead.py`）。

## 前置条件

| 需要 | 原因 | 缺失时 |
|---|---|---|
| Windows + Python 3.8+ | 用 `ctypes` 调用 `kernel32`/`psapi` | — |
| **游戏正在运行** | 全部意义所在：一个活着的进程 | 以退出码 2 输出 "start Helldivers 2 first"，而不是抛异常 |
| 目标 **PID** | 绝不猜是哪个进程；传 `--pid` | 枚举 `helldivers2`，并说明找到了什么 |
| `PROCESS_QUERY_LIMITED_INFORMATION` + `PROCESS_VM_READ` | 打开进程 | `OpenProcess failed (5)` = 拒绝访问；就照实这样报告 |
| 该构建的**版本指纹** | 偏移是构建特定的 | 指纹不匹配时拒绝解释偏移 |

只读：用 `PROCESS_VM_READ` 打开，绝不用 `PROCESS_VM_WRITE`，绝不调用进游戏，绝不安装钩子，
绝不触碰输入或窗口。把这一切都写进 docstring。

## 一个好的探针做什么

1. **用两种方式解析模块基址，并在两者不一致时把它们都打印出来。** 有一个探针记录到
   `exe_img=0x0`，而 `game_img` 却正常；模块列表与探针自己对 PE `SizeOfImage` 的解析不一致，
   只有把两者都打印出来才让这件事显形。一个恰好出错的单一来源，与一个出错的地址，是无法区
   分的。
2. **对每次读取都做页状态守卫**，这样探针永远不会触发缺页：
   ```python
   # 只接受已提交、私有、可读的页；绝不接受 guard/noaccess
   if state != 0x1000:                 # MEM_COMMIT
       return None, 'not MEM_COMMIT'
   if prot == 0 or prot % 256 == 1 or prot >= 0x100:
       return None, 'unreadable protection'
   ```
3. 在调用 `ReadProcessMemory` 之前**给每次读取设界**（长度和地址），并把短读当作失败，而不
   是当作一个更短的缓冲区。
4. **一次解析一级，并报告是哪一级失败了。**“链在第 3 级断裂（binding map owner = 0x0）”
   是诊断；“读取失败”不是。
5. **打印事实，而不是结论**：容量、计数、最初的若干桶、原始字段值 —— 然后让校验器去判断。
   一个只打印 PASS/FAIL 的探针，在老偏移失效时无法用来找出*新*偏移。
6. **`--json <path>`**，让这次运行可以被离线分析、与上一次运行比较，并附到报告里。正是这一
   点把一个样本变成证据。
7. **显式传 `--pid`**，或者用一个有文档记录的自动检测，并打印它选中了哪个。

## 骨架

```python
"""Read-only live check of <what>.

Runs against a RUNNING Helldivers 2 process and prints what the in-game probe sees, so a
wrong or unreadable address can be diagnosed without another mission. No writes, no game
calls, no hooks. Version-guarded by the shared fingerprint.

Usage:
  python tools/check_<name>.py --pid <pid> [--json out.json]

Prerequisites: the game running; --pid (or it enumerates and prints what it found).
"""
import argparse, ctypes, ctypes.wintypes as wt, json, struct, sys

k32 = ctypes.WinDLL('kernel32', use_last_error=True)
psapi = ctypes.WinDLL('psapi', use_last_error=True)
PROCESS_VM_READ, PROCESS_QUERY_LIMITED_INFORMATION = 0x0010, 0x1000
MEM_COMMIT = 0x1000


class Proc:
    def __init__(self, pid):
        self.h = k32.OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_LIMITED_INFORMATION,
                                 False, pid)
        if not self.h:
            raise SystemExit('OpenProcess failed (%d) - is the game running as another user?'
                             % ctypes.get_last_error())

    def read(self, addr, size):
        buf = ctypes.create_string_buffer(size)
        got = ctypes.c_size_t(0)
        if not k32.ReadProcessMemory(self.h, ctypes.c_void_p(addr), buf, size,
                                     ctypes.byref(got)) or got.value != size:
            return None
        return buf.raw
```

## 配合一个离线分析器来用它

这里最强的模式是一对搭档：

- **探针** —— 实时运行，用 `--json` 写出原始事实（不做解释）
- **分析器** —— 读取那份 JSON（以及 mod 的日志），做关联，下判断

这种分工让同一份证据可以在你了解更多之后被重新分析，而不必再跑一次。
`mobility-optimization/tools/` 两半都有（`sample_live.py` + `analyze_mobility_log.py`、
`check_live_probe.py` + `read_live_evidence.py`）—— 照着这个形状抄。

## 局限

- 偏移、模块大小和签名都是**构建特定的**。一个硬编码它们、又不做指纹检查的探针，会在一次
  游戏更新之后报出自信的胡说。
- 实时探针无法告诉你一次*写入*是否安全，只能告诉你一次读取是否可行。
- 对受保护的进程，`PROCESS_VM_READ` 会失败；报告这个失败模式，而不是用更大的权限去重试。

## 延伸阅读

`writing-mod-tools` 讲本工具遵循的规则（默认只读、退出码、`--json`、前置条件、诚实的局限）。
`docs/hd2-mod-failure-catalog.md` §5 讲内存读取的安全规则。
