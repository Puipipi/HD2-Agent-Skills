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

Filled geometry uses a different path: `World.create_world_gui(world, pose, 1, 1)` creates a WorldGUI, `Gui.triangle(gui, a, b, c, 100, color)` submits a triangle, and `Gui.update_triangle(gui, id, a, b, c, 100, color)` updates an existing face. The observed fill path renders through occluders, but the evidence does not establish a generic WorldGUI depth-test/no-depth switch. The literal `100` is a passed argument; do not claim it controls world depth or treat it as a verified fix. A component's perspective toggle wired only to line batches does not automatically change `Gui.triangle` depth behavior. Do not guess private materials, resource fields, or FFI parameters to alter it.

This path also assumes `sr`, `world`, `pose`, vertices, and colors are valid engine objects in a valid context; it is not a standalone example.

```lua
local gui = sr.World.create_world_gui(world, pose, 1, 1)
local id = sr.Gui.triangle(gui, a, b, c, 100, color)
```

Eagle's fill renderer submits reversed-winding triangles for two-sided visibility. That only covers back-face culling differences and remains subject to the fill material's world-depth behavior. If the desired result is a dashed outline where fill is occluded, source the lines from the component's original boundary; do not treat triangulation diagonals as outlines.

Clean up persistent objects to avoid residue after hiding the overlay or changing worlds. Reset a reused line object first; destroy it when no longer needed. The WorldGUI `clear` path destroys retained triangle IDs; `release` destroys the GUI and clears its handle. The observed destroy calls are `World.destroy_line_object(world, line)` and `World.destroy_gui(world, gui)`. Confirm the world/GUI is still valid before destruction and follow the project's lifecycle guards.

## Evidence boundary

These signatures and usage patterns come from Eagle's `src/eagle_direction_probe.lua` (line object creation, batch submission, and component perspective options) and `src/solid_renderer.lua` (WorldGUI, triangles, cleanup, and winding). Source calls establish the arguments and how that project organizes batches. The through-occluder fill result is an observation for that build, not a guarantee for every game version or material. No generic depth-fix parameter for `Gui.triangle` has been established.

This entry preserves a locally installed report. Its original source revision and game build were not recorded and were not independently rechecked for this update. Treat the signatures and results as build-specific reported guidance, not as verification of current APIs.
