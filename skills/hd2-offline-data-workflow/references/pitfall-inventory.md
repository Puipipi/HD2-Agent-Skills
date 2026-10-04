# Pitfall inventory — source material

This is the extracted inventory the sibling skills were written from: 106 facts
with a Why: line each, grouped by category, taken from a 958-line Chinese
workflow document (hd2-lua-mod) about Lua-injection mods for Helldivers 2.

It is kept verbatim as **evidence**, not as a guide to read first. Start with the
skills; come here when you want the item-level detail behind a rule, or when you
need a fact that was too niche to make the cut.

Confidence is not uniform, and the original says so per item. Items marked as
build-bound, environment-specific or unresolvable carry that marking here.

---

## memory-and-ffi

- **M1 — The in-memory copy of `generated_entities.dl_bin` is byte-identical to the file image**
  - Fact: Measured: `generated_entities.dl_bin` in memory is byte-for-byte the same as the file, so
    relative offsets computed offline can be used directly at runtime. Absolute addresses differ on every
    run (**ASLR**), so the only workable scheme is "locate by signature, then apply a relative offset".
  - Why: Without this, offsets derived offline would be unusable, or an absolute address would silently
    work once and then fail after a restart.
  - Conflicts: Contradicts any approach that hardcodes an absolute runtime address.

- **M2 — In `.patch_N` archives, array descriptors are relative offsets on disk but absolute pointers in memory**
  - Fact: In the file, the resource-array descriptors hold relative offsets; once the archive is loaded,
    the same structure is rewritten with absolute pointers.
  - Why: Named in the source as one of the "must-trip-over" pitfalls of the `.patch_N` format.

- **M3 — FFI pointer arguments must be passed through `ffi.cast`**
  - Fact: Passing a bare Lua number where a pointer is expected raises
    `cannot convert number to const void *`. Only real FFI exposes this; a fake test stub must be
    type-strict to catch it.
  - Why: A test double that accepted numbers let pointer bugs reach the game and fail there.

- **M4 — Writing to read-only pages: `VirtualProtect`, then restore the original protection**
  - Fact: When the target is a read-only page, temporarily open it with `VirtualProtect`, and after the
    write restore the original protection attributes.
  - Why: Part of the runtime-patch template that passed on-machine on the first attempt.

- **M5 — Never read game memory from an external process (nProtect GameGuard)**
  - Fact: Anti-cheat is **nProtect GameGuard** (install directory `bin/GameGuard`). Do not use Python /
    ctypes with `OpenProcess` + `ReadProcessMemory` — that is the most easily detected action. Only
    in-game read-only addons are acceptable.
  - Why: External process reading is the highest-risk action under this anti-cheat.
  - Conflicts: Contradicts the common external-tool habit (Cheat Engine-style attach-and-scan), which
    this document rules out entirely.

- **M6 — On-disk `game.dll` is packed: disk and in-process machine code are not the same**
  - Fact: `data/game/game.dll` (15.5 MB) is packed on disk. Evidence: the first 8 section names are
    blanked; those sections have entropy **8.000** (saturated) versus **6.338** for `kernel32.dll`;
    section VSize `0x210FA93` vs RawSize `0x850800` (memory image ~4× the disk image); the `.winlice`
    section has RawSize = **0** (filled only at runtime); import table `.idata` / export table `.edata`
    are only **0x200** bytes each; and the most common function prologue `48 89 5C 24 08` has **0**
    hits in the file (4104 hits in `kernel32.dll`). Consequences: no offline signature scanning or
    disassembly of the disk file (always 0 hits); verification must happen **in-process** (have the mod
    decode and log the results, comparing against known values) or by dumping the in-memory `game.dll`
    with a read-only probe. This is also why MDL re-scans signatures on every launch — it has no
    offline-queryable copy at all.
  - Why: Offline scans of the shipped `game.dll` returned zero hits and produced unusable offsets.
  - Conflicts: Contradicts the common belief that you can analyse the installed `game.dll` statically.

- **M7 — The same encryption applies to the on-disk data tables**
  - Fact: The `data/game/generated_*.dl_bin` files in the install directory are encrypted (entropy
    **7.9998 bit/byte**; `LDLD` appears **0** times in the 45 MB file; the file is usually only
    **48 bytes** larger than the plaintext mirror). Do not try to edit the on-disk files — they cannot
    be decoded and are not part of the mod pipeline.
  - Why: Encrypted on-disk tables are the reason all data work has to go through FileDiver's plaintext
    mirror instead of the installed game files.

- **M8 — MDL 1.4.2 baseline decoded values (2026-09-24 build) for in-process decoder checks**
  - Fact: Known-good values decoded by MDL 1.4.2 on this machine (2026-09-24 build):
    `native menu state: MenuSystem +0x347ce38, open byte +2185, 36 screen types`;
    `native tab: bar +1248, count +57448, labels +57320, text +8296, set_labels +0x17aac50,
    set_arg +0x143c950, labels 0xd876b36e 0x78934e12 0x8c02bd80`;
    `native font slots: font +0x3772268 atlas +0x3772ee8 material +0x37c5478`.
    (Values are tied to that build; treat them as a comparison baseline, not as portable offsets.)
  - Why: With no offline-verifiable machine code, these numbers are the only ground truth available for
    checking a decoder in-process.

---

## luajit-semantics

- **L1 — LuaJIT numbers have only 53 bits of precision; large IDs must never touch a number**
  - Fact: Storing `0x80F1A156D9FA1E36` in a Lua number yields `0x80F1A156D9FA2000`, which corrupts the
    search pattern. Any ID > 2^53 must be built from hex character pairs and never go through a number:
    `local function le_bytes_from_hex(hex) return (hex:gsub("%x%x", function(p) return string.char(tonumber(p,16)) end)):reverse() end`.
  - Why: A corrupted 64-bit search pattern silently never matched.
  - Conflicts: Contradicts the usual habit of writing 64-bit IDs as Lua hex literals or `tonumber('0x…')`.

- **L2 — `table.concat` renders numbers as decimal text**
  - Fact: `table.concat({65,66})` returns `"6566"`, not `"AB"`. A byte table that mixes numbers and
    strings therefore silently produces bytes of the wrong length, and on write it corrupts the
    neighbouring data. Byte operations must use pure-string concatenation.
  - Why: Mixed numeric/string byte tables silently produced wrong-length writes.
  - Conflicts: Contradicts the common byte-table idiom of mixing numbers and strings in one table.

- **L3 — Lua does not type-check fields; never reuse a field name with a different type**
  - Fact: Using `hits = {}` and `hits = 0` in the same table makes `hits + 1` throw
    `attempt to perform arithmetic on field 'hits'`. In the observed case the first hit aborted the
    whole scan round and the census was never flushed.
  - Why: A name collision between a set and a counter destroyed a full recon run.

- **L4 — `ffi.cast` on a pointer-to-string is how a Lua string's own address is obtained**
  - Fact: The self-address of a pattern string is
    `tonumber(ffi.cast("uintptr_t", ffi.cast("const char *", pattern)))`, called inside `pcall` because
    the cast can fail.
  - Why: Needed for self-hit skipping (see S1/S2); without it a scanner matches its own pattern data.

---

## data-tables

- **D1 — LDLD block header layout**
  - Fact: A data-table block is `LDLD` + u32 version (= **1**) + u32 type hash + u32 size.
  - Why: This signature is what both offline parsing and in-memory censusing key on.

- **D2 — LDLD instance data start depends on the file: settings `magic +40`, entities blob `magic +24`**
  - Fact: For `generated_*_settings.dl_bin` the data starts at magic **+40**; for
    `generated_entities.dl_bin` at magic **+24**. Do not guess: validate with content — a decoded record
    should have plausible fields (count ≤ **8**, speed in **1~5000**, item hash resolvable in the
    resource-name list).
  - Why: The two layouts differ, so a single hardcoded data start decodes one family of tables wrongly.

