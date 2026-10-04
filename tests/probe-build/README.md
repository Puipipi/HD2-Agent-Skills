# Pipeline probe — the one thing left to verify in-game

Everything in the `hd2-bingus-mod-development` skill is verified offline: the four
build gates, the packaging, the offline harness, the translation checks. The
**import + load** path is the only part no simulation can cover, because it needs
the real mod manager and the real game.

This folder closes that gap.

| File | What it is |
|---|---|
| `Bingus-Pipeline-Probe-0.1.0.zip` | The package to import. SHA-256 `9D80923035055AE70968586500229C0427547BFD57974B5039DB1FC4637007F4`. |
| `bingus_pipeline_probe.lua` | Its source — read it before you run it. |
| `build_probe.py` | The exact build script that produced the ZIP. |
| `test_probe.py` | The offline check that the ZIP matches this source. |

## What the probe does

Nothing gameplay-related. It **draws nothing, patches nothing, writes no game
data**. Its entire job is to leave evidence that a mod produced by this pipeline
loaded and ran:

- writes `Logs/BingusPipelineProbe.log` when it loads
- writes `Logs/BingusPipelineProbe-STATUS.txt` on load and on every stage change
- walks four staged preconditions (ffi surface → engine table → ship world →
  GUI resolution) and logs each hold reason by name
- logs `PIPELINE OK: all stages reached` once the engine is ready

Safe to delete: remove the mod folder and the two files under `Logs/`.

## Verify it (about one minute of your time)

1. **Import** `Bingus-Pipeline-Probe-0.1.0.zip` through the mod manager's normal
   import. This is the step under test — the manager parses `manifest.json`,
   registers the GUID and unpacks the addon.
2. **Enable** it and deploy (the manager's deploy writes the loader's data into
   the game folder). Do not enable anything else that was off before, so a crash
   would be attributable.
3. **Launch the game** and wait for the ship (15–25 s), then ~30 s more.
4. **Read the log**:
   ```powershell
   Get-Content "$env:LOCALAPPDATA\CowboyBingus\Helldivers2\Logs\BingusPipelineProbe.log" -Tail 20
   ```
5. **Report back** which of these you saw:
   - `enter version=0.1.0 (pipeline probe)` → the loader loaded it ✅
   - `PIPELINE OK: all stages reached` → it ran against the real engine ✅
   - only `stage N (...) held: <reason>` → it loaded but a precondition was not
     true yet. **The reason names the problem** — that line is the useful result,
     not a failure of the probe.
   - no file at all → the loader never loaded it. Then send
     `Logs\BingusSharedLoader.log` too.

## Why this is worth one minute

It tests the two things this repository cannot simulate:

1. The manager accepts a ZIP produced by `hd2-addon-build` — the manifest
   fields, the `Addon/` layout and the GUID.
2. A source that passes all four build gates actually initialises inside real
   LuaJIT with the game's engine present.

Item 1 is the real risk: importing a package is a different code path from
exporting one, so a valid-looking envelope is not proof the manager will take it.

## What this does not verify

It does not verify that the *skeleton* draws a panel (it draws nothing), nor that
the deployment/rollback procedure in the skill matches your install's slot numbers.
Those are covered by the skill's own "what is not verified" note.
