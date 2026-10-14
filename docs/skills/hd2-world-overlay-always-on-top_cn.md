---
name: hd2-world-overlay-always-on-top
description: "实现 HD2 世界图形的始终可见显示，并区分线条与真填充路径。"
---

# HD2 世界图形的顶层显示

[English](https://github.com/Puipipi/HD2-Agent-Skills/blob/main/skills/hd2-world-overlay-always-on-top/SKILL.md) / 简体中文

先确认需求指的是哪一种“顶层”：屏幕 UI 的绘制顺序、世界空间图形的深度测试，或三角形背面剔除。它们是不同机制。提高 UI layer 不等于关闭世界深度测试；反转三角形绕序只处理背面可见性，不会让被墙挡住的面显示出来。

在已核对的 Eagle 源码中，世界线有明确的深度与透视通道。主线对象使用 `World.create_line_object(world, false)`，源码将它作为深度测试通道；单独的透视线对象使用 `World.create_line_object(world, true)`。每帧更新对象时调用 `LineObject.reset(line)`，逐段 `LineObject.add_line(line, color, a, b)`，然后 `LineObject.dispatch(world, line)`。稀疏虚线由上游把原始边拆成线段产生；`add_line` 本身只提交线段，不会自动生成虚线。

示例中的 `sr` 是项目已取得的引擎 API 表；`world`、`color` 和端点 `a`、`b` 必须是在有效渲染上下文中构造的引擎对象。以下片段只展示调用顺序，不是可独立运行的模组。

```lua
local line = sr.World.create_line_object(world, true) -- 独立的透视线批次
sr.LineObject.reset(line)
sr.LineObject.add_line(line, color, a, b)
sr.LineObject.dispatch(world, line)
```

把应始终可见的线段送入单独的透视批次；需要正常遮挡的线段送入主批次。若每个组件有独立开关，应在组装对应组件的透视线批次时应用开关。Eagle 的 `through_air`、`through_sky`、`through_ground_triangles` 等选项就是按组件选择线条通道的例子。开关变量本身不会更改其他 renderer 的深度状态。

真填充使用另一条路径：`World.create_world_gui(world, pose, 1, 1)` 创建 WorldGUI，`Gui.triangle(gui, a, b, c, 100, color)` 提交三角形，更新已有面则调用 `Gui.update_triangle(gui, id, a, b, c, 100, color)`。已观察到这条填充路径会穿过遮挡物；当前证据没有证明一个通用的 WorldGUI depth-test/no-depth 开关。调用中的 `100` 是实际传入参数，但不能据此宣称它控制世界深度，也不能把它当作已验证的修复。不要猜私有材质、资源字段或 FFI 参数来改变行为。组件透视开关若只接在线条批次上，不会自动改变 `Gui.triangle` 的深度行为。

此处同样假设 `sr`、`world`、`pose`、顶点及颜色均为有效上下文中的引擎对象；这不是独立可运行示例。

```lua
local gui = sr.World.create_world_gui(world, pose, 1, 1)
local id = sr.Gui.triangle(gui, a, b, c, 100, color)
```

Eagle 的填充 renderer 会为双面显示提交反向绕序的三角形。这只能覆盖背面剔除差异，仍受填充材质的世界深度行为限制。若需求是被挡处保留虚线轮廓，线条应来自组件的原始边界；不要把三角剖分内部对角线当作轮廓。

清理持久对象，避免隐藏或切换世界后残留：复用线对象前先 `LineObject.reset`；不再使用时销毁 line object。WorldGUI 的 `clear` 路径销毁保留的 triangle id，`release` 路径销毁 GUI 并清掉句柄。源码中的销毁调用为 `sr.World.destroy_line_object(world, line)` 与 `sr.World.destroy_gui(world, gui)`。销毁前确认 world/GUI 仍有效，遵循项目现有生命周期守卫。

## 证据范围

这些签名和用法来自 Eagle 项目的 `src/eagle_direction_probe.lua`（线对象创建、批次提交、组件透视选项）和 `src/solid_renderer.lua`（WorldGUI、triangle、清理及绕序）。源码调用能证明传参和项目如何组织批次；填充穿遮挡是该构建中的观察结果，不构成所有游戏版本或材质的通用保证。`Gui.triangle` 没有已证的通用深度修复参数。

本条目收录自本地已安装的技能报告。原始源码修订和游戏 build 均未记录，本次也没有独立重新核验。应将这些签名和结果视作受 build 限制的来源报告，而不是当前 API 已验证的结论。
