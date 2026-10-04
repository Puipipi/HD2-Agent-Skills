---
name: hd2-offline-data-workflow
description: Locate and decode Helldivers 2 game data tables offline — from FileDiver's plaintext mirror and the game's own typelib — computing type hashes, field offsets and record layouts before anything runs, then doing only the minimal in-game verification. Use when you need a table's contents, offsets or signature, or when you are about to spend an in-game run on a scan you could have solved on disk.
---

# hd2-offline-data-workflow

English / [简体中文](https://github.com/Puipipi/HD2-Agent-Skills/blob/main/skills/hd2-offline-data-workflow/SKILL_cn.md)

A machine session costs a game restart, and Bingus Shared Loader has no hot reload, so every question you can answer on disk is a question you should never ask the running game. The plaintext mirror plus the typelib answer most of them. **Work offline first, go in-game last.**

Written for the Lua-injection addon class (addons loaded by Bingus Shared Loader, running inside the game's LuaJIT VM). Asset-replacement mods that swap `data/` resources are a different pipeline. The runtime-write side is out of scope here on purpose.

## Provenance and confidence — read this first

**Nothing in this file has been executed or re-measured in this repository.** It reorganises one
contributor's working notes, taken from
[`junze0910/junze-hd2-lua-mod`](https://github.com/junze0910/junze-hd2-lua-mod) (MIT). The author
states that not everything there has been tested and that some of it needs someone else to test
it. Treat every claim below as **reported and not independently verified here**.

Two exceptions, because they were checked in this repository rather than taken on faith:

- **"You cannot scan the shipped `game.dll` offline"** — independently reproduced. The on-disk
  image hashes to the loader's gate constant but its main sections have blanked names, ~7.9998
  entropy and no trace of a known code signature; see `docs/hd2-mod-failure-catalog.md` §5.
- **The name→hash function and the archive magic/type constants** — checked against the loader's
  own published test vectors by `hd2-addon-package-inspector`, which fails if they disagree.

One claim **could not** be checked here and is marked as such in the caveats: the assertion that
the in-memory image of `generated_entities.dl_bin` is byte-identical to the file on disk. The file
is not present in this workspace.

| Marking used below | What it means |
|---|---|
| *(verified in-game by the author)* | the source says it was observed on a live run. Still one machine, one build. |
| *(reported)* | stated by the source with no test described. Unverified. |
| *(build-bound)* | the value belongs to one game build, mod version or date. Not portable; re-derive it. |
| *(unresolved)* | two statements in the source disagree and it does not reconcile them. Both are kept. |

Do not cite anything here as established fact. If you need certainty, derive it yourself and say
how you did.

## The offline-first loop

1. **Find the plaintext offline** — the table's bytes and the type library, on disk.
2. **Compute offsets and values offline** — type hash, field offsets, record layout, and the candidate values themselves.
3. **Do a minimal verification in-game** — a read-only pass confirming the signature is where you computed and the layout is what you decoded.
4. Only then write.

On-machine recon is the expensive step; the plaintext mirror removes most of the need for it.

## Where the plaintext data comes from

FileDiver's `datalibrary` packages the plaintext data, typelib included, into the Go module with `//go:embed`. Run `go mod download github.com/xypwn/filediver` (or clone the source tree); files live at `<GOMODCACHE>/github.com/xypwn/filediver@<ver>/datalibrary/`:

| File | Contents |
|---|---|
| `generated_entities.dl_bin` | **45 MB**; all entity/component data — weapons, racks, equipment, inventory, stratagems |
| `generated_projectile_settings.dl_bin` (+ siblings) | projectile / damage / explosion / surface settings tables |
| `dl_library.dl_typelib` | the game's own type library |
| `*.go` | every component field's name and comment, generated from the typelib |

This mirror is the only source of plaintext tables, which is why it exists in the workflow at all: the shipped `data/game/generated_*.dl_bin` files in the install directory are encrypted (entropy **7.9998 bit/byte**; `LDLD` appears **0** times in the 45 MB file; the file is usually only **48 bytes** larger than the plaintext mirror). They cannot be decoded and are not part of the pipeline — do not try to edit them.

**Dump the typelib to JSON:** put `tools/dump_typelib/` into the FileDiver source tree under `cmd/` and run `go run ./cmd/dump_typelib -o typelib_all.json`. `-o` is not optional — PowerShell's `>` redirection writes UTF-16, which Python cannot read. The result, `typelib_all.json` / `typelib_names.tsv`, carries field offsets / sizes / member names for all **~1177** types plus the type-hash ↔ name correspondence; it is the authoritative offset source when a community struct disagrees with the current build.

## Locating a table: signature, not address

**ASLR moves everything between runs.** Absolute addresses differ on every launch, so the only workable scheme is "locate by signature, then apply a relative offset" — a hardcoded absolute runtime address silently works once and fails after a restart.

### The LDLD block header

A data-table block is `LDLD` + u32 version (= **1**) + u32 type hash + u32 size. Both offline parsing and in-memory censusing key on that signature.

### Type hash = djb2 with 5381 subtracted at the end

`dlsum(name)`: `r = 5381`; for each character `r = (r * 33 + ord(c)) & 0xFFFFFFFF`; return `(r - 5381) & 0xFFFFFFFF`. Example: `"HellpodRackComponentData"` → `0xA98BB156`. Every name in `typelib_names.tsv` maps to its LDLD table signature this way, which is what lets you go from a type name to a signature without the game.

### Resource-name hash is a different function

Resource names hash with `MurmurHash64A(name, seed=0)`. The two hashes look similar and are unrelated; using the type hash where a resource-name hash was required (or the reverse) silently finds nothing — a stream of "not found" with no error.

### Two possible data-start layouts — verify by content, never guess

| Table family | Instance data starts at |
|---|---|
| `generated_*_settings.dl_bin` | magic **+40** |
| `generated_entities.dl_bin` | magic **+24** |

A single hardcoded data start decodes one family of tables wrongly. Validate with content: a decoded record should have plausible fields — count ≤ **8**, speed in **1~5000**, item hash resolvable in the resource-name list.

### Not every table is an LDLD block

`StratagemSettings` is a **16-byte** container whose member is an ARRAY; the actual record is `StratagemInfo`, `size = 400`, offsets `+0` type, `+4` id, `+80` uses, `+104 / +108` cooldown float (success / fail), `+152 / +160` payload[2], `+168` package, `+176` icon, `+196` depends_on, `+200` additional_stratagem, `+204` max_in_loadout. Get the record type and field offsets from the typelib **first**, then choose a scanning strategy — assuming every data table is an LDLD block made the stratagem tables unfindable.

An AOB-path record layout for the stratagem pointer array (`StratagemCooldown 2.1.5`), for contrast, reads **0xB0**-byte records: `+0x00` id, `+0x04` hash, `+0x10` name string pointer, `+0x50` uses (int32, `-1` = infinite), `+0x68` cooldown (float), `+0xC8` the field the AOB itself accesses, corresponding to `additional_stratagem`.

### Is it a contiguous array? Test it, do not assume it

With contiguous records, stride `S`, and the `package` field at `+P`: `base = addr(pkg) - P - (id-1)*S`. If several known records yield the same base and their icons all match, it is a contiguous array; otherwise do not force `base + (ID-1)*S`. Measured: all **7** `StratagemInfo` packages were located but no common base existed — the records are not an ID-sorted contiguous 400 B array (more like pointers / scattered allocation), so each record has to be located by its package content instead.

### Fields hold enum values, not array indices

A record field stores the **enum value**, not a table index. Look records up by their own type field: `for i = 0, count-1 do if u32(rec + 0) == WANTED_TYPE then ... end end`. Looking up "array index 371" returned nothing; the "enum value 371" found the right record.

### Community structs are not ground truth

`datalibrary/*.go` files generated from the typelib — the ones carrying field comments — are trustworthy for the current build; hand-written Go structs in FileDiver may not be. When unsure, read the offsets in `typelib_all.json` or read `dl_library.dl_typelib` directly. A community struct that had drifted from the build sent a decode down the wrong path.

## The scanner

### Put the scan in one service

Do not write a private `VirtualQuery` + `ReadProcessMemory` full scan per mod. Seven mods were each full-scanning 9 GB before the work was converged into `Scanner`:

```lua
HD2Scanner.scan_request{
  id = 'exo_strat_pkg',
  patterns = { {key='a', bytes=...}, {key='b', bytes=...} },
  budget = 8 * 1024 * 1024,
  on_hit = function(key, addr) ... end,
  on_done = function(hits) ... end,
}
HD2Scanner.scan_cancel(id)
HD2Scanner.scan_status(id)
```

Inside it enumerates readable committed regions, chunks in **256 KB** blocks with overlap (so a pattern cannot straddle a boundary), enforces the `8 * 1024 * 1024` per-frame budget, skips its own patterns, queues multiple requests, and leaves structure validation and writing to the consumer. Consumers only validate and write; if the Scanner in the running build lacks `scan_request`, keep a self-scan fallback.

### Time-slice to ≤8 ms of CPU per step

64 MB per frame starves the game and it hangs on the loading screen. Use a deadline of `os.clock() + 0.008` (**≤8 ms** CPU per step), scan regions in **descending size order** (larger blocks are more likely to hold data tables), and defer scanning until frame **120**.

### A scan finds the scanner's own pattern strings

Pattern strings live in the Lua heap, so a memory scan hits them. Take each pattern's own address — `tonumber(ffi.cast("uintptr_t", ffi.cast("const char *", pattern)))`, called inside `pcall` because the cast can fail — collect all of them, and skip any hit within **±4096** bytes of any self address. A scan once completed "successfully" while matching only its own pattern data.

Register **every** pattern, not just the main signature, e.g. `local SELF_PATTERNS = { SIGNATURE, pkg_le_1, pkg_le_2, icon_le_1, ... }`. v1.2 SSProbe registered a self-address only for `LDLD + typeHash`, so every candidate was its own `SIGNATURE` copy with `size=0` — it looked like the target was found, but it was the probe itself.

### Structural validation is the second filter

LDLD candidates must have a plausible `magic + ver + typeHash + size`; `StratagemInfo` candidates must have `+8` icon and `+28` / `+36` equal to `0`.

### Wrap every loop level in `pcall`

A failed region read and a failed pattern scan must both be caught and skipped. Every loop level needs its own `pcall`; otherwise a single fault wastes the entire round.

### Clamp dump reads to the region base

An LDLD block may sit at allocation base **+4**. Starting a dump at `magic-64` reads outside the region, `ReadProcessMemory` returns **0 bytes**, and the dump file contains only a header. Clamp the read start to the region base, and on failure move the start forward a little and retry.

### A stable in-region offset can replace the scan entirely

Scanner's design notes record that an intra-region offset is stable across sessions, which locates a table without a scan at a cost of **1.1 MB / 117 ms** — about **7500×** cheaper than 7 mods each full-scanning 9 GB. Repeated full scans were the dominant cost.

### The AOB route: fast, preferred, never a contract

The `StratagemCooldown 2.1.5` AOB pair is `49 8B 84 C7 ?? ?? ?? ?? 44 8B 80 C8 00 00 00 8B C2 45 85 C0` — i.e. `mov rax, [r15 + rax*8 + disp32]` / `mov r8d, [rax + 0xC8]` / `mov eax, edx` / `test r8d, r8d`. Algorithm:

1. take the `game.dll` base and image size;
2. scan the image in **1 MB** chunks with **0x40** overlap;
3. require the AOB pair to be **unique** (0 matches = fail, >1 = ambiguous);
4. the hit is the `consumer`;
5. `disp = i32_at(consumer + 4)`;
6. scan back up to **0x1000** bytes for `4C 8D 3D` (`lea r15, [rip + disp32]`);
7. `r15_base = lea_addr + 7 + lea_disp`; 8. `table_base = r15_base + disp`;
9. `slot_ptr(id) = u64_at(table_base + id*8)`; 10. `rec = read_at(slot_ptr(id), 0xB0)`.

A game update can change the function, register allocation, instruction encoding, or adjacent code, turning a unique match into 0 matches or several ambiguous ones — or the AOB can still match while `disp` / `lea` / the pointer-array structure has moved. Therefore always check match uniqueness, check `sane_ptr` ranges, validate `slot_ptr(id)` and record fields (id / name / uses / cooldown plausible), **automatically fall back to a full-memory package content search** on failure, and log the AOB parse failure and the fallback reason explicitly. An AOB-only implementation stops working silently after an update.

### You cannot scan the shipped `game.dll` offline

`data/game/game.dll` (15.5 MB) is packed on disk. Evidence: the first 8 section names are blanked; those sections have entropy **8.000** (saturated) versus **6.338** for `kernel32.dll`; section VSize `0x210FA93` vs RawSize `0x850800` (memory image ~4× the disk image); the `.winlice` section has RawSize = **0** (filled only at runtime); import table `.idata` / export table `.edata` are only **0x200** bytes each; and the most common function prologue `48 89 5C 24 08` has **0** hits in the file (4104 hits in `kernel32.dll`).

Consequence: no offline signature scanning or disassembly of the disk file — always **0 hits**. This is also why MDL re-scans signatures on every launch: it has no offline-queryable copy at all.

### Anti-cheat boundary

Anti-cheat is **nProtect GameGuard** (install directory `bin/GameGuard`). Do not use Python / ctypes with `OpenProcess` + `ReadProcessMemory` from an external process — that is the most easily detected action, and it contradicts the common Cheat-Engine-style attach-and-scan habit. Only in-game read-only addons are acceptable.

## Reconnaissance addon: the one-shot read-only pass

Write an addon that **never calls `WriteProcessMemory` / `VirtualProtect`**:

1. time-sliced memory scan locating data tables by `LDLD + version + type hash`;
2. also search the unique ID hash (resource-name hash) in memory and dump **±512** bytes of context, so an object can be located even if the table header never turns up;
3. hex-dump to `%LOCALAPPDATA%/<your dir>/`;
4. attach a **census** of every `LDLD` block in memory (address / type / size / sample).

Read-only first, always. The loader requires an addon **once at startup** and there is no hot reload, so even a one-line change means closing and restarting the game — which is why the first version must be built so that "even if something goes wrong there is an artifact on disk". A recon run once ended in a crash with nothing written.

### Logging discipline for a one-shot run

- Flush periodically every N frames rather than only at the end of a scan, and flush on error too.
- Prefix lines with `[frame N]` so ship-loaded data can be told apart from data that only exists inside a mission.
- Rate-limit repeated error printing so the log is not flooded.
- Log the **expected value** alongside every assertion, so a mismatch is immediately readable as either "signature not found" or "found but the layout changed"; without it the two are ambiguous.
- Bulk diagnostic output must not go through the ring-capped log history — send it through a separate `dump()` that writes straight to disk, or the **400**-line cap eats it.
- The loader accepts only `.log` names: `if type(name) ~= 'string' or not name:match('^[%w_-]+%.log$') then return nil end`. `.txt` returns `nil`, and a `pcall` around the caller turns that into a silently missing file. Use `.log` for every dump, e.g. `SSProbe_dump.log` / `SSProbe_table.log`; when a file does not appear, check the name rule before suspecting the scan. The shared log directory is `%LOCALAPPDATA%/CowboyBingus/Helldivers2/Logs`.

### Census before you plan

Use an `LDLD` signature census, then choose the strategy. Measured: setting tables (projectile / damage / explosion) are permanently resident; component tables inside the entity blob are not necessarily present on the ship but are present once in a mission (the Leveller rack table was found only on the **second** scan round). A single scan pass on the ship concluded the table was missing. Budget for multiple scan rounds.

### Verifying a decoder when no offline machine code exists

With no offline copy of `game.dll` to check against, a second in-process implementation is the only reference: find another mod that already works on this machine (e.g. MDL) and copy the numbers it decoded from its logs; on the first successful run of your implementation log the same dozen numbers; compare item by item — all equal means the decoder is correct, one difference pinpoints the specific wrong `disp32`.

Known-good values decoded by MDL **1.4.2** on the **2026-09-24** build, usable as that comparison baseline (build-bound, not portable offsets):

| Decoder area | Values |
|---|---|
| native menu state | `MenuSystem +0x347ce38`, open byte `+2185`, **36** screen types |
| native tab | bar `+1248`, count `+57448`, labels `+57320`, text `+8296`, `set_labels +0x17aac50`, `set_arg +0x143c950`, labels `0xd876b36e 0x78934e12 0x8c02bd80` |
| native font slots | font `+0x3772268`, atlas `+0x3772ee8`, material `+0x37c5478` |

The (now retired) ESC-menu panel design used the same idea for `game.dll` itself: a "signature + self-check, disable yourself when it does not match" routine, a three-layer lazy determination, a runtime decision between the **4th / 5th** menu slot position, and MDL interoperation. The invariant survives the retirement — a menu host must not corrupt the game when the build it targeted has changed.

## UI integration

`_G.ModOptionsMenu` (`mom.register_option`) supports only `toggle`, `choice` (**2–16** fixed options) and `slider`. It does **not** support free text input, arbitrary buttons / Action rows, dynamic read-only status lines, or changing a `choice` list after registration. Practices that follow: left and right need separate `choice` pools (the left slot lists only left items, the right only right items); player-triggered actions (start scan / initialise) are carried by a `toggle` — Apply fires the callback, and after doing the work either immediately `menu.set(id,false)` to pop back or pop back when the operation finishes; anything that must be recomputed after a selection change is synced back with `menu.set`; Scanner itself uses 3 lines on the MODS page (status / AOB / diagnostics) and can be copied.

The whole `_G.HD2Menu` / `HD2MenuQueue` page system is retired (**2026-10-04**): the rendering host `ui.lua` had not been in the release package since **2026-10-03**, so pages could never display, and on 2026-10-04 `registry.lua` was deleted along with it. New mods must not write `menu.register{...}` or queue into `HD2MenuQueue` — `rawget(_G,'HD2Menu')` is now `nil`. Pages built on the retired host never rendered, wasting entire mod features.

## Tooling and workflow

### Verify the build before any machine work

Check `helldivers2.exe`'s version and SHA-256 before touching the machine. **An unchanged build means the old dumps, offsets and census are all still valid**, which saves an entire recon round; re-running recon on an unchanged build wastes a full cycle.

### Tool inventory

| Path | Purpose |
|---|---|
| `references/ldld.py` | **LDLD table parser** — `dlsum` / find instance / decode records |
| `tools/projectile_settings.py` | `generated_projectile_settings.dl_bin` parser |
| `tools/dump_typelib/` + `tools/go/` | typelib → JSON (run inside the FileDiver source tree); portable Go, needed only for that |
| `tools/inspect_patch.py` | archive structure view + automatic round-trip check |
| `tools/hd2_archive.py` / `tools/build_addon.py` | `.patch_N` read/write (round-trip verified) / `.lua` → installable ZIP |
| `_baseline_<build>/` | on-machine memory dump baselines, for comparison after an update |
| `tools/ljd/` — **third party** | LuaJIT bytecode decompiler, for reading other people's mods |
| `tools/filediver/` + `filediver-src/` — **third party** | unpacking tool + **plaintext datalibrary + field-name Go source** |

### Solve by differential, not by invention

Find the target table by type name with `dlsum` from the plaintext mirror and decode all records; take field offsets from `typelib_all.json` and field meanings from `datalibrary/*.go`; then find **same-family contrasts** and diff them — faster and harder than pinpoint kills. The task was "the Leveller drops one per airdrop" while EAT-17 and EAT-700 both drop two, so putting the three rack records side by side made the differing fields jump out (`slot1` empty + `SpawnPayloadSize`). Prefer copying a configuration that already works in-game over inventing values: the final **64 bytes** were **byte-identical** to EAT-17's slot1 with only an **8-byte** item hash differing — evidence that the reproduced behaviour is the engine's existing behaviour, where invented values would be unverified. Then verify offline: parse the dump with a script and confirm offsets and value ranges; if the memory layout matches the file image this step is pure verification, a cheap check that avoids a machine round.

### Cross-validate against the community wiki

`helldivers.wiki.gg`'s "Detailed Weapon Statistics" gives exact numbers; match them item by item against a data table, and a multi-item hit locks the record. Example: the Eruptor's impact explosion per the wiki is `225 damage / 30 fragments / inner radius 4 m / outer radius 7 m / demolition 20 / stagger 35 / push 40 / Medium armor penetration`, and of **413** explosion entries **only one** matched all 8. Wiki behaviour sentences (e.g. *"sent two at once like typical EAT-17"*) can lead straight to the same-family contrast. A multi-field wiki match pins the record without a machine scan.

### Simulate offline with `lupa` and a type-strict stub

Use `lupa` (`pip install`) to run Lua inside Python with a **fake memory space**. The stub must be type-strict or it cannot catch the class of bug where a bare Lua number is passed where a pointer is expected (`cannot convert number to const void *`):

```lua
function ffi.cast(ctype, v)
    if ctype:find("%*") then
        if type(v) == "number" then return { __ptr = v } end   -- pointers are special objects
        if type(v) == "table" and v.__ffi then return { __ptr = v } end
        error("ffi.cast(" .. ctype .. "): cannot cast " .. type(v))
    end
    return v
end
function kernel.ReadProcessMemory(proc, address, buf, size, count)
    address = as_pointer(address, "ReadProcessMemory")       -- passing a number errors immediately
    ...
end
```

A lenient stub let pointer-type bugs reach the machine.

### Mutation testing and fixtures

After fixing a bug, revert it and confirm the test **actually fails** — when a mutation is not caught, suspect the fixture before the code (the `SpawnPayloadSize` mutation escaped because the fixture itself had placed the decoy rack at the wrong offset). Build fixtures from a real captured memory dump so offsets are checked against real bytes, and add deliberate decoys: a table that looks legal but has wrong key fields (tests your validation) and a fake heap region containing your own pattern strings (tests self-detection). Mind the scan order — regions are scanned in **descending size order**, so make a decoy larger if it must fire first.

### `lupa` troubleshooting

| Symptom | Cause / fix |
|---|---|
| `cannot open ...: Illegal byte sequence` | Lua's `fopen` cannot open paths containing Chinese characters; put fixture files in `%TEMP%` (pure ASCII) |
| `too many registers (limit is 255)` | one `string.char(...)` call with tens of thousands of arguments; chunk it by **200** |
| `UnicodeDecodeError` on read-back | lupa decodes Lua strings as UTF-8 by default, which breaks on binary; have the Lua side return a **hex string** |

### Reference notes, and negative results

`hd2-eruptor-dominator-案例.md` — R-36 Eruptor projectile onto the JAR-5 Dominator (pure in-memory projectile-table edit). `hd2-leveller-double-案例.md` — EAT-411 Leveller dropping two per airdrop (full offline solve + one on-machine recon + **64-byte** patch). `hd2-ac8-rack-backpack-设计.md` — AC-8 backpack replacement v6 (content-anchor method). `hd2-scanner-设计定稿.md` — read before writing a new mod or changing scan/table-lookup logic. `hd2-stratagem-settings-笔记.md` — StratagemSettings / StratagemInfo notes (non-LDLD 400 B records, package content search, Scanner memscan service, ModOptionsMenu capability boundary). `hd2-strat-unlock-设计定稿.md` — read first for "make a stratagem selectable". `hd2-supply-custom-设计定稿.md` — read first for supply / rack changes. Vehicle parameter notes — **not found**: `+296`, `+300`, … each tried and rejected. Negative results are data: do not re-run an exhausted search.

Component layouts worth having on hand offline: `HellpodRackComponent` is **568 B** = `RackAttach[8]` (**64 B** per slot) + a tail, with `spawn_payload_size` at `+0x22C`; the AC-8 case locates `HellpodRackComponentData` by LDLD + type hash + in-record relative offsets (the "content anchor" method). Relative to the address `c` of a record's `package` field: `c+32` = `additional_stratagem`, `c-88` = `use`, `c-64` = `cooldown_duration_success`, `c-60` = `cooldown_duration_fail` — these targets live around the package pointer, not at fixed record offsets.

## Caveats: unresolved, unverified, and retired

- **Byte-identical memory image — reported by source, not established here.** The source states that the in-memory copy of `generated_entities.dl_bin` is byte-for-byte the same as the file, so relative offsets computed offline can be used directly at runtime. That claim could **not** be independently verified in this workspace because the file is not present. Treat it as reported-by-source and confirm it with a read-only probe before building on it. What *is* independently established is the consequence: absolute addresses differ on every run (ASLR), so "locate by signature, then apply a relative offset" is the only workable scheme.
- **Unresolved conflict — can a menu carry a dynamic read-only status line?** One statement says `ModOptionsMenu` does **not** support dynamic read-only status lines; another says a read-only status is obtained by making the `label` or `description` a **function**, which MOM recomputes every time the ESC menu opens. **The source does not reconcile the two.** Both are recorded; settle it by testing against your build.
- **Unresolved conflict — `.patch_N` descriptors.** On disk the resource-array descriptors hold relative offsets; once the archive is loaded the same structure is rewritten with absolute pointers. Named in the source as a "must-trip-over" pitfall; the two readings are not reconciled, so do not hardcode an absolute runtime address on either reading.
- **A data table that exists is not always in memory, and a table in memory is not always on the ship.** Census first; the Leveller rack table needed a second scan round.
- **A hit for a unique byte pattern does not necessarily belong to the game** — it is usually your own pattern string. Register every pattern's self address.
- **A numeric field is not an ordinal index.** Match the record's own type field, not "index N".
- **Build-bound values.** The MDL 1.4.2 / 2026-09-24 baseline values and the `StratagemCooldown 2.1.5` AOB are tied to those builds; the source does not say whether they hold elsewhere, and nothing in this workspace can confirm or refute it. Comparison baselines, never portable offsets.
- **Retired (2026-10-04).** The `_G.HD2Menu` / `HD2MenuQueue` page system and the ESC-menu panel design are both retired; the location-routine invariant is preserved above, but do not resurrect the page system. Third-party provenance (`tools/ljd/`, `tools/filediver/`, `filediver-src/`) stays marked.
