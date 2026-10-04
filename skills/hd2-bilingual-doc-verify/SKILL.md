---
name: hd2-bilingual-doc-verify
description: Keep a bilingual document set honest — verify that a translated markdown file still matches its source by recompiling its Lua blocks on LuaJIT, comparing code fences after comment removal, matching heading structure and links, and comparing directory trees by structure instead of prose. Use after editing either side of a docs pair, or when translations start drifting from the code.
---

# hd2-bilingual-doc-verify

`scripts/verify_translations.py` checks the things a translation must **not** change, so review
attention can go to the prose instead of to whether a code sample is still correct.

Written after this repository grew an English/Chinese pair for every document: six pairs of
`X.md` / `X.zh-CN.md`, where a stale code block in the Chinese copy is a bug nobody notices.

## Prerequisites

| Need | Why | If missing |
|---|---|---|
| Python 3.8+ | the script | — |
| **`lupa`** | recompiles the translated Lua blocks on real LuaJIT (check 1) | the other five checks still run; the script prints what it skipped |
| the pairs, in a repo layout | discovery expects `skills/<name>/SKILL.md` + `SKILL.zh-CN.md`, or `docs/`, `template/` | point it with `--root`, or extend `discover_pairs()` |

Nothing else: no game, no loader tools, no network. It writes nothing.

## Use

```powershell
python -B scripts/verify_translations.py                     # scan the repo root
python -B scripts/verify_translations.py --root <repo>       # or point at one
python -B scripts/verify_translations.py --no-luajit         # force the degraded mode
```

Exit 0 = every pair passed; non-zero = at least one failed, with the pair named.

## The six checks

1. **Translated Lua still compiles on LuaJIT** — extracts every `lua` fence from the
   *translation* and compiles it. Catches a translation that touched code.
2. **Code fences match the source after all comments are removed** — `--` and `--[[ ]]` for
   Lua, `#` for shell/PowerShell, `;` for pseudo-code. Comments *are* translated; code is not.
3. **Documentation fences match by structure** — directory trees and package layouts are
   documentation inside a code fence, so their annotations are meant to be translated. Those
   are compared by skeleton (tree glyphs, indentation, first token of each line), which still
   catches a dropped branch or a renamed path.
4. **Heading structure matches** — count and levels, in order. Catches a dropped section.
5. **Every relative link is carried over**, or is deliberately retargeted to a `.zh-CN` peer
   (reported as a note, not a failure). The source pointing *at* a `.zh-CN` file the
   translation *is* is also a note.
6. **Frontmatter is intact** — same keys, `name:` unchanged (it is an identifier), and
   `description:` translated (it is what a reader sees when choosing the skill).

## Two lessons baked into it

- **A verifier that assumes the obvious layout reports false failures.** The first version
  stripped only whole-line comments, so every code block containing a trailing `--` comment
  looked like a mismatch. Fixing the verifier, not the translations, was the right call —
  and it was only obvious because the failure count was implausibly high.
- **Check 3 exists because of a false positive too.** Four "code" fences in a new skill were
  directory trees; treating their translated annotations as a code change would have forced
  the translator to leave prose in English.

## Limitations

- It proves **structural** correspondence, not that the translation is *correct*. A mistranslated
  sentence passes every check. Read the prose.
- Check 3's structural fingerprint ignores annotation text by design, so a translation that
  replaced a path's description with something wrong is not caught.
- It only knows the layouts in `discover_pairs()`; a differently-organised repo needs that
  function extended.

## See also

`writing-mod-tools` (honest degradation, exit codes, stating what a tool cannot do).
