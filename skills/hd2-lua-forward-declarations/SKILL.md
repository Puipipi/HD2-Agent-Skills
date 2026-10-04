---
name: hd2-lua-forward-declarations
description: Fix the Lua failure where a function is called before its definition, so the call resolves to nil and fails silently — the pattern behind "I changed the setting and nothing happens". Use when a callback, rescan or refresh does nothing with no error, when a feature silently stopped working after a refactor, or when writing a mod where one function calls another defined further down the file.
---

# Lua forward declarations: the bug that reports nothing

English / [简体中文](https://github.com/Puipipi/HD2-Agent-Skills/blob/main/skills/hd2-lua-forward-declarations/SKILL_cn.md)

```lua
local function rescan() ... end   -- defined at line 900

register_option('x', { on_change = function(v) rescan() end })  -- registered at line 300
```

At registration the closure is built; at **call** time `rescan` is looked up. If the definition has
not executed yet, the upvalue holds `nil`, and `rescan()` is an attempt to call a nil value — inside a
callback that the framework often swallows. The option renders, the player clicks, the value moves, and
nothing happens. No error reaches the user.

## Provenance and confidence

This is not a hypothetical. In `mods/stratagem-cooldown`, deleting the definition of `mom_rescan`
while leaving its call site behind produced exactly this: in-game changes had no effect at all, and
the "rewrite every 10 seconds" loop had never once run. That single defect accounted for **every**
symptom from 3.0.0 to 3.7.0. It was found by comparing the call site against the definitions list,
not by reading the symptom.

## The rule

**Declare the local before anything can capture it; assign it where the body naturally lives.**

```lua
-- near the top, before any closure that might call it
local rescan

-- ... registration and other code that references rescan ...

-- where the implementation belongs
function rescan()
    ...
end
```

`local rescan` creates the binding; the later assignment fills it. Closures capture the **binding**,
not the value, so a call after the assignment works, and a call before it fails for a reason you can
see.

## Guard every call site that could run early

A forward declaration fixes ordering you control. It does not fix ordering you do not: a framework
callback, a timer, or another mod's hook can fire before your assignment.

```lua
if type(rescan) == 'function' then rescan() end
```

And prefer logging the guard's refusal over skipping quietly:

```lua
if type(rescan) ~= 'function' then
    log('rescan not ready yet (configuration changed before init finished)')
    return
end
```

## Why this class of bug is expensive

- **It fails at call time, not at definition time**, so a file compiles and loads cleanly.
- **The error lands in a callback the framework may pcall**, so it never reaches a log or a popup.
- **It looks like the setting is not being read**, so the natural next move is to debug the config
  parser or the memory write — the wrong subsystem entirely. That is exactly the detour this cost.
- **It appears after refactors**, when a definition moves below its first caller. Nothing else changes,
  so it reads as "this feature broke by itself".

## How to find it, rather than guess

Do not start from the symptom ("the setting does not apply"). Start from the **call graph**:

```powershell
# every local function definition, with line numbers
Select-String -Path src\*.lua -Pattern '^\s*local function (\w+)' |
  ForEach-Object { "{0,5}  {1}" -f $_.LineNumber, ($_.Matches[0].Groups[1].Value) }

# every call to one of them
Select-String -Path src\*.lua -Pattern 'rescan\s*\(' |
  ForEach-Object { "{0,5}  {1}" -f $_.LineNumber, $_.Line.Trim() }
```

If a call site has a **lower line number** than the only definition, and the call can happen before the
file finishes executing, that is the bug. A definition that is missing entirely shows up as a name
that is called and never defined — check that too, because a deleted definition with a surviving call
site is the same failure with a different cause.

Cheap mechanical check, worth running before every test round:

```lua
-- offline: assert that everything the mod calls exists by the time it is called
for _, name in ipairs({'rescan', 'apply', 'refresh'}) do
    assert(type(_G[name] or _ENV[name]) == 'function', name .. ' is not defined')
end
```

## The generalisation

This is one instance of a broader rule that the same project learned twice: **a gate that cannot
report its own failure will be read as a negative result.** A `nil` call, a `pcall` that returns
`false` without being checked, a registration that returns a reason nobody logs — all three look
identical from outside: "the feature does not work", with no clue which layer refused.

When a feature silently does nothing, add instrumentation at the layer **between** the user action and
the effect, and make it name what it refused and why. Do that before re-reading the logic, because the
logic is usually fine.
