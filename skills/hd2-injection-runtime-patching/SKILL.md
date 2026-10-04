---
name: hd2-injection-runtime-patching
description: Patch a running Helldivers 2 process from a LuaJIT addon — locating a table by signature and relative offset, opening read-only pages safely, getting LuaJIT numbers, strings and FFI casts right, and choosing when to write. Use when a mod reads and writes the Helldivers 2 process memory through FFI, or when a write silently does nothing, corrupts a neighbour, or is wiped by a map load.
---

# HD2 injection: patching memory at runtime

English / [简体中文](https://github.com/YC426/HD2-Agent-Skills/blob/main/skills/hd2-injection-runtime-patching/SKILL_cn.md)

Scope: addons that run inside the game's LuaJIT VM and read/write the Helldivers 2 process memory
through FFI at runtime. Asset-replacement mods (swapping `data/` resources) are a different class
and are not covered here.

Everything below is reproduced from the project's machine-verified notes. Where a value is bound to
one build or one mod version, the text says so — never promote a build-bound number into a portable
offset.

---

## 1. Getting a safe write primitive

**Locate by signature, then apply a relative offset. Never store an absolute address.**
The in-memory copy of `generated_entities.dl_bin` is byte-for-byte identical to the file image, so
relative offsets computed offline can be applied directly at runtime. Absolute addresses differ on
every run (ASLR). *Failure this prevents:* a hardcoded absolute address silently works once and then
fails after a restart. If a plan depends on a fixed runtime address, the plan is wrong.

**Disk and memory do not hold the same pointers.** In a `.patch_N` archive the resource-array
descriptors hold relative offsets; once the archive is loaded, the same structure is rewritten with
absolute pointers. The source names this as one of the must-trip-over pitfalls of the format.

**A read-only target page is opened, written, and closed again.** Use `VirtualProtect` to
temporarily open the page, write, and then restore the *original* protection attributes. This is
part of the runtime-patch template that passed on-machine on the first attempt; leaving the page
writable is not an option.

**Never read game memory from an external process.** The anti-cheat is **nProtect GameGuard**
(install directory `bin/GameGuard`). Do not use Python / ctypes with `OpenProcess` +
`ReadProcessMemory` — that is the most easily detected action available. Only in-game read-only
addons are acceptable. *Conflicts:* this rules out the entire Cheat Engine-style attach-and-scan
habit; it is not a preference, it is a boundary.

**You cannot analyse the shipped `game.dll` statically.** `data/game/game.dll` (**15.5 MB**) is
packed on disk. Evidence: the first 8 section names are blanked; those sections have entropy
**8.000** (saturated) against **6.338** for `kernel32.dll`; VSize `0x210FA93` versus RawSize
`0x850800` (the memory image is roughly 4× the disk image); the `.winlice` section has RawSize =
**0** (filled only at runtime; the segment name is reproduced verbatim, the source does not explain
it); the import table `.idata` and export table `.edata` are only **0x200** bytes each; and the most
common function prologue `48 89 5C 24 08` has **0** hits in the file against **4104** hits in
`kernel32.dll`. Consequence: no offline signature scanning or disassembly of the disk file (always 0
hits). Verification happens **in-process** — the mod decodes and logs results to be compared against
known values — or by dumping the in-memory `game.dll` with a read-only probe. This is also why MDL
re-scans signatures on every launch: it has no offline-queryable copy at all. *Conflicts:* the
common belief that you can point a disassembler at the installed `game.dll` is false; offline scans
of it returned zero hits and produced unusable offsets.

**Do not edit the on-disk data tables either.** The `data/game/generated_*.dl_bin` files in the
install directory are encrypted: entropy **7.9998 bit/byte**, `LDLD` appears **0** times in the
45 MB file, and the file is usually only **48 bytes** larger than its plaintext mirror. They cannot
be decoded and are not part of the mod pipeline — all table work goes through the plaintext mirror.

---

## 2. FFI correctness in this VM

**Pointer arguments must go through `ffi.cast`.** Passing a bare Lua number where a pointer is
expected raises `cannot convert number to const void *`. Only real FFI enforces this, so an offline
test stub must be type-strict to catch it — a lenient double accepted numbers, let pointer bugs
through, and they surfaced in the game instead.

**A Lua string's own address needs a pointer-to-string cast**, wrapped in `pcall` because the cast
can fail:

```lua
tonumber(ffi.cast("uintptr_t", ffi.cast("const char *", pattern)))
```

This is what makes self-hit skipping possible — without it a scanner matches its own pattern data,
which lives in the Lua heap, and a scan "succeeds" while finding nothing but itself.

---

## 3. LuaJIT numeric and string semantics that bite

**Numbers carry only 53 bits; a 64-bit ID must never touch one.** Storing
`0x80F1A156D9FA1E36` in a Lua number yields `0x80F1A156D9FA2000`, which corrupts the search
pattern. Any ID above 2^53 is built from hex character pairs:

```lua
local function le_bytes_from_hex(hex)
  return (hex:gsub("%x%x", function(p) return string.char(tonumber(p, 16)) end)):reverse()
end
```

*Failure:* a corrupted 64-bit pattern silently never matches. *Conflicts:* this contradicts the
usual habit of writing 64-bit IDs as Lua hex literals or `tonumber('0x…')`.

**`table.concat` renders numbers as decimal text.** `table.concat({65,66})` returns `"6566"`, not
`"AB"`. A byte table mixing numbers and strings therefore produces bytes of the wrong length and,
on write, corrupts the neighbouring data. Build byte payloads by pure-string concatenation.
*Conflicts:* the common byte-table idiom of mixing numbers and strings in one table is unsafe here.

**Lua does not type-check fields; never reuse a field name with a different type.** Using `hits = {}`
and later `hits = 0` in the same table makes `hits + 1` throw
`attempt to perform arithmetic on field 'hits'`. In the observed case the first hit aborted the whole
scan round and the census was never flushed — a full recon run lost to one name collision between a
set and a counter.

---

## 4. When and how often to write

### 4.1 The window decides, not the speed

A table being in memory does not mean the list that consumes it has not already been built. Measured
with stratagem attachments: writing `additional_stratagem` after entering a mission can be too late
— the current mission's list is already fixed and the change appears only back on the ship or in the
next mission. Scan speed only determines *when the address is known*; what decides whether a change
takes effect is the window after the table loads and before the list is built. Speeding up the scan
is not a substitute for finding that window. *Conflicts:* the assumption that finding the address
earlier is what makes a write take effect is wrong.

### 4.2 The runtime-patch template (passed on-machine in one pass)

1. Locate the table by signature and verify a known constant such as `size`.
2. Find the target record by **unique ID**; require the match to be unique (more than one → refuse).
3. Verify an expected constant inside the record (e.g. `SpawnPayloadSize == 2`).
4. **Back up the original bytes to disk before writing.**
5. Detect whether the patch is already applied (idempotence) so it is not written twice.
6. On a read-only page use `VirtualProtect` temporarily and restore the original protection after.
7. **Read back and verify field by field** — not merely "the write succeeded".
8. Re-check every **~5 seconds** and re-apply if a map reload wiped it.
9. Use `_G.<ModName>` as a singleton guard, rate-limit error logs, and log and refuse the write
   whenever any validation does not match.

### 4.3 Write guards that lock themselves out

**A guard that whitelists only {current == target, current == original} bricks its own write.**
The observed symptom: the first write to a mount slot succeeds, changing it to another item is
refused, and a mech that was first a carrier and later an addition becomes unwritable entirely —
because after the first successful write `cur` is the previous target, which matches neither branch.
Store **both** the current target and the original per address, and treat the previously written
value as a legal source:

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

`state.slots[address]` keeps `item` (current target, for recognising the next switch) and `orig`
(original value, for restoring during initialisation).

**Writing the original value back must always bypass every check.** Added 2026-10-03 (guard dog):
if the original value is itself blocked by the `cur` test, a player migrating from an older mod is
permanently stuck. Concretely: `guard-dog-mg43` already wrote **MG-43**, the new mod's `orig` =
**A32621E3BDE13379**, `cur` = MG-43, `last` = nil → `cur` is neither the original nor `last` →
refuse, so even selecting the original becomes impossible. Hence the `want == orig` clause in the
snippet above: whenever the target value equals the original, skip the check entirely and write
directly. "Writing back the original" can never be worse than leaving an unknown value in place.
Non-original item swaps stay protected. This is the second safeguard besides `force`; both
`exo_loadout` and `guard_dog_loadout` implement it, and guard-dog offline case **13** pins it
(memory holds MG-43 and the cfg selects AR-23P → the original must be written back). *Conflicts:*
directly contradicts the widespread write-guard idiom that whitelists only
{current == target, current == original} — which is exactly the shape of the broken guard.

**Initialisation must restore original defaults, not the last cfg.** Reusing the normal write-back
path (`apply_all('vanilla')`) left the last-exit configuration in memory, because the current value
matched neither original nor target and the guard refused silently. Fix: a `vanilla_force` mode —
`apply_all('vanilla', true)` — that validates only `node` / `pad` / `recIdx` and force-writes the
original. Initialisation does **not** read `ExoLoadout.cfg`; the last-exit cfg is the wrong
semantics. Consolidate it:

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

**The default additional body is `none`.** `CFG = { carry = 'patriot', extra = 'none', arms = {} }`.
A newly generated cfg uses `extra=none`, `reset_cfg()` returns to `extra=none`, the additional
`choice` defaults to none, and self-check must accept `extra='none'`. Any other default makes a
fresh install start already modified.

### 4.4 Additional-stratagem writes: one direction only

For carrying mech A plus additional mech B:

| record | field | action |
|---|---|---|
| A | `package+32` `additional_stratagem` | write B's stratagem ID |
| A | `package-88` `use` | write `2` |
| B | `package+32` `additional_stratagem` | do not touch |
| B | `package-88` `use` | write `2` |
| A/B | `package-64` / `package-60` cooldown | do not touch |

Write only the carrying record's single `additional_stratagem`; writing both ways creates a
stratagem nesting loop. Before writing, verify the current `+32` is `0` or already the target —
otherwise refuse.

### 4.5 Release discipline

Do read-only recon first; validate a value's range before writing and read it back after; refuse and
log on mismatch; verify the game version (`exe`/`dll` SHA-256) and refuse to write on mismatch. Warn
the user proactively that changing game behaviour while online can make the client differ from
teammates and carries anti-cheat risk, and state clearly that these are client-local changes most
other players will not see. All changes live in memory only, so disabling the mod plus Purge fully
restores the game.

---

## 5. Reading and interpreting a data table at runtime

### 5.1 Block format and identification

An LDLD block header is `LDLD` + u32 version (= **1**) + u32 type hash + u32 size. This is the
signature that both offline parsing and in-memory censusing key on.

**The instance-data start depends on the file family.** For `generated_*_settings.dl_bin` data
starts at magic **+40**; for `generated_entities.dl_bin` at magic **+24**. Never guess — validate
with content: a decoded record should have plausible fields (count ≤ **8**, speed in **1~5000**, an
item hash resolvable in the resource-name list). A single hardcoded data start decodes one family of
tables wrongly.

**The type hash is djb2 with 5381 subtracted at the end** — this is what you compare against the
block header for a type name: `r = 5381`; for each character `r = (r * 33 + ord(c)) & 0xFFFFFFFF`;
return `(r - 5381) & 0xFFFFFFFF`. Worked example: `"HellpodRackComponentData"` → `0xA98BB156`.
Every name in `typelib_names.tsv` maps to its LDLD signature this way.

**Resource-name hashes are a different function:** `MurmurHash64A(name, seed=0)`. The two hashes
look similar and are unrelated; using the type hash where a resource-name hash is required (or vice
versa) produces a stream of "not found" with no other symptom.

**Trust typelib-generated field data over hand-written structs.** The files generated from the
typelib (the ones carrying field comments) are trustworthy for the current build; hand-written
community Go structs may no longer match. When unsure, read `typelib_all.json` or read
`dl_library.dl_typelib` directly. *Conflicts:* contradicts the common practice of treating community
struct definitions as ground truth — a stale struct sent a decode down the wrong path.

### 5.2 Not every table is an LDLD block

`StratagemSettings` is **not** an LDLD block: it is a 16-byte container whose member is an ARRAY,
and the real record is `StratagemInfo`, `size = 400`, with offsets `+0` type, `+4` id, `+80` uses,
`+104` / `+108` cooldown float (success / fail), `+152` / `+160` payload[2], `+168` package,
`+176` icon, `+196` depends_on, `+200` additional_stratagem, `+204` max_in_loadout. Get the record
type and field offsets from the typelib first, then choose a lookup strategy; LDLD applies to only
some tables. *Failure:* assuming every data table is an LDLD block made the stratagem tables
unfindable.

**Writing around the `package` field.** With `c` = the address of a record's `package` field (the
source writes these as `package±N` without defining the frame; this is the sibling notes'
definition): `c+32` = `additional_stratagem`, `c-88` = `use`, `c-64` = `cooldown_duration_success`,
`c-60` = `cooldown_duration_fail`. The same fields also exist at record level: `+200`
`additional_stratagem` and `+104`/`+108` cooldowns on the 400 B `StratagemInfo` record. The write
targets live around the package pointer, not at fixed record offsets.

