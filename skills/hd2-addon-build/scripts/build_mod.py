# -*- coding: utf-8 -*-
"""Build one HD2 Lua mod release zip, with the gates that prevent a bad release.

Adapt the CONFIG block and run it. Every gate below is a real release failure,
not a style preference:

  * the source must compile under **LuaJIT**, not just Lua 5.1. This game runs
    LuaJIT, whose 65535-instruction-per-function cap makes the loader SILENTLY
    SKIP an oversized mod while a plain-Lua compile says "OK".
  * the source must declare **no user32 symbol**. LuaJIT's C namespace is
    process-global and `ffi.cdef` keeps the FIRST declaration, so declaring
    `GetCursorPos` with a different prototype disables every other mod that
    declared it first (this shipped once, and one mod disabled itself for a
    whole session).
  * the shipped README.txt is extracted from the source, so the in-game guide
    cannot drift from the code.
  * no loose .bat inside the upload archive (mod sites quarantine script files).

Usage:
    python build_mod.py --validate-only        # gates only, no packaging
    python build_mod.py                        # build the release zip
    python build_mod.py --with-source          # also a source bundle, for review

Requires: python3 + lupa  (`python -m pip install lupa`)
"""
import argparse
import io
import json
import os
import re
import sys
import zipfile
from pathlib import Path

import lupa.luajit21 as luajit

# ----------------------------------------------------------------- CONFIG ----
W = str(Path(__file__).resolve().parent)

MOD_SOURCE = os.path.join(W, "mymod.lua")        # your plaintext Lua entry
RESOURCE = "mods/yourauthor/mymod"               # mods/<author>/<entry>, underscore only
GUID = "00000000-0000-4000-8000-000000000000"    # YOUR uuid; REUSE it across releases
DISPLAY_NAME = "My Mod"
ICON = os.path.join(W, "icon.webp")              # optional; set to None to skip
README_MARKER = "[===[My Mod - quick guide"      # where the in-game README starts
VENDOR = os.path.join(W, "vendor", "bingus")     # holds build_addon.py + archive.py
OUTPUT_DIR = None                                # None = ./dist next to this script

# Symbols that must never appear in an ffi.cdef block in this source.
USER32 = {"GetCursorPos", "GetClientRect", "ScreenToClient", "GetForegroundWindow",
          "GetAsyncKeyState", "GetWindowThreadProcessId", "GetCurrentProcessId"}
# ------------------------------------------------------------------------------

default_out = Path(OUTPUT_DIR) if OUTPUT_DIR else Path(W) / "dist"
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--output-dir", type=Path, default=default_out)
parser.add_argument("--validate-only", action="store_true",
                    help="run the gates without packaging")
parser.add_argument("--with-source", action="store_true",
                    help="also assemble a source bundle (review handoff only)")
args = parser.parse_args()
OUT = str(args.output_dir.resolve())
Path(OUT).mkdir(parents=True, exist_ok=True)

src = io.open(MOD_SOURCE, encoding="utf-8").read()
ver = re.search(r"version\s*=\s*['\"]([\d.]+)['\"]", src).group(1)

# --- gate 1: compiles under LuaJIT (65535 instructions per function) ---------
try:
    luajit.LuaRuntime().compile(src)
except Exception as exc:
    raise SystemExit("FAIL LuaJIT compile: %s" % exc)
print("LuaJIT compile: OK (%d bytes)" % len(src))

# --- gate 2: no user32 symbol declared --------------------------------------
declared = set()
for block in re.findall(r"ffi\.cdef\s*\[\[(.*?)\]\]", src, re.S):
    declared.update(m.group(1) for m in
                    re.finditer(r"([A-Za-z_]\w*)\s*\([^;()]*\)\s*;", block))
# pcall(ffi.cdef, 'int Foo(void);') style
for chunk in re.findall(r"ffi\.cdef\s*,\s*'([^']*)'", src):
    declared.update(m.group(1) for m in
                    re.finditer(r"([A-Za-z_]\w*)\s*\([^;()]*\)\s*;", chunk))
clash = declared & USER32
if clash:
    raise SystemExit("FAIL refusing to build: user32 symbol(s) declared: %s"
                     % ", ".join(sorted(clash)))
