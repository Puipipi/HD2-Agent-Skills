# Verification status

English / [简体中文](https://github.com/YC426/HD2-Agent-Skills/blob/main/docs/verification-status_cn.md)

What has actually been run or measured **in this repository**, and what has not. Confidence is
not uniform across these skills, so it is stated per skill instead of implied by the tone of the
prose.

Two rules this file exists to enforce:

1. **A claim is "verified" only if it was run or measured here**, and the entry says how.
   Reading it in someone else's document, or in a shipped mod's source, is **reported**.
2. **Reported is not a lesser kind of wrong — it is simply untested here.** Several skills are
   reorganisations of a contributor's notes, and that contributor says plainly that not
   everything has been tested and some of it needs someone else to test it. Those are marked so
   the next person knows where to start.

## The three levels used

| Level | Meaning |
|---|---|
| **verified** | executed or measured here, and the entry names the command, file or measurement that did it |
| **reported** | reproduced faithfully from a source, no test here. The source may or may not have tested it. |
| **build-bound** | true for one game build, mod version or date. Not portable; re-derive it. |

## Skills

| Skill | Status | Evidence, or what is missing |
|---|---|---|
| `hd2-addon-build` | **verified** (gates) / **reported** (the format) | Ran it end to end on a fixture: all five gates pass on a clean source, and each gate was shown to *fail* when provoked — a `user32` declaration, a missing README block, and a script-like file in the archive each produced exit 1. The envelope format itself comes from the loader's tools, not from here. **Not verified:** that a manager imports the artifact. |
| `hd2-addon-package-inspector` | **verified** | Its name→hash implementation matches all three of the loader's published test vectors, and the tool now fails if it does not — demonstrated by corrupting a vector. Ran it against a real package built here (OK) and against a repackaged third-party mod (OK). |
| `hd2-ffi-audit` | **reported** | The scanner was run on our own skeleton and on one mod source. Its rules come from real breakage recorded in the workspace; the code was not re-derived from the loader. **Not verified:** that it catches a macro- or typedef-mediated symbol, which its own limitations section says it does not. |
| `hd2-bingus-toolchain-setup` | **verified** (search) / **not verified** (copy + build) | Confirmed it locates a complete tool set on this machine and reports a readable checklist. **Not verified:** the copy-then-build loop, and the `--url` path — neither was executed. |
| `hd2-offline-engine-harness` | **verified** | 24 checks pass on real LuaJIT 2.1 against a fake engine; the four engine states and the error budget were each exercised. It found two real bugs in the skeleton it tests (a `local` out of scope, and a `pcall` arity truncation), which is the strongest evidence it works. **Not verified:** anything about the real engine. |
| `hd2-bilingual-doc-verify` | **verified** | Runs clean over 12 document pairs. Both of its failure modes were demonstrated deliberately: a removed switcher, a switcher pointing at the wrong file, and a corrupted hash vector each fail the run. |
| `hd2-live-memory-probe` | **reported** (pattern) / **partly verified** (implications) | The technique is drawn from probe/checker pairs in this workspace. **Verified here:** that the on-disk `game.dll` cannot be scanned (its sections are blanked and ~7.9998 entropy, and a known signature is absent) — see `hd2-mod-failure-catalog.md` §5. **Not verified:** the probe skeleton itself has never been run against a live game. |
| `hd2-mod-log-analysis` | **reported** | Written from a real incident (a mod silent for 165 sessions) and the analyzer that resolved it. The tool pattern is not a shipped script here, so nothing was executed. |
| `hd2-no-quarantine-packaging` | **reported** (mechanism) / **verified** (the gate) | The mechanism is read from SmoothBoot's source (`provision_tools()`, `wr()`, the generated batch) — not reproduced by running it. **Verified here:** build gate 5 refuses an archive containing a script and deletes it before raising. **Not verified:** that a mod-site scanner accepts the resulting archive. |
| `hd2-bingus-mod-development` | **verified** (structure) / **reported** (paths) | The pipeline shape matches how the mods here were built and the build gates were exercised. Deployment paths, slot numbers and log locations are **observed values from one install** — re-derive them. |
| `hd2-mission-entry` | **reported** | Coordinates and failure modes come from real runs recorded in the workspace. Its three input tools compile, import and expose their entry points, **but their clicking and focusing behaviour needs the game running** and has not been tested here. The mod prerequisites were read from installed manifests. |
| `hd2-in-game-panel` | **reported** | A reorganised technique from Custom Armor Kit's own source, with the native-crash evidence quoted from its logs. The panel was not rebuilt or run here. |
| `hd2-native-panel-input-lock` | **reported** | From Super Earth Armory Forge v6.2.1 and, for the cursor and filter code, SHODAN Stat Editor. The provenance section states which parts are copyleft; nothing was executed. |
| `hd2-game-language-autodetect` | **reported** | The two detection methods are reorganised from our mods' source. The offline test seam exists in `mods/custom-armor-kit/work/standalone/test_armor_controls.py` and asserts the chain including "an unreadable setting preserves the last known value" — **read, not run, in this repository**, so this row stays reported. |
| `writing-mod-tools` | **verified** (rules) / **reported** (the incidents) | Every rule is drawn from a failure with a file and line, and several were re-encountered while building the tools in this repository — which is why the numbers are trustworthy. The incidents themselves are quoted, not re-run. |
| `hd2-offline-data-workflow` | **reported** | Reorganised from `junze0910/junze-hd2-lua-mod` (MIT). The author states that not everything has been tested. Two claims were checked here: the `game.dll` scanning restriction, and the hash constants via the inspector's vector self-test. One claim could **not** be checked — the byte-identity of the in-memory `generated_entities.dl_bin`, because the file is absent. |
| `hd2-injection-runtime-patching` | **reported** | Same source. **Nothing in it has been executed or re-measured here.** Every section is in-game work that needs a running game. |
| `hd2-mod-release-operations` | **reported** | Same source. The archive layout is verified *by the author's round trip*, not here; it is merely consistent with what this repository's own builder produces. Environment-specific values carry their own marking in the skill. |

## What this means for a contributor

If you are picking this up: the **reported** rows are where your testing is worth the most, and
they are ordered above roughly from "needs a running game" (hardest, most valuable) to "needs
only a fixture" (easiest way to start).

- Cheapest useful first step: run `hd2-offline-engine-harness` and `hd2-addon-package-inspector`
  against your own mod — they need no game.
- Highest value: anything in `hd2-injection-runtime-patching` and `hd2-offline-data-workflow`,
  because those rest entirely on one person's notes and a live game is the only way to confirm
  them.
- When you do test something, please say **what build and what mod version** — several of these
  facts are build-bound, and a confirmation without a build number is much less useful.

## Provenance

- Contributor notes: [`junze0910/junze-hd2-lua-mod`](https://github.com/junze0910/junze-hd2-lua-mod)
  — MIT, `Copyright (c) 2026 DSH`.
- Reference implementations cited per skill: Custom Armor Kit 2.5.10, SmoothBoot 3.0.x,
  Super Earth Armory Forge v6.2.1, Stratagem Cooldown 2.1.x, melee-vehicle-rescue,
  mobility-optimization.
- The v18 loader contract material (shared LuaJIT code cache, archive layout, fingerprint
  constants) comes from a delivered package that read 20 upstream repositories. **Those
  repositories have no repository-wide licence** — "No repository-wide license has been
  selected" — so no code from them is copied into this repository; only facts, with their
  sources named.
