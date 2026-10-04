---
name: hd2-mod-options-menu
description: Build an in-game settings page for a Helldivers 2 mod with the ModOptionsMenu (MOM) framework — the real registration contract, the two types it accepts, the 2-16 option limit, index-valued choices, and the single-owner rule for two controls writing one setting. Use when a mod needs user-facing options, when options silently fail to appear, or when a value changes in the page but nothing happens in game.
---

# ModOptionsMenu: the in-game settings page framework

English / [简体中文](https://github.com/Puipipi/HD2-Agent-Skills/blob/main/skills/hd2-mod-options-menu/SKILL_cn.md)

MOM is how a mod gives the player options without shipping a config file to hand-edit. Its contract
is small, and almost every part of it fails **silently** — a rejected option simply does not appear,
and a page that ignores a change logs nothing.

## Provenance and confidence

Taken from a working addon rather than guessed: the contract below is transcribed from
`mods/stratagem-cooldown/src/vehicle_cooldown.lua` **L1490–1500**, which states it was itself taken
from **ExoLoadout v0.8.0**, an addon known to work. The failures in the traps section are that mod's
own recorded incidents (v2.2.2 → 4.1.0, all reproduced on the day).

**Corrects an error elsewhere in this repository:** `hd2-offline-data-workflow` used to claim MOM
accepts `slider`. It does not, and that claim has been fixed — the source comment at L1494 reads
`spec.type = 'toggle' | 'choice' -- those two are what it really takes`.

## The contract

```lua
local host = rawget(_G,'ModOptionsMenu')   -- rawget, and check it exists
-- host.api == 1

host.register_option(id, spec)
--   spec.type        = 'toggle' | 'choice'      ONLY these two
--   spec.mod         = the mod's display name
--   spec.label       = the row's label
--   spec.description = the row's description
--   spec.choices     = { 'text', ... }          choice: 2 to 16 entries
--   spec.default     = <INDEX into choices>     a NUMBER, not the text
--   (slider: min / max / step)                  asked for, but refused - see traps

host.get(id)                 -- returns the INDEX of the current choice
host.set(id, index)
host.on_change(id, function(value) ... end)
```

The single most important consequence: **every setting with more than two states is a `choice` whose
value is an index.** `spec.default` is a number; `host.get()` returns a number; the callback receives
a number. Passing the option text gets you a row that renders and then does nothing.

Values the option list cannot express stay in `config.txt` — the mod this came from keeps a free
`percent=65` and `uses_add=7` there while the page offers coarse steps.

## Traps, each from a real incident

### `slider` is refused, and refusal is silent

Asked for a real slider, the framework rejected it. The mod that tried it responds by registering a
three-entry `choice` under a fallback id so the setting stays controllable, and logs:

```
menu: slider refused, the three-entry choice is in charge instead
```

Detection: the mod's own attempt showed **7 options registered 2** — the page showed only the two
that happened to be `toggle`s. A count of registered-versus-intended rows is the cheapest check there
is; log it. Implement the fallback rather than assuming the type works.

### A rejected option does not appear, and nothing is logged for you

`register_option` is called inside `pcall`; a rejection comes back as a falsy result with a reason
string. If you do not check it, the option is simply missing from the page. Record every rejection
with its key, its type and the reason:

```lua
local ok, res, why = pcall(host.register_option, id, spec)
if not (ok and res) then
  rejected[#rejected+1] = string.format('%s (%s): %s', o.key, o.kind, tostring(ok and why or res))
end
```

A vague report of "the options are incomplete" is usually one hard framework rule.

### More than 16 choices loses the whole row

The framework refuses a list longer than 16, and the log line names the limit:

```
refused: percent (choice): choices must list 2 to 16 names
```

The row does not truncate — it disappears. Shorten the list (the source mod moved counts to 7 steps
and Eagle to 6) or split the setting into two options.

### Two controls writing one setting fight each other

While experimenting, a percentage existed both as a `choice` and as a `slider`. Both registered,
both wrote the same value, and the last one clicked won.

**Single-owner rule:** the first successfully registered owner of a setting keeps it; every other
control for that setting still renders, but refuses to apply and says why.

```lua
if o.kind=='slider' and not mom.slider_owner then mom.slider_owner = o.key end
-- at change time:
local owned = (o.kind=='slider') and (mom.slider_owner==o.key)
              or (o.kind~='slider' and not mom.slider_owner)
if not owned then
  log('menu: '..o.key..' = '..tostring(v)..' (not applied: '..
      tostring(mom.slider_owner or 'the choice')..' owns this setting)')
  return
end
```

Silently ignoring the loser is the failure mode this prevents: a user clicks a row, sees it move,
and the value does not change.

### A registered callback that calls a function defined later

The mod's "changed in the page, nothing happens in game" symptom had a second cause: the function
itself was `nil` at call time. See `hd2-lua-forward-declarations` — this framework is the worst place
for that bug, because the option renders correctly and the callback fails silently.

### `config.txt` parsing has two paths, and fixing one is not enough

The mod parses its config both sectioned and flat. A fix applied to one parser was overwritten by the
other. When you touch config parsing, find every parser before declaring it fixed.

## What MOM does not support

- **Free text entry.** An exact number the list cannot express belongs in `config.txt`.
- **Arbitrary buttons or action rows.** A player-triggered action needs a different mechanism.
- **Dynamic read-only status lines.** Reported in conflicting terms by the source material: one note
  says it is unsupported, another says making `label`/`description` a function gives a read-only
  status that MOM recomputes when the menu opens. **This is unresolved — test it before relying on
  either.** 
- **Changing a `choice` list after registration.**

Design consequence used by the source mod: give left and right their own independent `choice` pools
rather than one dynamic list.

## The manager side, which fails differently

The in-game page and the mod-manager option tree are separate systems, and both fail silently:

| Symptom | Cause | Fix |
|---|---|---|
| The whole option tree does not appear in the manager | a sub-option used an empty `Include: [""]` as a "UI-only item" | every sub-option's `Include` must point at a directory that really exists and contains a payload; copy a mod known to display correctly |
| With a payload attached, the game crashes or shows a black screen | the sub-option payload was plain-text Lua | wrap it with the same `build_addon()` as the core, and have the packaging self-check compare each payload's first bytes against the core envelope |
| After import, nothing is changed at all | the manager imports with **every** block ticked, and the reader takes each block's first entry — so "off" sorted first | fall back to a built-in config when all blocks are off; better, move settings into the in-game page and ship zero manager configuration |
| Deploying overwrites a new layer with an old one | an old package still sat in the manager's library | re-import the new package before deploying, or use only the layer already in place |

## Testing it without the game

A fake host validates your logic and **not** the framework's behaviour — do not treat it as
acceptance. What it can do is catch the silent classes above: assert that the number of registered
options equals the number intended, that every `spec.default` is a number, and that every accepted
id has a change handler. Those three assertions would have caught every trap in this skill except the
`slider` refusal, which needs the real host.

## Verification checklist

1. Log `registered N of M options` and check the two numbers match.
2. Log every rejection with its key, type and reason string.
3. Log every applied change **and** every refusal-to-apply with the owner's name.
4. Confirm `spec.default` is a number for every `choice`.
5. Change a value in the page and require a **numeric** confirmation in the log (the source mod's
   evidence looks like `780 -> 273`), not "it works now".