print("ffi.cdef symbols: %s (no user32)"
      % (", ".join(sorted(declared)) or "none"))

# --- gate 3: every C symbol you CALL must be declared -----------------------
called = {m.group(1) for m in re.finditer(r"\b(?:k|u|kernel32|user32|bcrypt|ffi\.C)\.([A-Za-z_]\w*)\s*\(", src)}
missing = sorted(called - declared - {"GetModuleHandleA", "GetProcAddress"})
if missing:
    raise SystemExit("FAIL called but not declared (hard error at the call site): %s"
                     % ", ".join(missing))
print("called symbols all declared")

# --- gate 4: the in-game README block exists --------------------------------
r0 = src.find(README_MARKER)
r1 = src.find("]===]", r0) if r0 > 0 else -1
readme_txt = src[r0 + 5:r1] if r0 > 0 and r1 > 0 else ""
if not readme_txt:
    raise SystemExit("FAIL README block missing from the source: expected %r ... ]===]"
                     % README_MARKER)
print("README block: %d chars (extracted from the source)" % len(readme_txt))

if args.validate_only:
    print("Source validation complete; no in-game claim.")
    raise SystemExit(0)

# --- packaging: the official addon envelope ---------------------------------
# Only advertise an icon when the file is actually there: a manifest that points
# at a missing IconPath makes the manager show a blank entry.
have_icon = bool(ICON) and os.path.exists(ICON)
if ICON and not have_icon:
    print("note: ICON is set but %s does not exist - packaging without an icon" % ICON)

sys.path.insert(0, VENDOR)
import build_addon as official                                  # noqa: E402

target = os.path.join(OUT, "%s-%s.zip" % (DISPLAY_NAME.replace(" ", "-"), ver))
official.build_addon(RESOURCE, src.encode("utf-8"), GUID, target, DISPLAY_NAME)

tmp = target + ".tmp"
with zipfile.ZipFile(target) as zin:
    # --- gate 5: no script-like file inside the published archive ------------
    # Mod sites quarantine archives that contain scripts, and a quarantined
    # release reads as a mysterious rejection. Ship helpers by generating them at
    # runtime instead (see the hd2-no-quarantine-packaging skill). Checked on the
    # finished archive, before anything is written, so a later change cannot
    # quietly add one back and a refusal leaves no half-written file behind.
    SCRIPT_EXT = (".bat", ".cmd", ".ps1", ".vbs", ".js", ".exe", ".dll")
    offenders = [i.filename for i in zin.infolist() if i.filename.lower().endswith(SCRIPT_EXT)]
    if offenders:
        os.remove(target)
        raise SystemExit(
            "FAIL refusing to publish: script-like file(s) in the archive: %s\n"
            "     Mod sites quarantine these. Generate the helper at runtime into the\n"
            "     user's config folder instead, and say so in the in-game README."
            % ", ".join(offenders))
    print("archive contents: no script-like files")

    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for info in zin.infolist():
            data = zin.read(info.filename)
            if info.filename == "manifest.json" and have_icon:
                m = json.loads(data)
                m["IconPath"] = os.path.basename(ICON)
                for opt in m.get("Options", []):
                    opt.setdefault("Image", os.path.basename(ICON))
                data = (json.dumps(m, indent=2) + "\n").encode()
            zout.writestr(info, data)
        if have_icon:
            zout.write(ICON, os.path.basename(ICON))
        zout.writestr("README.txt", readme_txt.replace("\n", "\r\n"))
os.replace(tmp, target)
print("built %s: %d bytes" % (os.path.basename(target), os.path.getsize(target)))

if not args.with_source:
    print("source bundle skipped (pass --with-source only for a review handoff)")
    print("version: %s" % ver)
    raise SystemExit(0)

src_zip = os.path.join(OUT, "%s-source-%s.zip" % (DISPLAY_NAME.replace(" ", "-"), ver))
with zipfile.ZipFile(src_zip, "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr("source/" + os.path.basename(MOD_SOURCE), src.encode("utf-8"))
    z.writestr("source/build_mod.py",
               io.open(os.path.abspath(__file__), encoding="utf-8").read().encode("utf-8"))
print("built %s: %d bytes" % (os.path.basename(src_zip), os.path.getsize(src_zip)))
print("version: %s" % ver)
