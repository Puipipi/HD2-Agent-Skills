---
name: hd2-native-panel-input-lock
description: Open an in-game panel on a hotkey (F7) inside Helldivers 2, unlock the mouse so it can be used as a pointer, and keep the game from receiving keyboard/mouse input while the panel is open — Windows raw-input deregistration, an optional user32 window-procedure filter, cursor show/clip save and restore, client-pixel to Gui-unit conversion, wheel notches, and safe give-back on close/unfocus. Use when a mod panel needs a usable cursor, when clicks pass through to the armory behind the panel, or when the camera still turns while typing.
---

# HD2 native panel: hotkey, cursor unlock, input lock

> **Confidence:** reported. No code was executed; the provenance section says which parts are copyleft.

English / [简体中文](https://github.com/YC426/HD2-Agent-Skills/blob/main/skills/hd2-native-panel-input-lock/SKILL_cn.md)

Taken from **Super Earth Armory Forge v6.2.1** (F7 panel) — the section its comments
credit to **SHODAN Stat Editor v1.4.1** — cross-checked against the Custom Armor Kit's
simpler pointer handling. **Read §6 (provenance and licensing) before you copy anything**;
the lineage is not uniform and one branch of it is copyleft.

> Companion reading: [`docs/hd2-mod-failure-catalog.md`](../../docs/hd2-mod-failure-catalog.md)
> — §1 and §8 are why the input path is written defensively (a half-applied input grab is
> worse than none).

The problem in one line: the game's camera and UI *do* react to hardware keys and the
mouse, so a panel drawn on top is not enough — you must **take the mouse and keyboard
away from the game while the panel is open, then give them back exactly as they were**.

---

## 1. Hotkey: focused edge detection, once per press

```lua
local function hotkey_pressed(name)
    local vk = VK[name]                                  -- 'F7' -> 0x76
    if not vk then return false end
    local down = input.key_down(vk)                      -- GetAsyncKeyState(vk) < 0
    local was  = keys_was[name]
    keys_was[name] = down
    local focused = input.focused()                      -- foreground window is OUR process
    if down and not was and name == hotkey() then
        PP.note(focused and 'presses' or 'unfocused')     -- say when an unfocused press is dropped
    end
    return down and not was and focused
end
```

- **Edge, not level** (`down and not was`), and **focused**, or the panel opens when the
  user presses F7 in another application.
- `input.focused()` = `GetForegroundWindow()` → `GetWindowThreadProcessId` →
  compare with `GetCurrentProcessId()`. Never match the window by title: the HD2 title
  contains `™` and title-substring lookup fails.
- Log the **dropped** (unfocused) press. Otherwise "F7 doesn't work" is unattributable.
- Default the key from the mod table and validate it (`^F%d%d?$` → in `VK`), so a
  hand-edited config can never leave the panel unopenable.

```lua
panel_tick = function(now)
    if not input or not sr then return end
    if hotkey_pressed(hotkey()) then open_panel(not ui.open) end
    ...
end
```

## 2. Unlock the mouse — two cursors, both must be handled

There are **two** cursors: the game's own (`stingray.Window.show_cursor` /
`set_show_cursor` / `set_clip_cursor`) and the Win32 one (`ShowCursor` /
`ClipCursor`). Handle both, and remember their state so you can hand the mouse back.

```lua
local cursor = { taken = false }

local function window_fn(name)
    local f = sr.Window and rawget(sr.Window, name)
    return type(f) == 'function' and f or nil
end

local function engine_cursor_shown()
    local f = window_fn('show_cursor')
    if not f then return nil end
    local ok, shown = pcall(f)
    if ok and type(shown) == 'boolean' then return shown end
    return nil
end

local function take_cursor()
    if cursor.taken then return end
    cursor.taken = true
    local set_show, set_clip = window_fn('set_show_cursor'), window_fn('set_clip_cursor')
    cursor.was_shown = engine_cursor_shown()          -- may be nil: unknown
    cursor.engine = set_show ~= nil
    if cursor.engine then
        pcall(set_show, true)                         -- make the engine show it
        if set_clip then pcall(set_clip, false) end   -- and stop clipping it to the centre
    end
    cursor.shows = 0
    while input.show_cursor(true) < 0 and cursor.shows < 20 do cursor.shows = cursor.shows + 1 end
    cursor.shows = cursor.shows + 1
    cursor.clip = input.get_clip()                    -- save the game's clip rect
    input.set_clip(nil)                               -- free the cursor
end
```

