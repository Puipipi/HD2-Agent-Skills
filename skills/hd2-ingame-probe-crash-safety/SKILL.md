---
name: hd2-ingame-probe-crash-safety
description: Write an in-game Lua probe or debug addon that cannot take the process down — covering the crash classes `pcall` does not catch, the per-tick script temp-arena discipline, measuring an engine call's cost before multiplying it, startup and menu guards, and the status line that separates "idle" from "reading nothing". Use when adding a diagnostic or measurement addon to Helldivers 2, when a probe is suspected of a crash or a hang, when the game dies with 0xC0000409 or another fail-fast code while a probe is loaded, or when a probe loads but its log shows nothing.
---

# hd2-ingame-probe-crash-safety

English / [简体中文](https://github.com/Puipipi/HD2-Agent-Skills/blob/main/skills/hd2-ingame-probe-crash-safety/SKILL_cn.md)

> **Confidence:** the crash classes and the guards below are **verified in this workspace** — two
> probe builds really did terminate the game (both `0xC0000409` fail-fast), and both times the
> loader log, the probe log and a crash dump together identified the cause. The guard patterns
> are **reported** from mods that already run in this workspace and are cited as such.

An in-game probe is a guest inside a real-time engine, not a script in a sandbox. The boundary
that matters: **`pcall` catches Lua errors and nothing else.** A native fault past that boundary
ends the process, and it takes the player's session with it.

## When to use

- You are adding a read-only diagnostic or measurement addon to the running game.
- A probe is suspected of a crash, a freeze or a stutter.
- The game died with `0xC0000409` (`STATUS_STACK_BUFFER_OVERRUN` / `__fastfail`) while a probe was loaded.
- The loader log ends at `mods/<you>/<probe>: loading` with no matching `: loaded`.
- A probe loads fine but its log shows nothing, and you cannot tell "nothing to report" from "reading nothing".

## The two crash classes that actually happened

| | Case A | Case B |
|---|---|---|
| Symptom | fail-fast while the player was **in a menu** | fail-fast **at startup** |
| Loader log | completed, then the process died | last line is `: loading`, no `: loaded`, no `Startup finished` |
| Cause | no per-tick **script temp-arena** save/restore, so it grew until it overflowed | an engine API called with an **invented signature** (`in_session()` with no argument) |
| Cost was | **not** the cause — the per-call cost measured 0.00 ms | — |

Both are avoidable, and neither is caught by `pcall`.

## The rules

### 1. Never invent an engine API signature — copy one from a mod that runs

A missing argument reached native code and took the process down. Every proven mod in this
workspace writes the same call with the session argument:

```lua
-- Copy the signature from a mod that already runs. Do not guess it.
local ok, session = pcall(sr.Network.game_session)
if not ok or session == nil then return false, 'no session' end
local checked, value = pcall(sr.GameSession.in_session, session)   -- WITH the session
if checked then return value == true, 'GameSession.in_session(session)' end
```

Before calling anything unfamiliar, grep the installed mods for it and read every call site. A
`pcall` around a guessed signature buys nothing.

### 2. Save and restore the script temp arena every tick

The proven mods treat this as a per-frame discipline, not an occasional courtesy.

```lua
local saved = sr.Script.temp_byte_count()
-- ...engine reads here...
sr.Script.set_temp_byte_count(saved)
```

Check `sr.Script` and both members are functions first, and wrap the pair in `pcall`. The arena
is not reset for you, so a tick that allocates without restoring grows it.

### 3. Measure the call cost before multiplying the call count

The instinct "fewer calls must be safer" is not the useful question — **what does one call cost?**
Log units-and-milliseconds per key for a few ticks, then decide the rate. In this workspace an
engine query measured 0.00 ms, which is why the crash had nothing to do with call volume; the
mistake was assuming it did.

Bound the tick anyway: measure the tick, back off the interval when it overruns a budget, and
**stop sampling permanently** after a few consecutive breaches. A probe that can degrade the game
is not worth its data.

### 4. Touch nothing during startup, and do not infer state from an object existing

- Nothing at all for the first ~20 s after load; the game is still initialising.
- **Presence is not evidence.** A completely stationary unit with the target's resource id sits on
  the ship, so "the object exists" started a 29-second sampling run while the player was picking a
  stratagem in the loadout. Gate on a property that only the real thing has — for a thrown beacon,
  that it **moved** — and key per-instance state by the unit handle, because the identity string is
  the resource hash shared by every instance.
- A session check answers "is there a session", not "is the player in a mission": it was **true on
  the ship** in this workspace. Do not treat it as a mission gate.

### 5. Emit a status line in every state

A log that stays silent is indistinguishable from a broken probe. Write one line on a fixed
interval with the numbers you actually read — world count, session state and its reason, unit
counts, temp bytes, last tick cost — whether or not anything interesting is happening.

### 6. Flush as you go

A probe's most valuable data is often the run that ended badly. Buffered output written only on a
clean shutdown is lost exactly when you need it.

## Diagnosing a suspected probe crash

| Look at | What it tells you |
|---|---|
| Loader log's **last line** | `: loading` with no `: loaded` means it died inside your addon |
| `Startup finished: N loaded, M failed` | present in this session? if not, startup never completed |
| Crash dump and its exception stream | the code; `0xC0000409` is fail-fast, not a plain access violation |
| Probe log's last lines | which of your own steps ran |
| GameGuard / `NxStorage_*.txt` DirectStorage errors | **noise** — every session has 15–20, including sessions that ran fine |

## Quick reference

| Rule | Cheap form |
|---|---|
| API signature | grep the installed mods and copy the call, argument list included |
| Temp arena | `temp_byte_count()` / `set_temp_byte_count()` around every tick |
| Cost | log units + ms per call, then pick the rate; budget, back off, self-disable |
| Startup | ~20 s grace, no engine calls |
| State | gate on a property only the real target has; never on presence |
| Observability | one status line per interval in every state |
| Durability | flush the log as it goes |

## Common mistakes

| Mistake | Reality |
|---|---|
| "`pcall` will catch it" | It catches Lua errors only. Native faults end the process. |
| "Fewer calls is safer" | The wrong axis. Measure the per-call cost, then bound the tick. |
| "The object exists, so the event happened" | A stationary prop exists on the ship. Gate on behaviour. |
| "`in_session` means I am in a mission" | It was true on the ship here. Find a mission-specific signal. |
| "The GameGuard errors must be it" | Every session logs 15–20 of them, healthy ones included. |
| "I will add the guards after it works" | The guards are what make it work. They killed two builds here. |

## Related

- `hd2-live-memory-probe` — the read-only probe *outside* the process, where none of this applies.
- `docs/hd2-mod-failure-catalog.md` — the wider symptom → cause → fix catalogue.
- `writing-mod-tools` — prerequisites, exit codes, `--json`, honest limits.
