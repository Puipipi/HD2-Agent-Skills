---
name: hd2-game-language-autodetect
description: "Choose a mod's UI language from HD2's saved or active Text Language. Use when labels should follow the game's language."
---

# HD2 game language auto-detect

> **Confidence:** reported. The offline test seam exists in the armor kit's own tests but was read here, not run.

English / [简体中文](https://github.com/Puipipi/HD2-Agent-Skills/blob/main/docs/skills/hd2-game-language-autodetect_cn.md)

These signals answer different questions: a saved setting is portable but may not reflect a live
change; a verified runtime read can represent the active selection but is build-specific; font
coverage says what can render, not what language the player selected. Choose the source that matches
the product behavior and make its precedence explicit.

| # | Method | Reads | Survives a game update? | Fails when |
|---|---|---|---|---|
| Saved | Persisted `language` setting | the user's settings file | Independent of memory offsets, but the file contract can change and it can lag behind a live change | missing, malformed, unsupported, or ambiguous profile/settings |
| A | Selected **Text Language** via verified game.dll offsets | absolute offsets in `game.dll` | **No** — must be re-derived | offsets shifted; build hash mismatch |
| B | Engine **font glyph coverage** (`Gui.text_extents`) | only the engine's own API | **Yes** | engine font not ready / not measurable |

Method A needs a build proof before it is allowed to read a single byte. Method B needs
nothing but a live GUI handle. A saved setting can avoid memory reads when persisted preference is
the desired signal; Method A is the build-specific active-state route, and Method B is a
renderability check or fallback when the product explicitly wants glyph coverage. A config
override (`lang=zh` / `lang=en`) can remain the manual escape hatch.

> Optional repository companion: [failure catalog](https://github.com/Puipipi/HD2-Agent-Skills/blob/main/docs/hd2-mod-failure-catalog.md). This skill remains usable on its own; no network lookup is required.
> — §5 (memory-read safety: build proof, torn reads, id validation) and §6 (config parsing)
> are the rules this skill applies to a single value.

---

## 0. Read a saved setting when persisted preference is the intended signal

One verified HD2 implementation first reads the user's saved settings file, before attempting a
build-gated runtime read. Its reader uses the current user's application-data path, accepts exactly
one matching profile file and exactly one `language=` key, and maps only known language codes to
`zh` or `en`. Missing, malformed, unknown, or ambiguous settings are not guessed; the reader falls
through to the runtime method. This is a persisted preference, so confirm that it matches the
current session before using it for UI that must react immediately to an in-game language change.

The caller's unknown-language policy is separate from the reader. One menu-registration example
chooses English if both sources fail; other products may preserve their last known language or ask
the user. Do not describe a particular fallback as a property of the reader itself.

For a bilingual ModOptionsMenu, wait until its supported host-ready condition before registering
labels, select the locale once for that registration, and keep option IDs, saved keys, and choice
values stable across languages. Translate visible labels and descriptions; do not translate the
persisted values. A menu registered once does not automatically relocalize if the live game setting
changes later.

---

## 1. Method A — read the selected language (exact-offset, build-gated)

### The pointer chain

```
base = GetModuleHandleA('game.dll')
settings = *(void**)(base + 0x3326340)          ; settings object
index    = *(uint32*)(settings + 705712)        ; selected text-language index
if index >= 15 then fail end                    ; sanity gate
record   = *(void**)(base + 0x37c5650 + index*8); language record table
text     = *(void**)(record + 8)                ; the language code string
code     = text:match('^(%a[%a%-]*)%z')         ; "cn", "us", "zh-CN", ...
```

`cn/tw/zh/zhs/zht/zh-CN/zh-TW → zh`, everything else → `en`.

### Non-negotiable rules

1. **Gate on a build proof first.** `read_game_language()` refuses to run unless the
   same module-hash + byte-signature verification that the rest of the mod uses has
   passed. Never read an absolute offset "just to see".
   The armor kit's proof is: SHA-256 of `game.dll` **and** of the main module must equal
   the recorded build, then a byte compare at a known code site:
   ```lua
   assert(rd(VISBRIDGE.base + 0x14c0350, 16)
       == unhex('48895c24084889742410574883ec208b'), 'native presenter changed')
   ```
   If any of that fails, return `nil`; the caller applies its explicit unknown-language policy.
2. **Re-read the index and compare before trusting the string** (torn-read guard):
   ```lua
   local bytes = rd(settings + 705712, 4)
   local index = bytes and u32(bytes, 0)
   ...
   if rd(settings + 705712, 4) ~= bytes then return nil end   -- changed mid-read
   ```
3. **Validate the result shape**, not just non-nil: `index < 15`, code is `%a[%a%-]*`,
   `#code <= 12`, `text` truncated at a NUL. A garbage pointer otherwise yields a
   plausible-looking string.
4. **Return `nil` on any doubt.** `nil` means unknown, not English. Keep that state distinct and
   let the caller choose an explicit policy; preserving the last value is one option, not a
   universal rule.

### Throttle it

Language cannot change every frame. Poll at most every **120 frames (~2 s)** and cache
the option string so a forced value short-circuits the read entirely:

```lua
local function update_language(option, frames)         -- option: 'auto' | 'zh' | 'en'
    local selected, code
    if option == 'zh' or option == 'en' then
        selected = option                                -- forced: zero memory reads
    elseif M.lang_option ~= option or frames >= (M.lang_due or 0) then
        M.lang_due = frames + 120
        selected, code = read_game_language()             -- may be nil
    end
    M.lang_option = option
    if selected and M.lang ~= selected then
        M.lang = selected
        PANEL.sig = nil                                   -- force a UI redraw in the new language
        log('lang: UI -> ' .. selected .. ' (game=' .. tostring(code or 'config') .. ')')
    end
end
```

Note the two behaviours that matter:
- **First call runs immediately** (`M.lang_due` is nil), so the panel is not English for
  the first two seconds.
- In this `update_language` example, **`selected == nil` keeps `M.lang`**. That is this caller's
  policy; another menu may use an explicit fallback when it registers.
- Only log **on change**, not per poll.

### Test seam (how to prove it offline)

Stub `rd`, `u32`, `u64` and `VISBRIDGE.verify`, then drive `update_language` and assert:
language resolves from the setting, `auto` follows a changed code, an explicit override
wins, an out-of-range index preserves the last value, and a second call in the same
window performs **zero** reads. `test_armor_controls.py` in the Custom Armor Kit does
exactly this and is the model to copy.

---

## 2. Method B — ask the game's own font what it can draw

The engine font is the game's font: it has CJK glyphs when the game's text language is
Chinese and may not otherwise. Measure each character the translation would use and
compare against the width the engine gives a missing glyph.

```lua
local te = sr.Gui and rawget(sr.Gui, 'text_extents')
if te == nil or not font or not font.font then return 'no measuring' end

local function width(s)
    local ok, a, b = pcall(te, gui, s, font.font, 20)
    if not ok or not a or not b then return nil end
    return (Vector3.x(b) or 0) - (Vector3.x(a) or 0)      -- x1 - x0
end

local base, q = width('MMM'), width('?')
if not base or base <= 0 then return 'font not ready' end

local function missing(ch)
    local w = width(ch)
    return not w or w <= 0 or (q and q > 0 and math.abs(w - q) < 0.01)
end
```

Then:
- Collect every **unique** character actually used by the target-language strings
  (`str:gmatch('[\194-\244][\128-\191]*')` walks UTF-8 sequences).
- Measure once per character, cache the verdict per font.
- Decide with a **ratio, not a single character**: `nbad / checked < 0.5` means the font
  can draw the language. Single-character tests give false negatives on punctuation.
- Record *which* characters are missing (`PP.font_bad`) so a later pass can substitute
  ASCII stand-ins (`，→ ,`, `。→ .`, `：→ :`) instead of letting the engine paint `?`.
- **If the ratio fails, stay English.** Do not render a screen of `?`.

Method B can survive game updates, but it detects glyph support rather than the player's selected
language. Use it as a capability check or as an explicitly chosen fallback; do not silently treat
it as the authoritative locale when saved or runtime language state is available.

---

## 3. Wiring it into labels

Keep one translation entry point and never translate data:

```lua
-- UI-only, keyed on the exact source string
local ENLABELS = { ['新建卡片'] = 'New Card', ['保存并应用'] = 'Save & Apply', ... }
local function L(s) if M.lang == 'en' then return ENLABELS[s] or s end return s end
```

Rules that keep this maintainable:

1. **Bake one language, translate at the call site.** Write the code in the language you
   author in (English or Chinese) and run it through `L()` / `tr()` when drawing.
2. **Translate at draw/measure time, never at store time.** Data files, config,
   share codes and logs stay in the original language, so saves move between languages
   unchanged. The Super Earth Armory Forge does exactly this (`PP.tr` is applied inside
   `text()`/`measure()` and nowhere else).
3. **Cache the lookup.** `cache[source_string] = translated`, invalidated when the
   language changes — a panel redraws every frame and a `gsub` chain per frame is
   measurable.
4. **Match longest-first** for partial replacement, and skip short common words
   (`#key < 5..6`) so "on"/"off"/"id" are not replaced inside sentences.
5. **Run a coverage check in CI/local tests**: every label in the fallback table must be
   renderable by the chosen renderer (for a hand-made pixel font, assert every ASCII
   character in every English label has a glyph). The armor kit's
   `test_armor_controls.py` asserts exactly this over `ENLABELS`, `EN_ARMOR_NAMES` and
   `EN_PERKS`.

---

## Evidence / provenance

- `mods/custom-armor-kit/work/standalone/multi_perk.lua` — `read_game_language`
  (L1539-1559), `update_language` (L1560-1574), `ENLABELS`/`L` (L1886-1905),
  `PROBE` localization sweep (L750-794).
- `mods/custom-armor-kit/work/standalone/test_armor_controls.py` — offline test for the
  whole chain, including the "unreadable setting preserves last known language" case.
- `outputs/validated-2026-10-04/hud-compatibility/sources/installed-Super-Earth-Armory-Forge-v6.2.1-0-0.lua`
  — `PP.font_test` (method B) and `PP.tr` (draw-time translation with cache).
- A separate Eagle implementation reads one unambiguous saved `language` setting first and falls
  through to a build-fingerprinted runtime reader; its ModOptionsMenu chooses a locale only after
  the host is ready. Treat this as a source-pattern example, not as a universal settings path or
  evidence that saved settings track live changes.

## Gotchas that cost real time

| Symptom | Cause / fix |
|---|---|
| `attempt to index global 'PANEL' (a nil value)` right after the language flips | Auto-detect changed the UI signature and the panel table was declared *below* the scanner. Forward-declare anything the scan frame touches (`local PANEL`). |
| Language flickers between zh and en | Reading on every frame without a throttle, or trusting a torn read. Throttle + re-compare. |
| Panel goes all-`?` after a game update | Method A's offsets moved or failed validation. Return unknown and apply the caller's explicit policy; use Method B only to check glyph renderability, not to infer the selected language. |
| Translations leak into saved files | `tr()` applied on write instead of on draw. Translate only in the renderer. |
| Engine font measures nothing | Font library is built later than boot; the slot is NULL early. Retry, do not latch "no measuring" for the session. |
