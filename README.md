# HD2 Agent Skills

Agent skills for driving **Helldivers 2** unattended on Windows — launching the game,
reaching the ship, and entering a mission with a known loadout, with verifiable
evidence at each step.

These skills exist because the game gives no automation API: an agent has to work
through window focus, synthetic input, in-game menus, and mod logs. Every coordinate,
key sequence and failure mode here was verified in real runs.

**写模组（而不是驱动游戏）？** 先读[踩坑清单](docs/hd2-mod-failure-catalog.zh-CN.md)——
它按症状组织，第一节就是最花时间的那条规则（`pcall` 不抓原生崩溃）。然后拿
[模组骨架](template/README.zh-CN.md)：一个最小 addon，把那三条最贵的规则写对了，并且附带
一个不需要游戏就能跑的离线测试台。

**Writing a mod rather than driving the game?** Start with the
[failure catalog](docs/hd2-mod-failure-catalog.md) — it is organised symptom-first, and its
first section is the rule that costs the most time (`pcall` does not catch native crashes).
Then take the [mod skeleton](template/panel_skeleton.lua):
a minimal addon that gets the three expensive rules right, with an offline harness
(`hd2-offline-engine-harness`) you can run without the game.

**中文文档：** 每份文档都有 `.zh-CN.md` 版本（见下方表格的「中文」列）。

## Skills

Each skill is one topic. Tool skills ship the tool itself, with its prerequisites written down.

### Pipeline and techniques

| Skill | 中文 | Purpose |
|---|---|---|
| [`hd2-bingus-mod-development`](skills/hd2-bingus-mod-development/SKILL.md) | [中文](skills/hd2-bingus-mod-development/SKILL.zh-CN.md) | The whole pipeline for a Bingus/MDL Lua mod: repo layout, the source contract the loader enforces, the build gates, offline simulation, the addon ZIP, deployment paths and rollback, in-game log evidence, and the release discipline. |
| [`hd2-mission-entry`](skills/hd2-mission-entry/SKILL.md) | [中文](skills/hd2-mission-entry/SKILL.zh-CN.md) | Cold start to boots-on-ground: launch, skip intro, confirm ship readiness, star-map mission selection, briefing loadout, deploy, and the evidence to confirm each step. Ships the focus-verified key/mouse tools and lists the mods the sequence depends on. |
| [`hd2-in-game-panel`](skills/hd2-in-game-panel/SKILL.md) | [中文](skills/hd2-in-game-panel/SKILL.zh-CN.md) | Draw a clickable mod panel inside the game with only `Gui.rect` — retained screen-GUI lifecycle, staged bring-up, layer/native-screen invalidation, region hit-testing, dragging, and a 4x5 pixel font plus packed CJK bitmaps. |
| [`hd2-native-panel-input-lock`](skills/hd2-native-panel-input-lock/SKILL.md) | [中文](skills/hd2-native-panel-input-lock/SKILL.zh-CN.md) | Open the panel on a hotkey (F7), unlock the mouse, and keep the game from receiving keyboard/mouse while it is open — raw-input deregistration, a window-procedure filter, coordinate conversion, wheel notches, safe give-back. |
| [`hd2-game-language-autodetect`](skills/hd2-game-language-autodetect/SKILL.md) | [中文](skills/hd2-game-language-autodetect/SKILL.zh-CN.md) | Decide automatically whether the client is Chinese or English — build-verified `game.dll` offsets, with an engine-font glyph-coverage fallback, and labels localized at draw time only. |

### Tools (each ships its own script)

| Tool skill | Script | What it is for |
|---|---|---|
| [`hd2-addon-build`](skills/hd2-addon-build/SKILL.md) | `scripts/build_mod.py` | Package a mod into a manager-importable ZIP, refusing when the source fails a gate. |
| [`hd2-addon-package-inspector`](skills/hd2-addon-package-inspector/SKILL.md) | `scripts/inspect_package.py` | Read the built ZIP: manifest, archive header, name→hash mapping, declared icons, and whether it really contains the source you built. |
| [`hd2-ffi-audit`](skills/hd2-ffi-audit/SKILL.md) | `scripts/ffi_audit.py` | Static check that every called C symbol is declared, and none collides with another mod's declaration. |
| [`hd2-bingus-toolchain-setup`](skills/hd2-bingus-toolchain-setup/SKILL.md) | `scripts/fetch_bingus_tools.py` | Find the third-party addon packaging tools on this machine and put them where a build expects them. |
| [`hd2-offline-engine-harness`](skills/hd2-offline-engine-harness/SKILL.md) | `scripts/test_panel_skeleton.py` | Test a mod offline against a faked engine boundary on real LuaJIT — GUI counts, staged states, error budget. |
| [`hd2-bilingual-doc-verify`](skills/hd2-bilingual-doc-verify/SKILL.md) | `scripts/verify_translations.py` | Keep `X.md` / `X.zh-CN.md` pairs honest: code fences, heading structure, links, frontmatter. |
| [`hd2-live-memory-probe`](skills/hd2-live-memory-probe/SKILL.md) | — (pattern + skeleton) | Write and run a read-only probe against the running game to verify an address chain without another mission. |
| [`hd2-mod-log-analysis`](skills/hd2-mod-log-analysis/SKILL.md) | — (pattern + skeleton) | Turn "the mod does nothing" into a named stage, and write the analyzer that says so. |
| [`writing-mod-tools`](skills/writing-mod-tools/SKILL.md) | — | How to write these tools well: prerequisites and graceful degradation, safe-by-default mutation, exit codes, `--json`, dry-run, self-tests that reproduce the original bug, honest limits. |