**Test whether records form a contiguous array before using a formula.** With contiguous records,
stride `S`, and the `package` field at `+P`: `base = addr(pkg) - P - (id-1)*S`. If several known
records yield the same base and their icons all match, it is a contiguous array; otherwise do not
force `base + (ID-1)*S`. Measured: all **7** `StratagemInfo` packages were located but no common base
existed — the records are not an ID-sorted contiguous 400 B array (more like pointers / scattered
allocation), so fall back to locating each record by its package content.

**By-ID record lookup via the `StratagemCooldown 2.1.5` AOB path.** That path reads records of
`0xB0` bytes: `+0x00` id, `+0x04` hash, `+0x10` name string pointer, `+0x50` uses (int32, `-1` =
infinite), `+0x68` cooldown (float), `+0xC8` the field the AOB itself accesses, corresponding to
`additional_stratagem`. Note this is a by-ID shortcut, not a contract — an in-memory table read
through a signature is only as good as the build it was found on, and any implementation needs the
fallback path (by content) when the layout stops matching.

**Unlocking a stratagem by ID takes three conditions, all of which must hold** (v1.7 verified
on-machine): ① `StratagemInfo +0xC0` bit0; ② `+0x80` bit1 (= `selectable` in the plaintext data
table); ③ registry record `+0x14 ∈ {2,4}`. The earlier conclusion that `+0x14` is not the owned bit
has been overturned. The stratagem pointer table is `*(0x37CB600 + id*8)`. The write must include
the `selectable` bit as well. *Failure:* two-condition writes left stratagems locked; the third
condition was found by testing all three together.