- **D3 — Type hash = djb2, with 5381 subtracted at the end**
  - Fact: `dlsum(name)`: `r = 5381`; for each character `r = (r * 33 + ord(c)) & 0xFFFFFFFF`; return
    `(r - 5381) & 0xFFFFFFFF`. Example: `"HellpodRackComponentData"` → `0xA98BB156`. Every name in
    `typelib_names.tsv` maps to the LDLD table signature this way.
  - Why: Needed to go from a type name to the on-disk / in-memory table signature without the game.

- **D4 — Resource-name hash = MurmurHash64A(name, seed=0); it is a different function from djb2**
  - Fact: Resource names hash with `MurmurHash64A(名字, seed=0)`. The two hashes look similar but are
    unrelated; mixing them produces a stream of "not found".
  - Why: Using the type hash where a resource-name hash was required (or vice versa) silently finds
    nothing.

- **D5 — Plaintext table mirror contents (FileDiver `datalibrary/`)**
  - Fact: `generated_entities.dl_bin` (**45 MB**) holds all entity/component data — weapons, racks,
    equipment, inventory, stratagems; `generated_projectile_settings.dl_bin` and its siblings hold the
    projectile / damage / explosion / surface settings tables; `datalibrary/*.go` carry every component
    field's name and comment (generated from the game's own typelib).
  - Why: This mirror is what makes offline solving possible at all.

- **D6 — `typelib_all.json` / `typelib_names.tsv` give offsets and name↔hash mappings for ~1177 types**
  - Fact: `typelib_all.json` / `typelib_names.tsv` contain field offsets / sizes / member names for all
    **~1177** types, plus the type-hash ↔ name correspondence.
  - Why: Authoritative offset source when a community struct disagrees with the current build.

- **D7 — `typelib`-generated `datalibrary/*.go` is authoritative; hand-written community structs may be stale**
  - Fact: The files under `datalibrary/*.go` that were generated from the typelib (the ones carrying
    field comments) are trustworthy for the current build; hand-written Go structs in FileDiver may not
    match. When unsure, read the offsets in `typelib_all.json` or read `dl_library.dl_typelib` directly.
  - Why: A community struct that no longer matched the build sent a decode down the wrong path.
  - Conflicts: Contradicts the common practice of treating community struct definitions as ground truth.

- **D8 — `StratagemSettings` is not an LDLD block: a 16-byte container of ARRAYs wrapping `StratagemInfo` records**
  - Fact: `StratagemSettings` is a 16-byte container whose member is an ARRAY; the actual record is
    `StratagemInfo`, `size = 400`, with offsets: `+0` type, `+4` id, `+80` uses,
    `+104 / +108` cooldown float (success / fail), `+152 / +160` payload[2], `+168` package, `+176` icon,
    `+196` depends_on, `+200` additional_stratagem, `+204` max_in_loadout. Get the record type and field
    offsets from the typelib first, then choose a scanning strategy; LDLD applies to only some tables.
  - Why: Assuming every data table is an LDLD block made the stratagem tables unfindable.

- **D9 — Testing whether records form a contiguous array**
  - Fact: With contiguous records, stride `S`, and the `package` field at `+P`:
    `base = addr(pkg) - P - (id-1)*S`. If several known records yield the same base and their icons all
    match, it is a contiguous array; otherwise do not force `base + (ID-1)*S`. Measured: all 7
    `StratagemInfo` packages were located but no common base existed — the records are not an ID-sorted
    contiguous 400 B array (more like pointers / scattered allocation), so fall back to locating each
    record by its package content.
  - Why: A formula-derived table base produced nothing until tested against multiple known records.

- **D10 — AOB-path record layout for the stratagem pointer array**
  - Fact: The `StratagemCooldown 2.1.5` AOB path reads records of `0xB0` bytes with: `+0x00` id,
    `+0x04` hash, `+0x10` name string pointer, `+0x50` uses (int32, `-1` = infinite), `+0x68` cooldown
    (float), `+0xC8` the field the AOB itself accesses, corresponding to `additional_stratagem`.
  - Why: Gives a direct by-ID record lookup instead of a full-memory package content search.

- **D11 — Stratagem unlock by ID requires three conditions, all of which must hold**
  - Fact: (v1.7 verified on-machine) ① `StratagemInfo +0xC0` bit0; ② `+0x80` bit1 (= `selectable` in the
    plaintext data table); ③ registry record `+0x14 ∈ {2,4}`. The older conclusion that `+0x14` is not
    the owned bit has been overturned. The stratagem pointer table is `*(0x37CB600 + id*8)`. Writing
    includes the `selectable` bit.
  - Why: Two-condition writes left stratagems locked; the third condition was found by testing all three.

- **D12 — `HellpodRackComponent` layout (supply racks / backpack racks)**
  - Fact: `HellpodRackComponent` is **568 B** = `RackAttach[8]` (**64 B** per slot) + a tail;
    `spawn_payload_size` sits at `+0x22C`. The AC-8 case locates `HellpodRackComponentData` by
    LDLD + type hash + in-record relative offsets ("content anchor" method).
  - Why: Rack edits need the exact per-slot stride and the tail field position.

- **D13 — Supply-package cooldown and its write set**
  - Fact: A supply rack's 4 filled slots determine the cooldown (**30~150 s**, formula in the design
    doc). Writes go to three places: the rack slot's `item` / `offset` / `rotation_offset`, the
    stratagem's `cooldown_success` @ `+0x68`, and stratagem ID **77**'s three conditions. Configuration
    is four independent `choice` entries in ModOptionsMenu.
  - Why: Writing only one of the three places leaves the in-game cooldown inconsistent with the rack.

- **D14 — `additional_stratagem` / `use` / cooldown offsets relative to the `package` field address**
  - Fact: With `c` = the address of a record's `package` field (§6.23 writes these as `package±N`):
    `c+32` = `additional_stratagem`, `c-88` = `use`, `c-64` = `cooldown_duration_success`,
    `c-60` = `cooldown_duration_fail`. The record-level fields are `+200` `additional_stratagem` and
    `+104/+108` cooldowns on the 400 B `StratagemInfo` record.
  - Why: The write targets live around the package pointer, not at fixed record offsets.

---

## scanning-and-probing

- **S1 — A memory scan finds the scanner's own pattern strings; skip hits near the pattern's own address**
  - Fact: Pattern strings live in the Lua heap, so scanning memory hits them. Take each pattern's own
    address (`tonumber(ffi.cast("uintptr_t", ffi.cast("const char *", pattern)))` in `pcall`), collect
    all of them, and skip any hit within **±4096** bytes of any self address.
  - Why: A scan completed "successfully" while matching only its own pattern data.
  - Conflicts: Contradicts the assumption that a hit for a unique byte pattern must belong to the game.

- **S2 — Every searched pattern needs its own self-address registered, not just the main signature**
  - Fact: Register all patterns, e.g.
    `local SELF_PATTERNS = { SIGNATURE, pkg_le_1, pkg_le_2, icon_le_1, ... }`, and skip any hit within
    ±4096 of any of their addresses. Plus structural validation as a second filter: LDLD candidates must
    have plausible `magic + ver + typeHash + size`; `StratagemInfo` candidates must have `+8` icon and
    `+28`/`+36` equal to 0.
  - Why: v1.2 SSProbe registered a self-address only for `LDLD + typeHash`, so every candidate was its
    own `SIGNATURE` copy with `size=0` — it looked like the target was found but it was the probe itself.

- **S3 — Time-slice scanning to ≤8 ms of CPU per step, scan regions largest-first, start at frame 120**
  - Fact: 64 MB per frame starves the game and it hangs on the loading screen. Use a deadline of
    `os.clock() + 0.008` (≤8 ms CPU per step); scan regions in **descending size order** (larger blocks
    are more likely to be data tables); defer scanning until frame **120**.
  - Why: A full-speed scan froze the game during loading.

- **S4 — Wrap every loop level in `pcall`; one bad region or pattern must not kill the round**
  - Fact: A failed region read and a failed pattern scan must both be caught by `pcall` and skipped.
    Every loop level needs its own `pcall`; otherwise a single hit can waste the entire round.
  - Why: One fault aborted a whole scan pass.

