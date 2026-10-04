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
Then take the [mod skeleton](template/README.md): a minimal addon that gets the three
expensive rules right and comes with an offline harness you can run without the game.

**中文文档：** 每份文档都有 `.zh-CN.md` 版本（见下方表格的「中文」列）。

## Skills

| Skill | 中文 | Purpose |
|---|---|---|
| [`hd2-bingus-mod-development`](skills/hd2-bingus-mod-development/SKILL.md) | [中文](skills/hd2-bingus-mod-development/SKILL.zh-CN.md) | The whole pipeline for a Bingus/MDL Lua mod: repo layout, the source contract the loader enforces, the four build gates (LuaJIT compile, no user32 declaration, called⊆declared, README block), offline simulation with lupa, the addon-envelope ZIP a manager imports, deployment paths and rollback, in-game log evidence, and the release discipline. Includes a ready `build_mod.py`. |
| [`hd2-mission-entry`](skills/hd2-mission-entry/SKILL.md) | — | Cold start to boots-on-ground: launch, skip intro, confirm ship readiness, star-map mission selection, briefing loadout, deploy, and the evidence to confirm each step. |
| [`hd2-in-game-panel`](skills/hd2-in-game-panel/SKILL.md) | [中文](skills/hd2-in-game-panel/SKILL.zh-CN.md) | Draw a clickable mod panel inside the game with only `Gui.rect` — retained screen-GUI lifecycle, staged bring-up, layer/native-screen invalidation, region hit-testing, dragging, and a 4x5 pixel font plus packed CJK bitmaps. No engine font or material needed. |
| [`hd2-native-panel-input-lock`](skills/hd2-native-panel-input-lock/SKILL.md) | [中文](skills/hd2-native-panel-input-lock/SKILL.zh-CN.md) | Open the panel on a hotkey (F7), unlock the mouse (show + clip, save and restore), and keep the game from receiving keyboard/mouse while it is open — raw-input deregistration, a `GWLP_WNDPROC` filter, client-pixel→Gui-unit conversion, wheel notches, safe give-back. |
| [`hd2-game-language-autodetect`](skills/hd2-game-language-autodetect/SKILL.md) | [中文](skills/hd2-game-language-autodetect/SKILL.zh-CN.md) | Decide automatically whether the client is Chinese or English — read the selected Text Language by build-verified `game.dll` offsets, fall back to probing the engine font's glyph coverage, and localize labels at draw time only. |

## Reports

Field reports and measurements that stand on their own, published here so they can be
linked and discussed upstream.

| Report | 中文 | Summary |
|---|---|---|
| [`docs/hd2-mod-failure-catalog.md`](docs/hd2-mod-failure-catalog.md) | [中文](docs/hd2-mod-failure-catalog.zh-CN.md) | Symptom → root cause → fix for the ways an HD2 Lua mod dies: native crashes `pcall` cannot catch, engine library timing, retained-GUI invisibility, LuaJIT's silent limits, two pure-Lua scope/arity traps, memory-read safety, config handling, logging, and verified dead ends. |
| [`template/panel_skeleton.lua`](template/README.md) | [中文](template/README.zh-CN.md) | A minimal contract-correct mod skeleton plus an offline LuaJIT harness (24 checks) — the three rules as runnable code rather than prose. |
| [`docs/c4-quick-actions-performance-feedback-2026-10-04.md`](docs/c4-quick-actions-performance-feedback-2026-10-04.md) | — | Steady-state read-count and FPS evidence for HD2 C4 Quick Actions 1.11 (Chinese first, then English); submitted upstream as [issue #1](https://github.com/etxp/HD2-C4-Quick-Actions/issues/1). |

## Usage

Point your agent/skill loader at `skills/`, or copy a skill folder into your agent's
skill directory. Each skill is a self-contained `SKILL.md` with frontmatter
(`name`, `description`). A `SKILL.zh-CN.md` next to it is the Chinese translation for
human readers — loaders pick up `SKILL.md`, so the two never collide.

## Checks

Both run without the game and without the loader's tools:

```powershell
python -B tests/test_panel_skeleton.py     # 24 checks: the skeleton against a fake engine on LuaJIT
python -B tests/verify_translations.py     # every X.md vs its X.zh-CN.md
```

`verify_translations.py` enforces the things a translation must not change — code
fences byte-identical after comment removal, translated Lua still compiling on
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
