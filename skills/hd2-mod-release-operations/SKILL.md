---
name: hd2-mod-release-operations
description: Package and publish a Helldivers 2 Bingus/MDL Lua mod — project layout and package naming, multi-resource archives, the fixed seven-step release, GitHub push and Release publication, where the token lives, and the local/sandbox network traps that break HTTPS and proxy access. Use when shipping a HD2 mod, cutting or re-cutting a release, or debugging a failed push, upload or 403.
---

# HD2 mod release operations

> **Confidence:** reported; §1 lists the per-item status, including what is environment-specific.

English / [简体中文](https://github.com/YC426/HD2-Agent-Skills/blob/main/skills/hd2-mod-release-operations/SKILL_cn.md)

This is the operations half of HD2 mod work: how the project is laid out, how the package is
named and archived, the seven steps a release actually consists of, and what breaks on the
network. Every number below is evidence from one author's machine and repository
(`junze0910/junze-hd2-lua-mod`, MIT); where a value is local rather than general it says so.

**None of it has been executed in this repository either.** It is a reorganisation of that
author's notes, who states that not everything there has been tested. See §1 for the per-item
status. Two things about the archive format *are* independently checkable here and were checked:
this repository's own build produces and inspects packages with the same envelope, and the
name→hash function matches the loader's published vectors.

## 1. Scope and provenance — read this before trusting a number

| Item | Status |
|---|---|
| Proxy address `127.0.0.1:6382` | **Environment-specific, measured 2026-10-03** on the author's machine. Re-read the registry (see §10) instead of hardcoding it. |
| `Invoke-RestMethod` / `curl.exe` HTTPS failure | **Sandbox/host-specific**, not a general Windows rule. On this host the certificate store is locked, so every PowerShell HTTPS client fails; on a normal machine it may work. |
| Dates in §8 and §3 (`2026-10-02`, `2026-10-04`) | Dated incidents, kept because they explain why the rule exists. |
| Manifest GUIDs quoted as `2b8e6c51-…` / `7f2c8a04-…` | Truncated in the source; they are mod identities, not secrets. |
| `.patch_N` byte layout (§6) | Verified by the author's own round trip, **not re-verified here**. Consistent with the envelope this repository's build script produces and its inspector parses — but that is agreement, not proof. |

## 2. Project layout and the two artifact lines

Per-mod layout — conventional, so the build and release lines stay consistent:

```
<mod>/
  src/            main sources (split-out modules also live here)
  build.py        packaging (default output -> hd2-mod\build\; --release also copies into dist\)
  guid.txt        stable GUID, kept next to the sources
  DESIGN.md       engineering notes (design detail goes to hd2-mod\docs\)
  test/           offline regression (lupa, no game required)
```

Two artifact lines, never mixed:

| Path | Role | Tracked |
|---|---|---|
| `hd2-mod\build\` | working build area; the current version zip sits directly in the root | untracked |
| `hd2-mod\build\_deprecated\` | abandoned artifacts, whose names carry the reason | untracked |
| `hd2-mod\build\_old\` | earlier artifacts | untracked |
| `hd2-mod\build\_probes\` | recon / probe packages | untracked |
| `junze-hd2-lua-mod\dist\` | release area, distributed with the git repository plus `SHA256SUMS.txt` | **tracked** |

Do not create your own `dist/` or `build/` inside a mod subdirectory — a mod-local `dist/`
fights the tracked release line.

## 3. Naming: package, archived artifact, GUID

| Rule | Value / form | Why it exists |
|---|---|---|
| Package name | `<Mod-Name>-v<X.Y.Z>.zip`, **pure ASCII** | The mod manager uses the manifest `Name` as a folder name; Chinese characters produce 「目标名/目录名或卷标语法不正确」 and the install fails |
| Never overwrite a previous package | Move the old package into `_deprecated\` with the reason. On **2026-10-02** the package showing "page 5 tab crashes" was overwritten and the evidence was lost | An overwritten artifact cannot be re-diagnosed |
| Skip archiving identical rebuilds | Write to `.tmp` first, byte-compare with the existing artifact; byte-identical means **do not archive** | Otherwise `_deprecated` drowns in noise for a rebuild that lost nothing |
| Archive name | `<original name>_被同名重建覆盖_<timestamp>[_index].zip` | The timestamp is second-precision only, so same-second rebuilds collide — a sequence number is mandatory |
| Deprecated names state the reason | `AC8-Rack-Backpack-v1_census无门控+漏WriteCopy.zip`, `TD-110-Co-Op-v1.3_复查有bug.zip`, `TD-110-Co-Op-v1.7_射界未收紧.zip`, `More-Balanced-Exosuit-Emancipator-v1.0_兜底无退避.zip` | Without the reason in the name, the same mistake gets repeated |
| Manifest GUID | Never changes (e.g. AC-8 `2b8e6c51-…`, 实弹狗 `7f2c8a04-…`) | A changed GUID makes the manager treat an upgrade as a new mod, installing side by side with the old version |
| Patch slot number | Never hardcode `patch_N`. HD2 Mod Manager allocates and re-orders slots itself (measured: installing one new mod shifted the numbers of other mods). For a manual install take the current maximum number **+ 1**, then identify your own archive by timestamp / size | A hardcoded slot broke when the manager renumbered mods |

## 4. The addon envelope and discovery

The first line of the entry file must be:

```lua
-- HD2-Addon: mods/<author>/<module>
```

- No BOM, within **256 bytes**, and **plaintext**. Compiling to bytecode drops this comment
  line, which breaks automatic discovery — a bytecode-compiled addon was never discovered.
- To ship a bytecode implementation anyway, package **two resources** and make the entry
  `return require('..._impl')`.
- The loader's job is discovery + `require` + logging. It **never modifies memory**; the memory
  work is the addon's own code. Misattributing a memory write to the loader means debugging the
  wrong component.

Build command for an installable ZIP:

```powershell
python tools/build_addon.py --name mods/<author>/<name> --entry x.lua --guid <stable UUID> --display-name "name" --output build/X.zip
```

## 5. Multi-resource archives

Only the **entry** carries the `-- HD2-Addon:` declaration. Loader discovery (`discover.lua`)
accepts only "declared name == resource name hash", so declaring modules as well turns each
module into an independent addon — N separate mods in the manager.

- **Do not use `tools/build_addon.py --extra` for multi-resource packaging**: it also adds a
  declaration header to every extra. Write your own script.
- After packaging, read the archive back and confirm only the entry carries the declaration.
- Modules without the declaration can be compiled to bytecode (smaller and faster).
- Reference example: `hd2-mod/junze-hd2-lua-mod/menu-panel/` = **6** resources (entry + 5 modules).

## 6. `.patch_N` archive format (byte level)

The carrier file is `data/9ba626afa44a3aa3.patch_<N>`.

| Offset | Size | Layout |
|---|---|---|
| `+0` | 72 bytes | `<III20sQQ24s` = magic `0xF0000011`, `1`, count, 20×0, totalSize (Q), `0`, 24×0 |
| `+72` | 32 bytes × types | `<IIQIIII` = `0, 0, typeHash, count, 0, 16, 16` — this `count` drives the descriptor table size |
| `+104` | 80 bytes × count | `<7Q6I` = `nameHash, typeHash, offset, 0, 0, 0, 0, length, 0, 0, 16, 16, index` |

Data area = `align16(104 + 80*count)`; each resource is 16-byte aligned. A resource body is
`u32 bodyLen + u32 version(=2) + body`.

Resource type markers:

- Lua resource type tag = `0xA14E8DFA2CD117E2`
- The resource occupied by the loader = `core/wwise/lua/wwise_flow_callbacks` = `0x7251FDD9BB62480A`

Both are needed to recognise a Lua resource inside an archive and to stay off the loader's own
resource.

## 7. The release checklist (the fixed seven steps)

1. **Edit `local VERSION` in the source** — the single source of truth. Then
   `python tools\build_mod.py --list` to see the key names, then `python tools\build_mod.py <key>`.
   Scanner uses its own `hd2-scanner\build.py` (multi-resource archive). Neither overwrites: the
   same name or an old version automatically goes into `build\_deprecated\`, and byte-identical
   content is neither rebuilt nor archived.
2. **Copy the new package into `dist\`**; move the superseded old package into
   `build\_deprecated\from_dist\`.
3. **Recompute `dist\SHA256SUMS.txt`** — lowercase hash + **two spaces** + file name, so
   `sha256sum -c` works on it directly.
4. **Update `README.md`** (install table + release-line description) and **`RELEASE-NOTES.md`**
   (new section; the publish script extracts the body from here).
5. `git add -A` → commit (Chinese, with a `release:` / `docs:` prefix) → `git tag -a <tag> -m "…"`.
6. `push` — **must go through the proxy**, see §10.
7. `python tools\gh_publish.py` (creates the Release for that line, attaching only that line's
   packages and its own `SHA256SUMS.txt`; repeatable), then `python tools\gh_verify.py`.

Release lines and tags:

| Line (tag prefix) | Meaning |
|---|---|
| `core` | prerequisites |
| `infantry` | infantry |
| `vehicle` | vehicles |
| `logistics` | logistics, reserved |

Tags look like `core-v2.0`. **Tag version ≠ package version** — packages evolve independently
(AC-8 is 2.0, Scanner is 0.7.0). Per-line tagging is what lets independent packages release on
their own cadence.

## 8. GitHub Release mechanics

| Rule | Detail | Why |
|---|---|---|
| `gh_publish.py` never overwrites a same-named attachment | It uploads only names that do not already exist; a same-named attachment (especially `SHA256SUMS.txt`) is skipped. Whenever the attachment set changes (version change, deleted old package), **first delete the same-named / extra old attachments on the release page**, then run it | Stale checksum file listed packages that no longer existed (hit on **2026-10-04**) |
| `gh_verify.py` compares API digests | It uses `assets[].digest` and does not download attachments, because the proxy's TLS to `objects.githubusercontent.com` is frequently broken (the downloading version gets SSL EOF) | Attachment downloads failed through the proxy; the digest path is faster and unaffected |
| A tag's pointer is not recyclable | Once pushed, do not delete a tag or change what it points at — no `git tag -f` + force push. An empty release line occupies only a tag plus a placeholder Release, with no packages (`logistics-v0.1alpha` was left that way) | Moving a tag breaks reproducibility of what a release contained. *(Conflict: this contradicts the common habit of force-moving a tag to fix a release; the source keeps the prohibition.)* |
| Release content above a tag is mutable, with one caveat | Swap attachments for a patch package: delete the old attachment → upload the new package → recompute that line's `SHA256SUMS.txt`; title and body can also change — leave a line `附件已更新（日期）` in the body. `tools\gh_refresh_releases.py` is idempotent and re-runnable. **Caveat:** the "Source code (zip)" snapshot is the tree as of the tag, so download links in the body must point at the **`main` branch's `dist/`**, not at the tag snapshot | The tag snapshot is frozen, so links into it hand users stale packages |
| Two ways to re-cut, do not mix | Mutable release content (above) **or** a new patch tag (e.g. `infantry-v2.0.1`), which is useful when users should still be able to get the old package | Both work; mixing them leaves users unsure which artifact is current |
| Do not use `git push --tags` | A historical mistyped uppercase `V1.0` tag still exists locally | Pushing all tags would publish the mistyped tag |

## 9. Where the token lives

Keep the token in a **secrets directory outside the workspace**, never in the repository:

- That directory has its own `.gitignore` containing `*`.
- The first non-comment line of the token file is the token.
- Scripts read the environment variable **`GH_PAT`** first and fall back to that file.
- Never write the token into a skill document, and never echo it: when you must show a command
  that carries it, replace the credential with `***`. Keeping the token out of the repo is what
  prevents accidental publication.

Scope pitfalls:

| Token | Result |
|---|---|
| Classic token (scope `repo`) or a fine-grained token | Both work |
| Fine-grained token limited to this repository with `Contents: Read and write` | Cleanest |
| Any read-only scope | **Always 403**: the API reports `Resource not accessible by personal access token`, git reports `denied to <user>` |
| Repository access set to `Public repositories (read-only)` | Reading public repositories still works, writing never does |

A read-only-scoped token produces 403s that look like permission or network problems — check the
scope before debugging the network.

## 10. Network traps (local and sandbox)

**Trap 1 — PowerShell HTTPS is broken on this host (sandbox/host-specific).** The certificate
store is locked — `schannel: AcquireCredentialsHandle failed: SEC_E_NO_CREDENTIALS` — so even
`https://github.com` returns `HTTP=000` from `Invoke-RestMethod` / `curl.exe`. For outbound
access use **only git (bundled OpenSSL) and python (bundled OpenSSL)**. This is a property of
this sandboxed machine, not a general Windows rule.

**Trap 2 — the proxy lives only in the WinINET registry.** It is set by the VPN client, and it is
in neither environment variables nor git config:

```
HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings -> ProxyServer
```

Measured **2026-10-03** as `127.0.0.1:6382` (a dated, machine-specific value — re-read the
registry). Per-tool injection:

```powershell
git -c http.proxy=http://127.0.0.1:6382 push <url>
$env:HTTPS_PROXY='http://127.0.0.1:6382'    # python
```

Without this, git and python have no proxy configured and cannot reach GitHub at all.

**Trap 3 — push with a one-shot inline credential, never persisted.** The URL shape is
`https://x-access-token:<token>@github.com/junze0910/junze-hd2-lua-mod.git`: it authenticates the
push without writing the token into git config. When echoing such a command, replace the token
with `***`. `sh.exe: couldn't create signal pipe` is MSYS noise and can be ignored.

## 11. Diagnostics that must reach disk

Only the release-facing half of logging belongs here — what has to exist on disk after a run, and
where a user finds it.

| Rule | Detail | Why |
|---|---|---|
| Shared log directory | `%LOCALAPPDATA%/CowboyBingus/Helldivers2/Logs` | Fixed location used by the loader and by mods writing logs |
| `loader.open_log` accepts **only** `.log` names | The loader checks `if type(name) ~= 'string' or not name:match('^[%w_-]+%.log$') then return nil end`. `.txt` and every other extension return `nil`, and a caller wrapping that in `pcall` gets a silently missing file. Use `.log` for every dump, e.g. `SSProbe_dump.log` / `SSProbe_table.log` | The main log worked while dump files never appeared — check the file-name rule before suspecting the scan logic |
| Bulk diagnostics bypass the log ring | Send batch diagnostic output through a separate `dump()` that writes straight to disk | The 400-line ring cap silently ate census / dump content |

## 12. Unresolved

Nothing in the release, packaging or release-facing logging material conflicts with itself. The
one preserved contradiction is the tag rule in §8: the source forbids force-moving a tag while
noting it is the common habit — the prohibition is kept, the habit is not reconciled with it.
