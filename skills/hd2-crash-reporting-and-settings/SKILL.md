---
name: hd2-crash-reporting-and-settings
description: Turn Helldivers 2's crash reporter, dump writer and screenshot capture on or off by editing data/settings.ini, and clear the crash folders it leaves in AppData. Use when the crash-feedback popup is interrupting play, when you want crash dumps for a mod you are debugging, or when you need to know which of these keys change engine behaviour rather than just reporting.
---

# HD2 crash reporting and the settings.ini keys that control it

English / [简体中文](https://github.com/Puipipi/HD2-Agent-Skills/blob/main/skills/hd2-crash-reporting-and-settings/SKILL_cn.md)

Two things live here: the four keys people reach for when they want the crash popup gone, and the
reason one of those four is not like the others.

**The short answer:** set `crs_enabled`, `crash_dump` and `capture_image` to `false`, leave
`floating_point_exceptions` at `true`, then delete `%APPDATA%\Arrowhead\Helldivers2\crash_data\` and
`...\dumps\`. That is what the script does by default:

```powershell
python -B scripts/hd2_settings.py --off
```

Expect the keys to be put back by something eventually — see failure 4 — so re-run it after mod work.

## Provenance and confidence

The key names, values, line numbers and paths below were **read off a real install**
(build 25480438, `helldivers2.exe` 1.8.46015.0) — see the transcript at the bottom.

**Not verified:** that disabling these actually suppresses the popup. Confirming that requires a
real crash, and no crash was induced. Treat "the popup stops appearing" as the expected effect,
not as something measured here.

## The file

```
<game>\data\settings.ini          # e.g. D:\...\steamapps\common\Helldivers 2\data\settings.ini
```

Steam → right-click the game → Manage → Browse local files.

The engine is Autodesk Stingray, and this is its config format: `key = value`, grouped into
nested `block { ... }` sections. **The grouping matters** — see the trap below.

## The four keys

Measured values on the install inspected, and where each one sits:

| Key | Was | Nesting | What it controls |
|---|---|---|---|
| `crs_enabled` | `true` | direct child of `win32` | the crash reporting system as a whole |
| `crash_dump` | `true` | direct child of `win32` | writing a `.dmp` file on a crash |
| `capture_image` | `true` | inside the nested **`crs`** block | screenshot capture at crash time |
| `floating_point_exceptions` | `true` | direct child of `win32` | **not reporting** — see below |

The trap: `crs_enabled` and `crs { ... }` are **different things at different levels**. One is a
boolean on `win32`; the other is a block. Inside that block are the keys that matter for dumps:

```ini
win32 = {
	crs_enabled = true                     # line 74
	floating_point_exceptions = true       # line 75
	crash_dump = true                      # line 82
	crs = {                                # <- a BLOCK, not the flag above
		data_path = "%APPDATA%/Arrowhead/Helldivers2/crash_data"
		capture_image = true               # line 89
		kill_timeout_seconds = -1
		capture_video = false              # already off
	}
	panic_folder_path = "%APPDATA%/Arrowhead/Helldivers2/panic/"
}
crash_dump_path = "%APPDATA%/Arrowhead/Helldivers2/dumps/dump-%DATE%-%TIME%-%SESSION%-%HOSTNAME%.dmp"
```

Hand-editing guidance that says "set `crs_enabled` to false" without saying **which** `crs` is
easy to apply to the wrong one. Both are real; they do different jobs.

Also present and worth knowing, though not usually changed:

- `capture_video` — already `false` by default. Turning it on makes crashes much more expensive.
- `local_console_log` — where the console log goes, the file a mod developer actually reads.
- `panic_folder_path`, `data_path`, `crash_dump_path` — where each kind of output lands.

## `floating_point_exceptions` is not a reporting switch

The other three only decide whether diagnostics get *recorded*. This one decides whether an
arithmetic fault **stops the process at the point of failure**.

- **`true`** — a floating-point fault raises, you crash right there, and you get a stack that
  points at the cause.
- **`false`** — the fault is not raised. The bad value flows onward. The visible result moves:
  a crash becomes a wrong number, a corrupted state, or a fault somewhere unrelated later.

So turning it off can make a bug *harder* to find, not just quieter. If you are debugging a mod,
leave it on. If you are only trying to stop a popup interrupting your play, be aware that you are
also removing a correctness check, not merely a notification.

**Value:** keeps a loud, attributable failure from becoming a silent, misattributed one.

## Doing it safely

Use the script rather than an editor, because three failure modes here are silent:

```powershell
python -B scripts/hd2_settings.py --show        # current values, with line numbers
python -B scripts/hd2_settings.py --off --dry-run
python -B scripts/hd2_settings.py --off                  # the three reporting keys
python -B scripts/hd2_settings.py --off --keys crs_enabled,crash_dump,capture_image,floating_point_exceptions
python -B scripts/hd2_settings.py --on --keys floating_point_exceptions   # put the engine check back
python -B scripts/hd2_settings.py --restore <backup-file>
```

It refuses to edit while the game is running, writes a timestamped backup, and re-reads the file
to confirm the change instead of trusting the write.

### The four silent failure modes

1. **Editing while the game is running.** The game rewrites `settings.ini` when it exits, so your
   change disappears with no error. Close the game first. The script checks the process list and
   refuses unless you pass `--force`.
2. **Editing the wrong `crs`.** See the nesting trap above.
3. **Rewriting the line endings.** This one bit the tool's first version: the file uses **CRLF**,
   and a text-mode read-modify-write turns all 190 line endings into LF. The result is 186 bytes
   shorter, the four keys *do* change, and every diff tool reports the whole file as rewritten.
   The tool now reads and writes bytes so the only difference on disk is the lines it edited.
4. **Something puts the keys back.** This is the one that wastes the most time, because a plain
   re-read looks perfect and the popups keep coming anyway.

### Failure 4 in detail: the values revert, and re-reading cannot tell you

Measured on one install: the four keys were set false, and **seven days and several game sessions
later only `capture_image` was still false** — `crs_enabled` and `crash_dump` had returned to
`true`. Meanwhile crash dumps kept appearing, which looks exactly like "the switch does not work".

Two plausible causes, and you cannot tell them apart from the current file:

- the game rewrites those keys on exit, or
- **another tool restored the file.** This is the more likely one in practice: any mod-maintenance
  script that snapshots or "cleans up" the install can put a stock `settings.ini` back, and so can
  restoring a backup taken before the change.

**A re-read proves nothing here**, because the file you are re-reading is the one that was restored.
What distinguishes them is a comparison against a **pristine original**:

```powershell
# keep one untouched copy of settings.ini from before any edit, then diff later
python -c "import difflib,io; a=io.open(r'<pristine>').read().split('\n'); b=io.open(r'<game>\data\settings.ini').read().split('\n'); print('\n'.join(l for l in difflib.unified_diff(a,b,lineterm='') if l[:1] in '+-' and l[:3] not in ('---','+++')))"
```

If most of your keys are missing from that diff, they were reverted — by the game or by a tool —
and the fix is to re-apply, not to keep re-reading the file.

**If you do mod work on this install, expect this.** Re-run `--off` after any session where a tool
touched the install, and treat "dumps are still appearing" as evidence to check the keys, not as
evidence the keys do not work.

### How much the switch is actually worth

Counted on one install across three months of dumps:

| | dumps written |
|---|---|
| before the switch (2026-06-10 → 10-04) | **210** |
| after the switch (2026-10-04 → 10-11) | **4** |

So the keys are effective but **not absolute**: an occasional crash still writes a dump. Do not
promise "no more dump files" — promise "far fewer". If the goal is a clean folder, deleting
`crash_data\` and `dumps\` is what actually empties it, and the game recreates them when needed.

### Keep `floating_point_exceptions` on

It is deliberately **not** in the default set the tool turns off. Disabling reporting is about
diagnostics; disabling this changes execution. Recommended state:

```
crs_enabled                = false     reporting off
crash_dump                 = false     no dump files
capture_image              = false     no crash screenshot
floating_point_exceptions  = true      keep faults loud and attributable
```

### Prove the edit instead of believing it

A four-key change to a 191-line file should change **exactly 4 lines and add exactly 4 bytes**
(`true` → `false`). If the file shrank, the line endings were rewritten. If more lines differ,
something read the values as text and reflowed them.

```powershell
# byte delta must be +4, CRLF count must be unchanged
python -c "a=open(r'<backup>','rb').read(); b=open(r'<game>\data\settings.ini','rb').read();
print(len(b)-len(a), a.count(b'\r\n'), b.count(b'\r\n'))"
```

## Clearing what it already generated

The folders below are output, not configuration. Deleting them is safe; the game recreates them.

```
%APPDATA%\Arrowhead\Helldivers2\
    crash_data\        <- crs data_path
    dumps\             <- crash_dump_path    (.dmp files)
    panic\             <- panic_folder_path
    shader_cache\      <- unrelated, do not delete casually
    saves\             <- YOUR SAVE DATA, never delete
    user_settings.config, logs\
```

Deleting `crash_data` and `dumps` is the usual cleanup. **`saves\` is your progress — do not
touch it**, and do not let a "clear the crash folders" instruction talk you into clearing the
whole `Helldivers2` directory. `%APPDATA%` is hidden; in Explorer enable View → Show → Hidden
items.

## Interaction with mods

- **`local_console_log`** is where `print`-style output from a mod ends up. If a mod appears to log
  nothing, check this path and that the directory exists before suspecting the mod.
- **Disabling crash reporting removes the evidence you need when a mod crashes the game.** Keep a
  copy of the setting you changed, and turn reporting back on before filing a mod bug — a report
  that says "it crashed" with dumps disabled is not actionable.
- **`floating_point_exceptions = false` can make a mod bug look like a game bug.** A fault inside
  a mod that would have crashed immediately instead corrupts state and surfaces later, somewhere
  that gets blamed on the game or on another mod. If a bug is intermittent and hard to localise,
  putting this back to `true` is a cheap first experiment.

## What this does not do

- It does not stop the game from crashing. It stops it from *telling you*.
- It does not touch integrity checks. HD2 runs nProtect GameGuard; this edits a plain config file
  the game itself rewrites, which is a different thing from patching the process, but treat
  third-party tooling risk as yours.
- It does not affect the in-game settings UI. Some keys here are also surfaced in the game's own
  options; the game may write its own values back on exit and undo a manual edit.

## Transcript

Read from the install inspected (build 25480438):

```
win32 = {
	crs_enabled = true                     L74
	floating_point_exceptions = true       L75
	...
	crash_dump = true                      L82
	crs = {
		data_path = "%APPDATA%/Arrowhead/Helldivers2/crash_data"
		capture_image = true               L89
		capture_video = false              L91
	}
	panic_folder_path = "%APPDATA%/Arrowhead/Helldivers2/panic/"   L99
}
crash_dump_path = ".../dumps/dump-%DATE%-%TIME%-%SESSION%-%HOSTNAME%.dmp"   L140
```

After `--off`, verified byte-exactly: 5351 → 5355 bytes (**+4**), 190 → 190 CRLF, and exactly four
differing lines (74, 75, 82, 89). A first attempt rewrote all 190 line endings and was reverted
from the backup, which is how the CRLF trap above was found.