- **S5 — Clamp dump reads to the region base; a read that starts out of range returns 0 bytes**
  - Fact: An LDLD block may sit at allocation base **+4**. Starting a dump at `magic-64` reads outside
    the region, `ReadProcessMemory` returns 0 bytes, and the dump file contains only a header. Clamp the
    read start to the region base, and on failure move the start forward a little and retry.
  - Why: Dump files containing only a header.

- **S6 — Enum values are not array indices; match the record's own type field**
  - Fact: A record field stores the **enum value**, not a table index. Look records up by their own type
    field: `for i = 0, count-1 do if u32(rec + 0) == WANTED_TYPE then ... end end`. Looking up "array
    index 371" returned nothing; the "enum value 371" found the right record.
  - Why: A correct value used as an index silently returned an empty result.
  - Conflicts: Contradicts the natural reading of a numeric field as an ordinal index.

- **S7 — Census first: not all tables are resident, and some appear only inside a mission**
  - Fact: Use an `LDLD` signature census. Measured: setting tables (projectile / damage / explosion) are
    permanently resident; component tables inside the entity blob are not necessarily present on the
    ship but are present once in a mission (the 荡平者 / Leveller rack table was found only on the
    **second** scan round). Census first, choose the strategy afterwards, and budget for multiple scan
    rounds.
  - Why: A single scan pass in the ship concluded the table was missing.
  - Conflicts: Contradicts the assumption that a data table that exists is always in memory.

- **S8 — Centralise full-memory scans in the shared Scanner service**
  - Fact: Do not write a private `VirtualQuery` + `ReadProcessMemory` full scan per mod. Scanner exposes:
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
    Inside, it enumerates readable committed regions, chunks in **256 KB** blocks with overlap (so a
    pattern cannot straddle a boundary), enforces the `8 * 1024 * 1024` per-frame budget, skips its own
    patterns, queues multiple requests, leaves structure validation and writing to the consumer, and stops
    automatically after the write completes and the log is flushed. Consumers (e.g. `exo_loadout`) only
    validate and write; if the Scanner lacks `scan_request`, keep a self-scan fallback.
  - Why: Seven mods were each full-scanning 9 GB; the work was converged into one service.

- **S9 — Locating the stratagem pointer array through a `game.dll` AOB pair (`StratagemCooldown 2.1.5`)**
  - Fact: AOB =
    `49 8B 84 C7 ?? ?? ?? ?? 44 8B 80 C8 00 00 00 8B C2 45 85 C0`, i.e.
    `mov rax, [r15 + rax*8 + disp32]` / `mov r8d, [rax + 0xC8]` / `mov eax, edx` / `test r8d, r8d`.
    Algorithm: (1) take the `game.dll` base and image size; (2) scan the image in **1 MB** chunks with
    **0x40** overlap; (3) require the AOB pair to be unique (0 matches = fail, >1 = ambiguous);
    (4) the hit is the `consumer`; (5) `disp = i32_at(consumer + 4)`; (6) scan back up to **0x1000**
    bytes for `4C 8D 3D` (`lea r15, [rip + disp32]`); (7) `r15_base = lea_addr + 7 + lea_disp`;
    (8) `table_base = r15_base + disp`; (9) `slot_ptr(id) = u64_at(table_base + id*8)`;
    (10) `rec = read_at(slot_ptr(id), 0xB0)`.
  - Why: Avoids a full-memory package search and allows the table to be resolved once at load time,
    before the consumption lists are built.

- **S10 — The AOB path is a fast preferred route, never a stable contract; keep the fallback**
  - Fact: A game update can change the function, register allocation, instruction encoding, or adjacent
    code, turning a unique match into 0 matches or several ambiguous ones — or the AOB can still match
    while `disp` / `lea` / the pointer-array structure changed. Therefore always: check match uniqueness,
    check `sane_ptr` ranges, validate `slot_ptr(id)` and record fields (id / name / uses / cooldown
    plausible), **automatically fall back to a full-memory package content search** on failure, and log
    the AOB parse failure and the fallback reason explicitly.
  - Why: An AOB-only implementation would stop working silently after a game update.
  - Conflicts: Contradicts treating a byte signature as a permanent, version-proof anchor.

- **S11 — In-process decoder verification by comparison against a known-good mod**
  - Fact: When no offline-verifiable machine code exists: (1) find another mod that already works on this
    machine (e.g. MDL) and copy the numbers it decoded from its logs; (2) on the first successful run of
    your implementation, log the same dozen numbers; (3) compare item by item — all equal means the
    decoder is correct, one difference pinpoints the specific wrong `disp32`.
  - Why: There is no offline copy of the machine code to check against, so a second in-process
    implementation is the only reference.

- **S12 — Read-only recon addon specification**
  - Fact: Write an addon that **never calls `WriteProcessMemory` / `VirtualProtect`**: (1) time-sliced
    memory scan locating data tables by `LDLD + version + type hash`; (2) also search the unique ID hash
    (resource-name hash) in memory and dump **±512** bytes of context, so an object can be located even
    if the table header never turns up; (3) hex-dump to `%LOCALAPPDATA%/<your dir>/`; (4) attach a
    **census** of every `LDLD` block in memory (address / type / size / sample). Read-only first, always.
  - Why: The read-only-then-write ordering is stated as an invariant of the workflow.

- **S13 — Intra-region offsets are stable across sessions (measured), which can replace scanning**
  - Fact: Scanner's design notes record that an in-region offset is stable across sessions, which allows
    locating a table without a scan at a cost of **1.1 MB / 117 ms** — about **7500×** cheaper than
    having 7 mods each full-scan 9 GB.
  - Why: Repeated full scans of 9 GB per mod were the dominant cost.

- **S14 — `game.dll` location routine: signature + self-check, self-disable on mismatch**
  - Fact: The (now retired) ESC-menu panel design used a "signature + self-check, disable yourself when
    it does not match" routine for locating things in `game.dll`, and included a three-layer lazy
    determination plus a runtime decision between the 4th / 5th menu slot position, with MDL
    interoperation.
  - Why: A menu host must not corrupt the game when the build it targeted has changed.

---

## writing-and-timing

- **W1 — The write window decides which match a change takes effect in, not scan speed**
  - Fact: A table being in memory does not mean the list that consumes it has not already been built.
    Measured with stratagem attachments: writing `additional_stratagem` after entering a mission may be
    too late — the current mission's list is already fixed and the change shows up only back on the ship
    or in the next mission. Scan speed only determines when the address is known; what decides the match
    is the window after the table loads and before the list is built. Speeding up the scan is not a
    substitute for finding that window.
  - Why: A correct value written at the wrong moment appeared to have no effect.
  - Conflicts: Contradicts the assumption that finding the address earlier/faster is the thing that
    makes a write take effect.

- **W2 — Additional-stratagem write semantics (avoid stratagem nesting)**
  - Fact: For carrying mech A + additional mech B:
    | record | field | action |
    |---|---|---|
    | A | `package+32` `additional_stratagem` | write B's stratagem ID |
    | A | `package-88` `use` | write `2` |
    | B | `package+32` `additional_stratagem` | do not touch |
    | B | `package-88` `use` | write `2` |
    | A/B | `package-64` / `package-60` cooldown | do not touch |
    Write only the carrying record's single `additional_stratagem`; writing both ways creates a stratagem
    nesting loop. Before writing, verify the current `+32` is `0` or already the target; otherwise refuse.
  - Why: Mutual writes produced nested stratagems.

- **W3 — A mount slot could only be changed once: the write guard must also accept the last value you wrote**
  - Fact: Symptom: the first write to a mount slot succeeds, changing it to another item is refused, and a
    mech that was first a carrier and later an addition also becomes unwritable. Root cause: the guard
    accepted only two values —
    ```lua
    if cur == le(want) then
      -- already the target
    elseif cur == le(other) then
      -- the original, or the other legal value in the config
      write(...)
    else
      refuse
    end
    ```
    — so after the first successful write `cur` = the previous target A, `want` = new target B and
    `other` = original, and `cur` matches neither. Fix: also treat the previously written value as a legal
    source:
    ```lua
    local last = state.slots[address] and state.slots[address].item

    if cur == le(want) then
      state.slots[address] = { item = want, orig = orig, who = who }
    elseif force or want == orig or cur == le(other) or (last and cur == le(last)) then
      write(...)
      state.slots[address] = { item = want, orig = orig, who = who }
    else
      refuse
    end
    ```
    and store both `item` (current target, for recognising the next switch) and `orig` (original value,
    for restoring during initialisation) in `state.slots[address]`.
  - Why: The write guard locked out its own previous write.

