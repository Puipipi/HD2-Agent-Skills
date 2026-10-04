"""Turn Helldivers 2 crash-reporting settings on or off, safely.

A settings.ini edit is easy to get wrong in three ways this tool guards against:
editing while the game is running (the game rewrites the file on exit, silently
discarding the change), editing without a backup, and believing a change landed
without re-reading the file.

Usage:
  python hd2_settings.py --show
  python hd2_settings.py --game "D:\\...\\Helldivers 2" --show
  python hd2_settings.py --off                      # disable the reporting keys
  python hd2_settings.py --off --keys crs_enabled,crash_dump,capture_image
  python hd2_settings.py --restore <backup-file>
  python hd2_settings.py --off --dry-run

Exit codes: 0 done, 1 refused (game running / key missing), 2 usage error.
"""
from __future__ import annotations

import argparse
import datetime
import os
import re
import shutil
import subprocess
import sys

# Keys that only control reporting. Turning these off removes diagnostics and
# changes nothing about how the game executes.
REPORTING_KEYS = ("crs_enabled", "crash_dump", "capture_image")

# Kept separate on purpose: this one changes engine behaviour, not reporting.
# With it on, a floating-point fault stops the process where it happened; with it
# off the fault is not raised at all, so the same bad value propagates. That can
# turn a loud crash into a silent wrong value or a later, unrelated crash. See the
# skill for why it is not in the default set.
ENGINE_KEYS = ("floating_point_exceptions",)

ALL_KEYS = REPORTING_KEYS + ENGINE_KEYS

HINTS = [
    r"D:\Program Files (x86)\Steam\steamapps\common\Helldivers 2",
    r"C:\Program Files (x86)\Steam\steamapps\common\Helldivers 2",
    r"D:\SteamLibrary\steamapps\common\Helldivers 2",
    r"C:\SteamLibrary\steamapps\common\Helldivers 2",
]


def find_game(explicit=None):
    if explicit:
        return explicit
    for h in HINTS:
        if os.path.isfile(os.path.join(h, "data", "settings.ini")):
            return h
    return None


def settings_path(game):
    return os.path.join(game, "data", "settings.ini")


def game_running():
    """Return the running PIDs, if any, across the likely process names."""
    for name in ("helldivers2.exe", "helldivers2"):
        try:
            r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq " + name],
                               capture_output=True, text=True, timeout=20)
            if name.lower() in (r.stdout or "").lower():
                return True
        except Exception:
            pass
    return False


def read_lines(path):
    """Read as bytes and split on the file's own convention.

    Text mode is a trap here: it converts CRLF to LF on read, and writing back
    with newline="" leaves every line LF-terminated, so a four-key edit silently
    rewrites all 190 line endings of the file. Bytes in, bytes out, so the only
    difference on disk is the lines that were actually edited.
    """
    data = open(path, "rb").read()
    sep = b"\r\n" if b"\r\n" in data else b"\n"
    return data.split(sep), sep


def write_lines(path, lines, sep):
    with open(path, "wb") as f:
        f.write(sep.join(lines))


def scan(lines):
    """Map key -> (line index, current value, indent).

    Lines are bytes (they came from a byte read), so decode each one before
    matching. Later occurrences win, which matches how the engine reads the file.
    """
    found = {}
    for i, raw in enumerate(lines):
        line = raw.decode("utf-8", "surrogateescape")
        stripped = line.strip()
        if "=" not in stripped or stripped.startswith(("#", ";")):
            continue
        name, _, value = stripped.partition("=")
        name = name.strip()
        if name in ALL_KEYS:
            indent = line[: len(line) - len(line.lstrip())]
            found[name] = (i, value.strip(), indent)
    return found


