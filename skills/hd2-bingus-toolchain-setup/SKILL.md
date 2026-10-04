---
name: hd2-bingus-toolchain-setup
description: Put the Bingus/MDL addon packaging tools (build_addon.py, archive.py) where a build expects them, by locating them on this machine instead of redistributing them — searches explicit paths, every installed mod's scripts/tools/vendor folders, and the local checkout, reports what it found as a checklist, and copies only when asked. Use when a build fails with "No module named build_addon", or when setting up a new mod repo.
---

# hd2-bingus-toolchain-setup

> **Confidence:** discovery was verified here; the copy-then-build loop and `--url` were not run.

English / [简体中文](https://github.com/Puipipi/HD2-Agent-Skills/blob/main/skills/hd2-bingus-toolchain-setup/SKILL_cn.md)

`scripts/fetch_bingus_tools.py` finds the two third-party files that encode the loader's
addon envelope and copies them into `vendor/bingus/`.

**Why this is a tool and not a bundled file:** they are somebody else's code, and this
repository deliberately does not redistribute them. Instead of making you hunt for them, the
tool looks in the places they realistically already exist on your machine.

## Prerequisites

| Need | Why | If missing |
|---|---|---|
| Python 3.8+ | the script | — |
| **`build_addon.py` + `archive.py` somewhere on this machine** | they are the build dependency; they are not shipped here | exit 1 with instructions: get them from the loader author, or pass `--from` |
| a Bingus/MDL installation, if relying on auto-discovery | that is where the tools are found | use `--from <folder>` with a copy you obtained |
| network **only** if you pass `--url` | explicit opt-in download | never used automatically |

## Use

```powershell
# what exists on this machine? (copies nothing)
python -B scripts/fetch_bingus_tools.py --list

# copy the complete set into a build:
python -B scripts/fetch_bingus_tools.py --dest work/standalone/vendor/bingus

# from a specific place you obtained:
python -B scripts/fetch_bingus_tools.py --from "D:\src\bingus" --dest work/standalone/vendor/bingus

# explicit download (never automatic; verify before shipping):
python -B scripts/fetch_bingus_tools.py --url https://<host>/<path> --dest ... 
```

Exit codes: `0` copied (or listed successfully), `1` nothing found, `2` refused because the
destination is non-empty — pass `--force` if you really mean to overwrite.

## Where it looks, in order

1. `--from <path>` — an explicit file or folder
2. every installed mod folder: `%LOCALAPPDATA%\hd2arsenal\mods\*\scripts|tools|vendor|vendor/bingus`
   — the loader and several mods ship these as `scripts/build_addon.py`
3. the local checkout's own `vendor/bingus`, `tools` and `scripts` folders

It reports each candidate with an `OK` / `--` mark per required file, so a partial find is
obvious rather than a surprise at build time.

## After it runs

The tools are third-party. Keep them **out of anything you publish** and record the source:

```markdown
# THIRD_PARTY_NOTICES.md
The addon packaging tools (`build_addon.py`, `archive.py`) were obtained from <source>
and are not redistributed here. Obtain them with the appropriate upstream permission.
```

If the folder already contains them, the script refuses to overwrite — a partially different
version is how two builds start disagreeing about the same archive.

## Limitations

- It does not validate the tools it copies: they could be an older or patched version. If the
  build then produces packages the manager rejects, compare against a known-good release.
- `archive.py` may reference optional build inputs of the loader author's own tree (a LuaJIT
  binary, a boot blob). Those are not needed to package a normal addon; if yours requires
  them, the build will say so.
- `--url` performs no signature or hash verification. That is deliberate — the tool cannot
  know the right hash — but it means an explicit download is your responsibility.

## See also

`hd2-addon-build` (the consumer), `hd2-addon-package-inspector` (verifies the output),
`writing-mod-tools` (search before asking; never redistribute what you may not).
