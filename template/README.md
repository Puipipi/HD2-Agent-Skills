# template/ — a minimal, contract-correct HD2 mod skeleton

> 中文版：[README.zh-CN.md](README.zh-CN.md)

`panel_skeleton.lua` is a starting point that is deliberately boring. It draws nothing
meaningful; it exists to get the three expensive rules right from line one, before any
feature code hides a violation of them.

| File | What it is |
|---|---|
| `panel_skeleton.lua` | The skeleton. Drop it into a loader as an addon. |
| `../tests/test_panel_skeleton.py` | Offline harness: runs the skeleton on real LuaJIT with a fake engine. |

## The three rules it enforces

1. **A guard is a value check, not `pcall`.** `pcall` traps Lua errors only; a NULL engine
   slot or a bad pointer faults natively and kills the frame callback for the session.
   See `native_ok`, `callable`, and `read_mem`.
2. **Staged bring-up, advancing only on a positive fact.** Six named stages, re-checked
   every frame, each hold logged once with its reason. Nothing is latched as impossible on
   one early failure — engine libraries are built late.
3. **A frame error budget.** Five consecutive failures stop the feature and leave a named
   reason; the game keeps running.

Plus the supporting habits that make a mod diagnosable: a log line per state change,
a `-STATUS.txt` written even when nothing works, and a `MOD.work` seam so the failure path
is testable.

## Run the tests first

```powershell
python -B tests/test_panel_skeleton.py
```

It needs `lupa` (LuaJIT inside CPython). It does four things without the game:

* runs the workspace `ffi_audit.py` static check — every C symbol you *call* must be
  declared, because a missing declaration is a hard error at the call site;
* compiles the skeleton on LuaJIT 2.1 and asserts no engine writes / no allocations;
* drives it against a fake engine in four states — no engine, engine without a ship world,
  full engine, and a failing per-frame body — asserting that no GUI is created too early,
  that the stages stop at the right place, and that the error budget stops a broken loop;
* checks the STATUS file exists after load.

All 24 checks pass as committed. If you edit the skeleton, keep them passing: two of the
bugs this file has already had were invisible in review and instant in this harness.

## Using it for a real mod

1. Change `KEY`, `MOD.version` and the log/status names.
2. Adapt the `register()` section at the bottom to your loader's update hook. Call
   `MOD.tick(frames)` from it, or wire `MOD.frame` to the loader's callback — keep the
   budget wrapper in the path either way.
3. Add your feature work inside `MOD.work` (or replace the marked block in `frame`).
4. For anything that draws or takes input, read
   [`../skills/hd2-in-game-panel/SKILL.md`](../skills/hd2-in-game-panel/SKILL.md) and
   [`../skills/hd2-native-panel-input-lock/SKILL.md`](../skills/hd2-native-panel-input-lock/SKILL.md)
   before adding the calls.
5. Re-run `ffi_audit.py` on the result — every new `ffi.cdef` symbol needs its declaration
   in the list, and a wrong declaration can silently displace another mod's.

## What is *not* verified

The skeleton compiles, loads, stages, holds, fails and stops correctly **on a fake
engine**. It has not been deployed into a running game. Stage boundaries, frame numbers
and the ship-world timing are from the reference mods' logs, not from this file's own
run — treat its first live run as a test, and watch for the `stage N (...) held:` lines to
tell you which precondition is the one that is not true yet.
