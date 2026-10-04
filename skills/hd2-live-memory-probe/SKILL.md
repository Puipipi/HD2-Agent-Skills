---
name: hd2-live-memory-probe
description: Write and run a read-only live probe against the running Helldivers 2 process to verify a mod's pointer chain, module base, function signature or field offset without burning another in-game run — PROCESS_VM_READ handles, module enumeration, VirtualQuery page guards, version fingerprints, dual-source cross-checks, and --json output that an offline analyzer can consume later. Use when an address or signature is suspect, when a probe logged zeros, or before shipping anything that depends on absolute offsets.
---

# hd2-live-memory-probe

English / [简体中文](https://github.com/Puipipi/HD2-Agent-Skills/blob/main/skills/hd2-live-memory-probe/SKILL_cn.md)

> **Confidence:** the technique is reported from probes in this workspace; the probe skeleton itself has never been run against a live game here.

A live probe answers one question — *is this address chain what the mod thinks it is?* — while
the game is running, in seconds, instead of in another deployment + mission + log cycle.

Written from the probe/checker pairs in this workspace (`mobility-optimization/tools/*`,
`melee-vehicle-rescue/tools/*`, `stratagem-cooldown/tools/measure_overhead.py`).

## Prerequisites

| Need | Why | If missing |
|---|---|---|
| Windows + Python 3.8+ | `ctypes` with `kernel32`/`psapi` | — |
| **the game running** | the whole point: a live process | exit 2 with "start Helldivers 2 first", not an exception |
| the target **PID** | never guess which process; pass `--pid` | enumerate `helldivers2` and say what was found |
| `PROCESS_QUERY_LIMITED_INFORMATION` + `PROCESS_VM_READ` | opening the process | `OpenProcess failed (5)` = access denied; report it as such |
| a **version fingerprint** of the build | offsets are build-specific | refuse to interpret offsets when the fingerprint does not match |

Read-only: open with `PROCESS_VM_READ`, never `PROCESS_VM_WRITE`, never call into the game,
never install a hook, never touch input or the window. Say all of that in the docstring.

## What a good probe does

1. **Resolve the module base two ways and print both when they disagree.** One probe logged
   `exe_img=0x0` while `game_img` was fine; the module list and the probe's own PE
   `SizeOfImage` parse disagreed, and only printing both made that visible. A single source
   that happens to be wrong is indistinguishable from an address that is wrong.
2. **Guard every read against page state**, so a probe never faults:
   ```python
   # only committed, private, readable pages; never guard/noaccess
   if state != 0x1000:                 # MEM_COMMIT
       return None, 'not MEM_COMMIT'
   if prot == 0 or prot % 256 == 1 or prot >= 0x100:
       return None, 'unreadable protection'
   ```
3. **Bound every read** (length and address) before calling `ReadProcessMemory`, and treat a
   short read as failure, not as a shorter buffer.
4. **Resolve one level at a time and report which level failed.** "chain broken at level 3
   (binding map owner = 0x0)" is a diagnosis; "read failed" is not.
5. **Print the facts, not a verdict**: capacity, count, first buckets, raw field values —
   then let the checker decide. A probe that only prints PASS/FAIL cannot be used to find the
   *new* offset when the old one breaks.
6. **`--json <path>`** so the run can be analyzed offline, compared against a previous run,
   and attached to a report. This is what turns one sample into evidence.
7. **`--pid` explicitly**, or a documented auto-detect that prints what it picked.

## Skeleton

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

## Use it with an offline analyzer

The strongest pattern here is a pair:

- **probe** — runs live, writes `--json` with raw facts (no interpretation)
- **analyzer** — reads the JSON (and the mod's log), correlates, decides

That split lets the same evidence be re-analyzed after you learn more, without another run.
`mobility-optimization/tools/` has both halves (`sample_live.py` + `analyze_mobility_log.py`,
`check_live_probe.py` + `read_live_evidence.py`) — copy the shape.

## Limitations

- Offsets, module sizes and signatures are **build-specific**. A probe that hard-codes them
  without a fingerprint check will report confident nonsense after a game update.
- A live probe cannot tell you whether a *write* would be safe, only whether a read works.
- `PROCESS_VM_READ` on a protected process fails; report the failure mode rather than
  retrying with more access.

## See also

`writing-mod-tools` for the rules this tool follows (read-only default, exit codes, `--json`,
prerequisites, honest limits). `docs/hd2-mod-failure-catalog.md` §5 for the memory-read
safety rules.
