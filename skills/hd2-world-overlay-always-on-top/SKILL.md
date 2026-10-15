---
name: hd2-world-overlay-always-on-top
description: "Keep HD2 world-space lines visible and distinguish line overlays from filled geometry."
---

# HD2 world overlays that stay on top

English / [简体中文](https://github.com/Puipipi/HD2-Agent-Skills/blob/main/docs/skills/hd2-world-overlay-always-on-top_cn.md)

First identify what “on top” means: screen-UI draw order, world-space depth testing, or triangle back-face culling. They are separate mechanisms. Raising a UI layer does not disable world depth testing; reversing triangle winding only affects back-face visibility and does not reveal a face hidden behind an object.

In the inspected Eagle source, world lines have distinct depth and perspective paths. The main line object is created with `World.create_line_object(world, false)` and is used as the depth-tested path; a separate perspective line object uses `World.create_line_object(world, true)`. For each update, call `LineObject.reset(line)`, add each segment with `LineObject.add_line(line, color, a, b)`, then submit with `LineObject.dispatch(world, line)`. Sparse dashed lines are produced upstream by splitting source edges into segments; `add_line` submits a segment and does not create a dash pattern itself.

The example's `sr` is an engine API table already obtained by the project. `world`, `color`, and endpoints `a` and `b` must be valid engine objects in a valid render context. This snippet shows call order; it is not a standalone mod:

```lua
local line = sr.World.create_line_object(world, true) -- separate perspective batch
sr.LineObject.reset(line)
sr.LineObject.add_line(line, color, a, b)
sr.LineObject.dispatch(world, line)
```

Put lines that should remain visible into a separate perspective batch; put normally occluded lines in the main batch. If components have independent toggles, apply each toggle while assembling that component's perspective batch. Eagle's `through_air`, `through_sky`, and `through_ground_triangles` options are examples of selecting a line path per component. The toggle variable alone does not change another renderer's depth state.

Filled geometry uses a different path: `World.create_world_gui(world, pose, 1, 1)` creates a WorldGUI, `Gui.triangle(gui, a, b, c, 100, color)` submits a triangle, and `Gui.update_triangle(gui, id, a, b, c, 100, color)` updates an existing face. A WorldGUI triangle fill can depth-occlude normally: in one inspected build, its native material pipeline's `depth_test_enabled` state was verified to hide the fill behind scene geometry. This is material state, not a verified `Gui.set_depth_test` API or a universal WorldGUI option. The literal `100` is a passed argument; it is not evidence of a depth control. A component's perspective toggle wired only to line batches does not automatically change fill-material depth behavior. Treat `rect_3d` as a separate candidate path and verify its own selected material and occlusion behavior before claiming the same result.

To change fill occlusion, first identify the exact material resource and build, then verify its schema, the field definition, and how the renderer selects that material. Compare the same geometry with the relevant depth state changed while keeping the rest of the resource and render setup fixed; exercise occluded, visible, perspective, and disabled cases. Do not infer a field from an opaque byte offset, copy an offset from another build, or invent a public GUI API. Preserve unrelated native resource bytes when making a targeted material change.

This path also assumes `sr`, `world`, `pose`, vertices, and colors are valid engine objects in a valid context; it is not a standalone example.

```lua
local gui = sr.World.create_world_gui(world, pose, 1, 1)
local id = sr.Gui.triangle(gui, a, b, c, 100, color)
```

Eagle's fill renderer submits reversed-winding triangles for two-sided visibility. That only covers back-face culling differences and remains subject to the fill material's world-depth behavior. If the desired result is a dashed outline where fill is occluded, source the lines from the component's original boundary; do not treat triangulation diagonals as outlines. `LineObject.add_line` has no width parameter in the observed interface. Parallel strokes can approximate a meter-wide band, but they remain discrete lines rather than a native thick line or filled face; test visible gaps and account for the extra segment and draw cost at every supported width.

In the verified outline implementation, dash the semantic boundary first using cumulative world-space arc length, then expand those dash segments into parallel strokes so every lane shares the same dash phase. This is one tested construction pattern, not the only valid way to keep a wide dashed border aligned; avoid generating an independent dash pattern for each width lane.

The verified solid-with-occluded-dashes composition uses depth-tested fill material plus two line passes built from the same semantic boundary: a continuous depth-tested cover and an always-visible dashed copy. In this implementation the dashed pass dispatches first and the cover second, so visible portions stay continuous while the depth-hidden cover leaves only the dashed copy visible behind an occluder. This is renderer depth behavior, not CPU classification of hidden segments or a general mask API. Preserve the shared geometry and width, verify the target material and pass behavior, and test visible and partially occluded portions, the component toggle, and cleanup. Do not assume arbitrary material blending or submission order behaves the same.

Clean up persistent objects to avoid residue after hiding the overlay or changing worlds. Reset a reused line object first; destroy it when no longer needed. The WorldGUI `clear` path destroys retained triangle IDs; `release` destroys the GUI and clears its handle. The observed destroy calls are `World.destroy_line_object(world, line)` and `World.destroy_gui(world, gui)`. Confirm the world/GUI is still valid before destruction and follow the project's lifecycle guards.

## Evidence boundary

The line-batch, WorldGUI, and cleanup signatures are build-specific examples and should be verified against the target API. Separately, the material depth-state result for one inspected triangle-fill resource/build was verified; it does not establish a universal material field layout or GUI API. No generic depth-fix parameter or `Gui.set_depth_test` function has been established.

**Provenance:** These implementation notes were checked against the audited `HD2-EagleDirectionProbe` 1.10.0 release source. Its `eagle_direction_probe.lua` main file has SHA-256 `7562c947f525d915e3f1a0198556e736b56a0f76508a522a986cbb2e3ffdf8c2`; related outline and fill-renderer code is in `occlusion_outline.lua` and `solid_renderer.lua`. A human also verified partial-occlusion behavior and cleanup in game. No game fingerprint is recorded here, so treat the resource/build behavior as case-specific and re-verify it for another target.
