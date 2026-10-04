---
name: hd2-offline-engine-harness
description: Test a Helldivers 2 Lua mod offline by faking the engine boundary with lupa on real LuaJIT — count GUI creates/destroys, drive a staged bring-up through no-engine / no-world / full-engine / failing-body states, exercise a frame error budget, and assert invariants that otherwise cost a live run. Use when adding an offline test for a mod, or when you want to catch a boot-order or teardown bug without deploying.
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