**The display-count trap.** `ShowCursor` uses a per-thread counter, and the game may have
called it several times. Loop `ShowCursor(true)` until it returns `>= 0`, count how many
calls it took, and give back **exactly that many** `ShowCursor(false)`. Restore the
saved clip rect. If the game had the cursor shown, put it back the way it was:

```lua
local function release_cursor()
    if not cursor.taken then return end
    cursor.taken = false
    if cursor.engine and cursor.was_shown == false then
        local set_show, set_clip = window_fn('set_show_cursor'), window_fn('set_clip_cursor')
        pcall(set_show, false)
        if set_clip then pcall(set_clip, true) end
    end
    for _ = 1, cursor.shows or 0 do input.show_cursor(false) end
    if cursor.clip then input.set_clip(cursor.clip) end
end
```

**While the panel is open the game keeps hiding the cursor.** It calls its own
`set_show_cursor(false)` on camera/screen changes, so re-assert once per frame — cheaply:

```lua
local function keep_cursor()
    if not cursor.taken then return end
    if engine_cursor_shown() == false then
        local set_show, set_clip = window_fn('set_show_cursor'), window_fn('set_clip_cursor')
        if set_show then pcall(set_show, true) end
        if set_clip then pcall(set_clip, false) end
    end
end
```

Call order per frame: `keep_cursor()` → `hold_input()` → mouse/click handling.

### Where the pointer is, in the units the panel draws in

```lua
function self.cursor()                       -- client PIXELS from the TOP-LEFT + client size
    local window = self.window()
    if not window then return nil end
    if user.GetCursorPos(ffi.cast('void*', point)) == 0
       or user.ScreenToClient(window, ffi.cast('void*', point)) == 0
       or user.GetClientRect(window, ffi.cast('void*', rect)) == 0 then return nil end
    return point[0], point[1], rect[2] - rect[0], rect[3] - rect[1]
end

-- caller: pixels -> Gui units (Gui origin is bottom-left, y up)
local x, y, cw, ch = input.cursor()
if not x or cw <= 0 or ch <= 0 then return end
local width, height = sr.Gui.resolution()
local sx, sy = x * width / cw, y * height / ch       -- screen pixels, top-left origin
local gui_y  = height - sy                            -- Gui y for hit-testing / drawing
```

- Reject anything outside `[0,cw) x [0,ch)`, and reject a zero client size.
- The engine's `Mouse.button` is unreliable in menu states — read the button from
  Windows instead, and honour the swapped-buttons system setting:
  ```lua
  function self.mouse_left()
      local swapped = user.GetSystemMetrics(23) ~= 0          -- SM_SWAPBUTTON
      return user.GetAsyncKeyState(swapped and 0x02 or 0x01) < 0
  end
  ```
- Click on **press edge**, fire on **release over the same hit region** (`armed`), which
  is what stops a drag from also clicking a button underneath.

## 3. Stop the game receiving input

The game reads **mouse movement** as Windows **raw input** and **key presses, buttons and
the wheel** as **window messages**. Two mechanisms, used together:

### (a) Take the raw-input registrations away (movement + camera)

```lua
PP.gi = { state = 'not yet', saved = nil, next_check = 0 }

function PP.hold_input(now)
    local G = PP.gi
    if not PP.block_on() or G.broken or not (input.raw_list and input.raw_register) then return end
    if not input.focused() then return PP.give_input() end     -- unfocused: the game gets it back
    local hk = VK[hotkey()]
    if hk and input.key_down(hk) then return end               -- let the panel key "let go" first
    -- ... install the window filter once (see (b)) ...
    if now < G.next_check then return end
    G.next_check = now + 0.5                                   -- re-check twice a second
    local take, other = {}, false
    for _, d in ipairs(input.raw_list()) do
        if d.page == 1 and (d.usage == 2 or d.usage == 6) then  -- mouse (2) and keyboard (6)
            if input.raw_ours(d) then take[#take + 1] = d else other = true end
        end
    end
    if other then G.other = true end
    if #take == 0 then
        if not G.saved then
            G.state = other and 'raw input on another thread: left alone' or 'game has no raw input'
        end
        return
    end
    local remove = {}
    for _, d in ipairs(take) do remove[#remove + 1] = { page = 1, usage = d.usage, flags = 0x1, target = nil } end
    if input.raw_register(remove) then                             -- flags 0x1 = remove
        G.saved = G.saved or {}
        for _, d in ipairs(take) do G.saved[d.usage] = d end       -- remember the LATEST registration
        G.state = 'held'
    else
        G.state, G.broken = 'could not take it', true
        log("panel: could not take the game's raw input; it keeps it")
    end
end
```

