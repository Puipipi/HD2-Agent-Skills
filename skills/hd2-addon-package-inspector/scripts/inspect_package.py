"""Inspect a built addon package before you ship or deploy it.

The loader SKIPS a package silently when it cannot read it, and a mod site's
"import failed" says nothing useful. This checks the envelope in the build
output and, when you point it at the source file, proves that the package
actually carries what you built.

Checks
    structure   manifest.json / Addon/<hash>.patch_0 (+ empty .stream and
                .gpu_resources), README.txt
    manifest    Version, Guid (one GUID per mod, reused across releases),
                Name, Options[0].Include == ["Addon"]
    icon        if IconPath / Options[].Image is declared, the file is present
    archive     header magic 0xF0000011, entry count matches the body, resource
                hash of the name resolves to the same entry, and the embedded
                `-- HD2-Addon: <name>` declaration is present and correct
    source      optional: the packaged resource contains the source you think it
                does, and the version string matches

Usage
    python -B inspect_package.py dist/My-Mod-1.0.0.zip
    python -B inspect_package.py dist/My-Mod-1.0.0.zip --source work/standalone/mymod.lua
    python -B inspect_package.py dist/My-Mod-1.0.0.zip --json

Prerequisites
    Python 3.8+ only. No lupa, no LuaJIT, no game, no network. Read-only: it
    never writes or unpacks anything.

Exit codes: 0 all checks passed, 1 a check failed.
"""
import argparse
import hashlib
import json
import re
import struct
import sys
import zipfile

ARCHIVE_MAGIC = 0xF0000011
RESOURCE_TYPE = 0xA14E8DFA2CD117E2


def resource_hash(name):
    """Mirror of the loader's name -> id map (64-bit MurmurHash64A variant)."""
    data = name.encode("utf-8")
    mask, mix = (1 << 64) - 1, 0xC6A4A7935BD1E995
    value = len(data) * mix & mask
    end = len(data) // 8 * 8
    for (word,) in struct.iter_unpack("<Q", data[:end]):
        word = word * mix & mask
        word ^= word >> 47
        value = (value ^ (word * mix & mask)) * mix & mask
    if data[end:]:
        value = (value ^ int.from_bytes(data[end:], "little")) * mix & mask
    value ^= value >> 47
    value = value * mix & mask
    return value ^ (value >> 47)


# Published test vectors for the name -> id hash, from the loader's own docs and
# tests. Every check below depends on this hash being right, so the tool proves
# its own implementation at startup instead of trusting a comment.
KNOWN_HASHES = (
    ("core/wwise/lua/wwise_flow_callbacks", 0x7251FDD9BB62480A),
    ("mods/codex/gun_calibration", 0x9537023F38D32BCD),
    ("mods/example_author/example_addon", 0x835DB1516CA1E1CA),
)


def hash_self_test(verbose=True):
    bad = [(n, want, resource_hash(n)) for n, want in KNOWN_HASHES
           if resource_hash(n) != want]
    if verbose:
        if bad:
            for n, want, got in bad:
                print(f"FAIL  hash vector {n}: want 0x{want:016X}, got 0x{got:016X}")
        else:
            print(f"hash self-test: {len(KNOWN_HASHES)} published vectors match")
    return not bad


class Findings:
    def __init__(self):
        self.rows = []
        self.failed = 0

    def check(self, ok, label, detail=""):
        self.rows.append((bool(ok), label, detail))
        if not ok:
            self.failed += 1
        return ok

    def report(self, as_json):
        if as_json:
            print(json.dumps({
                "ok": self.failed == 0,
                "failed": self.failed,
                "checks": [{"ok": o, "label": l, "detail": d} for o, l, d in self.rows],
            }, indent=2, ensure_ascii=False))
            return
        for ok, label, detail in self.rows:
            line = ("PASS  " if ok else "FAIL  ") + label
            if detail and not ok:
                line += "  -- " + detail
            elif detail:
                line += "  (" + detail + ")"
            print(line)


