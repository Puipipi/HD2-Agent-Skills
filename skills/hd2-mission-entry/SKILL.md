---
name: hd2-mission-entry
description: Launch Helldivers 2 on Windows and drive it from ship into an active mission — window focus, key/mouse injection, the mods this sequence depends on, star-map mission selection, briefing loadout, and the verification evidence for each step. Use when an agent must start HD2 and enter a mission unattended (performance testing, mod validation, gameplay capture).
---

# HD2 Mission Entry (unattended)

English / [简体中文](https://github.com/YC426/HD2-Agent-Skills/blob/main/skills/hd2-mission-entry/SKILL_cn.md)

Goal: from a cold start, get the game **into a mission with a known loadout**, with
verifiable evidence at every step. Written from real runs; every coordinate and
gotcha below was hit and confirmed in practice.

## 0. Prerequisites

### Tools (shipped in `scripts/`)

| Tool | What it does |
|---|---|
| `hd2_window.py` | Finds the game's top-level window **by process id**, focuses it, and verifies the foreground actually changed. |
| `hd2_verified_input.py` | Presses one key (or chord) for a duration, with a **focus check before every injection** and a foreground re-check between repeats. |
| `hd2_click.py` | Clicks a logical coordinate **despite the game moving the cursor itself** — set, verify, correct with relative deltas, hover, then click. |

```powershell
python -B scripts/hd2_window.py                    # list the game's windows + handles
python -B scripts/hd2_window.py focus              # restore + focus, and report the match
python -B scripts/hd2_verified_input.py space 0.15 --repeat 8 --interval 0.25
python -B scripts/hd2_click.py 1410 795 --settle=0.9
```

Requirements: Windows, Python 3.8+, and **the game running as the same user** (otherwise it
cannot be focused). The tools never change privileges or system settings. `hd2_window.py`
must sit next to the other two — it is imported by both.

**Never use bare `SendKeys`**: keystrokes land in whatever window has focus.

### Game mods this sequence depends on

The autoplay relies on mods to open screens. Without them the clicks land on nothing —
this is the most common reason "the sequence stopped working".

| Mod | Why it is needed | Requirement |
|---|---|---|
| **Ship Station Hotkeys** (v1.7+, GUID `3d8fdb82-9df6-4dc9-a538-5f94fc60a2e7`; formerly *Galactic Menu Hotkey*) | Provides `Tab` → star map, `F1` → Armory, `F5` → Control Center, `F6` → ship management, `F8` → instant Hellpod entry after mission selection. The log this skill reads (`GalacticMenuHotkey.log`) comes from it. | Bingus Shared Loader **v17+** |
| **Stratagem MultiSelect** (v2 BSL, GUID `874d84d7-fa8a-4d48-832d-dc3cc374cd49`) | Lets the **same** stratagem be selected in all four slots, which is what makes "click one stratagem 4×" a valid loadout. Without it you must pick four different ones. | Bingus Shared Loader **v18+** |
| Bingus Shared Loader | Loads the above. | v18+ covers both; v17 is the floor for Ship Station Hotkeys |
| *(optional)* Mod Bindings Menu v2.0 | Only needed to **rebind** the six shortcuts (including controller). Not required for the defaults. | Bingus v17+ |

If any of these is missing or disabled, fix that before blaming the sequence. Confirm from
the manager that they are **enabled and deployed**, then confirm in the log (step 2) — a
missing `Tab` shortcut leaves the star map closed and every later click lands on the ship.

### Environment

- Game dir: `D:\Program Files (x86)\Steam\steamapps\common\Helldivers 2` (adjust).
- Steam running, game **not** running (check `Get-Process helldivers2`).
- Log directory: `%LOCALAPPDATA%\CowboyBingus\Helldivers2\Logs\` and
  `%APPDATA%\Arrowhead\Helldivers2\`.

## 1. Start the game and skip the intro

```powershell
Start-Process "steam://rungameid/553850"
Start-Sleep -Seconds 20
python -B scripts/hd2_verified_input.py space 0.15 --repeat 8 --interval 0.25
Start-Sleep -Seconds 35
python -B scripts/hd2_verified_input.py space 0.15 --repeat 8 --interval 0.25
```

- **Intro screens (city flyover) mean you pressed too early.** Keep pressing.
- If the tool reports `Game did not become foreground`, the window is not up yet: sleep and
  retry. Do not assume the input landed.
- The game window title contains `™`, so title-substring matching fails — hence resolving by
  **process id + EnumWindows** (`hd2_window.py` does this; it falls back to the title, then to
  the first visible window, because the class name is reported inconsistently too).

## 2. Verify ship readiness before touching Tab (mandatory)

```powershell
Get-Content "$env:LOCALAPPDATA\CowboyBingus\Helldivers2\Logs\GalacticMenuHotkey.log" -Tail 4
```

Ready = **all** of:

- `World detection: galaxy table present`
- `Super Destroyer detected.`
- `Native ship menu presenters ready for current game build.`

**Then confirm visually with a screenshot** — `Super Destroyer detected` alone can be
logged before you can actually act. Screenshot the ship interior (SES name + `R 采购`
prompt visible) before proceeding.

> Pressing `Tab` too early leaves star-map tooltips stuck over the ship HUD.

## 3. Star map → pick a mission

```powershell
python -B scripts/hd2_verified_input.py tab 0.15 --repeat 1
Start-Sleep -Seconds 6
# A/D nudge the selection onto a mission/planet node
python -B scripts/hd2_verified_input.py d 0.15 --repeat 2 --interval 0.5
```

- `GalacticMenuHotkey.log` confirms: `Galactic Map shortcut detected; entering native presenter 15.`
  **No such line means Ship Station Hotkeys is not loaded/enabled** — stop and fix that.
- **`Tab` opens the map but cannot close it.** Injected `Esc` / right-click do **not**
  close the star map either (verified). Do not burn cycles on those.
- **Selecting a mission = clicking the mission/ship marker with the mouse.**
  With the map on the 1707×1067 logical layout, click **logical (1410, 795)**:
  ```powershell
  python -B scripts/hd2_click.py 1410 795 --settle=0.9
  ```
  On success the map closes by itself and the log shows
  `Hellpod shortcut detected; opening the briefing.`
- Hover panels **follow the cursor**; text that looks like a button is often just a hint.
  Click the node itself.

## 4. Briefing → loadout → deploy

Wait **0.6–0.8 s** after the briefing appears, then (all logical coords, 1707×1067).
`--settle` is required here: the briefing grid only arms a slot once it has seen the pointer,
and `hd2_click.py` uses that hover window before clicking.

```powershell
python -B scripts/hd2_click.py 840 600 --settle=0.9      # mission map drop point
python -B scripts/hd2_click.py  85 779 --settle=0.9      # stratagem slot -> opens the picker
python -B scripts/hd2_click.py 128 477 --settle=0.6      # first stratagem; click 4x to fill 4 slots
python -B scripts/hd2_verified_input.py b 0.15 --repeat 3 --interval 0.7   # deploy
```

- Clicking the **same** stratagem 4× works **because Stratagem MultiSelect is installed**
  (see §0). On a stock loadout this produces one slot filled and three empty — a different
  failure that looks like "deploy did nothing".
- `b` is "deploy". If the briefing never opened you will see
  `select a mission first` or `presenter is busy (15/14)` in the log — that means the
  map is still open (see §3).
- **Coordinates are layout-specific.** Re-derive them if resolution/HUD scale changes.
- `hd2_click.py` prints `target=... before=... landed=... locked=...`: `landed=False` or
  `locked=False` means the game moved the pointer away, and the click went somewhere else.

## 5. Confirm you are actually in a mission

Screenshot: ground scene, `战略配备` top-left, compass, ammo counter bottom-right.
Log side: `World detection: galaxy table absent` (you left the ship).

To draw a specific weapon, press the slot key (e.g. `3` = support weapon). **Confirm
with a screenshot** — slot selection does *not* always register (known failure mode:
`gate.active=false,status=outside_c4` in mod logs while the HUD still shows the old weapon).

## 6. Returning to the ship

- Some confirm dialogs require a **long press** (`mouse_left` held ~1.5 s); a short click
  only selects the button:
  ```powershell
  python -B scripts/hd2_verified_input.py mouse_left 1.5 --repeat 1
  ```
- If the star map is stuck, the reliable way back is **restarting the game** — injected
  `Esc` does not work there.

## Gotchas that cost real time (do not re-learn these)

| Symptom | Cause / fix |
|---|---|
| Keystrokes do nothing | Target window not foreground. Verify focus **before** every injection. |
| `Tab` does nothing, no shortcut line in the log | **Ship Station Hotkeys is not loaded/enabled** (§0), not a coordinate problem. |
| Only one stratagem slot filled after clicking 4× | **Stratagem MultiSelect is missing** (§0). |
| Click lands next to the target | The game re-centers the cursor; `hd2_click.py` verifies and corrects. If it reports `landed=False`, re-derive the coordinate — do not retry blindly. |
| `Esc` does nothing in star map | Injected Esc is not accepted there. Click, or restart. |
| `Tab` will not close the star map | By design; use a mouse click on the mission node. |
| Intro animation on screen | Space pressed too early — keep pressing. |
| Window not found by title | Title contains `™`; enumerate by pid. |
| Wrong HUD text typed into another app | Bare `SendKeys` without focus check (e.g. typed into an Arsenal search box). |
| Action lands on the wrong screen entirely | A prerequisite mod changed or was disabled — re-read §0 before re-deriving coordinates. |

## What is verified, and what is not

- The coordinates, key sequences and failure modes are from real runs of this exact sequence.
- The tools are exercised as far as possible without the game (they compile, import, and
  expose their entry points), but **their clicking and focusing behaviour needs the game
  running** — nothing offline can confirm a click landed.
- The mod prerequisites are read from the installed manifests, not from a run performed for
  this document: Ship Station Hotkeys v1.7 (Bingus v17+), Stratagem MultiSelect v2 BSL
  (Bingus v18+), Mod Bindings Menu v2.0 optional.