`hd2-mission-entry` additionally ships `scripts/hd2_window.py`, `hd2_verified_input.py` and
`hd2_click.py` — pid-based window focusing with foreground verification, and a clicker that
survives the game re-centering the cursor.

## Reports

Field reports and measurements that stand on their own, published here so they can be
linked and discussed upstream.

| Report | 中文 | Summary |
|---|---|---|
| [`docs/hd2-mod-failure-catalog.md`](docs/hd2-mod-failure-catalog.md) | [中文](docs/hd2-mod-failure-catalog.zh-CN.md) | Symptom → root cause → fix for the ways an HD2 Lua mod dies: native crashes `pcall` cannot catch, engine library timing, retained-GUI invisibility, LuaJIT's silent limits, two pure-Lua scope/arity traps, memory-read safety, config handling, logging, and verified dead ends. |
| [`template/panel_skeleton.lua`](template/README.md) | [中文](template/README.zh-CN.md) | A minimal contract-correct mod skeleton; pair it with the `hd2-offline-engine-harness` (24 checks) — the three rules as runnable code rather than prose. |
| [`tests/probe-build/`](tests/probe-build/README.md) | — | The pipeline probe: the one import-and-load step no simulation covers, with a one-minute verification procedure. |
| [`docs/c4-quick-actions-performance-feedback-2026-10-04.md`](docs/c4-quick-actions-performance-feedback-2026-10-04.md) | — | Steady-state read-count and FPS evidence for HD2 C4 Quick Actions 1.11 (Chinese first, then English); submitted upstream as [issue #1](https://github.com/etxp/HD2-C4-Quick-Actions/issues/1). |

## Usage

Point your agent/skill loader at `skills/`, or copy a skill folder into your agent's
skill directory. Each skill is a self-contained `SKILL.md` with frontmatter
(`name`, `description`). A `SKILL.zh-CN.md` next to it is the Chinese translation for
human readers — loaders pick up `SKILL.md`, so the two never collide.

## Checks

All of these run without the game and without the loader's third-party tools:

```powershell
python -B tests/probe-build/test_probe.py                                    # the probe reaches PIPELINE OK
python -B skills/hd2-offline-engine-harness/scripts/test_panel_skeleton.py   # 24 checks
python -B skills/hd2-bilingual-doc-verify/scripts/verify_translations.py     # every doc pair
python -B skills/hd2-ffi-audit/scripts/ffi_audit.py template/panel_skeleton.lua
python -B skills/hd2-addon-package-inspector/scripts/inspect_package.py <zip>
```

`verify_translations.py` enforces the things a translation must not change — code
fences identical after comment removal, translated Lua still compiling on
LuaJIT, matching heading structure, links carried over, frontmatter intact — while
treating directory trees and package layouts as documentation to be translated
(compared by structure). Run it after editing either side of a pair.

## Conventions

- Coordinates are **logical pixels** on a 1707x1067 layout (the game runs at a
  non-100% DPI scale, so physical = logical x scale).
- In-game panels use the engine's **Gui** coordinate space: bottom-left origin, y up,
  sized from `Gui.resolution()` and scaled by `min(w/1920, h/1080)`. Convert a Win32
  client pixel with `gui_y = height - y * height / client_h`.
- Input injection always verifies the **target window is foreground** before sending.
- Every step has a **log evidence line or screenshot** to confirm it actually happened.
- Skills describe **techniques**, not other authors' code: reference implementations are
  cited by file and line. Where a referenced implementation's code is copyleft, the skill
  says so and gives an independently written equivalent rather than the original — see
  the provenance section of `hd2-native-panel-input-lock` for a worked example.

## License

MIT