- **W4 — Writing the original value back must always bypass every check**
  - Fact: Added 2026-10-03 (guard dog): if the "original" value is itself blocked by the `cur` test, a
    player switching over from an older mod is permanently stuck: e.g. `guard-dog-mg43` already wrote
    **MG-43**, the new mod's `orig` = **A32621E3BDE13379**, `cur` = MG-43, `last` = nil → `cur` is
    neither the original nor `last` → refuse, so even selecting the original is impossible. Therefore
    `want == orig` is passed through directly (`elseif force or want == orig or cur == le(other) or (last and cur == le(last)) then write(...)`).
    "Writing back the original" can never be worse than leaving an unknown value in place. Non-original
    item swaps remain protected. This is the second safeguard besides `force` in §6.25-`vanilla_force`:
    initialisation is an explicit action and everyday switching should not depend on it. Both the mech mod
    (`exo_loadout`) and the guard dog (`guard_dog_loadout`) implement it. Guard-dog offline case **13**
    pins this: memory holds MG-43 and cfg selects AR-23P → the original must be written back.
  - Why: Players coming from an older mod were locked out even from restoring the original.
  - Conflicts: Contradicts the common write-guard idiom that whitelists only {current == target,
    current == original}, which is exactly the shape of the pre-fix guard.

- **W5 — Initialisation restores original defaults, not the last cfg**
  - Fact: Symptom: after pressing initialise, memory still holds the last exit / last Apply configuration
    instead of the original. Root cause: initialisation reused the normal write-back path
    (`apply_all('vanilla')`), which is still subject to the §6.24 guard, so the current value (neither
    original nor target) was refused and the initialisation silently did nothing. Fix: add a
    `vanilla_force` mode, call `apply_all('vanilla', true)`, and validate only `node` / `pad` / `recIdx` —
    force-write the original regardless of the current value. Iron rule: **whenever the target value
    equals the original, skip the check entirely** (`want == orig` writes directly, without looking at the
    current value), so initialisation, confirmed reset, and original restore can never be blocked by an
    unknown current value. Consolidate initialisation into one function:
    ```
    do_initialize()
      -> cancel Scanner memscan
      -> restore_strat()          -- restore original additional / use values
      -> restore_arms_all()       -- restore all tracked slots
      -> apply_all('vanilla', true)
      -> reset_cfg()              -- back to default: patriot + none + original
      -> clear strat_addr / strat_hits / strat_pair / scanner state
      -> sync ModOptionsMenu
    ```
    Initialisation does **not** read `ExoLoadout.cfg`; the last-exit cfg is the wrong semantics.
  - Why: Initialisation appeared to run but left the previous configuration in memory.

- **W6 — The default additional body must be `none`**
  - Fact: `CFG = { carry = 'patriot', extra = 'none', arms = {} }`. Newly generated cfg uses
    `extra=none`; `reset_cfg()` returns to `extra=none`; the old panel's and ModOptionsMenu's additional
    `choice` default to none; self-check must accept `extra='none'`.
  - Why: Any other default makes a fresh install start in a modified state.

- **W7 — Runtime-patch template (validated on-machine in one pass)**
  - Fact: Locate the table by signature and verify known constants such as `size`; find the target record
    by **unique ID** and require it to be unique (more than one → refuse); verify an expected constant in
    the record (e.g. `SpawnPayloadSize == 2`); **back up the original bytes to disk before writing**;
    detect whether the patch is already applied (idempotence) so it is not written twice; on a read-only
    page use `VirtualProtect` temporarily and restore the original protection afterwards; **read back and
    verify field by field** (not merely "write succeeded"); re-check every **~5 seconds** and re-apply if
    a map reload wiped it; use `_G.<ModName>` as a singleton guard; rate-limit error logs; log and refuse
    the write whenever any validation does not match.
  - Why: This is the template the source records as passing on-machine on the first attempt.

- **W8 — Write-safety rules for release (version pinning, refusal, user warning)**
  - Fact: Do read-only recon first; validate the value range before writing and read back after; refuse
    and log on mismatch; verify the game version (`exe`/`dll` SHA-256) and refuse to write on mismatch.
    Warn the user proactively that changing game behaviour while online may make the client differ from
    teammates and carries anti-cheat risk, and state clearly that these are client-local changes that most
    other players will not see. All changes live in memory only, so disabling the mod + Purge fully
    restores the game.
  - Why: Safety and compliance section; a version mismatch is treated as a reason to refuse writes
    outright.

---

## logging

- **G1 — `loader.open_log` is overwrite mode, so "append" is accumulate-and-rewrite by contract**
  - Fact: `loader.open_log` truncates on every open, so appending means accumulating the text and writing
    the whole buffer back. This is not a bug but the interface contract; the bug is in when and how much
    is written back.
  - Why: The source's log-rewrite incident was initially misread as a loader bug.
  - Conflicts: Contradicts the assumption that `open_log` gives you an appending file handle.

- **G2 — Correct log writer: ring cap + dirty flag with a 1-second throttle**
  - Fact:
    ```lua
    local LOG_CAP = 400
    local loghist, log_dirty, log_at = {}, false, -10

    local function flush_log(force)
      if #loghist == 0 then return end
      local now = os.clock()
      if not force and (not log_dirty or now - log_at < 1) then return end
      log_dirty, log_at = false, now
      local text = table.concat(loghist, '\n') .. '\n'
      pcall(function()
        local loader = rawget(_G, 'CowboyBingusModLoader')
        local file = loader and loader.open_log and loader.open_log('<ModName>.log')
        if file then file:write(text); file:close() end
      end)
    end
    ```
    Only a genuinely new message forces a flush (`if keep then flush_log(true) end`).
  - Why: The three-layer incident: an unbounded `loghist`, `keep=true` bypassing consecutive dedupe, and
    rewriting the whole file on every report.

- **G3 — Fold repeated consecutive messages into one line with `(×N)`**
  - Fact: In `report(message, keep)`, if `message == state.status` then increment
    `state.repeat_n = (state.repeat_n or 1) + 1` and rewrite the last line as
    `('[frame %d] %s  (×%d)'):format(state.frame, message, state.repeat_n)`, set `log_dirty = true`, and
    return — without `print`, without appending a new line and without forcing a flush. On a new message:
    `state.status, state.repeat_n = message, 1`, `print('[<Tag>] ' .. message)`, append
    `('[frame %d] %s'):format(state.frame, message)`, and trim with
    `if #loghist > LOG_CAP then table.remove(loghist, 1) end`.
  - Why: A per-frame operation produced hundreds of near-identical log lines.

- **G4 — Three log invariants with thresholds for the offline fixture**
  - Fact: (assertions to pin in offline tests; the fake loader needs an `open_log` counter)
    `open_log` call count over **600 frames** ≤ **20** (1/second plus a few forced flushes) — it was
    ≈**600** before the fix; log line count over **3000 frames** ≤ **400**, and nearly identical to the
    count at 300 frames; one repeated identical message occupies only **1** line and contains `(×N)`.
  - Why: Without counters the "fix" is unverifiable offline.

- **G5 — `#loghist % N == 0` throttling degenerates once a ring cap exists**
  - Fact: A "flush every N entries" throttle such as `#loghist % N == 0` becomes "flush on every entry"
    when combined with a ring buffer, because `#loghist` sticks permanently at 400 and `400 % 10 == 0` is
    always true. Replace any such construct on sight.
  - Why: The ring cap silently turned a throttle into a per-message rewrite.

- **G6 — Bulk diagnostics must not go through `loghist`**
  - Fact: Send batch diagnostic output through a separate `dump()` that writes straight to disk;
    otherwise the 400-line cap eats it.
  - Why: Census / dump content silently disappeared under the ring cap.