### 5.3 Rack and supply records

`HellpodRackComponent` is **568 B** = `RackAttach[8]` (**64 B** per slot) plus a tail;
`spawn_payload_size` sits at `+0x22C`. The AC-8 case locates `HellpodRackComponentData` by LDLD +
type hash + in-record relative offsets (the "content anchor" method). Rack edits need the exact
per-slot stride and the tail field position.

A supply rack's **4** filled slots determine the cooldown (**30~150 s**). A complete change writes to
three places: the rack slot's `item` / `offset` / `rotation_offset`, the stratagem's
`cooldown_success` at `+0x68`, and the three conditions of stratagem ID **77**. *Failure:* writing
only one of the three leaves the in-game cooldown inconsistent with the rack.

### 5.4 Verifying a decoder in-process

When no offline-verifiable machine code exists (see §1), the only ground truth is another
implementation that already works on this machine: copy the numbers a known-good mod decoded from
its logs, log the same dozen numbers on your first successful run, and compare item by item. All
equal means the decoder is correct; one difference pinpoints the specific wrong `disp32`.

Known-good baseline decoded by **MDL 1.4.2** on this machine (**2026-09-24 build**):
`native menu state: MenuSystem +0x347ce38, open byte +2185, 36 screen types`;
`native tab: bar +1248, count +57448, labels +57320, text +8296, set_labels +0x17aac50,
set_arg +0x143c950, labels 0xd876b36e 0x78934e12 0x8c02bd80`;
`native font slots: font +0x3772268 atlas +0x3772ee8 material +0x37c5478`.

These numbers are tied to that one build — treat them as a comparison baseline, **not** as portable
offsets, and re-derive them after a game update.
