---
name: hd2-offline-engine-harness
description: Test or compare a Helldivers 2 Lua mod offline with lupa on real LuaJIT — fake engine boundaries, count GUI creates/destroys, drive staged bring-up and teardown, exercise a frame error budget, or measure a production hot path against a fixed source ref. Use when adding offline mod tests, diagnosing boot-order/teardown bugs, or checking whether a hot-path change reduces cost without deploying.
---

# hd2-offline-engine-harness

English / [简体中文](https://github.com/Puipipi/HD2-Agent-Skills/blob/main/skills/hd2-offline-engine-harness/SKILL_cn.md)

> **Confidence:** verified here against a fake engine on real LuaJIT; it found two real bugs. It proves your control flow, not the engine's behaviour.

`scripts/test_panel_skeleton.py` is a worked harness: 24 checks that run **without the game**,
in a second, against `template/panel_skeleton.lua`.

You cannot unit-test the engine. You *can* test your code against an **engine boundary**, which
is where the expensive bugs live — a GUI created before the world exists faults natively and
`pcall` cannot catch it, so the only cheap way to find that class of bug is to control the
boundary in a test.

## Prerequisites

| Need | Why | If missing |
|---|---|---|
| Python 3.8+ | driver | — |
| **`lupa`** (`pip install lupa`) | supplies real **LuaJIT 2.1** with `ffi`, not plain Lua 5.1 | the harness cannot run; install it, do not substitute Lua 5.4 |
| the Lua source under test | obviously | — |
| nothing else | no game, no loader, no network | it writes one scratch log directory |

The harness writes a fake `LOCALAPPDATA` under its own folder so the mod's logging does not
pollute the real one. Keep that directory out of version control.

## The pattern

1. **Fake `stingray` and count the calls that matter.**
   ```python
   PRELUDE = """
   CREATED = 0
   WORLD = { name = 'ship' }
   stingray = { Gui = { resolution = function() return 1920, 1080 end },
                World = { create_screen_gui = function() CREATED = CREATED + 1; return {} end },
                Application = { main_world = function() return WORLD end } }
   """
   ```
   Then assert **counts**, not just "no error": two frames must create exactly one GUI.

2. **Drive the four engine states and assert where it stops.**
   | State | Assertion |
   |---|---|
   | no engine at all | no GUI is created; it names the reason it is holding |
   | engine, but no ship world | stops before the GUI stage; `CREATED == 0` |
   | full engine | reaches the last stage; records the resolution; creates at most one GUI |
   | a per-frame body that throws | stops after exactly `FAIL_LIMIT` failures, leaves a reason, does not call the broken work again |

3. **Expose seams so the failure path is reachable.** The skeleton calls `MOD.work(...)`, and
   the test replaces `MOD.work` to force a throw. Replacing the whole frame body would have
   bypassed the very guard under test — the first version of this harness did that and
   "passed" a broken budget.

4. **Point the log somewhere disposable** by overriding `os.getenv`, then read it back:
   ```python
   rt.execute(f"os.getenv = function(n) "
              f"if n == 'LOCALAPPDATA' then return [[{scratch}]] end end")
   ```
   Then assert the diagnostic file *says what happened* (the skeleton's STATUS file must show
   the stage it actually reached).

5. **Test the tooling too**: run the static FFI audit and assert the source compiles on
   LuaJIT, in the same harness. A mod that fails those should never reach a live run.

## Comparing offline hot-path cost

Control-flow tests answer what the code does; a benchmark measures how long that work takes. Neither
replaces the other. For a worked example, see [AutoChat build 10's benchmark
notes](https://github.com/Puipipi/HD2-AutoChat/blob/4445596a76ed387edc3c09d0d25aa9d06ffd5b11/docs/PERFORMANCE-OFFLINE-1.0.0.md)
and
[`bench_frame_performance.py`](https://github.com/Puipipi/HD2-AutoChat/blob/4445596a76ed387edc3c09d0d25aa9d06ffd5b11/work/standalone/bench_frame_performance.py).
Run these commands from the AutoChat checkout root, not this skills repository:

```powershell
python -B work/standalone/bench_frame_performance.py --source-ref 5237d9b --runs 3 --frames 12000 --warmup 1200
python -B work/standalone/bench_frame_performance.py --runs 3 --frames 12000 --warmup 1200
```

Load the same production entry point (`_G.update()` in this example), compare a fixed old ref with
the working source, and record both source SHA-256 values. Use a fresh LuaJIT runtime for each run,
warm it up, then collect samples with QPC inside Lua so Python/Lua boundary calls do not dominate
per-frame timing. Store samples in Lua tables. A standalone fixture once failed while extending an
FFI sample array; that was an instrumentation failure, not evidence of a game or engine fault. Make
GUI stubs count draw/measure calls without retaining every text/draw record, so fixture arrays and
their GC do not pollute timing.

Report steady frames separately from periodic work. The current example runs three fresh runtimes
per case and reports the median: steady-frame mean; periodic-poll mean and p99; and overall mean,
p99, and max. For a **0.05 ms** target, inspect mean, p99, and max together; an overall mean is not a
per-frame upper bound. AutoChat's periodic observation runs every 30 frames; that interval belongs
to this mod and is not a general recommendation to lower check frequency. Record task count, role,
enabled/done/due state, and call counters. A 100/1,000 “future task” fixture must contain
active-role tasks that are enabled, unfinished, and not yet due.

A safe scheduler optimization example is to preflight for any enabled, unfinished, retry-ready
task due for the role selected by the same active/default-role logic as production, before building
and sorting the task-array snapshot. If none is due, skip that snapshot allocation; daily tasks
must use the same date condition. Once something is due, preserve the full task snapshot and sort,
per-item dynamic checks, and send/save/retry side effects. Do not improve numbers by lowering check
frequency or by adding a cross-frame deadline cache without invalidation for changing state.

Fewer calls do not prove faster execution: AutoChat tried a wrapped-text cache, found no stable
gain, and removed it. The default open/redraw case draws only short hints; it does not represent
long text, mixed CJK/English, or many rules. To optimize those cases, add representative inputs and
verify each run really redraws; keep layout-correctness assertions separate from timing. Fake
engine, font mocks, and offline QPC results are not in-game latency evidence and cannot guarantee
that the game stays below 0.05 ms per frame.

## What it found, as evidence this is worth it

Writing this harness against the skeleton found two real bugs that code review had missed:

- a `local` declared **below** the function that used it, so the reference silently compiled to
  a global `nil` and `0 >= nil` raised on the first frame;
- `local ok, a = pcall(fn, ...)` dropping every return value after the first, so a two-value
  engine call always arrived with a `nil` second value and every guard on it failed forever.

Neither is visible by reading. Both are instant in a harness.

## Limitations

- A fake engine proves **your** control flow, not the engine's behaviour. Passing here is not
  evidence that the feature works in game.
- Fixtures drift: if the real API gains a return value or a field, the fake keeps the old
  shape until someone updates it. Treat the fake as part of the code under review.
- It cannot catch native crashes caused by calling a real API at the wrong time; it can only
  catch that your code *tried* to, given the state you simulated.

## See also

`hd2-bingus-mod-development` §4 for how these tests fit the build loop,
`docs/hd2-mod-failure-catalog.md` §9, `writing-mod-tools`.