- **G7 — `loader.open_log` only accepts `.log` file names**
  - Fact: The loader checks
    `if type(name) ~= 'string' or not name:match('^[%w_-]+%.log$') then return nil end`.
    `.txt` and any other extension return `nil`, and if the caller wraps that in `pcall` the result is a
    silently missing file. Use `.log` for every dump, e.g. `SSProbe_dump.log` / `SSProbe_table.log`;
    when something does not appear, check the file-name rule before suspecting the scan logic.
  - Why: The main log worked while dump files never appeared.

- **G8 — Log flush discipline for recon addons (one shot per game run)**
  - Fact: Flush periodically every N frames rather than only at the end of a scan (a mid-way crash leaves
    not one byte), flush on error too, prefix lines with `[frame N]` so ship-loaded data can be told apart
    from data that only exists inside a mission, and rate-limit repeated error printing so the log is not
    flooded.
  - Why: A recon run ended in a crash with nothing on disk.

- **G9 — Print each assertion's expected value**
  - Fact: Log the expected value alongside every assertion, so it is immediately visible whether the
    signature was not found or it was found but the layout changed.
  - Why: Without the expected values, a mismatch was ambiguous between "not located" and "located but
    different layout".

- **G10 — Shared log directory**
  - Fact: The shared log directory is `%LOCALAPPDATA%/CowboyBingus/Helldivers2/Logs`.
  - Why: Fixed location used by the loader and by mods writing logs.

---

## packaging-and-layout

- **P1 — Addon declaration line: `-- HD2-Addon: mods/<author>/<module>`**
  - Fact: The first line must be `-- HD2-Addon: mods/<author>/<module>` with no BOM, within **256 bytes**,
    and **must be plaintext**. Compiling to bytecode drops this comment line, which breaks automatic
    discovery. To ship a bytecode implementation, package two resources and make the entry
    `return require('..._impl')`.
  - Why: A bytecode-compiled addon was never discovered.

- **P2 — Addon build command**
  - Fact: `python tools/build_addon.py --name mods/<author>/<name> --entry x.lua --guid <stable UUID> --display-name "name" --output build/X.zip`.
  - Why: The supported packaging path for an installable ZIP.

- **P3 — Never hardcode the patch number**
  - Fact: HD2 Mod Manager allocates and re-orders slots itself (measured: installing one new mod shifted
    the numbers of other mods). For a manual install, take the current maximum number + 1, and afterwards
    identify your own archive by timestamp / size.
  - Why: A hardcoded `patch_N` slot broke when the manager renumbered mods.

- **P4 — The loader only discovers, requires and logs; it never modifies memory**
  - Fact: Bingus Shared Loader's job is discovery + `require` + logging. The actual memory work is done by
    the addon's own code.
  - Why: Misattributing memory writes to the loader leads to debugging the wrong component.

- **P5 — `.patch_N` header (byte-level verified)**
  - Fact: At `+0`, 72 bytes: `<III20sQQ24s` = magic `0xF0000011`, `1`, count, 20×0, totalSize (Q), `0`,
    24×0.
  - Why: Archive-format fact needed to read or generate an archive.

- **P6 — `.patch_N` type records at `+72`**
  - Fact: At `+72`, 32 bytes × types: `<IIQIIII` = `0, 0, typeHash, count, 0, 16, 16`.
  - Why: Archive-format fact; the `count` here drives the descriptor table size.

- **P7 — `.patch_N` resource descriptors at `+104`**
  - Fact: At `+104`, 80 bytes × count: `<7Q6I` = `nameHash, typeHash, offset, 0, 0, 0, 0, length, 0, 0,
    16, 16, index`.
  - Why: Archive-format fact needed to locate each resource body.

- **P8 — `.patch_N` data area and resource body layout**
  - Fact: Data area = `align16(104 + 80*count)`, each resource 16-byte aligned. A resource body is
    `u32 bodyLen + u32 version(=2) + body`.
  - Why: Computing resource offsets requires the aligned data-area base.

- **P9 — Carrier file name**
  - Fact: The carrier file is `data/9ba626afa44a3aa3.patch_<N>`.
  - Why: Fixed install path for injected mods.

- **P10 — Resource type markers**
  - Fact: Lua resource type tag = `0xA14E8DFA2CD117E2`; the resource occupied by the loader is
    `core/wwise/lua/wwise_flow_callbacks` = `0x7251FDD9BB62480A`.
  - Why: Needed to recognise a Lua resource inside an archive and to avoid the loader's own resource.

- **P11 — Multi-resource addons: only the entry carries the declaration**
  - Fact: Only the entry gets the `-- HD2-Addon:` declaration. Loader discovery (`discover.lua`) accepts
    only "declared name == resource name hash", so declaring modules as well turns each module into an
    independent addon shown as N separate mods. Warning: `tools/build_addon.py --extra` also adds a
    declaration header to every extra — do not use it for multi-resource packaging; write your own
    script. After packaging, read the archive back and confirm only the entry carries the declaration.
    Modules without the declaration can be compiled to bytecode (smaller and faster). Example:
    `hd2-mod/junze-hd2-lua-mod/menu-panel/` = **6** resources (entry + 5 modules).
  - Why: Modules with declarations appeared as separate mods in the manager.

- **P12 — Two artifact lines, never mixed**
  - Fact: `hd2-mod\build\` = working build area (current version zip sits directly in the root;
    untracked); `hd2-mod\build\_deprecated\` = abandoned artifacts, whose names carry the reason
    (untracked); `hd2-mod\build\_old\` = earlier artifacts (untracked); `hd2-mod\build\_probes\` =
    recon / probe packages (untracked); `junze-hd2-lua-mod\dist\` = release area, distributed with the git
    repository plus `SHA256SUMS.txt` (**tracked**). Do not create your own `dist/` or `build/` inside a
    mod subdirectory — it fights those two lines.
  - Why: A mod-local `dist/` conflicts with the tracked release line.

- **P13 — Package name must be pure ASCII**
  - Fact: `<Mod-Name>-v<X.Y.Z>.zip`, pure ASCII. The mod manager uses the manifest `Name` as a folder
    name, and Chinese characters produce the error 「目标名/目录名或卷标语法不正确」.
  - Why: A non-ASCII package name failed to install.

- **P14 — Never overwrite a previous package; archive it with a reason, and skip archiving identical rebuilds**
  - Fact: Before repackaging, move the old package into `_deprecated\` with the reason — do not overwrite
    it (on 2026-10-02 the package showing "page 5 tab crashes" was overwritten and the evidence was lost).
    Best done automatically by the build script: write to `.tmp` first, byte-compare with the existing
    artifact — byte-identical means **do not archive** (a same-source rebuild lost nothing, and otherwise
    `_deprecated` drowns in noise); only on difference move it into `_deprecated\`. Archive name =
    `<original name>_被同名重建覆盖_<timestamp>[_index].zip`; the timestamp is only second-precision, so
    same-second rebuilds collide and a sequence number is mandatory.
  - Why: Overwriting destroyed the evidence needed to diagnose a known crash, and noise flooded the
    deprecation folder.

- **P15 — Deprecated artifact names must state why**
  - Fact: Real examples:
    `AC8-Rack-Backpack-v1_census无门控+漏WriteCopy.zip`,
    `TD-110-Co-Op-v1.3_复查有bug.zip`,
    `TD-110-Co-Op-v1.7_射界未收紧.zip`,
    `More-Balanced-Exosuit-Emancipator-v1.0_兜底无退避.zip`.
  - Why: Without the reason in the name, the same mistake gets repeated later.

- **P16 — Per-mod project layout**
  - Fact:
    ```
    <mod>/
      src/            main sources (split-out modules also live here)
      build.py        packaging (default output -> hd2-mod\build\; --release also copies into dist\)
      guid.txt        stable GUID, kept next to the sources
      DESIGN.md       engineering notes (design detail goes to hd2-mod\docs\)
      test/           offline regression (lupa, no game required)
    ```
  - Why: Conventional layout so build and release lines stay consistent.

- **P17 — The manifest GUID must never change**
  - Fact: If the manifest GUID changes, the mod manager treats an upgrade as a new mod (e.g. AC-8
    `2b8e6c51-…`, 实弹狗 `7f2c8a04-…`).
  - Why: A changed GUID makes upgrades install side by side with the old version.

---

## tooling-and-workflow

- **T1 — Offline first, machine second**
  - Fact: The order is always: find the plaintext offline → compute offsets and values offline → do a
    minimal verification on-machine. A machine session costs a game restart, so do the bulk of the work
    before it.
  - Why: On-machine recon is the expensive step; the plaintext mirror removes most of the need for it.

- **T2 — Getting the plaintext mirror from FileDiver**
  - Fact: FileDiver's `datalibrary` packages the plaintext data (typelib included) into the Go module with
    `//go:embed`. `go mod download github.com/xypwn/filediver` (or clone the source tree); the files are
    at `<GOMODCACHE>/github.com/xypwn/filediver@<ver>/datalibrary/`:
    `generated_*.dl_bin` (plaintext data tables, including the 45 MB `generated_entities.dl_bin`),
    `dl_library.dl_typelib` (the game's own type library), and `*.go` (per-component field names and
    comments generated from the typelib).
  - Why: This is the only source of plaintext tables (see D5/M7).

