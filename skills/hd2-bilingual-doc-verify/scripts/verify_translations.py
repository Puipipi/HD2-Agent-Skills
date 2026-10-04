"""Verify that a translated doc still matches its source.

Run this after editing either side of a `X.md` / `X.zh-CN.md` pair. It checks the
things a translation must NOT change, so review attention can go to the prose:

  1. every Lua block extracted from the TRANSLATION still compiles on LuaJIT
  2. code fences match the source after all comments are removed
     (lua `--` and `--[[ ]]`, powershell `#`, pseudo-code `;`)
  3. documentation fences (directory trees, package layouts) match by STRUCTURE
     -- glyphs, indentation and the first token of each line -- because their
     annotations are meant to be translated
  4. heading structure (levels and order) matches
  5. every relative link is carried over, or deliberately retargeted to a
     `.zh-CN` peer (reported, not failed)
  6. frontmatter keys are intact, `name:` is unchanged, `description:` translated

Run:  python -B scripts/verify_translations.py [--root <repo>]

Prerequisites
    Python 3.8+
    lupa, for check 1 (recompiling the translated Lua). Without it, the other five
    checks still run and the script says which one it skipped instead of raising.
    Nothing else: no game, no loader tools, no network. It writes nothing.
"""
import argparse
import hashlib
import io
import os
import re
import sys

try:
    import lupa.luajit21 as lj
except ImportError:                                    # a missing prerequisite
    lj = None                                          # degrades, never traces back

# script lives at <repo>/skills/<skill>/scripts/, so the repo root is 4 up
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

BLOCK_COMMENT = re.compile(r"--\[\[.*?\]\]", re.S)
DOC_FENCES = ("text", "txt", "markdown", "md", "")


def split_code_blocks(text):
    blocks, in_block, lang, buf = [], False, None, []
    for line in text.split("\n"):
        if line.lstrip().startswith("```"):
            if in_block:
                blocks.append((lang, "\n".join(buf)))
                in_block, buf = False, []
            else:
                in_block, lang, buf = True, line.strip()[3:].strip(), []
            continue
        if in_block:
            buf.append(line)
    return blocks


def strip_comments(body, lang):
    """Keep only code: comments are translated, code is not."""
    body = BLOCK_COMMENT.sub("", body)
    line_comment = "--" if lang in ("lua", "luajit") else None
    hash_comment = lang in ("powershell", "ps1", "bash", "sh", "shell", "cmd")
    out = []
    for line in body.split("\n"):
        cut, in_s, quote, esc = None, False, None, False
        j = 0
        while j < len(line):
            c = line[j]
            if in_s:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == quote:
                    in_s = False
            else:
                if c in "\"'":
                    in_s, quote = True, c
                elif line_comment and line[j:j + 2] == line_comment:
                    cut = j
                    break
                elif hash_comment and c == "#":
                    cut = j
                    break
                elif c == ";" and lang not in ("lua", "luajit"):
                    cut = j
                    break
            j += 1
        if cut is not None:
            line = line[:cut]
        line = line.strip()
        if line:
            out.append(line)
    return "\n".join(out)


def structural_fingerprint(body):
    """For documentation fences: skeleton only, annotations excluded."""
    kept = []
    for line in body.split("\n"):
        s = line.rstrip()
        if not s.strip():
            continue
        m = re.match(r"^([\s│├└─┌┐┘┴┬|`+\-]*)(.*)$", s)
        indent, rest = m.group(1), m.group(2)
        token = re.split(r"\s{2,}|\s+—|\s+--", rest.strip(), maxsplit=1)[0].strip()
        kept.append(f"{indent}|{token}")
    return hashlib.sha256("\n".join(kept).encode("utf-8")).hexdigest()[:16]


def headings(text):
    return [(len(m.group(1)), m.group(2).strip())
            for m in re.finditer(r"^(#{1,6})\s+(.*)$", text, re.M)]


def links(text):
    return sorted(set(re.findall(r"\]\((?!https?:)([^)#]+)\)", text)))


def frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return None
    out = {}
    for line in m.group(1).split("\n"):
        if ":" in line:
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip()
    return out


def compiles_on_luajit(body):
    if lj is None:                       # lupa absent: skip, never fail the run
        return None
    rt = lj.LuaRuntime()
    try:
        return rt.eval("function(s) return loadstring(s, 'block') end")(body) is not None
    except Exception:
        return False


