---
name: hd2-in-game-panel
description: Draw a clickable mod panel inside Helldivers 2 using only the engine's Gui.rect primitive — retained screen GUI lifecycle, staged bring-up, z-layer and native-screen invalidation, region hit-testing, panel dragging with saved position, and a 4x5 pixel font (plus packed CJK bitmaps) so text needs no engine font or material. Use when building or fixing an in-game mod UI, especially when Gui.text / materials are unavailable or crash the game.
---

# HD2 in-game panel (rect-only, retained GUI)

> **Confidence:** reported from Custom Armor Kit's source and logs; not rebuilt or run here.

English / [简体中文](https://github.com/Puipipi/HD2-Agent-Skills/blob/main/skills/hd2-in-game-panel/SKILL_cn.md)

A working in-game panel with **no engine font, no material, no Gui.text** — every pixel,
including Chinese characters, is a `Gui.rect`. Source: `Custom Armor Kit 2.5.10`
(`mods/custom-armor-kit/work/standalone/multi_perk.lua`).

**Why this shape:** `World.create_screen_gui` before the engine finished building its
font/material libraries faults at **native** level — `pcall` does not catch it. Evidence:
the log stopped at `building the panel`, the process threw `ntdll 0xc0000026` every few
seconds, and the frame callback stayed dead. Rects carry no such dependency.

> Companion reading: [`docs/hd2-mod-failure-catalog.md`](../../docs/hd2-mod-failure-catalog.md)
> — §1 (native crashes `pcall` cannot catch), §2 (engine build timing) and §3 (the three
> reasons a retained panel goes invisible) are the failure modes this skill is shaped around.

---

## 1. Hard preconditions (all four, or defer the whole frame)

```lua
local function ui_frame(conf_data, frames)
    if not M.ship_ok then return end                  -- ship gate / native screen gate
    if not M.ship_world then return end               -- world resolved (~frame 600)
    local sr = rawget(_G, 'stingray')
    if type(sr) ~= 'table' or type(sr.Gui) ~= 'table' then return end
    if not (M.ui_font and M.ui_material) then return end
    local okr, rw, rh = pcall(sr.Gui.resolution)
    if not okr or rw < 640 or rh < 480 then return end
    ...
end
```

- Never call `create_screen_gui` before the ship world exists. The panel was armed at the
  wrong time once and the panel's own creation killed the frame callback.
- Re-check `stingray.Gui` **every frame** — it is absent in some states.
- `Gui.resolution()` is the only layout authority; validate plausible numbers before use.

## 2. Staged bring-up — one engine milestone per step, logged

Do not do "create + bind + text + draw" in one call. Each step returns `ok, why` and the
ladder only advances on success, so a failure names the exact engine call:

```lua
local LNAMES = {'create gui','bind material','dance (off)','dance (off)','dance (off)',
                'draw panel','text (off)','finalize'}

if n == 1 then
    local okg, gui = pcall(sr.World.create_screen_gui, PANEL.world, 'scale', 1, 1)
    if not okg or gui == nil then return false, 'create: ' .. tostring(gui) end
    PANEL.gui = gui
    PANEL.draw_guis = {{world = PANEL.world, gui = gui}}
    return true
end
if not PANEL.gui then return false, 'gui lost before step ' .. n end
if n == 2 then
    -- binding only proves the id resolves; the ink is intentionally unused
    local oki, ink = pcall(G.material, PANEL.gui, material_id64)
    if not oki then return false, 'G.material error: ' .. tostring(ink) end
    return true
end
if n == 6 then panel_draw(conf_data, rw, rh) return true end
```

Steps 3-5 and 7 are `return true, 'skipped (...)'` — the material-parameter dance
faulted at native level even with a verified id64. **A skipped-by-design step must still
be honest in the log**; do not silently drop it.

## 3. Retained GUI: you must invalidate deliberately

The engine keeps a screen GUI's primitives until that GUI is recreated. So the panel is
**not** re-created per frame; a signature decides whether the retained copy is stale:

```lua
if PANEL.sig ~= sig then
    PANEL.sig = sig
    PANEL.gui = nil                 -- force re-creation next frame
    PANEL.ladder, PANEL.ladder_done = 1, false
    panel_clear()                   -- destroy every GUI this panel owns
end
```

Invalidate on: panel opened/closed, language changed, draw layer changed (`layer=` in
config), native screen changed, resolution changed, any state that alters layout.

Two traps that both produce "the click does nothing":

- **Layer.** A retained GUI redraws at its old layer, so a `layer=` change *must* rebuild.
- **Native screens above you.** The armory draws its own full-screen layer, and a panel
  built before the armory opened stays **under** it forever. Watch the native screen id
  and rebuild when it changes:
  ```lua
  local screen = (M.gate_info and M.gate_info.ui and M.gate_info.ui.screen) or 0
  if screen ~= M.ui_screen then
      M.ui_screen = screen
      if PANEL.armed and M.ship_ok then PANEL.sig = nil end   -- redraw, do not just log
  end
  ```

## 4. Teardown — `panel_clear()` must be complete

```lua
local function panel_clear()
    local sr = rawget(_G, 'stingray')
    if sr and sr.Application and sr.World then
        local function owner_is_live(owner)
            if not owner then return false end
            local app = sr.Application
            if type(app.main_world) == 'function' then
                local ok, main = pcall(app.main_world)
                if ok and main == owner then return true end
            end
            -- Use only this game's verified world-list API. If its snapshot is
            -- unavailable, the old native owner is unknown and must not be touched.
            if type(app.worlds) == 'function' then
                local ok, worlds = pcall(app.worlds)
                if ok and type(worlds) == 'table' then
                    for i = 1, #worlds do
                        if worlds[i] == owner then return true end
                    end
                end
            end
            return false
        end
        local entries = PANEL.draw_guis or {{world = PANEL.world, gui = PANEL.gui}}
        for _, entry in ipairs(entries) do
            if entry.gui and owner_is_live(entry.world) then
                pcall(sr.World.destroy_gui, entry.world, entry.gui)
            end
        end
    end
    PANEL.gui, PANEL.draw_guis, PANEL.sig = nil, nil, nil
    PANEL.regions, PANEL.font, PANEL.material, PANEL.ink = {}, nil, nil, nil
    PANEL.bounds, PANEL.move_x, PANEL.move_y, PANEL.drag = nil, nil, nil, nil
    PANEL.ladder_done = false
    PANEL.ladder, PANEL.lnext, PANEL.lfail = 1, 0, 0
end
```

- Destroy only a GUI this panel owns, and only after a fresh `main_world()` or `worlds()`
  snapshot confirms its owner is still live. If the owner is missing or the snapshot fails,
  clear the Lua handle and stop using it; do not call native destroy on an uncertain world.
  `pcall` catches Lua errors, not native faults from stale engine objects. An owned GUI whose
  owner remains live as an overlay may still be destroyed after current snapshot confirmation;
  owner liveness does not guarantee every native destroy call is safe.
- When the UI manager creates multiple owned GUI copies, apply that same live-owner check
  separately to every copy; never destroy objects owned by another mod.
- Reset the ladder so returning from a menu re-runs bring-up.
- Do not create a GUI in an unverified or unsupported world just to chase draw layers; use
  the currently verified owner context. This panel may destroy only GUI objects it created,
  never a game world.
- Offline test: count live GUI objects before/after two frames and assert exactly one,
  then `panel_clear()` and assert the set is empty
  (`mods/custom-armor-kit/work/standalone/test_armor_ui.py` does this with `lupa`).
- AutoChat's [`test_panel_interaction.py`](https://github.com/Puipipi/HD2-AutoChat/blob/4445596a76ed387edc3c09d0d25aa9d06ffd5b11/work/standalone/tests/test_panel_interaction.py)
  also distinguishes a replaced main world whose old GUI owner is still in the live world
  list (destroy it) from a missing/replaced owner that must be discarded without native access.

## 5. Geometry and layout

```lua
local scale = math.min(rw / 1920, rh / 1080)          -- one scale factor, everywhere
local pw    = 560 * scale                             -- panel width
local px    = rw - pw - 20 * scale                    -- docked bottom-right
local rowh  = 54 * scale; local titleh = 78 * scale; local hint = 30 * scale
local content = titleh + hint + #cards * rowh + rowh   -- height derived from content
local x, y = px, rh - 94 * scale - content
if y < 10 then y = 10 end
```

- **Gui origin is bottom-left.** A "title at the top" is at `y + h - titleh`.
  Bitmap row 1 of a glyph is its **top**, so it lands at the highest y:
  `rect(x + col*zcell, y + (bm.h - r)*zcell, ...)` — getting this backwards mirrors text.
- Derive height from content per mode; clamp to the viewport.
- Store `PANEL.bounds = {x=, y=, w=, h=, title=}` — hit-testing and dragging both need it.

### Moving the panel without rebuilding it

Use `Gui.move` on the retained GUI, and compute a **delta** from the desired position:

```lua
local function panel_offset(sr, rw, rh)
    local b = PANEL.bounds
    if not b then return 0, 0 end
    local s = math.min(rw / 1920, rh / 1080)
    local x, top = b.x, b.y + b.h
    if PANEL.place then x, top = PANEL.place.x * s, PANEL.place.top * s end
    x   = math.max(0, math.min(rw - b.w, x))
    top = math.max(b.h, math.min(rh, top))            -- keep the whole panel in view
    local dx, dy = x - b.x, top - b.y - b.h
    if PANEL.gui and (dx ~= PANEL.move_x or dy ~= PANEL.move_y) then
        local ok, why = pcall(sr.Gui.move, PANEL.gui, dx, dy)
        if not ok then return PANEL.move_x or 0, PANEL.move_y or 0 end
        PANEL.move_x, PANEL.move_y = dx, dy
    end
    return dx, dy
end
```

- **Never call move when the delta is unchanged** — a stationary panel must perform zero
  native calls (assert this in a test).
- Dragging starts on the **title strip** (`y >= b.y + b.h - b.title`) and follows the
  cursor until the button is released; on release, persist `x/top` to
  `panel_position.txt` and keep the drawn position.
- Clamp during the drag too, not only at load.

## 6. Click handling: press-edge against regions built this frame

`panel_draw` rebuilds `PANEL.regions` from scratch on every draw, and the input pass
consumes them — so hit-testing always matches what is on screen **this** frame.

```lua
PANEL.regions = {}
-- ... while drawing ...
PANEL.regions[#PANEL.regions+1] = {x=bx, y=by, w=bw, h=bh, action='save', index=i}

-- ... in the input pass ...
if not dragging and input and input.down and not PANEL.was_down then
    for _, r in ipairs(PANEL.regions) do
        if input.x >= r.x and input.x < r.x + r.w
           and input.y >= r.y and input.y < r.y + r.h then
            -- dispatch on r.action / r.index
        end
    end
end
```

- **Press edge only** (`down and not PANEL.was_down`) — no repeat while held, no ghost
  click on release.
- A drag swallows the click; check `dragging` first.
- Every input sample goes through `pcall`; a sample error must not kill the frame.
- The same action must be reachable from a **non-mouse** path where possible (the armor
  kit dispatches rows by number key too) so the panel survives a scene that refuses to
  show a pointer.

## 7. Text with no engine text API

### 4x5 ASCII pixel font, drawn with the one proven primitive

```lua
local GLYPHS = {}
local defs = { A='0110 1001 1111 1001 1001', B='1110 1001 1110 1001 1110', ... }
for ch, def in pairs(defs) do
    local rows = {}
    for row in def:gmatch('%d+') do rows[#rows+1] = row end
    GLYPHS[ch] = rows
end

local function asciirun(x, y, s, c, cell)
    local cx = x
    for i = 1, #s do
        local g = GLYPHS[s:sub(i,i)]
        if g then
            for r = 1, 5 do
                local row = g[r]
                for col = 1, 4 do
                    if row:sub(col,col) == '1' then
                        rect(cx + (col-1)*cell, y + (5-r)*cell, cell, cell, c)
                    end
                end
            end
        end
        cx = cx + 5*cell
    end
    return cx
end
```

- Cell size matched to the CJK glyph height so mixed text reads evenly:
  `acell = max(2, floor((16*zcell)/5 + 0.5))`.
- Uppercase everything ASCII — then assert in a test that **every** character used by
  every label exists in `GLYPHS`. A missing glyph silently renders nothing.

### Packed CJK bitmaps

Ship CJK as a **packed string**, not a giant Lua table constructor: LuaJIT's
65535-bytecode-instruction-per-function cap turns a large constructor into
`function too long` and the loader **silently skips the whole mod**. Parse lazily on
first draw:

```lua
-- ZH_PACK: one line per glyph, "hexkey,w,h,row.row.row..." with rows as hex nibbles
local function zh_init()
    if zh_inited then return end
    zh_inited = true
    local hc = {}
    for b = 0, 255 do hc[string.format('%02x', b)] = string.char(b) end
    for line in ZH_PACK:gmatch('[^\n]+') do
        local kh, w, h, rows = line:match('^(%x+),(%d+),(%d+),(.+)$')
        if kh then
            local key = {}
            for i = 1, #kh, 2 do key[#key+1] = hc[kh:sub(i,i+1)] end
            local r = {}
            for row in rows:gmatch('[^.]+') do r[#r+1] = row end
            ZH[table.concat(key)] = {w = tonumber(w), h = tonumber(h), r = r}
        end
    end
end
```

- Key glyphs by the **phrase** first (a packed phrase beats per-character packing), then
  fall back to per-character, then to a blank advance.
- Walking a UTF-8 string: derive the length from the lead byte
  (`>=0xF0 → 4`, `>=0xE0 → 3`, `>=0xC0 → 2`, else 1). Do not assume 3.
- Log **once** when a character is outside the packed font (`M.zh_miss`) — one line, not
  one per frame.

### One text entry point that handles all three kinds

```lua
local function txt(x, y, s, c, acell_)
    if type(s) == 'table' then                 -- pre-packed bitmap
        if s.r then return zhdraw(x, y, s, c) end
        return x
    end
    local bm = ZH[s]
    if bm then return zhdraw(x, y, s, c) end   -- whole packed phrase
    s = tostring(s):upper()
    if s:find('[\128-\255]') then              -- mixed: split into CJK / ASCII runs
        ...
    end
    return asciirun(x, y, s, c, acell_ or acell)
end
```

Mixed strings are the easy bug: `L('[ 打开 ]')` and `'已选 3'` previously lost their CJK
half to the ASCII fallback. Split the string into maximal runs by
`byte(i) >= 128` and render each run with the right path, carrying the x cursor forward.

### Chinese bitmap scale

```lua
local zcell = math.max(1, math.floor(1.15 * scale + 0.5))     -- 1 unit per font pixel
```
`zhdraw(x, y, bm, c)` walks `bm.r`, expands each hex nibble into 4 pixels via a
`W8 = {8,4,2,1}` bit test, and returns `x + (bm.w + 2) * zcell` so the next glyph
advances correctly.

### Responsive layout when a text path is verified

Keep the rect-only renderer as the safe default. Call `Gui.text` or
`Gui.text_extents` only after the font path and its lifecycle are verified; do not probe an
unverified engine API just to measure. For a rect/CJK fallback, measure with the same glyph
advance and fallback rules that the renderer actually uses, including mixed CJK/ASCII runs.

Lay out labels and help by measured width at the same font, size, scale, and locale used to
draw them. Wrap on UTF-8 codepoint boundaries, normalize CRLF as one line break, and keep
explicit leading, interior, and trailing blank lines. Use line count and line spacing to calculate
the required text-block and control-row heights, then advance later y positions. Keep the font,
spacing, and padding readable; apply one consistent scale to padding, line height, and control
sizes. Reducing the font is not a substitute for fitting the content.

Use a side-by-side label/value or input only when both fit the available width. Otherwise stack
them and move later controls down. Apply the same rule to tabs, navigation, and buttons. Keep
each hit region aligned with the visible control after wrapping or clipping; fully clipped
controls must not remain clickable. Static help should wrap instead of silently truncating.
Long user-entered values may scroll horizontally to keep the caret and visible tail in view
without changing the stored value.

Give independently scrollable content its own viewport and offset. Clip both drawing and hit
regions to that viewport, clamp offsets after content or size changes, and make the last item
reachable. For long lists, draw only visible rows plus a small overscan instead of traversing
and drawing every item each frame. A retained panel should redraw only when its signature is
dirty; do not add a cross-frame measurement cache without a clear invalidation key. Keep
measurement work inside the redraw path rather than repeating it on ordinary frames.

Verify through the production draw and hit-test path, not only a wrapping helper: capture the
drawn text and rectangles, assert their bounds against each viewport, and compare visible
controls with their hit regions. Include narrow resolutions, wide CJK metrics, English and
Chinese, long help/name samples, scroll-to-end, and an input-tail case when those paths exist.
Keep these layout assertions separate from performance timing; see
[`hd2-offline-engine-harness`](../hd2-offline-engine-harness/SKILL.md) for offline cost comparisons.
AutoChat's [panel source](https://github.com/Puipipi/HD2-AutoChat/blob/4445596a76ed387edc3c09d0d25aa9d06ffd5b11/src/auto_chat.lua)
and tests cover low-resolution bilingual timer/forms ([`test_ui_preview.py`](https://github.com/Puipipi/HD2-AutoChat/blob/4445596a76ed387edc3c09d0d25aa9d06ffd5b11/work/standalone/tests/test_ui_preview.py)),
enemy help and clipped hitboxes ([`test_alert_layout.py`](https://github.com/Puipipi/HD2-AutoChat/blob/4445596a76ed387edc3c09d0d25aa9d06ffd5b11/work/standalone/tests/test_alert_layout.py)),
and the last-row interaction in a 105-task list ([`test_panel_interaction.py`](https://github.com/Puipipi/HD2-AutoChat/blob/4445596a76ed387edc3c09d0d25aa9d06ffd5b11/work/standalone/tests/test_panel_interaction.py));
that evidence does not cover every font or every mod. For lifecycle and focus/input ownership, use
[`hd2-native-panel-input-lock`](../hd2-native-panel-input-lock/SKILL.md).

## 8. Logging that makes a hidden panel diagnosable

One line per state change, plus a heartbeat every N frames while blocked — never per
frame:

```lua
local changed = (M.gate_phase ~= phase) or (M.gate_last_reason ~= reason)
if changed or frames - M.gate_last_frame >= 600 then
    log('ui gate ' .. phase .. ': ' .. tostring(reason) .. ' frame=' .. frames
        .. ' world=' .. tostring(world) .. ...)
end
```

Log at least: whether the GUI exists, `Gui.is_visible`, ladder step, resolution, world
identity (use a weak-keyed serial map — `tostring(world)` is `[World]` for every world),
and the blocking reason by name. "blocked" with no reason costs hours.

## 9. Offline test harness (LuaJIT behaviour without the game)

There is no way to unit-test the engine, but you can test *your* code against an engine
boundary. `lupa` (LuaJIT inside CPython) plus a fake `stingray` table that counts
`create_screen_gui` / `destroy_gui` / `Gui.move` calls catches:

- retained rebuild leaks (two frames must create exactly one GUI),
- `panel_clear()` not destroying something,
- a stationary panel calling `Gui.move`,
- drag clamping outside the viewport,
- bring-up finishing within eight frames with **no fixed waits**,
- the cards branch drawing distinct labels for two cards that share an armor id.

Run it as part of the normal test suite; it is much cheaper than finding the same bug live.

---

## Evidence / provenance

- `mods/custom-armor-kit/work/standalone/multi_perk.lua` — `ui_frame` (L2593-2740),
  `panel_draw` (L2035-2398), `ladder_step` (L2402-2447), `panel_clear` (L1713-1730),
  `panel_offset` (L1737-1760), `panel_drag` (L1761-1787), `GLYPHS` (L1814-1849),
  `zh_init` (L1862-1880), `ui_resources` (L1414-1487), screen-change redraw (L3026-3037).
- `mods/custom-armor-kit/work/standalone/test_armor_ui.py`,
  `test_armor_controls.py` — the offline lifecycle / drag / font-coverage assertions.
- `mods/custom-armor-kit/RETIREMENT-FINDINGS.md` — the native-crash write-up for
  creating a GUI before the engine's resource libraries exist.

## Gotchas that cost real time

| Symptom | Cause / fix |
|---|---|
| `ntdll 0xc0000026`, frame callback dead, log stops at "building the panel" | `create_screen_gui` before the engine's font/material libraries exist. Gate on ship world + resources; `pcall` will **not** save you. |
| Panel is built but invisible | Retained GUI below a native screen (armory) or wrong `layer`. Rebuild on native-screen / layer change. |
| Clicks do nothing but the UI looks fine | Hit-test against `PANEL.regions` from **this** frame, consume the press edge, and ignore samples while dragging. |
| Text renders mirrored | Bitmap row 1 is the glyph top; draw it at the highest y (`bm.h - r`). |
| Mod silently does not load at all | Oversized table constructor → `function too long` in LuaJIT. Pack the data into a parsed string. |
| Mixed zh/en label loses its Chinese half | ASCII fallback applied to the whole string. Split into UTF-8 runs. |
| `Gui.move` stack builds up | Move on delta change only; assert zero calls when stationary. |