Rules extracted from this, all of which are load-bearing:

- **Enumerate, do not guess.** `GetRegisteredRawInputDevices(nil, &count, size)` first to
  get the count, add headroom, then read the list. Devices are `{page, usage, flags,
  target}` `RID_DEVICE_INFO`-sized records; a `void*` cast avoids a clash with another
  mod's own struct declaration in the same Lua state.
- **Only touch registrations whose window belongs to this thread**:
  ```lua
  function self.raw_ours(dev)
      if dev.target == nil then return true end
      return user.GetWindowThreadProcessId(dev.target, nil) == kernel.GetCurrentThreadId()
  end
  ```
  Giving back another thread's registration can fail and **leave the game with no mouse**.
- **Re-check every 0.5 s** — the game re-registers its devices when screens change.
- **Keep the game's latest flags**, not the first snapshot, so give-back is faithful.
- `other` = another mod/thread owns raw input: leave it alone and say so in the log.

### (b) Drop key presses and buttons with a window-procedure filter

Raw-input removal does not stop window messages. Install one tiny window-procedure hook
(`SetWindowLongPtrW(window, -4 /* GWLP_WNDPROC */, entry)`) that forwards everything to
`CallWindowProcW` except presses the panel owns:

```lua
-- build_input(): the hook's machine code is a small table of bytes plus a data slot
-- {[0]=enabled,[1]=wheel notches,[2]=keys dropped,[3]=buttons dropped,[4]=held buttons}
local function filter_install(window)
    if window == nil then return nil, 'no game window' end
    local current = user.GetWindowLongPtrW(window, -4)            -- GWLP_WNDPROC
    local call = kernel.GetProcAddress(kernel.GetModuleHandleA('user32.dll'), 'CallWindowProcW')
    local block = kernel.VirtualAlloc(nil, 4096, 0x3000, 0x40)    -- commit+reserve, RWX
    if call == nil or block == nil or current == 0 then return nil, 'no memory for it' end
    -- write: original wndproc, CallWindowProcW, message table, machine code, then
    -- SetWindowLongPtrW(window, -4, entry) and FlushInstructionCache
end
```

- Track buttons already held at install time so the release message is never
  swallowed (`held` bitmask in the data slot). Releasing a button the game never saw
  pressed is a stuck-input bug.
- **Data-slot contract** (what the machine code and the Lua side agree on): an integer
  array at the block's start, `u[0]` = enabled flag, `u[1..3]` = wheel-notches / keys
  dropped / clicks dropped counters, `u[8]` (byte offset 32) = held-button bitmask seeded
  at install. The code entry point is `block + 64`, so the header carries the original
  window procedure and `CallWindowProcW` and the body is appended after it.
- **Never remove the filter.** Another mod may have chained its own procedure after
  yours; instead flip the enable flag in the shared data slot (`filter_set(on)`).
- The filter also **counts wheel notches** — the panel needs them and they would
  otherwise be lost with the rest of the game's input:
  ```lua
  function PP.filter_wheel()
      local G = PP.gi
      if not G.filtering then return nil end
      local total = input.filter_wheel()
      local turned = total - (G.wheel_seen or total)
      G.wheel_seen = total
      G.wheel_rest = (G.wheel_rest or 0) + turned
      local n = G.wheel_rest >= 0 and math.floor(G.wheel_rest / 120)
                                 or -math.floor(-G.wheel_rest / 120)   -- WHEEL_DELTA
      G.wheel_rest = G.wheel_rest - n * 120
      return n
  end
  ```
- The panel reads its own input through `GetAsyncKeyState` / `GetCursorPos`, which the
  filter and the raw-input removal do **not** affect.

### (c) Give everything back — with a fallback that cannot leave the game mute

