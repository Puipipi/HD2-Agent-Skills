---
name: hd2-mission-entry
description: Launch Helldivers 2 on Windows and drive it from ship into an active mission — window focus, key/mouse injection, star-map mission selection, briefing loadout, and the verification evidence for each step. Use when an agent must start HD2 and enter a mission unattended (performance testing, mod validation, gameplay capture).
---

# HD2 Mission Entry (unattended)

Goal: from a cold start, get the game **into a mission with a known loadout**, with
verifiable evidence at every step. Written from real runs; every coordinate and
gotcha below was hit and confirmed in practice.

## 0. Preconditions

- Game dir: `D:\Program Files (x86)\Steam\steamapps\common\Helldivers 2` (adjust).
- Steam running, game **not** running (check `Get-Process helldivers2`).
- A verified input helper that checks the foreground window before sending keys.
  Never use bare `SendKeys` — keystrokes land in whatever window has focus.
- Log directory (Bingus/MDL based mods):
  `%LOCALAPPDATA%\CowboyBingus\Helldivers2\Logs\` and `%APPDATA%\Arrowhead\Helldivers2\`.

## 1. Start the game and skip the intro

```powershell
Start-Process "steam://rungameid/553850"
Start-Sleep -Seconds 20
# space, held ~0.15s, repeated — this is what fast-forwards the intro/loading
python work\tools\hd2_verified_input.py space 0.15 --repeat 8 --interval 0.25
Start-Sleep -Seconds 35
python work\tools\hd2_verified_input.py space 0.15 --repeat 8 --interval 0.25
```

- **Intro screens (city flyover) mean you pressed too early.** Keep pressing.
- If the helper reports `Game did not become foreground`, the window is not up yet:
  sleep and retry. Do not assume the input landed.
- The game window title contains `™`, so title-substring matching fails — resolve the
  window by **process id + EnumWindows**, not by title.

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
python work\tools\hd2_verified_input.py tab 0.15 --repeat 1
Start-Sleep -Seconds 6
# A/D nudge the selection onto a mission/planet node
python work\tools\hd2_verified_input.py d 0.15 --repeat 2 --interval 0.5
```

- `GalacticMenuHotkey.log` confirms: `Galactic Map shortcut detected; entering native presenter 15.`
- **`Tab` opens the map but cannot close it.** Injected `Esc` / right-click do **not**
  close the star map either (verified). Do not burn cycles on those.
- **Selecting a mission = clicking the mission/ship marker with the mouse.**
  With the map on the 1707×1067 logical layout, click **logical (1410, 795)**.
  On success the map closes by itself and `GalacticMenuHotkey.log` shows
  `Hellpod shortcut detected; opening the briefing.`
- Hover panels **follow the cursor**; text that looks like a button is often just a hint.
  Click the node itself.

## 4. Briefing → loadout → deploy

Wait **0.6–0.8 s** after the briefing appears, then (all logical coords, 1707×1067):

```powershell
python <clicker> 840 600 --settle=0.9     # mission map drop point
python <clicker>  85 779 --settle=0.9     # stratagem slot → opens the stratagem picker
python <clicker> 128 477 --settle=0.6     # first stratagem; click 4× to fill 4 slots
python work\tools\hd2_verified_input.py b 0.15 --repeat 3 --interval 0.7
```

- Clicking the **same** stratagem 4× is fine and is the fastest path to a valid loadout.
  (Some setups require 4 different stratagems; this one does not.)
- `b` is "deploy". If the briefing never opened you'll see
  `select a mission first` or `presenter is busy (15/14)` in the log — that means the
  map is still open (see §3).
- **Coordinates are layout-specific.** Re-derive them if resolution/HUD scale changes.

## 5. Confirm you are actually in a mission

Screenshot: ground scene, `战略配备` top-left, compass, ammo counter bottom-right.
Log side: `World detection: galaxy table absent` (you left the ship).

To draw a specific weapon, press the slot key (e.g. `3` = support weapon). **Confirm
with a screenshot** — slot selection does *not* always register (known failure mode:
`gate.active=false,status=outside_c4` in mod logs while the HUD still shows the old weapon).

## 6. Returning to the ship

- Some confirm dialogs require a **long press** (`mouse_left` held ~1.5 s); a short click
  only selects the button.
- If the star map is stuck, the reliable way back is **restarting the game** — injected
  Esc does not work there.

## Gotchas that cost real time (do not re-learn these)

| Symptom | Cause / fix |
|---|---|
| Keystrokes do nothing | Target window not foreground. Verify focus **before** every injection. |
| `Esc` does nothing in star map | Injected Esc is not accepted there. Click, or restart. |
| `Tab` will not close the star map | By design; use a mouse click on the mission node. |
| Intro animation on screen | Space pressed too early — keep pressing. |
| Window not found by title | Title contains `™`; enumerate by pid. |
| Mouse lands off-target | Game re-centers the cursor; use a closed-loop clicker that verifies landing, and convert physical→logical coordinates by the DPI scale. |
| Wrong HUD text typed into another app | Bare `SendKeys` without focus check (e.g. typed into an Arsenal search box). |
