---
name: hd2-addon-build
description: Build a Helldivers 2 Bingus/MDL Lua mod into a mod-manager-importable ZIP, refusing to package when the source fails a gate — LuaJIT's per-function instruction cap (an oversized mod is silently skipped by the loader), a user32 ffi.cdef declaration (it displaces another mod's declaration), a called-but-undeclared C symbol, or a missing in-game README block. Use to package a HD2 Lua mod, or when a mod loads but does nothing.
---

# hd2-addon-build

`scripts/build_mod.py` turns one plaintext Lua entry into the addon envelope a mod
manager imports, and stops before packaging when the source is unsafe to ship.

## Prerequisites

| Need | Why | If missing |
|---|---|---|
| Python 3.8+ | the script | — |
| **`lupa`** (`python -m pip install lupa`) | `--validate-only` compiles the source with **LuaJIT 2.1**. Every gate that matters depends on this. | the build aborts; do not fall back to plain Lua 5.1, which accepts sources LuaJIT will silently drop |
| **`vendor/bingus/build_addon.py` + `archive.py`** | they encode the loader's archive format. **Not bundled** (third-party). | `hd2-bingus-toolchain-setup` fetches them into place |
| A `GUID` you own | the manager recognises an upgrade by GUID | generate one UUID and **reuse it for every release** |
| The source in plaintext UTF-8 | no BOM, no bytecode, no `\0` | the loader skips the package |

Not needed: the game, the loader, network access. The build never deploys — deployment
is a separate, deliberate step.

## Configure

Edit the CONFIG block at the top of `scripts/build_mod.py`:

```python
MOD_SOURCE   = os.path.join(W, "mymod.lua")        # your entry
RESOURCE     = "mods/yourauthor/mymod"             # mods/<author>/<entry>, underscores only
GUID         = "…"                                 # your UUID, reused across releases
DISPLAY_NAME = "My Mod"
ICON         = os.path.join(W, "icon.webp")        # or None
README_MARKER = "[===[My Mod - quick guide"        # the in-game README lives in the source
VENDOR       = os.path.join(W, "vendor", "bingus")
```

## Use

```powershell
python -B scripts/build_mod.py --validate-only    # gates only, stops before packaging
python -B scripts/build_mod.py                    # -> dist/<Name>-<version>.zip
python -B scripts/build_mod.py --with-source      # also a source bundle, review handoff only
```

## What it checks

1. **LuaJIT compile.** The 65535-bytecode-instruction-per-function cap makes the loader
   skip an oversized mod **silently** — you get a mod that "installed fine" and does
   nothing, with no log line. A plain-Lua compile accepts it.
2. **No `user32` symbol in any `ffi.cdef`.** LuaJIT's C namespace is process-global and
   `ffi.cdef` keeps the *first* declaration, so re-declaring `GetCursorPos` with a
   different prototype disables every mod that declared it first. Ships as a hard refusal.
3. **Every called C symbol is declared.** A missing declaration is a hard error at the
   call site; it once shipped as "clicking the card does nothing".
4. **The README block exists**, and it is extracted from the source into `README.txt`, so
   the in-game guide cannot drift from the code.

It also avoids two packaging mistakes: it advertises an icon only when the file is
actually packaged (a dangling `IconPath` shows a blank manager entry), and it writes
`README.txt` with CRLF.

## Output

```
dist/My-Mod-1.0.0.zip
├─ manifest.json                       Version, Guid, Name, Description, Options[Include:["Addon"]]
├─ Addon/9ba626afa44a3aa3.patch_0      the Lua archive
├─ Addon/9ba626afa44a3aa3.patch_0.stream
├─ Addon/9ba626afa44a3aa3.patch_0.gpu_resources
├─ icon.webp                           only if present
└─ README.txt                          extracted from the source
```

Exit code 0 = gates passed (and packaged, unless `--validate-only`); non-zero = refused,
with the failing gate named on stderr.

## Verify the result

The build says the envelope is *well formed*; it cannot say the manager will accept it.
Check the artifact itself with **`hd2-addon-package-inspector`** before shipping, and
confirm the import + in-game load once by hand.

## Limitations

- It validates the envelope, not your mod's behaviour: a mod that passes every gate can
  still do nothing useful at runtime.
- `RESOURCE` must match the `-- HD2-Addon:` line already in the source, if there is one;
  a mismatch is refused rather than silently rewritten.
- The build never deploys. Paths and slots are in `hd2-bingus-mod-development`.