- **T3 — Dumping the typelib to JSON**
  - Fact: Put `tools/dump_typelib/` into the FileDiver source tree under `cmd/` and run
    `go run ./cmd/dump_typelib -o typelib_all.json` (1177 types' field offsets / sizes / member names).
    `-o` is not optional: PowerShell's `>` redirection writes UTF-16, which Python cannot read.
  - Why: A redirected JSON file could not be opened by Python.

- **T4 — Toolchain inventory**
  - Fact:
    | path | purpose |
    |---|---|
    | `tools/hd2_archive.py` | `.patch_N` read/write (round-trip verified) |
    | `tools/build_addon.py` | `.lua` → installable ZIP |
    | `tools/inspect_patch.py` | archive structure view + automatic round-trip check |
    | `tools/projectile_settings.py` | `generated_projectile_settings.dl_bin` parser |
    | `tools/dump_typelib/` | typelib → JSON (run inside the FileDiver source tree) |
    | `tools/ljd/` | LuaJIT bytecode decompiler, for reading other people's mods — **third party** |
    | `tools/filediver/` + `filediver-src/` | community unpacking tool + **plaintext datalibrary + field-name Go source** — **third party** |
    | `tools/go/` | portable Go (only needed to dump the typelib) |
    | `references/ldld.py` | **LDLD table parser** (`dlsum` / find instance / decode records) |
    | `_baseline_<build>/` | on-machine memory dump baselines, for comparison after a game update |
  - Why: Consolidated tool map; the third-party entries are marked so their provenance is not lost.

- **T5 — Verify the game build before doing machine work**
  - Fact: Check `helldivers2.exe`'s version and SHA-256 before touching the machine. **An unchanged build
    means the old dumps, offsets and census are all still valid**, which saves an entire recon round.
  - Why: Re-running recon on an unchanged build wastes a full cycle.

- **T6 — Solve offline by differential against the same family**
  - Fact: Step 0: (1) find the target table by type name with `dlsum` from the plaintext mirror and decode
    all records; (2) take field offsets from `typelib_all.json` and field meanings from `datalibrary/*.go`;
    (3) find "same-family contrasts" and diff them — faster and harder than pinpoint kills: the task was
    "the Leveller drops one per airdrop" while EAT-17 and EAT-700 both drop two, so putting the three rack
    records side by side made the differing fields jump out (`slot1` empty + `SpawnPayloadSize`);
    (4) prefer copying a configuration that already works in-game over inventing values — the final
    **64 bytes** were **byte-identical** to EAT-17's slot1 with only an **8-byte** item hash differing,
    which is evidence that the reproduced behaviour is the engine's existing behaviour.
  - Why: Invented values would be unverified; a diff of a working sibling gives the answer directly.

- **T7 — Step 2: verify offsets and value ranges offline**
  - Fact: Parse the dump with a script and confirm offsets and value ranges. If the memory layout matches
    the file image, this step is pure verification.
  - Why: Cheap check that avoids a machine round.

- **T8 — Cross-validate against the community wiki**
  - Fact: `helldivers.wiki.gg`'s "Detailed Weapon Statistics" gives exact numbers; match them item by item
    against a data table — a multi-item hit locks the record. Example: the Eruptor's impact explosion per
    the wiki is `225 damage / 30 fragments / inner radius 4 m / outer radius 7 m / demolition 20 /
    stagger 35 / push 40 / Medium armor penetration`, and of **413** explosion entries **only one**
    matched all 8. Wiki behaviour sentences (e.g. *"sent two at once like typical EAT-17"*) can lead
    straight to the same-family contrast.
  - Why: A multi-field wiki match pins the record without a machine scan.

- **T9 — Offline simulation with `lupa` and a type-strict stub**
  - Fact: Use `lupa` (pip install) to run Lua inside Python with a **fake memory space**. The test stub
    must be type-strict or it cannot catch bugs like M3:
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
  - Why: A lenient stub let pointer-type bugs reach the machine.

- **T10 — Mutation testing: a test that cannot fail is worthless**
  - Fact: After fixing a bug, revert it and confirm the test **actually fails**. When a mutation is not
    caught, suspect the fixture before the code — the `SpawnPayloadSize` mutation escaped because the
    fixture itself had placed the decoy rack at the wrong offset.
  - Why: An uncaught mutation means the test is not actually checking the thing.

- **T11 — Use real dumps as fixtures, and add deliberate decoys**
  - Fact: The fixture should be a memory dump captured from a real machine, so offsets are checked against
    real bytes. Add decoys: a table that looks legal but has wrong key fields (tests your validation); a
    fake heap region containing your own pattern strings (tests self-detection); and mind the scan order —
    regions are scanned in **descending size order**, so make a decoy larger if it must fire first.
  - Why: Real bytes plus decoys are what make the offline suite able to catch real failures.

- **T12 — `lupa` troubleshooting**
  - Fact:
    | symptom | cause / fix |
    |---|---|
    | `cannot open ...: Illegal byte sequence` | **Lua's `fopen` cannot open paths containing Chinese characters**; put fixture files in `%TEMP%` (pure ASCII) |
    | `too many registers (limit is 255)` | one `string.char(...)` call with tens of thousands of arguments; chunk it by **200** |
    | `UnicodeDecodeError` on read-back | **lupa decodes Lua strings as UTF-8 by default**, which breaks on binary; have the Lua side return a **hex string** |
  - Why: Each of these was hit while building the offline harness.

- **T13 — The loader requires an addon once at startup; there is no hot reload**
  - Fact: Loader requires the addon only at startup — there is no hot reload, so even a one-line change
    means closing and restarting the game. That is why the first version must be built so that "even if
    something goes wrong there is an artifact on disk".
  - Why: A recon run was lost because nothing had been written when the game restarted / crashed.

- **T14 — Document in three synchronised places**
  - Fact:
    | location | role |
    |---|---|
    | `hd2-mod\docs\<topic>-设计定稿.md` | **original** — changes are authoritative there |
    | `skills\hd2-lua-mod\references\hd2-<topic>.md` | **copy** (loaded directly by a new session), first line must say "this file is a copy, the original is the source" |
    | `SKILL.md` §12 instance table | **index** line pointing at the copy |
    After editing the original you must sync the copy, or a new session reads the old version.
  - Why: New sessions read the copy, so an unsynced copy serves stale instructions.

- **T15 — Reference design notes indexed in the source (what to read for which problem)**
  - Fact: `hd2-eruptor-dominator-案例.md` = putting the R-36 Eruptor's projectile onto the JAR-5
    Dominator (pure in-memory projectile-table edit); `hd2-leveller-double-案例.md` = EAT-411 Leveller
    dropping two per airdrop (full offline solve + one on-machine recon + 64-byte patch);
    `hd2-ac8-rack-backpack-设计.md` = AC-8 backpack replacement v6 (content-anchor method,
    `HellpodRackComponentData`, LDLD + type hash + in-record relative offsets);
    `hd2-scanner-设计定稿.md` = sentinel/scanner design (7 mods' full scans of 9 GB converged into 1;
    in-region offsets stable across sessions; 1.1 MB / 117 ms, ~7500× cheaper) — read before writing a
    new mod or changing scan/table-lookup logic; `hd2-menu-panel-设计定稿.md` = ⛔ retired 2026-10-04,
    ESC-menu panel design (native tab via the game's `set_labels`, fallback to a self-drawn floating panel
    when occupied, three-layer lazy determination, runtime decision on the 4th/5th slot, MDL
    interoperation, signature + self-check + self-disable `game.dll` routine);
    `hd2-载具参数-笔记.md` = vehicle parameter notes (**not found**; fields `+296`/`+300`/… each tried and
    rejected — negative results are data, do not re-run);
    `hd2-td-110-挂载与射界-笔记.md` = TD-110 mount / traverse notes (including the "read it as TD-220"
    lesson and why two mount slots were swapped by position);
    `hd2-stratagem-settings-笔记.md` = StratagemSettings / StratagemInfo notes (non-LDLD 400 B records,
    package content search, additional-stratagem write semantics, Scanner memscan service, ModOptionsMenu
    capability boundary, write timing); `hd2-strat-unlock-设计定稿.md` = unlock a stratagem by ID (v1.7
    verified; three conditions, pointer table `*(0x37CB600+id*8)`, Scanner AOB API, offline fixtures and
    pitfall list) — read first for "make a stratagem selectable"; `hd2-supply-custom-设计定稿.md` =
    custom supply (rack 4 slots determine the cooldown, 30~150 s; `HellpodRackComponent` 568 B =
    `RackAttach[8]` (64 B/slot) + tail, `spawn_payload_size` @ `+0x22C`; three write sites; config via
    four independent MOM choices) — read first for supply / rack changes.
  - Why: The reference set is the project's accumulated negative and positive results; reading the wrong
    one means repeating solved work.

- **T16 — Interpreting a "not found" result**
  - Fact: Vehicle power / speed parameters were never located: each candidate field (`+296`, `+300`, …)
    was tried and rejected. The lesson recorded with it is that a negative result is itself material —
    do not re-run the search.
  - Why: Re-running an exhausted search wastes machine rounds.

---

## release-and-network

- **R1 — Repository, paths and release lines**
  - Fact: Repository `junze0910/junze-hd2-lua-mod`, local `10-projects\hd2\hd2-mod\junze-hd2-lua-mod`.
    Four release lines (tag prefixes): `core` (prerequisites) / `infantry` (infantry) / `vehicle`
    (vehicles) / `logistics` (logistics, reserved). Tags look like `core-v2.0`. **Tag version ≠ package
    version** — packages evolve independently (AC-8 is 2.0, Scanner is 0.7.0).
  - Why: Per-line tagging lets independent packages release on their own cadence.

- **R2 — The fixed seven-step release procedure**
  - Fact: (1) edit `local VERSION` in the source (the single source of truth) → `python tools\build_mod.py --list`
    to see the key names → `python tools\build_mod.py <key>`; Scanner uses its own
    `hd2-scanner\build.py` (multi-resource archive). Neither overwrites: the same name / an old version
    automatically goes into `build\_deprecated\`, and byte-identical content is neither rebuilt nor
    archived. (2) Copy the new package into `dist\`; move the superseded old package into
    `build\_deprecated\from_dist\`. (3) Recompute `dist\SHA256SUMS.txt`. (4) Update `README.md` (install
    table + release-line description) and `RELEASE-NOTES.md` (new section; the publish script extracts the
    body from here). (5) `git add -A` → commit (Chinese, with a `release:` / `docs:` prefix) →
    `git tag -a <tag> -m "…"`. (6) `push` (**must go through the proxy**, see R9). (7)
    `python tools\gh_publish.py` (creates the Release for that line, attaching only that line's packages
    and its own `SHA256SUMS.txt`; repeatable), then `python tools\gh_verify.py`.
  - Why: The procedure that keeps tag, package and checksum file consistent.

- **R3 — `SHA256SUMS.txt` format**
  - Fact: Lowercase hash + **two spaces** + file name, so `sha256sum -c` works on it directly.
  - Why: Standard format required for the file to be verifiable in one command.

- **R4 — `gh_publish.py` never overwrites a same-named attachment**
  - Fact: `gh_publish.py` only uploads attachment names that do not already exist; a same-named attachment
    (especially `SHA256SUMS.txt`) is skipped. So whenever the attachment set changes (version change,
    deleted old package), you must first delete the same-named / extra old attachments on the release
    page, then run `gh_publish.py` — otherwise `SHA256SUMS.txt` stays in its old state and lists deleted
    packages. Hit on 2026-10-04.
  - Why: A stale checksum file listed packages that no longer existed.

- **R5 — `gh_verify.py` compares API digests instead of downloading**
  - Fact: `gh_verify.py` compares using the API's `assets[].digest` and does not download attachments,
    because the proxy's TLS to `objects.githubusercontent.com` is frequently broken (the downloading
    version gets SSL EOF). The digest version is faster and unaffected by the proxy.
  - Why: Attachment downloads failed through the proxy.

- **R6 — Token storage**
  - Fact: Keep the token in a secrets directory **outside the workspace** (that directory's own
    `.gitignore` is `*`; the first non-comment line of the file is the token). Scripts read the
    environment variable `GH_PAT` first and fall back to that file. Never write the token into the skill
    document.
  - Why: Keeping the token out of the repo prevents accidental publication.

- **R7 — Token scope pitfalls**
  - Fact: A classic token (scope `repo`) or a cleaner fine-grained token both work; the cleanest is a
    fine-grained token limited to this repository with `Contents: Read and write`. **Read-only always
    yields 403** — the API reports `Resource not accessible by personal access token`, git reports
    `denied to <user>`. Another hidden trap: if Repository access is set to
    `Public repositories (read-only)`, reading public repositories still works but writing never does.
  - Why: A read-only-scoped token produced 403s that looked like permission/network problems.

- **R8 — Network trap 1: `Invoke-RestMethod` / `curl.exe` HTTPS is broken on this machine**
  - Fact: The certificate store is locked
    (`schannel: AcquireCredentialsHandle failed: SEC_E_NO_CREDENTIALS`), so even `https://github.com`
    returns `HTTP=000`. For outbound access use **only git (bundled OpenSSL) and python (bundled
    OpenSSL)**.
  - Why: HTTPS clients in PowerShell failed outright.

- **R9 — Network trap 2: the proxy lives only in the WinINET registry**
  - Fact: The proxy is registered only in the WinINET registry (set by the VPN client), not in environment
    variables and not in git config: `HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings` →
    `ProxyServer`; measured **2026-10-03** as `127.0.0.1:6382`. git:
    `git -c http.proxy=http://127.0.0.1:6382 push <url>`; python:
    `$env:HTTPS_PROXY='http://127.0.0.1:6382'`.
  - Why: git/python had no proxy configured and could not reach GitHub.

- **R10 — Network trap 3: one-shot inline credentials for push**
  - Fact: Push with a one-shot inline credential that is never written into git config:
    `https://x-access-token:<token>@github.com/junze0910/junze-hd2-lua-mod.git`; when echoing, replace the
    token with `***`. `sh.exe: couldn't create signal pipe` is MSYS noise and can be ignored.
  - Why: Avoids persisting the token while still authenticating the push.

- **R11 — A tag's pointer is not recyclable**
  - Fact: Once pushed, do not delete a tag or change what it points at (no `git tag -f` + force push). An
    empty release line only occupies a tag plus a placeholder Release, with no packages
    (`logistics-v0.1alpha` was left that way).
  - Why: Moving a tag breaks reproducibility of what a release contained.
  - Conflicts: Contradicts the common habit of force-moving a tag to fix a release.

- **R12 — Release content above a tag is mutable, with one caveat**
  - Fact: The Release content on a tag can change: swap attachments for a patch package (delete the old
    attachment → upload the new package → recompute that line's `SHA256SUMS.txt`); the title and body can
    also change — just leave a line "附件已更新（日期）" in the body. Use
    `tools\gh_refresh_releases.py` (idempotent, re-runnable). Caveat: the "Source code (zip)" snapshot is
    still the tree as of the tag, so download links in the body must point at the **`main` branch's
    `dist/`**, not at the tag snapshot. The alternative is a new patch tag (e.g. `infantry-v2.0.1`), useful
    when users should still be able to get the old package; both paths work — do not mix them.
  - Why: The tag snapshot is frozen, so links into it hand users stale packages.

- **R13 — Do not use `git push --tags`**
  - Fact: Do not use `git push --tags` — a historical mistyped uppercase `V1.0` tag still exists locally.
  - Why: Pushing all tags would publish the mistyped tag.

---

## ui-integration

- **U1 — ModOptionsMenu capability boundary**
  - Fact: `ModOptionsMenu` is not a general UI framework. It supports only `toggle`, `choice` (2–16 fixed
    options) and `slider`. It does **not** support free text input, arbitrary buttons / Action rows,
    dynamic read-only status lines, or changing a `choice` list after registration. Practice: left and
    right must have separate `choice` pools (the left slot lists only left items, the right only right
    items); player-triggered actions (start scan / initialise) are carried by a `toggle` — Apply fires the
    callback, and after doing the work either immediately `menu.set(id,false)` to pop back or pop back
    when the operation finishes; anything that must be recomputed after a selection change is synced back
    into the menu with `menu.set`.
  - Why: The available widget set constrains how mod settings and manual actions can be expressed.

- **U2 — The interface goes only through ModOptionsMenu; HD2Menu is retired (2026-10-04)**
  - Fact: The whole `_G.HD2Menu` / `HD2MenuQueue` page system is retired: the rendering host `ui.lua` has
    not been in the release package since **2026-10-03**, so pages could never display, and on
    **2026-10-04** `registry.lua` was deleted along with it. New mods must not write
    `menu.register{...}` or queue into `HD2MenuQueue` — `rawget(_G,'HD2Menu')` is now `nil`. Always use
    `_G.ModOptionsMenu` (`mom.register_option`), which has only `toggle` / `choice` / `slider`. For a
    "read-only status", make the `label` or `description` a **function** (MOM recomputes it every time the
    ESC menu opens, see §6.21). For an "action button", use `toggle` + do the work in `on_change` +
    `mom.set(id, false)` to pop back. Scanner itself uses exactly this (3 lines on the MODS page: status /
    AOB / diagnostics) and can be copied.
  - Why: Pages built on the retired menu host never rendered, wasting entire mod features.
  - Conflicts: §6.21 lists "dynamic read-only status lines" as unsupported; §6.28 prescribes exactly that
    via a function-valued `label` / `description`. The two statements are not reconcilable from the source
    text — see UNCLEAR.

---

## Coverage

All sections of the source were read in full. Legend: `covered` = facts extracted into this inventory;
the item IDs in parentheses are where each section landed (a section may map to several items, and one
item may serve two sections).

- §0 先离线,后上机 — covered (T1, T2, D5, D6, D7, M7; the plaintext-resource table is fully represented)
- §1 两个哈希函数,别混 — covered (D3, D4)
- §2 数据表(LDLD)实例:两种布局 — covered (D2, M1; the note that `references/ldld.py` is the ready
  parser for `dlsum` / instance finding / record decoding is in T4)
- §3 固定常量(不会变) — covered (D1, D4, M5, M7, G10, P9, P10)
- §4 `.patch_N` 归档格式 — covered (M2, P5, P6, P7, P8)
- §5 Addon 约定 — covered (P1, P2, P3, P4)
- §6 运行环境陷阱清单 — covered, all 28 entries:
  - 6.1 — covered (L1)
  - 6.2 — covered (S1)
  - 6.3 — covered (L2)
  - 6.4 — covered (M3, T9)
  - 6.5 — covered (S3)
  - 6.6 — covered (S6)
  - 6.7 — covered (D7)
  - 6.8 — covered (S7)
  - 6.9 — covered (S4)
  - 6.10 — covered (T13, G8)
  - 6.11 — covered (L3)
  - 6.12 — covered (S5)
  - 6.13 — covered (M6, M7)
  - 6.14 — covered (M8, S11, G9)
  - 6.15 — covered (G1, G2, G3, G4, G5, G6)
  - 6.16 — covered (G7)
  - 6.17 — covered (S2)
  - 6.18 — covered (D8)
  - 6.19 — covered (D9)
  - 6.20 — covered (S8)
  - 6.21 — covered (U1)
  - 6.22 — covered (W1)
  - 6.23 — covered (W2, D14)
  - 6.24 — covered (W3, W4)
  - 6.25 — covered (W5)
  - 6.26 — covered (W6)
  - 6.27 — covered (S9, S10, D10)
  - 6.28 — covered (U2); note that in the file this item is physically nested under the `## 7. 工作流`
    heading (line 694), before `### 第 0 步`
- §7 工作流 — covered (T6, S12, T7, T8, W7; the four steps map to T6 / S12 / T7 / T8+W7)
- §8 离线仿真测试 — covered (T9, T10, T11, T12)
- §9 工具链 — covered (T4, T5; the reference-index material around it is in T15/T16)
- §10 产物与目录约定 — covered (P12, P13, P14, P15, P16, T14, P11 for §10.4)
  - 10.1 包名 — covered (P13, P14, P15)
  - 10.2 mod 工程内部布局 — covered (P16)
  - 10.3 文档三处同步 — covered (T14)
  - 10.4 多资源 addon — covered (P11)
- §11 安全与合规 — covered (W8, M5)
- §12 实例 — covered (T15, T16, D11, D12, D13, S13, S14)
- §13 发布(GitHub push + Release) — covered (R1–R13)
  - 13.1 一次发布固定七步 — covered (R2, R3, R4, R5)
  - 13.2 token 放哪 — covered (R6, R7)
  - 13.3 本机/沙箱网络三坑 — covered (R8, R9, R10)
  - 13.4 别做的事 — covered (R11, R12, R13, P17)

Nothing in the numbered §6 list was skipped.

---

## UNCLEAR

1. **§6.21 vs §6.28 on read-only status lines.** §6.21 states `ModOptionsMenu` does not support dynamic
   read-only status lines; §6.28 states that a read-only status is obtained by making `label` or
   `description` a **function** (MOM recomputes on every ESC menu open). The source never reconciles the
   two. Recorded as a conflict on U2 rather than resolved here.
2. **Reference frame of the `package±N` offsets in §6.23.** SKILL.md writes `package+32`, `package-88`,
   `package-64`, `package-60` without saying what `package` denotes. The sibling notes
   (`references/hd2-stratagem-settings-笔记.md`) define `c` = the address of the record's `package` field,
   giving `c+32` = `additional_stratagem`, `c-88` = `use`, `c-64`/`c-60` = cooldown success/fail. That
   definition is used in D14; the source alone leaves it implicit.
3. **§6.13 segment name `.winlice`.** Reproduced verbatim from the source; the source does not explain the
   segment or confirm the spelling. No local file was inspected to verify it (the game is not installed in
   this workspace).
4. **§12 `hd2-td-110-挂载与射界-笔记.md` entry ("read it as TD-220").** Only the index line exists in
   SKILL.md; the actual field offsets, the misread cause, and the slot-swap rationale are not in the
   source, so no rule could be stated beyond "a misread as TD-220 occurred and two mount slots were
   swapped by position". The reference file was not read (supporting material outside the requested
   source). Its content is reached only through T15.
5. **§12 vehicle parameters (`+296`, `+300`, …).** The source records that these candidate offsets were
   tried and rejected but gives neither the field names nor the struct they index into. Recorded as a
   negative result (T16) with no interpretation added.
6. **§6.14 MDL baseline applicability.** The values (M8) are bound to the 2026-09-24 build of MDL 1.4.2;
   the source does not say whether they hold for other builds, and nothing in this workspace can confirm
   or refute that.
7. **§6.20 "old Scanner without `scan_request`".** The source does not give the version at which
   `scan_request` was introduced (the sibling notes mention Scanner v0.7+ / v0.8.0). No version number is
   stated here because SKILL.md does not state one.
8. **§7 / §6.28 placement.** §6.28 is in the §6 numbering but sits under the §7 heading in the file
   (line 694). Noted in Coverage; not corrected.
