# HD2 Agent Skills

Agent skills for driving **Helldivers 2** unattended on Windows — launching the game,
reaching the ship, and entering a mission with a known loadout, with verifiable
evidence at each step.

These skills exist because the game gives no automation API: an agent has to work
through window focus, synthetic input, in-game menus, and mod logs. Every coordinate,
key sequence and failure mode here was verified in real runs.

## Skills

| Skill | Purpose |
|---|---|
| [`hd2-mission-entry`](skills/hd2-mission-entry/SKILL.md) | Cold start to boots-on-ground: launch, skip intro, confirm ship readiness, star-map mission selection, briefing loadout, deploy, and the evidence to confirm each step. |
| [`hd2-in-game-panel`](skills/hd2-in-game-panel/SKILL.md) | Draw a clickable mod panel inside the game with only `Gui.rect` — retained screen-GUI lifecycle, staged bring-up, layer/native-screen invalidation, region hit-testing, dragging, and a 4x5 pixel font plus packed CJK bitmaps. No engine font or material needed. |
| [`hd2-native-panel-input-lock`](skills/hd2-native-panel-input-lock/SKILL.md) | Open the panel on a hotkey (F7), unlock the mouse (show + clip, save and restore), and keep the game from receiving keyboard/mouse while it is open — raw-input deregistration, a `GWLP_WNDPROC` filter, client-pixel→Gui-unit conversion, wheel notches, safe give-back. |
| [`hd2-game-language-autodetect`](skills/hd2-game-language-autodetect/SKILL.md) | Decide automatically whether the client is Chinese or English — read the selected Text Language by build-verified `game.dll` offsets, fall back to probing the engine font's glyph coverage, and localize labels at draw time only. |

## Reports

Field reports and measurements that stand on their own, published here so they can be
linked and discussed upstream.

| Report | Summary |
|---|---|
| [`docs/c4-quick-actions-performance-feedback-2026-10-04.md`](docs/c4-quick-actions-performance-feedback-2026-10-04.md) | Steady-state read-count and FPS evidence for HD2 C4 Quick Actions 1.11 (Chinese first, then English); submitted upstream as [issue #1](https://github.com/etxp/HD2-C4-Quick-Actions/issues/1). |

## Usage

Point your agent/skill loader at `skills/`, or copy a skill folder into your agent's
skill directory. Each skill is a self-contained `SKILL.md` with frontmatter
(`name`, `description`).

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
