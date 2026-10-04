---
name: hd2-ffi-audit
description: Static check that every C symbol a Helldivers 2 Lua mod calls is declared, and that no declaration conflicts with one another mod may have made — because LuaJIT's ffi.cdef keeps the first declaration, a wrong prototype silently disables another mod. Use before packaging any mod that uses ffi, or when a mod loads but an action throws "missing declaration for symbol".
---

# hd2-ffi-audit

> **Confidence:** the scanner runs, but its rules are reported, not re-derived from the loader. Its known blind spots are listed below. See [verification status](../../docs/verification-status.md).

English / [简体中文](https://github.com/YC426/HD2-Agent-Skills/blob/main/skills/hd2-ffi-audit/SKILL_cn.md)

`scripts/ffi_audit.py` reads Lua source as text and reports two classes of breakage that have
both shipped in this ecosystem:

1. **Called but not declared.** `k.VirtualAllocEx(...)` without a matching `ffi.cdef` is a
   hard error at the call site. It shipped once as *"clicking a card does nothing"*.
2. **Declared differently by someone else.** LuaJIT's C namespace is process-global and
   `ffi.cdef` **keeps the first declaration**. A mod that declared `GetCursorPos(int32_t*)`
   displaced another mod's `HD2CS_POINT*` form and that mod disabled itself for the whole
   session.

## Prerequisites

| Need | Why | If missing |
|---|---|---|
| Python 3.8+ | the script | — |

Nothing else: **no LuaJIT, no lupa, no game, no network.** It is a regex scanner over text, and
it writes nothing.

## Use

```powershell
python -B scripts/ffi_audit.py path\to\mod.lua
python -B scripts/ffi_audit.py work\standalone\*.lua      # one report per file
```

Exit 0 = every called symbol is declared; non-zero = at least one missing, listed with the
line number of its first call.

It recognises all three declaration styles used in this ecosystem:

- `ffi.cdef[[ ... ]]` blocks
- `pcall(ffi.cdef, 'int Foo(void*);')` one-liners
- `bind('int (*)(int32_t *)', 'GetCursorPos')` (resolved through `GetProcAddress`)

## What it cannot do

Be aware before you trust it:

- It is **regex-based**, so a symbol reached through a macro, a typedef or a computed name is
  not seen.
- It checks that a symbol *is declared somewhere*, not that the prototype is **correct**. The
  user32 rule (`hd2-addon-build`) exists because a plausible-looking wrong prototype is the
  dangerous case, and only a whitelist catches it.
- It has no knowledge of other mods' declarations; it can tell you a declaration *may*
  conflict (the symbol is in the known user32 set) but not that it *does*.
- It says nothing about whether the symbol exists in the loaded library.

For the runtime half — a `cdef` string with a typo that the regex accepts — log the failure
instead of swallowing it:

```lua
for _, d in ipairs(FFI_LIST) do
    local ok, err = pcall(ffi.cdef, d)
    if not ok then log('ffi.cdef FAILED for: ' .. d .. ' -- ' .. tostring(err)) end
end
```

## See also

`hd2-addon-build` runs an equivalent check as a build gate (plus the user32 refusal);
`writing-mod-tools` for why the limits above are stated here rather than discovered by a user.
