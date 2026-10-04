---
name: hd2-bilingual-doc-verify
description: Keep a bilingual document set honest — verify that a translated markdown file still matches its source by recompiling its Lua blocks on LuaJIT, comparing code fences after comment removal, matching heading structure and links, and comparing directory trees by structure instead of prose. Use after editing either side of a docs pair, or when translations start drifting from the code.
---

# hd2-bilingual-doc-verify

`scripts/verify_translations.py` checks the things a translation must **not** change, so review
attention can go to the prose instead of to whether a code sample is still correct.

Written after this repository grew an English/Chinese pair for every document: six pairs of
`X.md` / `X_cn.md`, where a stale code block in the Chinese copy is a bug nobody notices.

## Prerequisites

| Need | Why | If missing |
|---|---|---|
| Python 3.8+ | the script | — |
| **`lupa`** | recompiles the translated Lua blocks on real LuaJIT (check 1) | the other five checks still run; the script prints what it skipped |
| the pairs, in a repo layout | discovery finds any `X.md` with an `X_cn.md` beside it, anywhere in the tree | point it with `--root` |

Nothing else: no game, no loader tools, no network. It writes nothing.

## Use

```powershell
python -B scripts/verify_translations.py                     # scan the repo root
python -B scripts/verify_translations.py --root <repo>       # or point at one
python -B scripts/verify_translations.py --no-luajit         # force the degraded mode
```

Exit 0 = every pair passed; non-zero = at least one failed, with the pair named.

## The seven checks

1. **Translated Lua still compiles on LuaJIT** — extracts every `lua` fence from the
   *translation* and compiles it. Catches a translation that touched code.
2. **Code fences match the source after all comments are removed** — `--` and `--[[ ]]` for
   Lua, `#` for shell/PowerShell **and Python** (an inline `# …` comment is translatable
   text), `;` for pseudo-code. Comments *are* translated; code is not.
3. **Documentation fences are compared as documentation** — a fence counts as documentation
   when it has no executable code, i.e. a directory tree / package layout, a `text` block of
   prose, or a code fence that quotes only a docstring or comments. Trees are compared by
   skeleton (glyphs, indentation, first token per line), which still catches a dropped branch
   or a renamed path; prose is compared by line count only, because every word is translated.
4. **Heading structure matches** — count and levels, in order. Catches a dropped section.
5. **Every relative link is carried over**, or is deliberately retargeted to a `_cn` peer
   (reported as a note, not a failure). The source pointing *at* a `_cn` file the translation
   *is* is also a note.
6. **Frontmatter is intact** — same keys, `name:` unchanged (it is an identifier), and
   `description:` translated (it is what a reader sees when choosing the skill).
7. **The language switcher exists, once, and points at the counterpart** — in the header block
   of both sides, with the current language left unlinked:
   ```
   English / [简体中文](https://github.com/OWNER/REPO/blob/main/README_cn.md)
   [English](https://github.com/OWNER/REPO/blob/main/README.md) / 简体中文
   ```
   Absolute URLs are deliberate — copied from DeepSeek's own repositories, because the
   switcher is the one link a reader needs before they can navigate anything else. It is
   checked rather than trusted: removing one, pointing it at the wrong file, or leaving two
   in the header all fail the run.

## Two lessons baked into it

- **A verifier that assumes the obvious layout reports false failures.** The first version
  stripped only whole-line comments, so every code block containing a trailing `--` comment
  looked like a mismatch. Fixing the verifier, not the translations, was the right call —
  and it was only obvious because the failure count was implausibly high. The same thing then
  happened twice more: an inline `#` comment in a **Python** fence (the stripper only knew
  shell), and a `python` fence that quoted **only a docstring** (no executable code at all, so
  the whole block is prose). Each fix made check 3 narrower and truer: *compare code as code,
  and documentation as documentation, and decide that from the content rather than the fence
  label.*
- **Check 3 exists because of a false positive too.** Four "code" fences in a new skill were
  directory trees; treating their translated annotations as a code change would have forced
  the translator to leave prose in English.

**When a verifier reports failures, look at the failures before touching the translation.**
In all three of the above cases the translations were correct — including the one where the
"code" was a docstring explaining the deploy incident, translated on purpose. A linter that is
wrong costs more than no linter: it teaches people to ignore it.

## Limitations

- It proves **structural** correspondence, not that the translation is *correct*. A mistranslated
  sentence passes every check. Read the prose.
- Check 3's structural fingerprint ignores annotation text by design, so a translation that
  replaced a path's description with something wrong is not caught.
- It only knows the layouts in `discover_pairs()`; a differently-organised repo needs that
  function extended.

## See also

`writing-mod-tools` (honest degradation, exit codes, stating what a tool cannot do).
