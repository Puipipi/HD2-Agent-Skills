---
name: writing-mod-tools
description: How to write a maintenance and diagnostics tool for a Helldivers 2 mod (or any game-mod project) so it is safe, honest about its prerequisites, machine-checkable, and actually catches the bug it was written for — safe-by-default mutation, exit codes, --json, dry-run, self-tests that reproduce the original failure, and the discipline of a README/status split. Use when adding a build script, a log analyzer, a live memory probe, a deployer, or any helper another person will run.
---

# Writing mod tools

Distilled from the ~120 tools across the mods in this workspace: four build scripts, a
guarded deployer, a dozen live memory probes, log analyzers, offline simulators and a
static FFI auditor. Every rule below is something one of them got right — usually after
getting it wrong first.

The audience is a **stranger who is already annoyed**. They run your tool because
something is broken. Every minute it wastes is a minute it failed.

---

## 1. State the prerequisites, and degrade instead of crashing

A tool that dies with a traceback because `lupa` is not installed has taught the user
nothing except that your tool is fragile.

```python
try:
    import lupa.luajit21 as lj
except ImportError:            # a missing prerequisite degrades, never tracebacks
    lj = None
...
if lj is None:
    print("note: LuaJIT check skipped (lupa not installed, or --no-luajit)")
```

Then say **what still works without it** — "the other five checks do not need it" — so the
run is still useful. Offer the same switch explicitly (`--no-luajit`) so the degraded mode
is testable rather than hypothetical.

Write prerequisites as a table with the consequence of absence, not as prose:

| Need | Why | If missing |
|---|---|---|
| Python 3.8+ | the script | — |
| `lupa` | compiles the source with the real LuaJIT | the check is skipped, and says so |
| the game **running** | a live probe reads its memory | exit 2 with "start the game first" |

Separate "required" from "optional" explicitly. A prerequisite that is only needed for one
sub-command belongs in that sub-command's help, not the top of the file.

## 2. Be read-only by default, and when you must write, be guarded

Most tools here are read-only and say so in the docstring — `README`-level honesty:

> Read-only: it opens the game with `PROCESS_VM_READ` … Nothing is written to the game,
> and no window or input automation is used.

For anything that mutates, follow `safe_deploy.py` — a deployer written *because* an earlier
build hard-coded a game slot, overwrote the mod loader, and made every Lua mod in the
install disappear. Its rules generalise to any file-mutating tool:

1. **Identify the target by content, never by a number you remember.** It finds its slot by
   the `-- HD2-Addon:` declaration inside the layer. "String search is useless for
   identity" for the loader, so it matches the envelope bytes by SHA-256 instead.
2. **Refuse anything that is not provably yours.** `classify()` returns `mine` / `foreign` /
   `missing`, and *unknown* counts as `foreign`.
3. **`dry_run=True` first**, printing what it would do.
4. **Never displace:** with no slot yet, allocate a new number above the current maximum.
5. **Verify after writing**, then re-verify everything else is unchanged, and abort loudly
   if a bystander moved:
   ```python
   before = {n: _digest(...) for n, p in layer_numbers().items()}
   ...
   for n, h in before.items():
       if n != target and _digest(...) != h:
           raise DeployRefused("slot %d changed during deploy - aborting" % n)
   ```
6. **Give it a self-test that reproduces the original bug**, and run it as the default entry
   point. `safe_deploy.py`'s `_self_test()` feeds the historical hard-coded slot back in and
   asserts it is refused — the regression cannot come back silently.

A mutation tool without a dry-run, a refusal path and a self-test is a footgun with a CLI.

## 3. Exit codes and `--json` are the interface

Humans read the summary; scripts and agents read the exit code. Both, always.

- `0` success, non-zero failure, with the **reason on stderr** — and name the gate:
  `FAIL refusing to build: user32 symbol(s) declared: GetCursorPos`.
- Two failure modes deserve different codes when the fix differs: "nothing found" (1) versus
  "refused to overwrite" (2).
- `--json` for anything an agent or CI will consume. Structure it (`{"ok": false, "failed":
  1, "checks": [...]}`), never a wall of text with a JSON flag bolted on.
- Print a machine-verifiable footer: byte size and **SHA-256**. That is how the next person
  checks they have the artifact you meant.

## 4. Make discovery free, and look everywhere before you ask

`fetch_bingus_tools.py` searches an explicit path, every installed mod's `scripts/`, `tools/`
and `vendor/` folders, and the checkout's own neighbourhoods — then, if it finds a complete
set, prints where and stops rather than guessing a destination. `--list` shows what would
happen and copies nothing.

Generalise: a tool that needs a file should **search the obvious places first**, report what
it found as a table with `OK`/`--` per required file, and only then ask. Never make the user
hunt for something you can locate.

