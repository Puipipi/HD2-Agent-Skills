---
name: hd2-addon-package-inspector
description: Inspect a built Helldivers 2 addon ZIP before shipping — manifest fields and GUID, the Addon archive's binary header, entry ranges, the resource name-to-hash mapping, declared-but-missing icons, and whether the packaged resource really contains the source you built. Use after a build, before uploading or deploying, or when a mod manager refuses an import the build called successful.
---

# hd2-addon-package-inspector

> **Confidence:** verified here — its hash matches the loader's three published vectors and it exits non-zero if they disagree. See [verification status](../../docs/verification-status.md).

English / [简体中文](https://github.com/YC426/HD2-Agent-Skills/blob/main/skills/hd2-addon-package-inspector/SKILL_cn.md)

`scripts/inspect_package.py` reads the artifact, not the build log. A build that says "built
OK" has proven nothing about the ZIP: the loader will **silently skip** a package it cannot
read, and a mod site's "import failed" tells you nothing.

## Prerequisites

| Need | Why | If missing |
|---|---|---|
| Python 3.8+ | the script | — |

**No lupa, no LuaJIT, no game, no network.** Read-only: it never writes and never unpacks to
disk.

## Use

```powershell
python -B scripts/inspect_package.py dist/My-Mod-1.0.0.zip
python -B scripts/inspect_package.py dist/My-Mod-1.0.0.zip --source work/standalone/mymod.lua
python -B scripts/inspect_package.py dist/My-Mod-1.0.0.zip --resource mods/yourauthor/mymod --json
```

Exit 0 = every check passed; non-zero = a check failed, named on stdout. It always prints the
package size and SHA-256, which is what the next person uses to confirm they have your file.

## What it checks

| Group | Checks |
|---|---|
| structure | `manifest.json`, `README.txt`, exactly one `Addon/*.patch_0`, both sidecars (`.stream`, `.gpu_resources`) |
| manifest | `Version`, `Guid`, `Name` present; GUID is a UUID; `Version == 1`; `Options[].Include` contains `Addon`; **any declared `IconPath`/`Image` is actually packaged** (a dangling reference shows a blank manager entry) |
| archive | magic `0xF0000011`, version 1, entry count, each entry's resource type, each entry's data range inside the file, each resource's 8-byte header (version 2, body length matches) |
| identity | the resource name → 64-bit hash mapping resolves to a real entry; the name matches the allowed `mods/<author>/<entry>` shape |
| hash self-test | before any of the above, the name→hash implementation is checked against the **three published vectors** (`core/wwise/lua/wwise_flow_callbacks` → `0x7251FDD9BB62480A`, `mods/codex/gun_calibration` → `0x9537023F38D32BCD`, `mods/example_author/example_addon` → `0x835DB1516CA1E1CA`). If the hash is wrong, every identity check below is meaningless, so the tool refuses to continue and exits 1 |
| declaration | the resource carries a `-- HD2-Addon: <name>` line, and it matches `--resource` when given |
| source (`--source`) | the packaged bytes contain the source you built, and its version string matches the ZIP's file name |

## One detail worth knowing

The declaration is **not** at offset 0 of a resource. Each resource is a
`<u32 body length><u32 version=2>` header followed by the entry body (which itself starts with
the `-- HD2-Addon:` line). A verifier that assumes the obvious layout reports false failures —
the first version of this tool did exactly that.

## Limitations

- It validates the **envelope**, not the mod: a package can pass every check and still do
  nothing at runtime.
- It cannot prove the **manager** will accept the import. Import is a different code path from
  export, so confirm it once by hand (see `tests/probe-build/README.md`).
- It does not verify that the archive's other `patch_N` numbering matches the destination
  slot — a deployer's job, not a package's.

## See also

`hd2-addon-build` (produces what this inspects), `writing-mod-tools` (read the artifact, not
your own success message).
