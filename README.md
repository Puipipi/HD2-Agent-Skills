# HD2 Agent Skills

English / [简体中文](https://github.com/Puipipi/HD2-Agent-Skills/blob/main/README_cn.md)


Agent skills for driving **Helldivers 2** unattended on Windows — and for building,
validating and packaging the mods that make it automatable. Every coordinate, key
sequence and failure mode here came from real runs.

The game gives no automation API: an agent has to work through window focus, synthetic
input, in-game menus, and mod logs. These skills exist so the next person does not have to
rediscover that.

**Writing a mod rather than driving the game?** Start with the
[failure catalog](docs/hd2-mod-failure-catalog.md) — it is organised symptom-first, and its
first section is the rule that costs the most time (`pcall` does not catch native crashes).
Then take the [mod skeleton](template/SKELETON.md): a minimal addon that gets the three
expensive rules right, with an offline harness (`hd2-offline-engine-harness`) you can run
without the game.

## Skills

Each skill is one topic. Tool skills ship the tool itself, with its prerequisites written
down. A `_cn` file next to any document is its Chinese version.

### Pipeline and techniques

| Skill | 中文 | Purpose |
|---|---|---|
| [`hd2-bingus-mod-development`](skills/hd2-bingus-mod-development/SKILL.md) | [中文](skills/hd2-bingus-mod-development/SKILL_cn.md) | The whole pipeline for a Bingus/MDL Lua mod: repo layout, the source contract the loader enforces, the build gates, offline simulation, the addon ZIP, deployment paths and rollback, in-game log evidence, and the release discipline. |
| [`hd2-mission-entry`](skills/hd2-mission-entry/SKILL.md) | [中文](skills/hd2-mission-entry/SKILL_cn.md) | Cold start to boots-on-ground: launch, skip intro, confirm ship readiness, star-map mission selection, briefing loadout, deploy, and the evidence to confirm each step. Ships the focus-verified key/mouse tools and lists the mods the sequence depends on. |
| [`hd2-in-game-panel`](skills/hd2-in-game-panel/SKILL.md) | [中文](skills/hd2-in-game-panel/SKILL_cn.md) | Draw a clickable mod panel inside the game with only `Gui.rect` — retained screen-GUI lifecycle, staged bring-up, layer/native-screen invalidation, region hit-testing, dragging, and a 4x5 pixel font plus packed CJK bitmaps. |
| [`hd2-native-panel-input-lock`](skills/hd2-native-panel-input-lock/SKILL.md) | [中文](skills/hd2-native-panel-input-lock/SKILL_cn.md) | Open the panel on a hotkey (F7), unlock the mouse, and keep the game from receiving keyboard/mouse while it is open — raw-input deregistration, a window-procedure filter, coordinate conversion, wheel notches, safe give-back. |
| [`hd2-game-language-autodetect`](skills/hd2-game-language-autodetect/SKILL.md) | [中文](skills/hd2-game-language-autodetect/SKILL_cn.md) | Decide automatically whether the client is Chinese or English — build-verified `game.dll` offsets, with an engine-font glyph-coverage fallback, and labels localized at draw time only. |

### Tools (each ships its own script)

| Tool skill | Script | What it is for |
|---|---|---|
| [`hd2-addon-build`](skills/hd2-addon-build/SKILL.md) | `scripts/build_mod.py` | Package a mod into a manager-importable ZIP, refusing when the source fails a gate. |
| [`hd2-addon-package-inspector`](skills/hd2-addon-package-inspector/SKILL.md) | `scripts/inspect_package.py` | Read the built ZIP: manifest, archive header, name→hash mapping, declared icons, and whether it really contains the source you built. |
| [`hd2-ffi-audit`](skills/hd2-ffi-audit/SKILL.md) | `scripts/ffi_audit.py` | Static check that every called C symbol is declared, and none collides with another mod's declaration. |
| [`hd2-bingus-toolchain-setup`](skills/hd2-bingus-toolchain-setup/SKILL.md) | `scripts/fetch_bingus_tools.py` | Find the third-party addon packaging tools on this machine and put them where a build expects them. |
| [`hd2-offline-engine-harness`](skills/hd2-offline-engine-harness/SKILL.md) | `scripts/test_panel_skeleton.py` | Test a mod offline against a faked engine boundary on real LuaJIT — GUI counts, staged states, error budget. |
| [`hd2-bilingual-doc-verify`](skills/hd2-bilingual-doc-verify/SKILL.md) | `scripts/verify_translations.py` | Keep `X.md` / `X_cn.md` pairs honest: code fences, heading structure, links, frontmatter. |
| [`hd2-live-memory-probe`](skills/hd2-live-memory-probe/SKILL.md) | — (pattern + skeleton) | Write and run a read-only probe against the running game to verify an address chain without another mission. |
| [`hd2-mod-log-analysis`](skills/hd2-mod-log-analysis/SKILL.md) | — (pattern + skeleton) | Turn "the mod does nothing" into a named stage, and write the analyzer that says so. |
| [`hd2-crash-reporting-and-settings`](skills/hd2-crash-reporting-and-settings/SKILL.md) | [中文](skills/hd2-crash-reporting-and-settings/SKILL_cn.md) | Turn the crash reporter, dump writer and crash screenshot on or off in `data/settings.ini`, control the crash folders in `%APPDATA%`, and see why `floating_point_exceptions` is not just another reporting switch. |
| [`hd2-mod-release-operations`](skills/hd2-mod-release-operations/SKILL.md) | [中文](skills/hd2-mod-release-operations/SKILL_cn.md) | Packaging and publishing: project layout, package naming, the byte-level archive format, the seven-step release checklist, GitHub mechanics, token handling and the network traps. |
| [`hd2-injection-runtime-patching`](skills/hd2-injection-runtime-patching/SKILL.md) | [中文](skills/hd2-injection-runtime-patching/SKILL_cn.md) | The runtime half: a safe write primitive, FFI and LuaJIT semantics that bite, when and how often to write, and reading a data table at runtime. |
| [`hd2-offline-data-workflow`](skills/hd2-offline-data-workflow/SKILL.md) | [中文](skills/hd2-offline-data-workflow/SKILL_cn.md) | Work offline first, go in-game last: locate a data table by signature, decode it from the plaintext mirror, the LDLD block format and both hashes, scanner design, and the one-shot reconnaissance addon. Ships the full 106-item pitfall inventory as evidence. |
| [`hd2-no-quarantine-packaging`](skills/hd2-no-quarantine-packaging/SKILL.md) | — | Ship a mod whose helper scripts survive site scanning: generate the `.bat`/`.ps1` at runtime into the user's config folder instead of putting it in the archive, and gate the build on it. |
| [`writing-mod-tools`](skills/writing-mod-tools/SKILL.md) | — | How to write these tools well: prerequisites and graceful degradation, safe-by-default mutation, exit codes, `--json`, dry-run, self-tests, validating the criterion before a live run, honest limits. |

`hd2-mission-entry` additionally ships `scripts/hd2_window.py`, `hd2_verified_input.py` and
`hd2_click.py` — pid-based window focusing with foreground verification, and a clicker that
survives the game re-centering the cursor.

## Reports

| Report | 中文 | Summary |
|---|---|---|
| [`docs/hd2-mod-failure-catalog.md`](docs/hd2-mod-failure-catalog.md) | [中文](docs/hd2-mod-failure-catalog_cn.md) | Symptom → root cause → fix for the ways an HD2 Lua mod dies: native crashes `pcall` cannot catch, engine library timing, retained-GUI invisibility, LuaJIT's silent limits, pure-Lua scope/arity traps, memory-read safety, config handling, logging, and verified dead ends. |
| [`template/SKELETON.md`](template/SKELETON.md) | [中文](template/SKELETON_cn.md) | A minimal contract-correct mod skeleton; pair it with the `hd2-offline-engine-harness`. |
| [`tests/probe-build/`](tests/probe-build/README.md) | — | The pipeline probe: the one import-and-load step no simulation covers, with a one-minute verification procedure. |
| [`docs/c4-quick-actions-performance-feedback-2026-10-04.md`](docs/c4-quick-actions-performance-feedback-2026-10-04.md) | — | Steady-state read-count and FPS evidence for HD2 C4 Quick Actions 1.11; submitted upstream as [issue #1](https://github.com/etxp/HD2-C4-Quick-Actions/issues/1). |

## Usage

Point your agent/skill loader at `skills/`, or copy a skill folder into your agent's skill
directory. Each skill is a self-contained `SKILL.md` with frontmatter (`name`,
`description`); loaders pick up `SKILL.md`, so a `SKILL_cn.md` beside it never collides.

## Checks

All of these run without the game and without the loader's third-party tools:

```powershell
python -B tests/probe-build/test_probe.py                                    # the probe reaches PIPELINE OK
python -B skills/hd2-offline-engine-harness/scripts/test_panel_skeleton.py   # 24 checks
python -B skills/hd2-bilingual-doc-verify/scripts/verify_translations.py     # every doc pair
python -B skills/hd2-ffi-audit/scripts/ffi_audit.py template/panel_skeleton.lua
python -B skills/hd2-addon-package-inspector/scripts/inspect_package.py <zip>
```

`verify_translations.py` enforces the things a translation must not change — code fences
identical after comment removal, translated Lua still compiling on LuaJIT, matching heading
structure, links carried over, frontmatter intact — while treating directory trees and prose
fences as documentation. Run it after editing either side of a pair.

## Conventions

- Coordinates are **logical pixels** on a 1707x1067 layout (the game runs at a non-100% DPI
  scale, so physical = logical x scale).
- In-game panels use the engine's **Gui** coordinate space: bottom-left origin, y up, sized
  from `Gui.resolution()` and scaled by `min(w/1920, h/1080)`. Convert a Win32 client pixel
  with `gui_y = height - y * height / client_h`.
- Input injection always verifies the **target window is foreground** before sending.
- Every step has a **log evidence line or screenshot** to confirm it actually happened.
- Skills describe **techniques**, not other authors' code: reference implementations are
  cited by file and line. Where a referenced implementation's code is copyleft, the skill says
  so and gives an independently written equivalent — see the provenance section of
  `hd2-native-panel-input-lock`.

## Contributing and provenance

Confidence is not uniform across these skills, so it is stated per skill in
[`docs/verification-status.md`](docs/verification-status.md): what was actually run or measured
here, what was only read from a source, and what is bound to one game build. If you want to help,
that file lists the reported items roughly from cheapest to most valuable to test, and asks you to
name your game build when you report a result.

Reference implementations are cited per skill. Where a referenced project's code is copyleft, the
skill says so and gives an independently written equivalent. One delivered package drew on 20
upstream repositories that carry **no repository-wide licence**, so no code from them is copied
here — only facts, with their sources named.

## License

MIT