When a tool genuinely needs a third-party artifact you may not redistribute, do not bundle
it — fetch-from-local or fetch-by-explicit-URL (`--url`, never automatic), and tell the user
to record the source in their notices file.

## 5. Read the artifact, not just your own success message

The build says "built OK"; that says nothing about whether the artifact is *right*.
`inspect_package.py` exists to close that gap and check the envelope independently:

- structure (required members present, exactly one archive, sidecars)
- manifest semantics (GUID is a UUID, `Version` is 1, declared icon is actually packaged)
- **binary format** (magic, entry count, each entry's type, ranges inside the file, header
  length matching the body)
- **identity** (the name → hash mapping resolves to a real entry)
- **provenance** (`--source` proves the packaged resource contains the code you built, and
  the version in the source matches the file name)

Note the parsed detail: the embedded declaration is *not* at offset 0 of a resource, because
each resource is prefixed with an 8-byte header. A verifier that assumes the obvious layout
reports false failures — the first version of this one did.

## 6. Failures worth a tool of their own

The best tools here were each written after a specific, expensive failure. Use that as your
test for whether a tool is worth writing:

| Failure | Tool | What makes it good |
|---|---|---|
| a mod was **silently skipped on load** (LuaJIT's 65535-instruction cap) | `build_mod.py` | refuses to package; the gate names the limit |
| a declaration **displaced another mod's** and disabled it | `ffi_audit.py`, build gate | exact rule, list of the offending symbols |
| a mod stayed **silent for 165 sessions** | `analyze_vehicle_cooldown_log.py` | reports stage by stage, so "did nothing" becomes "stopped at locate" |
| a probe's address chain was unreadable live | `check_live_probe.py` | cross-checks two independent sources (module list *and* the probe's own header parse) and prints both when they disagree |
| the addon's own timing was unusable | `measure_overhead.py` | explains *why*: `os.clock()` resolution is ~15.6 ms, so sub-millisecond work rounds to 0.000; measures from outside instead |
| a hard-coded slot deleted the mod loader | `safe_deploy.py` | content-based targeting, dry-run, refusal, post-write verification, self-test |

So: **write the tool for the failure you just paid for**, and record that failure in the
docstring. The next person then knows why the tool exists and when to reach for it.

## 7. Comments carry the evidence

The docstring is where the expensive knowledge lives. The good ones here read like incident
reports:

```python
"""Guarded envelope deploy for HD2 Arsenal / Bingus mods.

Why this file exists (2026-10-01, user report "加上这个模组后会让所有lua模组直接不生效"):
    build121.py ... wrote the ... envelope into a HARD-CODED game slot ...
    Overwriting it deletes the mod loader, so the whole Lua ecosystem dies ...
"""
```

Include: the date, the symptom as the user reported it, the mechanism, and the rule that
follows. Not "handles edge cases" — that tells nobody anything.

Also state what the tool **cannot** do. `ffi_audit.py` says plainly that it is a regex
scanner: it will not catch a symbol reached through a macro or typedef, and a declaration
that resembles another mod's is only checked for the symbols it knows. Honest limits are
what make a tool trustworthy.

## 8. Test the tool itself, including the failure path

- Drive the failure path in a test: the build script's gates are exercised by declaring a
  known-bad symbol and asserting a non-zero exit.
- Prefer a **differential** check when the tool claims an improvement: "original 189 reads,
  adapter 53, every observed field identical" is verifiable; "faster" is not.
- Make the tool's own verdict reproducible: emit the command that reproduces it, and keep
  the fixture under version control.

## 9. Deliver the tool with its verdict, not with a claim

- Put the exit code and the artifact hash in the summary.
- Say which part is **verified** and which is **not** — a tool tested against a fake input is
  not a tool tested against the real thing. Both facts belong in the README.
- When a check is skipped, say so in the output. A silent skip reads as a pass, and that is
  the single most dangerous behaviour a validation tool can have.

---

## Workflow

1. Name the failure the tool exists for, with its date and symptom.
2. Decide read-only vs mutating. Mutating ⇒ dry-run, content-based targeting, refusal path,
   post-write verification, self-test.
3. Write the docstring first: prerequisites, what it checks, what it cannot do.
4. Implement `main()` with `argparse`, real prerequisites, `--json`, meaningful exit codes,
   and a hash/size footer.
5. Add the degraded path for each optional prerequisite, and a flag to force it.
6. Add a test that drives the failure it was written to catch.
7. State the verified/not-verified split in the skill or README that ships with it.

## Related tools in this repository

`hd2-addon-build`, `hd2-addon-package-inspector`, `hd2-ffi-audit`,
`hd2-bingus-toolchain-setup`, `hd2-bilingual-doc-verify`, `hd2-offline-engine-harness` — each
is one tool, with its prerequisites written down, and is a worked example of the rules above.
