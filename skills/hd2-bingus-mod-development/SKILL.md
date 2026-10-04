---
name: hd2-bingus-mod-development
description: Develop, validate and package a Helldivers 2 Lua mod for the Bingus/MDL loader — repo layout, the LuaJIT compile and FFI gates a build must run, offline simulation with lupa, the addon envelope ZIP a mod manager can import, deployment paths and rollback, in-game log evidence, and the release discipline that stops an unverified build from being called done. Use when creating a new HD2 mod, adding a feature to one, packaging a release, or setting up the build pipeline that does all of it.
---

# HD2 Bingus mod development

> **Confidence:** the pipeline structure was exercised here; deployment paths, slot numbers and log locations are observed values from one install — re-derive them.

English / [简体中文](https://github.com/Puipipi/HD2-Agent-Skills/blob/main/skills/hd2-bingus-mod-development/SKILL_cn.md)

The pipeline that produced the mods in this workspace. A HD2 mod is **not** "write Lua and
drop it in the game folder" — it is:

> 独立 git 仓库 → 纯文本 LuaJIT 源码 → 离线沙盒自检 → 信封包 ZIP → 管理器手动部署 → 实机日志取证

and it has a hard release discipline: a build that fails its gates **deploys nothing**, and
no change counts as done until it has run in the real game.

Two related skills carry the parts that are about *what breaks* rather than *how to build*:
[`docs/hd2-mod-failure-catalog.md`](../../docs/hd2-mod-failure-catalog.md) (symptom → cause)
and the code-level techniques in `hd2-in-game-panel`, `hd2-native-panel-input-lock`,
`hd2-game-language-autodetect`. Read this skill for the pipeline; read those for a feature.

---

## 1. Repo layout

One mod, one git repo. Keep the source, the build and the tests together so the build can
gate on the tests.

```text
mymod/
├─ README.md                  bilingual status: what is verified, what is not
├─ THIRD_PARTY_NOTICES.md     what you depend on and may not redistribute
├─ work/standalone/           the build lives here (this is the upstream convention)
│  ├─ mymod.lua               the mod source: plaintext UTF-8 Lua, no BOM
│  ├─ build_mod.py            gates + packaging  (see template/build_mod.py)
│  ├─ vendor/bingus/          build_addon.py + archive.py — SUPPLIED SEPARATELY
│  ├─ test_*.py               offline tests, one file per feature
│  └─ fixtures/*.lua          captured reference Lua the tests replay
└─ dist/                      built ZIPs (and nothing else)
```

`vendor/bingus/build_addon.py` and `archive.py` encode the loader's addon envelope and are
**third-party tools you obtain from the loader author, not files you write or redistribute**
— this workspace deliberately keeps them out of its published snapshots. Get them once and
treat them as a build dependency, like a compiler.

Python side: `python -m pip install lupa` (LuaJIT inside CPython). `requirements-dev.txt`
should pin it.

## 2. The source contract

These are enforced by the loader/builder, not preferences. Violating them either fails the
build or breaks *someone else's* mod:

| Rule | Why |
|---|---|
| `-- HD2-Addon: mods/<author>/<entry>` is the first line | The builder writes it from the resource name; if it is already there it must match exactly. ≤ 256 bytes including the newline. |
| Resource name matches `mods/[A-Za-z0-9_]+/[A-Za-z0-9_]+(/...)*` | Letters, digits and **underscores** only — no hyphens. `mods/codex/loader` is reserved. |
| Plaintext UTF-8, no BOM, no `\0`, no Lua bytecode | The builder rejects all of these. |
| **No `user32` symbol in any `ffi.cdef`** | LuaJIT's C namespace is process-global and `ffi.cdef` keeps the **first** declaration. Declaring `GetCursorPos` with a different prototype silently disables every mod that declared it first — one mod disabled itself for a whole session this way. Declare `kernel32`/`bcrypt` symbols; if you need the cursor, do not redeclare it. |
| Cached module table: `if rawget(_G, KEY) then return rawget(_G, KEY) end` | The loader may re-run your entry; without this you get two copies of your state. |
| Single source of truth for the version | The build reads `version='x.y.z'` out of the source and names the ZIP from it. Do not bump a version in two places; the build asserts the one it finds. |

Ship the in-game README **inside the source** in a long-bracket block
(`[===[My Mod - quick guide ... ]===]`) and have the build extract it into `README.txt`.
Then the guide can never drift from the code.

Runtime paths the mod should use (create the directory yourself with `CreateDirectoryW` via
FFI, never by spawning a shell from the update thread):

```text
%LOCALAPPDATA%\CowboyBingus\Helldivers2\          log + config root
  Logs\<Mod>.log                                  append-only, across launches
  <Mod>\config.txt                                user options
  <Mod>\<Mod>-STATUS.txt                          written even when nothing works
```

## 3. The gates (what a build must refuse)

`hd2-addon-build` implements all of them; adapt its CONFIG block rather than writing your
own.

| Gate | Check | Failure it prevents |
|---|---|---|
| **LuaJIT compile** | `lupa.luajit21.LuaRuntime().compile(src)` | The 65535-instruction-per-function cap makes the loader **silently skip** an oversized mod, while a plain-Lua compile says OK. This is a real shipped "mod loads but does nothing". |
| **No user32 declaration** | scan every `ffi.cdef` block for the user32 symbol set | Displacing another mod's declaration (see §2). |
| **Called ⊆ declared** | every `k.Foo(` / `u.Foo(` call has a declaration | `missing declaration for symbol 'X'` is a hard error at the call site; it once shipped as "clicking the card does nothing". |
| **README block present** | the `[===[...]===]` marker exists | A release with no in-game guide. |

Run `--validate-only` on every save; it stops before packaging.

```powershell
python -B work/standalone/build_mod.py --validate-only
```

## 4. Offline tests: simulate the engine, not the game

You cannot unit-test the game. You can test your code against an **engine boundary**, which
is where the expensive bugs live. `lupa.luajit21` gives you the real LuaJIT:

- **Fake the engine table** (`stingray`) and count the calls that matter
  (`create_screen_gui`, `destroy_gui`, `Gui.move`). Assert *counts*, not just "no error":
  two frames must create exactly one GUI.
- **Replay captured Lua fixtures.** `work/standalone/fixtures/*.lua` hold the reference
  functions the mod adapts (e.g. a game UI consumer); the tests run the original and your
  adapter against the same synthetic state and compare results and read counts.
- **Differential tests are the strongest kind here.** "Original: 189 native reads;
  adapter: 53; every observed field identical" is a claim you can verify offline. Write it
  that way, and keep the fixture under version control.
- **Test the failure paths**: option off, exclusion, unknown function fingerprint, read
  fault, reload. A mod that only restores correctly on the happy path will strand users.
- **Assert the observables you will quote**: callback counts, every return value including
  trailing `nil`, allocation deltas, and that a *stationary* panel performs zero native
  calls.

Then keep the test list explicit and run it every build:

```powershell
python -B work/standalone/test_sb2.py
python -B work/standalone/test_sb3_autopause.py
python -B work/standalone/test_sb5_interdict.py
python -B work/standalone/ffi_audit.py work/standalone/mymod.lua
```

A test that has been failing for months is worse than no test: this workspace carries two
(`test_smoothboot.py` has 6 known failures; `test_sb4_writerhold.py` requires a different
version) and the rule is to **say so** rather than quietly counting them as passing. If you
cannot fix a stale test, mark it in the README as known-failing with the reason.

## 5. Packaging: the addon envelope

`build_addon.py` turns your source into an archive the loader reads, and wraps it in a ZIP
the mod manager imports:

```text
<Display-Name>-<version>.zip
├─ manifest.json                       Version, Guid, Name, Description, Options[Include:["Addon"]]
├─ Addon/9ba626afa44a3aa3.patch_0      the Lua archive (header + resource entries)
├─ Addon/9ba626afa44a3aa3.patch_0.stream          (empty)
├─ Addon/9ba626afa44a3aa3.patch_0.gpu_resources   (empty)
├─ icon.webp                           only if you actually have one
└─ README.txt                          extracted from the source
```

Rules that matter:

- **One GUID, forever.** `Guid` is how the manager recognises an upgrade instead of a second
  install. Reuse the same UUID for every release of the mod.
- **Never ship a loose `.bat`** inside the archive — mod sites quarantine script files. If
  you need a helper script, write it out at runtime next to `config.txt` (SmoothBoot's log
  collector works this way, and says so in `THIRD_PARTY_NOTICES.md`).
- **Do not publish the "Source code" ZIP** a git host generates automatically; it is not a
  mod package and the manager will not import it.
- If your manifest references an icon, the file must be in the archive. A dangling
  `IconPath` shows a blank entry.

```powershell
python -B work/standalone/build_mod.py                 # -> dist/<Name>-<version>.zip
python -B work/standalone/build_mod.py --with-source   # only for a code-review handoff
```

## 6. Deploy, verify in-game, and be able to roll back

Deployment is a deliberate act, never a side effect. Some build scripts do it behind an
explicit flag (`build_armor.py --deploy`); the contract is:

> **a build that fails any gate does not deploy anything.**

Where files land:

| Target | Path |
|---|---|
| Game patch slot | `...\Helldivers 2\data\9ba626afa44a3aa3.patch_<slot>` |
| Mod-manager library | `%LOCALAPPDATA%\hd2arsenal\mods\<ModDir>\Addon\9ba626afa44a3aa3.patch_0` |

**Know which slot is yours.** Identify it by the declaration inside the layer
(`-- HD2-Addon: mods/<author>/<entry>`). Everything else in `data\` and every other entry in
the manager library belongs to the game or to another author: never read, write or depend
on it. Some build scripts sync both locations; if yours does, still verify both afterwards.

**Rollback before you experiment.** Keep a copy of a build you have actually seen run
without crashing, record its byte size and a hash prefix, and know both paths to overwrite.
If an experimental build crashes the game, restore both copies and restart — do not debug on
a broken install.

The loop, end to end:

```powershell
# 1. edit work/standalone/mymod.lua
# 2. gates + tests
python -B work/standalone/build_mod.py --validate-only
python -B work/standalone/test_sb2.py
# 3. package
python -B work/standalone/build_mod.py
# 4. deploy (explicit), then verify
Start-Process 'steam://rungameid/553850'      # ~15-25 s to the ship
#     observe 60-120 s, then read the logs
```

Redirect build output to a file before searching it — test-runner noise is mixed into
stdout/stderr, so a bare pipe will mislead you.

## 7. In-game evidence

A mod without a log is undebuggable, and a claim without a log is not a result.

- **Log one line per state change**, plus a heartbeat while stuck — never per frame.
- **Write a `-STATUS.txt`** on load and on a heartbeat, so "the panel never opened" still
  produces a file to send.
- **Logs append across launches and are UTC.** To judge "this run", filter by timestamp
  (`12:xx:xxZ` = 20:xx local at UTC+8), not by file position. This has caused real
  mis-readings.
- Read `BingusSharedLoader.log` first: it tells you whether the loader even loaded your
  entry. Then your own log.
- Note in the log by name **why** anything was skipped or held. "blocked" costs hours;
  "held: ship world not resolved" costs seconds.

## 8. Release discipline

This is the part that keeps the project honest, and it is cheap:

1. **Separate "verified offline" from "verified in game".** Every README in this workspace
   says which is which. A simulation result is never an FPS or behaviour result.
2. **Never claim a live result you did not observe.** State the pending item explicitly
   ("live acceptance remains pending").
3. **Keep candidates as candidates.** A dev ZIP is not a stable release.
4. **Say what you did not fix.** Known-failing tests, unresolved reports, unmeasured
   boundaries.
5. **Leave the game in a state you have seen work.** Verify it launches and does not crash
   before you finish.
6. **Only touch your own mod.** Not the game, not another author's files.
7. **Do not change behaviours a user already confirmed** (display timing, hotkeys, defaults)
   without being asked. Fix the thing you were asked to fix.

## Workflow

1. Copy `skills/hd2-addon-build/scripts/build_mod.py`, fill in the CONFIG block (source path,
   resource name, GUID, display name, README marker).
2. Get `build_addon.py` + `archive.py` into `work/standalone/vendor/bingus/`.
3. Start the source from `template/panel_skeleton.lua`
   (staged bring-up, value-check guards, frame error budget, STATUS file, testable seam) —
   it is a package-independent mod skeleton, not a Bingus-specific one.
4. Build features against the code-level skills for the part you are writing.
5. `--validate-only` on every save; write an offline test for each feature.
6. Package, deploy deliberately, observe in-game, read the logs.
7. Update the README's verified/unverified split before you call it done.

## Reference

- `hd2-addon-build` — the build script with all four gates, icon handling and README
  extraction. Adapt the CONFIG block; it runs as-is.
- `hd2-in-game-panel`, `hd2-native-panel-input-lock`, `hd2-game-language-autodetect` —
  features: drawing, input/cursor, localisation.
- [`docs/hd2-mod-failure-catalog.md`](../../docs/hd2-mod-failure-catalog.md) — when something
  breaks: symptom → root cause → fix, including the traps that do not raise.

## What is not verified

The pipeline structure, gate behaviour and packaging format are taken from the mods in this
workspace and the build script here has been exercised end to end (gates pass, packaging
produces a valid envelope, a user32 declaration is correctly refused). The **deploy paths,
slot numbers and log locations above are this workspace's observed values** — re-derive the
slot for your own install from the `-- HD2-Addon:` declaration rather than copying a number.