```lua
function PP.give_input()
    local G = PP.gi
    if G.filtering then pcall(input.filter_set, false); G.filtering = false end
    G.next_check = 0
    if not G.saved then return end
    local list = {}
    for _, d in pairs(G.saved) do list[#list + 1] = d end
    table.sort(list, function(a, b) return a.usage < b.usage end)
    G.saved = nil
    if input.raw_register(list) then G.state = 'given back'; return end
    -- never leave the game without a mouse and keyboard: again without a window
    local plain = {}
    for _, d in ipairs(list) do
        local f = tonumber(d.flags) or 0
        for _, m in ipairs({ 0x100, 0x1000, 0x2000 }) do   -- INPUTSINK, EXINPUTSINK, DEVNOTIFY need a window
            if math.floor(f / m) % 2 == 1 then f = f - m end
        end
        plain[#plain + 1] = { page = 1, usage = d.usage, flags = f, target = nil }
    end
    local ok = input.raw_register(plain)
    if not ok then for _, d in ipairs(plain) do d.flags = 0 end; ok = input.raw_register(plain) end
    G.state, G.broken = 'broken', true                     -- blocking off for the rest of the session
    log('panel: could not give the game its raw input back as it was; registered it again without a window (' ..
        tostring(ok) .. '); game input blocking is off for this session')
end
```

Give input back when: the panel **closes**, the game window **loses focus**, or any step
of the block path **throws**. Mark the whole mechanism `broken` after one failure and stop
trying — a half-applied input grab is far worse than no grab.

Make it opt-out-able (`block_input = off` in the panel's own config file, surfaced in a
Keys tab) and log a one-line descriptor so a problem report says what happened:

```
game input while open: blocked (held); dropped: 12 key presses, 3 clicks; raw input now: mouse, keyboard
```

## 4. Per-frame order that works

```lua
local function panel_frame(now)
    pcall(keep_cursor)                                   -- 1. re-assert the cursor
    local held, why = pcall(PP.hold_input, now)          -- 2. take/refresh input ownership
    if not held then
        PP.gi.broken = true
        log('panel: game input blocking off for this session: ' .. tostring(why))
        pcall(PP.give_input)
    end
    -- 3. re-resolve the draw world when the world set changes (armory adds/removes worlds)
    local main, worlds = sr.Application.main_world(), sr.Application.worlds() or {}
    if not same_worlds(worlds, ui.worlds) or main ~= ui.main then
        ui.worlds, ui.main = worlds, main                -- rebuild the retained GUI
    end
    -- 4. cursor -> hover -> press edge -> action; 5. controller
end
```

- **Wrap the whole frame in `pcall` in the tick**, count consecutive errors and close the
  panel after ~5 in a row, clearing the GUI. One bad frame must not wedge the game.
- Accept input only when `input.focused()`.

## 5. Controller (optional but cheap and it removes the mouse dependency)

Sony-style pad via `XInputGetState` (try `xinput1_4`, `xinput1_3`, `xinput9_1_0`), Back +
Start toggles the panel, D-pad/left stick moves a focus box, A presses, B goes back,
LB/RB switch tabs, right stick scrolls. Two details:

- **Probe an empty slot rarely** (one slot per 60 frames) — asking an empty slot is slow.
- **The mouse takes over again** the moment it moves more than ~2 px: drop the focus box
  and bump a `ui.version` counter so the panel redraws.

## 6. Provenance and licensing — read before copying code

This skill describes a technique; the code in it was written for this document. That
distinction is deliberate, because the reference implementation's lineage is **not**
uniform and one branch of it is copyleft:

| Piece | Where it comes from | Status |
|---|---|---|
| Cursor take / keep / release (`ShowCursor` / `ClipCursor` / `sr.Window.set_*_cursor`) | **adapted from SHODAN Stat Editor** — its own header says so | **GPL-3.0** |
| Window-message filter machine code + the parameter block that builds it | **the same SHODAN code**, byte-identical in both mods (verified) | **GPL-3.0** |
| `mouse_left` via `GetAsyncKeyState` + `SM_SWAPBUTTON` | Armory Forge's own — not present in SHODAN | Armory Forge |
| Raw-input deregistration / give-back, `mouse()` / hit-testing / click arming, controller support | Armory Forge's own — not present in SHODAN | Armory Forge |
| `bd` / `sd` / `bl` / `filters[].u` data-slot contract | Armory Forge's own | Armory Forge |

**The trap:** Armory Forge's `CREDITS.txt` (and its README) describe SHODAN Stat Editor
v1.4.1 as *"public domain / Unlicense"*. The repository itself is **GPL-3.0** — the
`LICENSE` file and GitHub's license metadata both say so. Verified 2026-10-04:

```
GET https://api.github.com/repos/SHODAN-HORAI/SHODAN-Stat-Editor
  license: { "key": "gpl-3.0", "spdx_id": "GPL-3.0" }
GET https://raw.githubusercontent.com/SHODAN-HORAI/SHODAN-Stat-Editor/main/LICENSE
  → "GNU GENERAL PUBLIC LICENSE / Version 3, 29 June 2007"
```

The mod comment is wrong, so **do not treat "the mod says public domain" as a licence
grant**. A publicly downloadable mod is not the same as permissively licensed code, and a
GPL-3.0 file copied into a repository that carries a different licence (this one is MIT)
is not something the mod author can authorise — only the copyright holder can.

Practical consequences:

- **You want to use it in your own mod?** Fine, and simplest: keep the attribution to
  SHODAN, and licence your mod GPL-3.0 (or GPL-compatible). The Armory Forge author's
  extra permission is not needed on top of that.
- **Copying GPL-3.0 bytes into a permissively-licensed repo?** Not recommended. The
  filter bytes above are exactly that case. Everything else here is the technique plus
  this document's own code, which is why the byte table is deliberately absent.
- **Independent reimplementation is genuinely easy here.** The Windows ABI facts are not
  copyrightable: the `RID_DEVICE_INFO`-sized `{page, usage, flags, target}` layout, the
  `RIM_TYPEMOUSE = 0` / `RIM_TYPEKEYBOARD = 1` usage values on page `0x01`, `flags = 0x1`
  removing a registration, the `GWLP_WNDPROC = -4` index, `CallWindowProcW` chaining, and
  the `WHEEL_DELTA = 120` accumulator. Implement the same slot contract from those facts
  and the safety invariants in §3 and you get the behaviour without the lineage.

If you specifically want the two byte tables (`FILTER_TABLE`, `FILTER_CODE`), get them
from the GPL-3.0 source with that licence noted alongside — they are not reproduced here.

## Evidence / provenance

- `outputs/validated-2026-10-04/hud-compatibility/sources/installed-Super-Earth-Armory-Forge-v6.2.1-0-0.lua`
  — `build_input()` (L2874-3075), `PP.hold_input`/`PP.give_input` (L5330-5400),
  `hotkey_pressed` (L5938-5947), `mouse()` (L5452-5521), cursor take/keep/release
  (L5675-5727), `panel_frame` (L5745+), `panel_tick` (L5949-6001).
  Header comment at L5267-5279 states the raw-input vs window-message split; the panel
  provenance note is at L2822-2831. `CREDITS.txt` in that repository is where the
  (incorrect) "public domain" claim about SHODAN Stat Editor appears — see §6.
- `mods/custom-armor-kit/work/standalone/multi_perk.lua` — the minimal version:
  `sample_input` (L1791-1810), `panel_drag` (L1761-1787). Note its own finding:
  *"the engine's Mouse.button reports unreliably in menu states, which made clicks feel
  dead in the Armory"* — hence `GetAsyncKeyState(0x01)`.
- `mods/custom-armor-kit/work/standalone/test_armor_controls.py` — offline drag/clamp test.

## Gotchas that cost real time

| Symptom | Cause / fix |
|---|---|
| Camera still turns while the panel is open | Only the raw-input registrations were taken; window-message wheel/keys still arrive, or you took only one of mouse(2)/keyboard(6). |
| Keys and clicks still reach the armory behind the panel | Raw-input removal does not stop window messages — you need the `GWLP_WNDPROC` filter. |
| Clicks feel dead in menus | Reading the button from `sr.Mouse.button`. Use `GetAsyncKeyState` (+ `SM_SWAPBUTTON`). |
| Click fires after a drag | No `armed` region / fire-on-release-over-same-region logic. |
| Cursor visible but frozen at screen edge | The game re-hid or re-clipped it; `keep_cursor()` every frame, and clear `ClipCursor`. |
| Cursor invisible again on close, or the game has *two* cursors | `ShowCursor` is a per-thread counter. Count the calls on take and give back the same number; restore the saved clip rect. |
| Game left with no mouse after closing | Give-back used flags needing a window (`INPUTSINK`/`EXINPUTSINK`/`DEVNOTIFY`) or restored another thread's registration. Strip those flags, retry plain, then mark broken and stop. |
| Panel opens when F7 is pressed in another app | No foreground-window check on the edge. |
| Stuck movement/aim after opening the panel | A button held at filter-install time was swallowed; seed the held-bitmask. |
| Wheel does nothing in the panel | The wheel is a window message; counting notches in the filter is the only source while input is held. |
