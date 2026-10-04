# Field guide: what breaks an HD2 Lua mod, and how to tell it apart

English / [简体中文](https://github.com/Puipipi/HD2-Agent-Skills/blob/main/docs/hd2-mod-failure-catalog_cn.md)

> 中文版：[hd2-mod-failure-catalog_cn.md](hd2-mod-failure-catalog_cn.md)

For people writing a Helldivers 2 mod (Bingus/MDL loader, LuaJIT FFI). Every entry below is
a **symptom → root cause → fix** taken from a real attempt, mostly from the Custom Armor
Kit 2.5.10 and SmoothBoot development logs in this workspace. The point is that you should
recognise the failure and know what to log *before* you spend a weekend on it.

Read §1 first. It is the single most expensive thing on this page.

---

## 1. `pcall` does not catch native crashes

**This is the rule that costs the most time.** `pcall` traps Lua errors. A wrong pointer,
a NULL engine slot or a bad native call does not raise a Lua error — it faults inside
`game.dll`/`ntdll` and takes the process with it.

Observed shapes:

| Shape | What it looks like | Example |
|---|---|---|
| `ntdll 0xc0000026` (`STATUS_INVALID_DISPOSITION`) repeating every few seconds, frame callback dead | The game keeps running but your mod never ticks again | `World.create_screen_gui` called before the engine built its font/material libraries |
| `APPCRASH` in `game.dll` with an address in the log | Hard crash to desktop | `G.set_scalar` / material parameter calls with an unverified id64 |
| Silent stop | Log simply ends mid-function, nothing after | Any native call in a `pcall` that "returned" but never came back |

Consequences for how you write the mod:

1. **Never call into the engine to "see if it works."** Guard on a positive fact you already
   have (world resolved, resource slot non-NULL, build verified) and skip the frame otherwise.
2. **A guard must be a value check, not a `pcall`.** `local ok = pcall(f)` tells you nothing
   about whether `f` was safe to call. `if slot ~= nil and slot > 65536 then ... end` does.
3. **Order your work so the unsafe part is last.** Read → validate → then call.
4. **Log before every risky call, not after.** The line before the crash is your only witness.
   Several of these were diagnosed purely from "the log stops at this string".

---

## 2. Timing: the engine is not built yet

The engine comes up in stages. Everything below was observed as a real failure.

| Symptom | Root cause | Fix / evidence |
|---|---|---|
| `ntdll 0xc0000026` loop; log stops at `building the panel` | `World.create_screen_gui` before the font/material libraries exist | Defer all panel work until the **ship world resolves** (armor kit: it resolves around frame 600). Log `held - ship world not resolved yet` once, not per frame |
| `Attempt to index a nil value` in an engine slot read | The resource **slot** holds NULL early even when the manager pointer is valid | Retry instead of latching failure. The armor kit retried every 600 frames after having abandoned the panel for a whole session on one early failure |
| Panel works on the ship, invisible in the armory | The armory is a different/native screen; a retained GUI built for the ship is not shown there | Watch the native screen id and rebuild (see §3) |
| Language/font measurements return nothing | Font library built later than boot | Treat "not measurable" as *retry*, never as "unsupported" |

Rule: **anything that depends on an engine library must be retried on a frame budget, and
the first success must be logged** (`drawing resources acquired on try N`). If you latch a
failure at boot you will ship a mod that is dead for the whole session on some machines.

---

## 3. Retained GUIs: the panel "disappears" for three different reasons

`create_screen_gui` returns a **retained** object. The engine keeps drawing its primitives
until you destroy it. That gives three distinct failure modes with the *same* user-visible
symptom:

1. **You invalidated the signature but never rebuilt.** The GUI was destroyed and the draw
   path did not run again.
2. **The layer is stale.** A retained GUI keeps drawing at the layer set when it was built.
   Changing `layer` in config therefore requires a rebuild — a live layer change does
   nothing (armor kit: `ui: draw layer -> N (panel redraw requested)`).
3. **Another screen draws above you.** The armory draws its own full-screen layer. A panel
   built before the armory opened stays underneath it for the rest of the visit (armor kit:
   `ui: native screen X -> Y ... (panel redraw requested)`).

Fixes:

- Invalidate on **all** of: open/close, resolution, language, draw layer, native screen id,
  and any state that changes layout.
- Rebuild the GUI where it must be visible, and **destroy every GUI you own in every world**
  when clearing (the armory path builds a copy per world):
  ```lua
  for _, entry in ipairs(PANEL.draw_guis) do
      pcall(sr.World.destroy_gui, entry.world, entry.gui)
  end
  ```
- If you invalidate per frame instead of per state, you will allocate and destroy a GUI every
  frame. Test it: two frames must create exactly **one** GUI.
- Offline, this is testable with `lupa` — see the harness note in §9.

**Do not allocate a GUI in a world you do not own.** That experiment caused a native crash.

---

## 4. LuaJIT limits that fail *silently*

| Limit | Symptom | Fix / evidence |
|---|---|---|
| **65535 bytecode instructions per function** | `function too long` at load; the loader **silently skips the whole mod** — nothing in the log | Hit for real by a large bitmap table constructor. Pack data into a string and parse lazily at first use |
| **200 locals per function** | `too many local variables` | The panel is one big function for exactly this reason (`The whole panel lives in one function: Lua allows 200 locals per function`); if you hit it, split into closures or make the panel a table of methods |
| **Calls made very early can hang the game** | One reporter's game hung at frame 120 | Spawning a shell / `CreateDirectoryW` from the update thread. Prefer `ffi` calls, do file work once at startup, never per frame |

The silent-skip behaviour is what makes the bytecode cap so expensive: you get a mod that
"installed fine" and does nothing. When a mod produces **no log line at all**, suspect this
first.

### 4b. Two pure-Lua traps that read like engine bugs

Both were hit while writing `template/panel_skeleton.lua`, and both are worth recognising
because the symptom points at the engine instead of at your code.

**A `local` declared below an earlier function is not in scope in that function.** It
compiles, and the name silently becomes a *global* read:

```lua
local function frame()
    if count >= FAIL_LIMIT then return end   -- FAIL_LIMIT is NOT the local below!
end
local FAIL_LIMIT = 5                          -- too late: out of scope above
```

`FAIL_LIMIT` inside `frame` is the global, i.e. `nil`, so `0 >= nil` raises
`attempt to compare number with nil` on the first frame. Lua emits no warning. Declare
limit constants above the functions that use them, and if a guard behaves as if a constant
were nil, check the declaration order before the engine.

**`local ok, a = pcall(fn, ...)` drops every return value after the first.** A two-value
engine call then arrives with a nil second value, and every guard checking it fails
forever:

```lua
local function call(what, fn, ...)
    local ok, a = pcall(fn, ...)     -- resolution()'s second value is gone
    return true, a
end
local ok, w, h = call('Gui.resolution', sr.Gui.resolution)   -- h is always nil
```

The symptom is a permanent `resolution not numeric` / "the engine never returns what the
docs say" — you will go and re-derive an engine offset that was never wrong. Spell the
arity out (`local ok, a, b = pcall(fn, ...)`) and grow it deliberately; do not paper over
it with `select('#', ...)`, which makes the caller's destructuring unsafe.

Both are covered by the offline harness (`hd2-offline-engine-harness`), which is the
point of having one: these bugs are invisible in code review and instant in a test.

---

## 5. Reading the game's memory

- **Read only committed, private, readable pages.** Use
  `VirtualQuery` and skip `state ~= 0x1000 (MEM_COMMIT)`, `prot == 0` (no access) and
  `prot == 1` (no access). The armor kit also prefers pages `>= 64 KiB` for scans, and a
  `Hot` window around the first structural hit (Armory Forge walks ±4 MiB around the first
  armor-passive block instead of the whole address space).
- **Bound every read.** The armor kit's reader refuses `n < 1 or n > 262144`, addresses
  below `65536`, and above `140737488355328`. Clamp before you pass a length to
  `ReadProcessMemory`.
- **Never write to a guard page.** Before `WriteProcessMemory`, read `VirtualQuery`'s
  protect field and reject anything `>= 0x100` (guarded/noaccess) or `0`. Then
  `VirtualProtect` to RW, write, and **restore the original protection**. Fighting guard
  pages corrupts live engine state.
- **Verify builds before using absolute offsets.** Hash the module (`BCrypt` SHA-256 of
  `game.dll` plus the main module) and compare a short byte signature at a known code site.
  Skip the whole feature when it does not match rather than reading a stale offset:
  ```lua
  assert(rd(base + 0x14c0350, 16) == unhex('48895c24084889742410574883ec208b'),
         'native presenter changed')
  ```
- **Torn reads are real.** Read a value, derive from it, then re-read the source and compare
  before trusting the result (the armor kit's language read does exactly this).
- **`VirtualQuery` inspects YOUR process, not the target.** The non-`Ex` forms
  (`VirtualQuery`, `VirtualProtect`) act on the calling process; for a cross-process tool you
  must use `VirtualQueryEx(handle, addr, …)` / `VirtualProtectEx(handle, …)`. Getting this
  wrong is silent and self-consistent: the tool truthfully reports the page unreadable — for
  the wrong address space — so a probe reports `total writes=0` and the run looks like a
  negative result. This cost a live validation round in
  `mods/mobility-optimization` (`tools/ability1_live.py` §docstring).
- **A write needs a handle with write rights — a read-only handle fails as "zero writes".**
  A handle opened with `PROCESS_QUERY_INFORMATION | PROCESS_VM_READ` cannot
  `VirtualProtectEx`; it needs `PROCESS_VM_OPERATION`, and `WriteProcessMemory` needs that
  **plus** `PROCESS_VM_WRITE` (`0x0400 | 0x0010 | 0x0008 | 0x0020`). Reusing a reader's handle
  for a write path is a category error, and it does not report "permission denied" — it
  reports that nothing was written.
- **A "write happened once" observation may be code-path specific.** One state byte appeared
  to be written only on a key press — until the character was actually *moving*, and the game
  recomputed it **every frame**, overwriting any single clear within ~50 ms. Verify a write is
  still there N frames later, under the conditions you intend to ship.
- **Validate id64s.** Engine id64s are large. The armor kit refuses a captured value below
  `2^48` as "looks like a pointer or garbage", and for the material slot it follows the
  pointer (the real id64 lives 24 bytes in) because feeding `G.material` a wrong id makes it
  return garbage ink and faults later at native level.
- **The on-disk `game.dll` is packed: you can hash it, but you cannot read code from it.**
  Measured on build 25480438 (`data/game/game.dll`, 15,522,408 bytes):

  | Observation | Value |
  |---|---|
  | SHA-256 of the on-disk file | matches the loader's `GAME_DLL_SHA` gate constant exactly |
  | PE header parse | fine — `PE\0\0`, 16 sections, `machine=0x8664` |
  | section **names** of the main sections | blanked to spaces |
  | Shannon entropy of the section holding the code | **7.9998** (8.0 = random) |
  | custom sections present | `.winlice`, `.vm_sec`, `.boot` (a decompression stub) |
  | a 16-byte code signature at its RVA, anywhere in the file | **absent** |

  Consequences, in order of how much time they cost:

  - **Hashing the disk file is correct and useful.** That is exactly what the loader's version
    gate does, which is why the disk SHA-256 matches `GAME_DLL_SHA`. Fingerprint checks are fine.
  - **Reading code, scanning for a byte signature, or mapping an RVA to a file offset on the
    disk image is meaningless.** The RVAs resolve past the section's raw data (virtual size is
    far larger than raw size) and the bytes there are not what the process executes. Scan the
    file and you get "signature not found", from which it is easy to wrongly conclude the game
    updated.
  - **To analyse code offline, dump it from the process first and analyse the dump.** The
    `melee-vehicle-rescue` tools are the right shape: `tools/dump_range.py` and friends write
    `research/private/*.bin`, and `pe_sections.py` / `native_xrefs.py` / `raw_strings.py` /
    `type_tables.py` read those snapshots — never the installed file. `c4_input_facts.py` scans
    live process memory instead. Both work; reading the install does not.
  - **Do not try to unpack it yourself.** Verify the build by hash, then read what you need
    from the running process.

---

## 6. Config / data handling in a shipped mod

Config bugs are cheap to prevent and expensive to debug, because the mod is the only thing
that ever sees the file:

- **Parse strictly.** Match the whole line with an anchored pattern
  (`^%s*rows%s*=%s*(%d+)%s*$`) so a commented-out or partial line cannot silently change
  behaviour. Ignore comments explicitly.
- **Clamp every numeric option** (`math.max(1, math.min(11, v))`) — a bad value must not
  reach an engine call.
- **Keep a legacy flag from changing behaviour.** The armor kit forces
  `statrows = true` regardless of the config value, because the option no longer controls
  anything and users still have it in their file.
- **Never truncate to fit a limit.** Oversized merges are *refused*; a truncated record
  fast-fails the game. Refusing with a message beats a crash.
- **Read-modify-write the config carefully.** Unknown keys must survive: the armor kit strips
  only its own `card.*` lines, rewrites them, and leaves every other line untouched.
- **Never write to the config during a frame where you also read it** without clearing the
  cache (`M.conf_text = nil`), or the change is invisible until restart.

---

- **A config fix missed one of two parsers.** The same settings file was read by a sectioned
  parser and by a flat one. A fix applied to one was overwritten by the other, so the change
  looked ineffective. When you touch config parsing, enumerate every parser before declaring it
  fixed — the mod had two, and both had to change (`stratagem-cooldown` 2.9.5 → 2.9.6).
- **Chinese values silently produced invalid keys.** Values like `仅载具` / `仅支援武器` / `全部`
  parsed to nothing, so the config line was written and ignored — and a malformed value like
  `仅vehicles` was generated. Fix: an alias table, matched **longest-first**, covering every new
  word. Evidence: `stratagem-cooldown` `docs/pitfalls-and-fixes.md` §3.
- **An unknown category was excluded by default.** `in_scope()` rejected anything it did not
  recognise, `nil` included, so any stratagem added by a future game update would simply not be
  modified. Default unknown families to following the existing colour/toggle switches instead of
  to exclusion (`stratagem-cooldown` 3.8.0). Default-open fails loudly; default-closed fails by
  doing nothing.

## 7. Logging that makes a bug findable

The mods that got fixed had this; the ones that did not, did not.

1. **One line per state change**, plus a heartbeat every N frames while stuck. Not per frame.
2. **Name the reason, never a bare "blocked".** `ui gate blocked: no_ship_markers frame=1832
   world=3 session=false in_session=false markers=0` is a diagnosis; `ui gate blocked` is a
   support thread.
3. **Log the facts you will need, before you need them**: resolution, GUI exists,
   `Gui.is_visible`, ladder step, world count, and a **stable serial per world object** —
   `tostring(world)` prints `[World]` for every world, so it cannot tell two apart:
   ```lua
   local map = setmetatable({}, {__mode = 'k'})   -- weak keys: no leak
   ```
4. **Log the first success of every retried resource** and the attempt count when it keeps
   failing (`still missing (try 40) font=nil material=nil`).
5. **Write a STATUS file** the user can send when the panel never opens (Armory Forge's
   `ArmoryForge-STATUS.txt`). If your only diagnostics live in a panel that will not draw,
   they do not exist.
6. Keep a **local development driver** (a marker file plus a command file, e.g.
   `development.enable` + `development.command`) so you can drive the mod from outside
   instead of adding hotkeys you will ship. Disabled unless the marker is present.

---

## 8. Things that look doable and are not

Verified dead ends. Do not spend time here.

| Attempt | Result |
|---|---|
| Allocating the screen GUI in another world to keep it alive | Native crash |
| The material parameter dance on this engine build | Faults at native level **even with a verified id64**; rects need no material — skip it and say so |
| Setting the material id to a pointer-or-garbage value | `G.material` returns junk ink, `set_scalar` faults later, `pcall` catches none of it |
| Live colour-scheme swaps | Worked for a second, then the game unloaded the textures and the armour went black — dropped rather than shipped |
| A retried-once resource acquisition | One early NULL slot abandoned the panel for the whole session |
| Closing the star map / star map with injected input | `Tab` opens it and cannot close it; injected `Esc`/right-click do not either (see `hd2-mission-entry`) |

---

- **`tasklist`'s `/FI` filter is case-sensitive, and the wrong case reads as "not running".**
  Checking for `Helldivers2.exe` against a process actually named `helldivers2.exe` reported the game
  as not started — four times, each costing a round trip. Detect the lowercase name, and treat a
  process check that gates a whole run as something to log rather than to trust.
- **Launch through Steam (`-applaunch`), not the exe.** Running `helldivers2.exe` directly leaves a
  ~92 MB Steam DRM stub spinning, which presents as a black screen or a hang and gets blamed on the
  game or on a mod. The symptom disappears when the game is started the way Steam starts it.
- **A stale package in the mod manager's library will overwrite a newer layer.** With an old package
  in the library and a hand-placed newer layer on disk, pressing Deploy applies the old one. Either
  re-import the new package before deploying, or use only the layer already in place — and prefer
  having exactly one package in flight.

## 9. Test the parts you can, offline

You cannot unit-test the engine. You can test **your** code against an engine boundary:

- `lupa` (LuaJIT in CPython) + a fake `stingray` table that counts `create_screen_gui` /
  `destroy_gui` / `Gui.move` catches: retained-rebuild leaks, incomplete teardown, a
  stationary panel calling `Gui.move`, drag clamping, bring-up finishing without fixed waits.
- Compile-check every source file with LuaJIT and assert the FFI surface you expect — the
  armor kit's `ffi_audit.py` gates the build on it. A missing `ffi.cdef` for a symbol you
  actually call is a hard error at the call site, and it was a shipped bug once:
  `missing declaration for symbol 'VirtualAllocEx'` was the real cause of "clicking a card
  does nothing".
- Assert **data invariants** too, not just code: every label must have a glyph in your pixel
  font; every English name must match the native id; no description may exceed the panel
  width.

Write these when the feature is small. Retrofitting them after a crash is much slower.

---

- **Your own test can be the thing that lies.** A deployment check filtered for `.patch_0` while
  the deployed file was named `.patch_323`, and reported "0 layers in the game directory" — which
  sent the investigation after a deployment that was in fact correct. Match by content and compare
  **sha256 byte-for-byte** instead of trusting a filename pattern.
- **A test that asserts removed behaviour fails while the product is right.** A unit test still
  pinned "snap the percentage to 100/80/50" long after that behaviour had been deliberately
  removed, so a green-to-red change pointed at the test, not the code. When you remove a feature,
  grep the tests for it in the same commit. The replacement assertion described the new contract:
  "a free value is used as-is, out-of-range is clamped".

## Evidence and what is *not* verified

**Source of the entries:** `mods/custom-armor-kit/work/standalone/multi_perk.lua`,
`mods/custom-armor-kit/RETIREMENT-FINDINGS.md`, `mods/custom-armor-kit/work/standalone/ffi_audit.py`,
`outputs/validated-2026-10-04/hud-compatibility/sources/installed-Super-Earth-Armory-Forge-v6.2.1-0-0.lua`,
plus `outputs/reports/` for the crash and blue-screen write-ups.

**Honest scope:**

- The crash mechanisms and log strings are from real runs and are quoted from the code's own
  comments and evidence.
- No single mod has been built *from this guide* and run end to end. Treat the entries as
  "this is what happened to someone", not "this is the only way it can happen".
- Addresses, frame numbers and thresholds are build-specific. Re-derive them; do not copy
  them as constants.
- §1's rule is the one that generalises to any build and any feature. If you only take one
  thing from this page, take that one.
