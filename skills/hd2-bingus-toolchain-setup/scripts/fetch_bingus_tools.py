"""Fetch the Bingus addon packaging tools into a mod's vendor/bingus/ folder.

WHY THIS IS A TOOL AND NOT A BUNDLED FILE
    `build_addon.py` and `archive.py` encode the loader's addon envelope. They are
    third-party files: obtain them from the loader author with the appropriate
    permission, or copy them from an installation you already have. This script
    does the second thing — it never downloads and never redistributes them, and
    the repo it lives in deliberately does not contain them.

WHERE IT LOOKS (first match wins)
    1. --from <path>                     an explicit file or folder
    2. every installed mod folder         %LOCALAPPDATA%\\hd2arsenal\\mods\\*\\scripts\\
       (the loader and some mods ship these as `scripts/build_addon.py`)
    3. --url <base>                       opt-in only, never automatic

Usage
    python -B fetch_bingus_tools.py --dest work/standalone/vendor/bingus
    python -B fetch_bingus_tools.py --from "D:\\src\\bingus" --dest work/standalone/vendor/bingus
    python -B fetch_bingus_tools.py --list          # show what was found, copy nothing
    python -B fetch_bingus_tools.py --url https://example.invalid/bingus --dest ...

Exit codes: 0 copied (or listed), 1 nothing found, 2 refused (destination exists).
"""
import argparse
import os
import shutil
import sys
import urllib.request

NEEDED = ("build_addon.py", "archive.py")
# archive.py may resolve an optional external LuaJIT / boot blob; those are the
# loader author's build inputs, not yours, and are not required just to package.
OPTIONAL = ("luajit.exe",)


def candidate_dirs(explicit):
    """Every place worth looking, most specific first.

    Mod repos nest these at different depths (`vendor/bingus`,
    `work/standalone/vendor/bingus`, `scripts/`), so walk each mod folder a few
    levels deep instead of guessing one layout and missing the file.
    """
    seen, out = set(), []

    def add(path):
        if not path:
            return
        path = os.path.abspath(path)
        if path not in seen and os.path.isdir(path):
            seen.add(path)
            out.append(path)

    def walk_roots(root, max_depth=3):
        root = os.path.abspath(root)
        if not os.path.isdir(root):
            return
        base_depth = root.rstrip(os.sep).count(os.sep)
        for dirpath, dirnames, _ in os.walk(root):
            depth = dirpath.rstrip(os.sep).count(os.sep) - base_depth
            if depth >= max_depth:
                dirnames[:] = []          # stop descending, do not skip this dir
                continue
            add(dirpath)

    add(explicit)

    local = os.environ.get("LOCALAPPDATA")
    if local:
        mods = os.path.join(local, "hd2arsenal", "mods")
        if os.path.isdir(mods):
            for entry in sorted(os.listdir(mods)):
                base = os.path.join(mods, entry)
                if os.path.isdir(base):
                    walk_roots(base, max_depth=3)

    # the script's own neighbourhood. Walk far enough to reach a workspace root:
    # from skills/<name>/scripts/ up to <workspace> is SIX levels, and a shorter
    # walk silently never visits <workspace>/mods/.
    here = os.path.dirname(os.path.abspath(__file__))
    ancestors, cur = [], here
    for _ in range(8):
        cur = os.path.dirname(cur)
        if not cur or cur == os.path.dirname(cur):
            break
        ancestors.append(cur)
    for up in [here] + ancestors:
        walk_roots(up, max_depth=3)
        # a workspace: every sibling mod repo, and the shared test/tool folders.
        # depth 6 because the tools sit at
        #   mods/<mod>/work/standalone/vendor/bingus/  (depth 5)
        mods = os.path.join(up, "mods")
        if os.path.isdir(mods):
            for entry in sorted(os.listdir(mods)):
                base = os.path.join(mods, entry)
                if os.path.isdir(base):
                    walk_roots(base, max_depth=6)
        for extra in ("work", "tools", "scripts", "outputs"):
            walk_roots(os.path.join(up, extra), max_depth=3)
    return out


def scan(dirs):
    """Return {dirname: {filename: full path}} for dirs holding any needed file."""
    found = {}
    for d in dirs:
        try:
            names = set(os.listdir(d))
        except OSError:
            continue
        hit = {n: os.path.join(d, n) for n in NEEDED if n in names}
        if hit:
            found[d] = hit
    return found


def completeness(hit):
    return len(hit), sorted(NEEDED)


def report(found, verbose=True):
    if not found:
        print("no addon packaging tools found on this machine.")
        print("Get them from the loader author (Bingus Shared Loader), or point at them:")
        print("  python -B fetch_bingus_tools.py --from <folder with build_addon.py + archive.py> --dest <target>")
        return None
    best = None
    for d, hit in found.items():
        have = len(hit)
        if verbose:
            print("  %s  (%d/%d)" % (d, have, len(NEEDED)))
            for n in NEEDED:
                print("      %s %s" % ("OK " if n in hit else "-- ", n))
        if have == len(NEEDED) and (best is None or len(d) < len(best[0])):
            best = (d, hit)
    return best


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dest", help="target folder, e.g. work/standalone/vendor/bingus")
    p.add_argument("--from", dest="src", help="explicit file or folder to copy from")
    p.add_argument("--url", help="opt-in download base URL (never used automatically)")
    p.add_argument("--list", action="store_true", help="show what was found, copy nothing")
    p.add_argument("--force", action="store_true", help="overwrite an existing destination")
    args = p.parse_args()

    explicit = args.src
    if explicit and os.path.isfile(explicit):
        explicit = os.path.dirname(explicit)

    import time
    t0 = time.time()
    dirs = candidate_dirs(explicit)
    print("searching %d location(s) ..." % len(dirs))
    found = scan(dirs)
    best = report(found, verbose=not args.list)
    print("(%.1fs)" % (time.time() - t0))

    if args.list:
        if best:
            print()
            print("complete set: %s" % best[0])
            print("re-run with --dest <target> to copy it.")
        return 0 if best else 1

    if args.url:
        # Only when the user asks for it by name. The repo does not ship these.
        try:
            os.makedirs(args.dest or ".", exist_ok=True)
            for n in NEEDED:
                target = os.path.join(args.dest or ".", n)
                if os.path.exists(target) and not args.force:
                    print("refusing to overwrite %s (use --force)" % target)
                    return 2
                with urllib.request.urlopen(args.url.rstrip("/") + "/" + n) as r:
                    data = r.read()
                with open(target, "wb") as f:
                    f.write(data)
                print("downloaded %s (%d bytes)" % (target, len(data)))
            print("note: verify these against the loader author's own release before shipping.")
            return 0
        except Exception as exc:
            print("download failed: %s" % exc)
            print("prefer --from with a folder you already have.")
            return 1

    if not best:
        return 1
    if not args.dest:
        print()
        print("found a complete set in: %s" % best[0])
        print("re-run with --dest <target> to copy it.")
        return 0

    dst = os.path.abspath(args.dest)
    if os.path.isdir(dst) and os.listdir(dst) and not args.force:
        print("refusing to overwrite non-empty %s (use --force)" % dst)
        return 2
    os.makedirs(dst, exist_ok=True)
    for n in NEEDED:
        shutil.copy2(best[1][n], os.path.join(dst, n))
        print("copied %s -> %s" % (n, dst))

    print()
    print("These are third-party files: keep them out of anything you publish.")
    print("Record the source in your THIRD_PARTY_NOTICES.md, e.g.:")
    print("  addon packaging tools obtained from <source>; not redistributed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
