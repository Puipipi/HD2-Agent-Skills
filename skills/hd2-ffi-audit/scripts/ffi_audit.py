# -*- coding: utf-8 -*-
"""Static FFI audit for HD2 Lua mods: every C symbol that is CALLED must be
declared, and no symbol may be declared with a struct-pointer parameter that
another mod in the ecosystem declares differently.

Both rules come from real breakage on 2026-10-01:
  * multi_perk called kernel32.VirtualAllocEx while the cdef list never
    declared it -> "missing declaration for symbol 'VirtualAllocEx'" on every
    card apply ("点击应用卡片没反应", MultiPerk.log 2026-09-30T21:46:07Z);
  * SmoothBoot declared int GetCursorPos(int32_t*) and silently displaced
    Clickable Scrollbars' HD2CS_POINT* declaration (LuaJIT keeps the first
    declaration) -> that mod disabled itself for the whole session.
"""
import re
import sys

CALL_RE = re.compile(r"\b(?:k|u|k32|u32|gdi32|kernel32|user32|bcrypt|ffi\.C)\.([A-Za-z_]\w*)\s*\(")
DECL_RE = re.compile(r"\b([A-Za-z_]\w*)\s*\([^;()]*\)\s*;")
CDEF_BLOCK_RE = re.compile(r"ffi\.cdef\s*\[\[(.*?)\]\]", re.S)
# one-declaration-per-pcall style: pcall(ffi.cdef,'int Foo(void*);')
CDEF_STRING_RE = re.compile(
    r"'\s*(?:void|int|unsigned|signed|short|long|size_t|ssize_t|char|float|double|bool|"
    r"u?int\d+_t)\b[^']*\([^']*\)\s*;'")
# prototype-bound-by-address style: bind('int (*)(int32_t *)','GetCursorPos')
BIND_RE = re.compile(r"bind\(\s*'[^']*'\s*,\s*'([A-Za-z_]\w*)'\s*\)")
# symbols that come from the engine, not from a C library
ENGINE_OK = {"json", "load"}


def declared_symbols(src):
    out = set()
    for block in CDEF_BLOCK_RE.findall(src):
        out.update(m.group(1) for m in DECL_RE.finditer(block))
    for chunk in CDEF_STRING_RE.findall(src):
        out.update(m.group(1) for m in DECL_RE.finditer(chunk))
    out.update(BIND_RE.findall(src))      # resolved through GetProcAddress
    return out


def called_symbols(src):
    return {m.group(1) for m in CALL_RE.finditer(src)}


def audit_source(src, name="<source>", verbose=True):
    declared, called = declared_symbols(src), called_symbols(src)
    missing = sorted(s for s in called - declared if s not in ENGINE_OK)
    if verbose:
        print("%s" % name)
        print("  declared: %d symbol(s)" % len(declared))
        print("  called  : %d symbol(s)" % len(called))
        if missing:
            for s in missing:
                line = next((i + 1 for i, l in enumerate(src.split("\n"))
                             if re.search(r"\b\w+\.%s\s*\(" % s, l)), "?")
                print("  MISSING DECLARATION: %-24s (first call at line %s)" % (s, line))
        else:
            print("  all called symbols are declared")
    return missing


def audit(path, verbose=True):
    src = open(path, encoding="utf-8", errors="replace").read()
    return audit_source(src, path, verbose)


if __name__ == "__main__":
    bad = 0
    for p in sys.argv[1:]:
        bad += len(audit(p))
    print()
    print("audit result: %s" % ("FAIL" if bad else "OK"))
    sys.exit(1 if bad else 0)