def check_pair(src_path, dst_path, label):
    src = io.open(src_path, encoding="utf-8").read()
    dst = io.open(dst_path, encoding="utf-8").read()
    ok = True
    print(f"== {label}")

    sb, db = split_code_blocks(src), split_code_blocks(dst)
    if len(sb) != len(db):
        print(f"  FAIL code block count: {len(sb)} vs {len(db)}")
        return False
    print(f"  code blocks: {len(sb)} == {len(db)}")

    mismatches, compiled, doc_fences = [], 0, 0
    for i, ((sl, sbody), (dl, dbody)) in enumerate(zip(sb, db)):
        if sl != dl:
            mismatches.append(f"#{i} fence language {sl!r} vs {dl!r}")
        elif sl in DOC_FENCES:
            doc_fences += 1
            if structural_fingerprint(sbody) != structural_fingerprint(dbody):
                mismatches.append(f"#{i} documentation structure differs (branch/path lost?)")
        elif hashlib.sha256(strip_comments(sbody, sl).encode()).hexdigest() != \
                hashlib.sha256(strip_comments(dbody, dl).encode()).hexdigest():
            mismatches.append(f"#{i} code differs after comment removal")
        if sl in ("lua", "luajit") and compiles_on_luajit(dbody):
            compiled += 1
    if mismatches:
        print("  FAIL code identity:")
        for m in mismatches:
            print("     - " + m)
        ok = False
    else:
        print("  code identity: %d code fence(s) match; %d documentation fence(s) "
              "match by structure" % (len(sb) - doc_fences, doc_fences))
    if compiled:
        print(f"  LuaJIT: {compiled} translated lua block(s) compile standalone")

    sh, dh = headings(src), headings(dst)
    if len(sh) != len(dh):
        print(f"  FAIL heading count: {len(sh)} vs {len(dh)}")
        ok = False
    elif any(a[0] != b[0] for a, b in zip(sh, dh)):
        print("  FAIL heading levels differ")
        ok = False
    else:
        print(f"  headings: {len(sh)} == {len(dh)}, levels match 1:1")

    sl, dl = links(src), links(dst)
    for l in [x for x in sl if x not in dl]:
        peer = l.replace(".md", ".zh-CN.md")
        if peer in dl:
            print(f"  note: link retargeted to its Chinese peer: {l} -> {peer}")
        elif ".zh-CN." in l:
            print(f"  note: cross-language link not needed in the translation: {l}")
        else:
            print(f"  FAIL relative link lost: {l}")
            ok = False

    sf, df = frontmatter(src), frontmatter(dst)
    if sf and df:
        if set(sf) != set(df):
            print(f"  FAIL frontmatter keys: {set(sf)} vs {set(df)}")
            ok = False
        elif sf.get("name") != df.get("name"):
            print(f"  FAIL name changed: {sf.get('name')!r} -> {df.get('name')!r}")
            ok = False
        elif sf.get("description") == df.get("description"):
            print("  WARN description not translated")
        else:
            print("  frontmatter: keys intact, name unchanged, description translated")
    print(f"  {'OK' if ok else 'PROBLEM'}")
    return ok


def discover_pairs(root):
    """Every X.md that has an X.zh-CN.md sibling."""
    pairs = []
    for dirpath, _, names in os.walk(os.path.join(root, "skills")):
        for n in names:
            if n == "SKILL.zh-CN.md":
                pairs.append((os.path.join(dirpath, "SKILL.md"), os.path.join(dirpath, n)))
    for sub in ("docs", "template"):
        d = os.path.join(root, sub)
        if not os.path.isdir(d):
            continue
        for n in sorted(os.listdir(d)):
            if n.endswith(".zh-CN.md"):
                base = n[:-len(".zh-CN.md")] + ".md"
                pairs.append((os.path.join(d, base), os.path.join(d, n)))
    return sorted(pairs)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=ROOT,
                    help="repo root to scan (default: four levels above this script)")
    ap.add_argument("--no-luajit", action="store_true",
                    help="skip the LuaJIT recompile check (it needs lupa)")
    args = ap.parse_args()
    ROOT = os.path.abspath(args.root)
    if args.no_luajit:
        lj = None

    if lj is None:
        print("note: LuaJIT recompile check skipped (lupa not installed, or --no-luajit)")
        print("      the other five checks do not need it")
        print()

    all_ok = True
    pairs = discover_pairs(ROOT)
    if not pairs:
        print("no X.md / X.zh-CN.md pairs found under %s" % ROOT)
        sys.exit(1)
    for src, dst in pairs:
        all_ok &= check_pair(src, dst, os.path.relpath(dst, ROOT))
        print()
    print("OVERALL:", "OK" if all_ok else "see above")
    sys.exit(0 if all_ok else 1)