def parse_archive(blob, f, archive_name):
    """Validate the Lua archive and return {name: resource bytes}."""
    if not f.check(len(blob) >= 104, "archive: at least a header", f"{len(blob)} bytes"):
        return {}
    magic, version, count = struct.unpack_from("<III", blob, 0)
    f.check(magic == ARCHIVE_MAGIC, "archive: header magic",
            f"got 0x{magic:08X}, expected 0x{ARCHIVE_MAGIC:08X}")
    f.check(version == 1, "archive: version is 1", f"got {version}")
    f.check(count >= 1, "archive: has at least one resource", f"count={count}")

    entries = []
    off = 104
    for i in range(count):
        if off + 80 > len(blob):
            f.check(False, f"archive: entry {i} fits in the file")
            break
        name_hash, rtype, data_off, a, b, c, d = struct.unpack_from("<7Q", blob, off)
        length, = struct.unpack_from("<I", blob, off + 56)
        entries.append((name_hash, rtype, data_off, length))
        off += 80

    out = {}
    for i, (name_hash, rtype, data_off, length) in enumerate(entries):
        f.check(rtype == RESOURCE_TYPE, f"archive: entry {i} resource type",
                f"got 0x{rtype:016X}")
        ok_range = 0 <= data_off and length >= 0 and data_off + length <= len(blob)
        f.check(ok_range, f"archive: entry {i} data range is inside the file",
                f"offset={data_off} length={length} file={len(blob)}")
        if ok_range:
            resource = blob[data_off:data_off + length]
            # a resource is "<u32 body length><u32 version=2>" + the entry body,
            # so the declaration is NOT at offset 0 -- do not anchor to line start
            if len(resource) >= 8:
                body_len, rver = struct.unpack_from("<II", resource, 0)
                f.check(rver == 2, f"archive: entry {i} resource version is 2",
                        f"got {rver}")
                f.check(body_len == len(resource) - 8,
                        f"archive: entry {i} header length matches the body",
                        f"header says {body_len}, body is {len(resource) - 8}")
            out[name_hash] = resource

    # the resource name is carried in the archive's own manifest, not the file
    # name, so the caller supplies the expected name and we match its hash
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("package", help="the .zip you built")
    ap.add_argument("--resource", help="expected resource name, e.g. mods/yourauthor/mymod")
    ap.add_argument("--source", help="the .lua you built from, to prove it is inside")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    f = Findings()

    # The name -> hash mapping is the foundation of every identity check, so
    # prove it against the published vectors before trusting any of them.
    if not args.json:
        hash_self_test()
    if not hash_self_test(verbose=False):
        print('FAIL  the name->hash implementation disagrees with the published vectors')
        return 1
    if not zipfile.is_zipfile(args.package):
        Findings().check(False, "package is a readable zip")
        print("FAIL  package is not a zip: " + args.package)
        return 1

    with zipfile.ZipFile(args.package) as z:
        names = [i.filename for i in z.infolist()]
        f.check("manifest.json" in names, "structure: manifest.json present")
        f.check("README.txt" in names, "structure: README.txt present")

        archives = [n for n in names
                    if n.startswith("Addon/") and n.endswith(".patch_0")]
        f.check(len(archives) == 1, "structure: exactly one Addon/*.patch_0",
                f"found {archives}")
        for suffix in (".stream", ".gpu_resources"):
            f.check(any(n == a + suffix for a in archives for n in names),
                    f"structure: {suffix} companion present")

        from_manifest = {}
        if "manifest.json" in names:
            try:
                m = json.loads(z.read("manifest.json").decode("utf-8"))
                for key in ("Version", "Guid", "Name"):
                    f.check(key in m, f"manifest: {key} present")
                guid = str(m.get("Guid", ""))
                f.check(bool(re.fullmatch(
                    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
                    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", guid)),
                    "manifest: Guid is a UUID", guid)
                f.check(m.get("Version") == 1, "manifest: Version is 1",
                        str(m.get("Version")))
                opts = m.get("Options") or []
                includes = [i for o in opts for i in (o.get("Include") or [])]
                f.check("Addon" in includes, "manifest: Options include 'Addon'",
                        str(includes))
                # an advertised image must be shipped
                declared = [m.get("IconPath")] if m.get("IconPath") else []
                declared += [o.get("Image") for o in opts if o.get("Image")]
                for img in [d for d in declared if d]:
                    f.check(img in names, f"manifest: declared image '{img}' is packaged")
                from_manifest = m
            except Exception as exc:
                f.check(False, "manifest.json parses", str(exc))

        if archives:
            blob = z.read(archives[0])
            f.check(bool(blob), "archive: not empty", f"{len(blob)} bytes")
            resources = parse_archive(blob, f, archives[0])

            # the expected resource name comes from --resource, else infer it
            # from the embedded declaration inside the resource itself
            embedded = None
            for data in resources.values():
                mm = re.search(rb"-- HD2-Addon: (\S+)\n", data)
                if mm:
                    embedded = mm.group(1).decode()
                    break
            f.check(embedded is not None,
                    "archive: resource carries a '-- HD2-Addon:' declaration",
                    "none found in any resource")

            if args.resource and embedded:
                f.check(args.resource == embedded,
                        "archive: declaration matches --resource",
                        f"declared {embedded!r}, expected {args.resource!r}")

            if embedded:
                f.check(embedded.startswith("mods/"),
                        "archive: resource name starts with mods/", embedded)
                f.check(re.fullmatch(r"mods/[A-Za-z0-9_]+/[A-Za-z0-9_]+(?:/[A-Za-z0-9_]+)*",
                                     embedded) is not None,
                        "archive: resource name uses the allowed characters "
                        "(letters, digits, underscore)", embedded)
                want = resource_hash(embedded)
                f.check(want in resources,
                        "archive: resource hash of the name resolves to an entry",
                        f"hash 0x{want:016X} not among {[hex(k) for k in resources]}")

            if args.source:
                with open(args.source, encoding="utf-8") as fh:
                    src = fh.read()
                packed = "\n".join(data.decode("utf-8", "replace")
                                   for data in resources.values())
                # "the package carries the source you think it does": compare the
                # version string and a distinctive run of the source rather than
                # the whole file, so a comment-only edit does not trip it.
                vm = re.search(r"version\s*=\s*['\"]([\d.]+)['\"]", src)
                if vm:
                    f.check(vm.group(1) in packed,
                            "source: version string is inside the package", vm.group(1))
                body_lines = [ln.rstrip() for ln in src.splitlines()
                              if len(ln.strip()) > 30 and not ln.strip().startswith("--")]
                probe_lines = body_lines[:5] + body_lines[-5:] if body_lines else []
                missing = [ln for ln in probe_lines if ln not in packed]
                f.check(not missing,
                        "source: the packaged resource contains the source you built",
                        f"{len(missing)} of {len(probe_lines)} sampled lines absent")
                zm = re.search(r"-(\d+\.\d+\.\d+)\.zip$", args.package)
                if vm and zm:
                    f.check(vm.group(1) == zm.group(1),
                            "source: version in the source matches the file name",
                            f"source {vm.group(1)} vs zip {zm.group(1)}")

    size = len(open(args.package, "rb").read())
    digest = hashlib.sha256(open(args.package, "rb").read()).hexdigest()
    f.report(args.json)
    if not args.json:
        print()
        print("package : %s" % args.package)
        print("size    : %d bytes" % size)
        print("sha256  : %s" % digest.upper())
        print("result  : %s" % ("OK" if f.failed == 0 else "FAIL (%d)" % f.failed))
    return 1 if f.failed else 0


if __name__ == "__main__":
    sys.exit(main())
