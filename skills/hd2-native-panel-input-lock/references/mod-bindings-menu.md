# Mod Bindings Menu: default keys and panel-toggle safety

Use this note when adding a Mod Bindings Menu (MBM) hotkey to an HD2 panel. Verify the current MBM release and the actual consuming mod before choosing a default-key strategy; the details below are verified against MBM v2.2 at commit [`ade82733b3c174bfe120d00c0ca65f551abdacc3`](https://github.com/CowboyBingus/ModBindingsMenu/tree/ade82733b3c174bfe120d00c0ca65f551abdacc3).

## Where defaults come from

The MBM v2.2 contract includes `register_binding(id, label, slot, options)`, `is_down(id)`, `ready()`, the `revision` field, and optional `poll(ids, out)`. `revision` is a field, not a function. In this version, registration has no default-key argument and the API has no query for whether a registered action currently has a user mapping. A successful call allocates or selects an action; it does not by itself bind a key.

Automatic bindings (`slot = nil` or `0`) start unbound. The user must assign a key on the MODS binding page. A fixed slot is a different mechanism: it selects a particular native action whose default mappings may come from MBM's packaged `content/input.config` resource. The MBM build patches that resource for Ship Station Hotkeys' six fixed actions, which explains its Tab, F1, and F5–F8 defaults. The consumer also keeps its own hardware-key fallback for frames where `is_down` returns `nil`; that fallback is not a default mapping installed through `register_binding`.

Do not infer that every fixed slot has a useful default. In MBM v2.2, slots 1 and 3–7 are reserved for Ship Station Hotkeys; slot 2 is the legacy third-party slot. MBM's input-config build leaves `Debugmenu.Open` (slot 2) unchanged, and its sweep removes inherited developer mappings for a registered action except the six MBM-provided keyboard defaults. Slot 2 therefore is not an available, reliable K-default slot. A different mod may also request it, and the API can assign that request automatically instead of preserving slot 2.

## Interpret the API states correctly

- `is_down(id) == nil` means the binding is not registered, native input is unavailable, or this MBM release does not support the current game build. Handle it as unavailable and use the mod's documented fallback if appropriate.
- `is_down(id) == false` means the action is not activated in this sample. It does **not** mean that the action has no mapping; the public API cannot distinguish an unbound action from a mapped action that is currently up.
- When `register_binding` refuses, keep the fallback and report the refusal once. Do not retry every frame. On API versions with `revision`, retry after the revision changes; on older versions without it, retry only when the host table changes.
- If the menu action becomes authoritative after successful registration, stop using the old default key as a toggle source. You may continue sampling it solely to consume stale edges. Leaving both active as toggle sources means the old key still toggles the panel after the user rebinds it. Conversely, keeping a default until the first menu-key press cannot guarantee that the old key is already disabled when the user expects it to be.

If a feature requires a default mapping and also needs to disable its fallback as soon as a user changes that mapping, first confirm that the framework exposes both operations or an equivalent binding-state signal. When it does not, the clean solution requires framework support for setting a first-run default while preserving saved user mappings, or a query/notification for mapping changes. Do not silently claim that a registration-only implementation provides both behaviors. Do not write MBM's assignments file, overwrite the game's input configuration, or add a private native mapping writer to work around the API without explicit authorization and a separate safety review.

## Preserve panel input and test boundaries

Sample the binding state every frame while the panel feature is active, and preserve the existing focus, chat, loading, world-availability, and input-lock guards. When a binding host appears late or is replaced, seed the first valid sample as the prior state; a key already held across initialization or reload must not create a fresh toggle edge. Continue to consume the fallback-key edge while a context gate blocks opening so the key must be released and pressed again after the gate clears.

An offline test may fake MBM's native action-state memory and exercise the real registration-to-panel path. That verifies the mod's state machine and guards, not that the game continues updating native action state while the mod removes keyboard raw input registration. Verify in game that the mapped key opens and closes the panel with the input lock active, and that the previous default key no longer acts after rebinding. If this live check has not happened, say so. The AutoChat v1.1.3 integration was only tested offline and is not evidence of that engine behavior.

## Sources

- [MBM v2.2 README, “For mod authors”](https://github.com/CowboyBingus/ModBindingsMenu/blob/ade82733b3c174bfe120d00c0ca65f551abdacc3/README.md#for-mod-authors): fixed-slot ownership, registration states, `is_down`, optional `poll`, and automatic bindings.
- [MBM v2.2 build source](https://github.com/CowboyBingus/ModBindingsMenu/blob/ade82733b3c174bfe120d00c0ca65f551abdacc3/scripts/build.py#L44-L51) and [input-resource extension](https://github.com/CowboyBingus/ModBindingsMenu/blob/ade82733b3c174bfe120d00c0ca65f551abdacc3/scripts/build.py#L125-L133): which actions receive defaults in the packaged input resource and the preserved third-party action.
- [MBM v2.2 mapping sweep](https://github.com/CowboyBingus/ModBindingsMenu/blob/ade82733b3c174bfe120d00c0ca65f551abdacc3/src/sweep.lua#L33-L38) and [inherited-mapping check](https://github.com/CowboyBingus/ModBindingsMenu/blob/ade82733b3c174bfe120d00c0ca65f551abdacc3/src/sweep.lua#L88-L93): which shipped keyboard defaults survive cleanup of inherited developer mappings.
- [Ship Station Hotkeys](https://github.com/CowboyBingus/ShipStationHotkeys): the reference consumer for fixed slots, hardware-key fallbacks, and menu registration.