def show(path):
    lines, _sep = read_lines(path)
    found = scan(lines)
    print("settings.ini: %s" % path)
    print()
    print("  %-30s %-6s %s" % ("key", "value", "status"))
    for key in ALL_KEYS:
        if key in found:
            i, val, _ = found[key]
            tag = "reporting" if key in REPORTING_KEYS else "ENGINE BEHAVIOUR"
            print("  %-30s %-6s line %-4d %s" % (key, val, i + 1, tag))
        else:
            print("  %-30s %-6s %s" % (key, "-", "ABSENT from this file"))
    return found


def apply_keys(path, keys, value, dry_run=False):
    lines, sep = read_lines(path)
    found = scan(lines)
    missing = [k for k in keys if k not in found]
    if missing:
        print("REFUSING: these keys are not in the file: %s" % ", ".join(missing))
        print("  A settings.ini without them means a different game build or a")
        print("  different file; adding keys by guesswork is not safe.")
        return 1

    changes = []
    for key in keys:
        i, current, indent = found[key]
        if current == value:
            print("  %-30s already %s" % (key, value))
            continue
        lines[i] = ("%s%s = %s" % (indent, key, value)).encode()
        changes.append((i, key, current, value))
        print("  %-30s %s -> %s   (line %d)" % (key, current, value, i + 1))

    if not changes:
        print("\nnothing to do; the file already has these values.")
        return 0

    if dry_run:
        print("\ndry run: %d line(s) would change, file untouched." % len(changes))
        return 0

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = "%s.backup-%s" % (path, stamp)
    shutil.copy2(path, backup)
    print("\nbackup written: %s" % backup)

    write_lines(path, lines, sep)

    # verify by re-reading, never by trusting the write
    after = scan(read_lines(path)[0])
    ok = all(after.get(k, (None, None, None))[1] == value for k in keys)
    for key in keys:
        i, val, _ = after[key]
        print("  verify %-30s now %s" % (key, val))
    if not ok:
        print("\nVERIFY FAILED - restoring the backup")
        shutil.copy2(backup, path)
        return 1
    print("\nOK. Restart the game for the change to take effect.")
    print("Restore with: python %s --restore \"%s\"" % (os.path.basename(__file__), backup))
    return 0


def restore(path, backup):
    if not os.path.isfile(backup):
        print("no such backup: %s" % backup)
        return 2
    shutil.copy2(backup, path)
    print("restored %s from %s" % (path, backup))
    show(path)
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--game", help="game install directory (auto-detected if omitted)")
    ap.add_argument("--show", action="store_true", help="print the current values")
    ap.add_argument("--off", action="store_true", help="set the selected keys to false")
    ap.add_argument("--on", action="store_true", help="set the selected keys to true")
    ap.add_argument("--keys", default=",".join(ALL_KEYS),
                    help="comma-separated keys (default: all of %s)" % ",".join(ALL_KEYS))
    ap.add_argument("--dry-run", action="store_true", help="show what would change")
    ap.add_argument("--restore", metavar="BACKUP", help="restore settings.ini from a backup")
    ap.add_argument("--force", action="store_true",
                    help="edit even if the game appears to be running (the game will overwrite it)")
    args = ap.parse_args()

    game = find_game(args.game)
    if not game:
        print("could not find the game. Pass --game <install dir>.")
        print("hint: Steam -> right-click the game -> Manage -> Browse local files")
        return 2
    path = settings_path(game)

    if args.restore:
        return restore(path, args.restore)

    keys = [k.strip() for k in args.keys.split(",") if k.strip()]
    unknown = [k for k in keys if k not in ALL_KEYS]
    if unknown:
        print("unknown key(s): %s" % ", ".join(unknown))
        print("known keys: %s" % ", ".join(ALL_KEYS))
        return 2

    if not (args.show or args.off or args.on):
        args.show = True

    if args.show:
        show(path)

    if args.off or args.on:
        if not args.force and game_running():
            print("\nREFUSING to edit: the game appears to be running.")
            print("  It rewrites settings.ini when it exits, so the change would vanish.")
            print("  Close the game first, or pass --force if you know better.")
            return 1
        print()
        return apply_keys(path, keys, "false" if args.off else "true", args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
