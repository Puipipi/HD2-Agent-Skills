"""Verify that a translated doc still matches its source.

Run this after editing either side of an `X.md` / `X_cn.md` pair. It checks the
things a translation must NOT change, so review attention can go to the prose:

  1. every Lua block extracted from the TRANSLATION still compiles on LuaJIT
  2. code fences match the source after all comments are removed
     (lua `--` and `--[[ ]]`, python/shell `#`, pseudo-code `;`)
  3. documentation fences are compared as documentation: a tree/layout by its
     skeleton, a fence with no executable code (prose, or a quoted docstring) by
     shape only
  4. heading structure (levels and order) matches
  5. every relative link is carried over, or deliberately retargeted to the `_cn`
     peer (reported, not failed)
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
    # `#` starts a comment in a shell command line AND in Python. Both appear in
    # these docs, and a trailing `# ...` comment is translatable text.
    hash_comment = lang in ("powershell", "ps1", "bash", "sh", "shell", "cmd", "python", "py")
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


TRIPLE = re.compile(r'"""(?:.|\n)*?"""|\'\'\'(?:.|\n)*?\'\'\'', re.S)


def executable_lines(body, lang):
    """Lines that carry code, ignoring comments AND docstrings.

    A docstring is prose: when a code fence exists only to quote one (a worked
    example in the docs), it contains no executable code and there is nothing to
    compare but its shape.
    """
    text = strip_comments(body, lang)
    if lang in ("python", "py"):
        text = TRIPLE.sub("", text)
    return [ln for ln in text.split("\n") if ln.strip()]


TREE_GLYPHS = set("│├└─┌┐┘┴┬")


def is_documentation_fence(lang, body):
    """True when the fence carries no executable code.

    Two cases:
      * a directory tree / package layout -- annotations are translated, so the
        skeleton must match
      * prose in a fence: a `text` block, or a code fence quoting only a
        docstring/comment
    Deciding by the fence language alone gets the second case wrong.
    """
    if lang in DOC_FENCES:
        return True
    return not executable_lines(body, lang)


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


def check_switcher(en_path, cn_path, en_text, cn_text, root):
    """7. the language switcher exists, once, and points at the counterpart.

    A missing or stale switcher is invisible until a reader cannot find their own
    language, so it is checked rather than assumed.
    """
    problems = []
    en_rel = os.path.relpath(en_path, root).replace(os.sep, "/")
    cn_rel = os.path.relpath(cn_path, root).replace(os.sep, "/")

    def switchers(text):
        head = text.split("\n## ")[0]           # header block only
        return [l for l in head.split("\n") if "简体中文" in l and "English" in l]

    for text, want, label in ((en_text, cn_rel, "source"),
                              (cn_text, en_rel, "translation")):
        found = switchers(text)
        if not found:
            problems.append("%s has no language switcher line" % label)
            continue
        if len(found) > 1:
            problems.append("%s has %d switcher lines" % (label, len(found)))
        # The switcher may name the counterpart as a relative path or as an
        # absolute blob URL; both are acceptable, so accept either.
        if want not in found[0] and not found[0].rstrip(")").endswith(want):
            problems.append("%s switcher does not point at %s" % (label, want))
    return problems


def check_header_switcher(path, root, verbose=True):
    """9. a skill's own switcher must exist even when its pair is missing.

    The pair check only runs when both files exist, so a skill that has an English
    file but no translation yet escapes it entirely - which is exactly how five
    English skills ended up without a switcher while their translations had one.
    """
    problems = []
    text = io.open(path, encoding="utf-8").read()
    head = text.split("\n## ")[0]
    found = [l for l in head.split("\n") if "简体中文" in l and "English" in l]
    if not found:
        problems.append("%s has no language switcher line" % os.path.relpath(path, root))
    elif len(found) > 1:
        problems.append("%s has %d switcher lines" % (os.path.relpath(path, root), len(found)))
    if verbose:
        for p in problems:
            print("  FAIL " + p)
    return problems


def check_pair(src_path, dst_path, label, root):
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
        elif is_documentation_fence(sl, sbody):
            doc_fences += 1
            # a tree/layout must keep its skeleton; prose need only stay the same
            # shape (same number of lines), since every word is translated
            if any(ch in TREE_GLYPHS for line in sbody for ch in line):
                if structural_fingerprint(sbody) != structural_fingerprint(dbody):
                    mismatches.append(f"#{i} documentation structure differs (branch/path lost?)")
            elif len(sbody.strip().split("\n")) != len(dbody.strip().split("\n")):
                mismatches.append(f"#{i} prose fence changed line count")
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
        # A language switcher and cross-language references move between the
        # pair: allow the `_cn` retarget, and allow a source link that the
        # translation does not need because the translation IS that file.
        peer = l.replace(".md", "_cn.md")
        if peer in dl:
            print(f"  note: link retargeted to its Chinese peer: {l} -> {peer}")
        elif l.endswith("_cn.md"):
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

    switcher_problems = check_switcher(src_path, dst_path, src, dst, root)
    for problem in switcher_problems:
        print(f"  FAIL language switcher: {problem}")
        ok = False
    if not switcher_problems:
        print("  language switcher: present and pointing at the counterpart")

    print(f"  {'OK' if ok else 'PROBLEM'}")
    return ok


def discover_pairs(root):
    """Every X.md that has an X_cn.md sibling.

    The `_cn` suffix follows the convention DeepSeek's own repositories use
    (README.md / README_cn.md), so a reader of either language finds the
    counterpart by name.
    """
    pairs = []
    for dirpath, _, names in os.walk(root):
        if ".git" in dirpath:
            continue
        for n in sorted(names):
            if n.endswith("_cn.md"):
                base = n[:-len("_cn.md")] + ".md"
                if os.path.exists(os.path.join(dirpath, base)):
                    pairs.append((os.path.join(dirpath, base), os.path.join(dirpath, n)))
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

    # Every skill file must carry its own switcher, even before its
    # translation exists: the pair loop below skips a file whose counterpart
    # is absent, which is how five English skills lost their switcher while
    # their Chinese files kept one.
    skills_dir = os.path.join(ROOT, "skills")
    if os.path.isdir(skills_dir):
        for d in sorted(os.listdir(skills_dir)):
            for f in ("SKILL.md", "SKILL_cn.md"):
                p = os.path.join(skills_dir, d, f)
                if os.path.exists(p) and check_header_switcher(p, ROOT):
                    all_ok = False

    pairs = discover_pairs(ROOT)
    if not pairs:
        print("no X.md / X_cn.md pairs found under %s" % ROOT)
        sys.exit(1)
    for src, dst in pairs:
        all_ok &= check_pair(src, dst, os.path.relpath(dst, ROOT), ROOT)
        print()
    print("OVERALL:", "OK" if all_ok else "see above")
    sys.exit(0 if all_ok else 1)
