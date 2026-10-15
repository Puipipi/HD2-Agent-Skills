---
name: hd2-mod-release-operations
description: "Package and publish a HD2 Bingus/MDL mod: layout, archives, the seven-step release, GitHub push and Release, network traps. Use when shipping a mod or debugging a failed push or 403."
---

# HD2 mod release operations

> **Confidence:** reported; §1 lists the per-item status, including what is environment-specific.

English / [简体中文](https://github.com/Puipipi/HD2-Agent-Skills/blob/main/docs/skills/hd2-mod-release-operations_cn.md)

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

These paths and the tracked `dist/` layout describe this repository's convention. Follow the
selected mod repository's release contract or the path the user specified; a mod-local `dist/`
or `build/` is not inherently wrong. Preserve existing artifacts and do not relocate or delete
them unless the chosen release procedure calls for it.

## 3. Naming: package, archived artifact, GUID

| Rule | Value / form | Why it exists |
|---|---|---|
| Package name | `<Mod-Name>-v<X.Y.Z>.zip`, **pure ASCII** | The mod manager uses the manifest `Name` as a folder name; Chinese characters produce 「目标名/目录名或卷标语法不正确」 and the install fails |
| Do not overwrite a previous package | Preserve it at its existing or user-selected path. Archive a copy with a reason only when the repository policy or user-requested workflow calls for it. On **2026-10-02** a package showing "page 5 tab crashes" was overwritten and the evidence was lost | An overwritten artifact cannot be re-diagnosed; moving a user-selected artifact can also break the requested output contract |
| Skip archiving identical rebuilds | In workflows that archive rebuilt artifacts, write to `.tmp` first and byte-compare with the existing artifact; byte-identical means **do not archive** | Otherwise `_deprecated` drowns in noise for a rebuild that lost nothing |
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

## 7. Release checklist (adapt these steps to the requested scope)

### Identify the release source and reconcile the version

Record the hash of the reviewed source contents that produced the package. A reviewed, uncommitted
working tree can be a valid source; isolate the reviewed files or use a verified frozen copy when
the tree also contains unreviewed or unrelated changes. Remove temporary captures, automatic
CSV/request pollers, and pure-observation modules from production when they are no longer required;
decide by behavior, not
by a filename containing `probe` or `diagnostic`, since a similarly named module may provide a real
user feature. Recompute source/module inventory counts after cleanup instead of assuming an older
count still applies.

Before choosing a stable version, inspect the repository's tags and release artifacts. Confirm the
candidate follows the project's normal SemVer scheme and that source constants, manifest, startup
banner, ZIP filename, and user-facing README agree. A pre-release tag does not by itself prove that
the matching stable version is already published. For repositories that keep a canonical per-mod
`dist/`, put the release ZIP there; treat copies in research, staging, or Downloads as secondary and
compare their hashes with the canonical artifact.

After packaging, read the ZIP back and verify the complete payload, native resources/sidecars,
manifest identity, and archive integrity. Record the archive hash separately from source hashes.

1. Identify the target mod's version field, builder and output contract. In this repository, edit
   `local VERSION`, use `python tools\build_mod.py --list` to see key names, and build with
   `python tools\build_mod.py <key>`; the scanner uses `hd2-scanner\build.py` for multi-resource
   archives. Those repository-specific builders archive conflicts into `build\_deprecated\`
   and skip byte-identical rebuilds; do not assume another mod uses the same behavior.
2. **Write the package to the selected release path.** Preserve prior packages; archive them
   only if that repository's policy or the user's request calls for it.
3. **Update the checksum file if the repository maintains one.** Keep checksums aligned with the
   package set required by that repository, retain unrelated entries, and do not silently remove
   old ZIPs or their records. If its manifest covers the whole directory, preserve that coverage.
   This repository uses lowercase hashes, two spaces, and one filename per line for
   `sha256sum -c` compatibility.
4. Update install documentation and release notes when the requested release includes them;
   do not expand a local packaging task into a documentation or publication task by default.
5. Review `git status` and stage only the intended release files. Use `git add -A` only when the
   entire worktree has been reviewed and the requested commit is meant to include all of it.
   Create commits and tags only when they are in scope.
6. Push only when requested or otherwise authorized, using the transport configured for the
   current host. The proxy below is one machine's measured setup, not a general requirement.
7. Create or update a GitHub Release only when requested or authorized, then verify its assets.
   The `gh_publish.py` and `gh_verify.py` behavior described here belongs to this repository.

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
| `gh_publish.py` never overwrites a same-named attachment | It uploads only names that do not already exist; a same-named attachment (especially `SHA256SUMS.txt`) is skipped. For an authorized release asset update, remove same-named or extra old attachments before rerunning it; preserve existing assets unless replacement or removal is in scope | Stale checksum file listed packages that no longer existed (hit on **2026-10-04**) |
| `gh_verify.py` compares API digests | It uses `assets[].digest` and does not download attachments, because the proxy's TLS to `objects.githubusercontent.com` is frequently broken (the downloading version gets SSL EOF) | Attachment downloads failed through the proxy; the digest path is faster and unaffected |
| A tag's pointer is not recyclable | Once pushed, do not delete a tag or change what it points at — no `git tag -f` + force push. An empty release line occupies only a tag plus a placeholder Release, with no packages (`logistics-v0.1alpha` was left that way) | Moving a tag breaks reproducibility of what a release contained. *(Conflict: this contradicts the common habit of force-moving a tag to fix a release; the source keeps the prohibition.)* |
| Release content above a tag is mutable, with one caveat | For an authorized release asset update, replace a patch package by deleting the old attachment → uploading the new package → recomputing that line's `SHA256SUMS.txt`; title and body can also change — leave a line `附件已更新（日期）` in the body. Preserve existing assets unless replacement or removal is in scope. `tools\gh_refresh_releases.py` is idempotent and re-runnable. **Caveat:** the "Source code (zip)" snapshot is the tree as of the tag, so download links in the body must point at the **`main` branch's `dist/`**, not at the tag snapshot | The tag snapshot is frozen, so links into it hand users stale packages |
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

**Trap 1 — HTTPS failed in one measured host environment.** There, PowerShell's certificate
store returned `schannel: AcquireCredentialsHandle failed: SEC_E_NO_CREDENTIALS`, and even
`https://github.com` returned `HTTP=000` from `Invoke-RestMethod` / `curl.exe`. First verify the
actual client error on the current host; if it matches, use a working configured client such as
git or python with its bundled OpenSSL. Do not generalize this workaround to other Windows hosts.

**Trap 2 — this host's proxy lives only in the WinINET registry.** It is set by the VPN client,
and on the measured machine it is in neither environment variables nor git config. Other hosts
may have no proxy or a different configuration; inspect the current host rather than copying
the measured address:

```
HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings -> ProxyServer
```

Measured **2026-10-03** as `127.0.0.1:6382` (a dated, machine-specific value — re-read the
registry). Per-tool injection:

```powershell
git -c http.proxy=http://127.0.0.1:6382 push <url>
$env:HTTPS_PROXY='http://127.0.0.1:6382'    # python
```

On that machine, without this configuration git and python could not reach GitHub. Do not assume
the same network failure or proxy requirement on another host.

**Trap 3 — do not put credentials in remote URLs or command output.** Prefer an authenticated
GitHub CLI session, the host's credential manager, or the CI secret mechanism already selected
for the repository. If a task requires a one-shot secret, pass it through a protected input or
environment mechanism supported by that tool; redact it from logs and never persist it in a
remote URL or repository config. `sh.exe: couldn't create signal pipe` was harmless MSYS noise
on the measured host; verify errors on the current host before dismissing them.

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
one source tension retained is the tag rule in §8: it forbids force-moving a tag while noting
that this is a common habit; the prohibition is kept, and the habit is not reconciled with it.
