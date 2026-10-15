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

真填充使用另一条路径：`World.create_world_gui(world, pose, 1, 1)` 创建 WorldGUI，`Gui.triangle(gui, a, b, c, 100, color)` 提交三角形，更新已有面则调用 `Gui.update_triangle(gui, id, a, b, c, 100, color)`。WorldGUI 三角形填充可以正常进行深度遮挡：某个经过检查的 build 中，已验证其原生材质 pipeline 的 `depth_test_enabled` 状态会让填充被场景几何挡住。这是材质状态，不是已验证的 `Gui.set_depth_test` API，也不是通用 WorldGUI 选项。调用中的 `100` 只是传入参数，不能据此认为它控制深度。只接在线条批次上的组件透视开关不会自动改变填充材质的深度行为。`rect_3d` 应视为独立候选路径；在声称相同结果前，应分别核实它选择的材质和遮挡行为。

修改填充遮挡前，先确认准确的材质资源和游戏 build，再核对资源 schema、字段定义及 renderer 如何选择该材质。保持其余资源和渲染设置不变，只改变目标深度状态，并对比被遮挡、可见、透视和关闭场景。不要从不透明字节偏移推断字段、照搬其他 build 的偏移或杜撰公开 GUI API。定点修改材质时保留其他原生资源字节。

此处同样假设 `sr`、`world`、`pose`、顶点及颜色均为有效上下文中的引擎对象；这不是独立可运行示例。

```lua
local gui = sr.World.create_world_gui(world, pose, 1, 1)
local id = sr.Gui.triangle(gui, a, b, c, 100, color)
```

Eagle 的填充 renderer 会为双面显示提交反向绕序的三角形。这只能覆盖背面剔除差异，仍受填充材质的世界深度行为限制。若需求是被挡处保留虚线轮廓，线条应来自组件的原始边界；不要把三角剖分内部对角线当作轮廓。观察到的 `LineObject.add_line` 接口没有宽度参数。平行线可以近似出米制宽带，但它仍是离散线段，不是原生粗线或填充面；要检查线间缝隙，并把支持的每种宽度增加的线段和绘制成本计入。

已验证的轮廓实现先沿语义边界按累计世界弧长生成虚线，再把虚线段扩展为平行线，使每一列共享相同的虚线相位。这是一种经过验证的构造模式，并非保持宽虚线边框对齐的唯一方法；避免让每条宽度列各自生成虚线。

已实测的“实心填充 + 仅遮挡处显虚线”组合使用深度测试填充材质，以及从同一语义边界构造的两条线批次：连续的深度测试 cover 与始终可见的虚线副本。在该实现中先提交虚线，再提交 cover；可见处由 cover 保持连续，遮挡处 cover 被深度测试隐藏，只剩虚线副本可见。这依靠 renderer 的深度行为，不是 CPU 对隐藏线段分类，也不是通用 mask API。保持两条线批次使用相同几何和宽度，核实目标材质与提交行为，并测试可见处、局部遮挡、组件开关和清理生命周期。不要假定任意材质混合方式或提交顺序都有相同表现。

清理持久对象，避免隐藏或切换世界后残留：复用线对象前先 `LineObject.reset`；不再使用时销毁 line object。WorldGUI 的 `clear` 路径销毁保留的 triangle id，`release` 路径销毁 GUI 并清掉句柄。源码中的销毁调用为 `sr.World.destroy_line_object(world, line)` 与 `sr.World.destroy_gui(world, gui)`。销毁前确认 world/GUI 仍有效，遵循项目现有生命周期守卫。

## 证据范围

线条批次、WorldGUI 和清理签名是受 build 限制的示例，应针对目标 API 再核对。另有一个已检查的三角形填充资源/build，其材质深度状态已验证；这不能证明通用材质字段布局或 GUI API。没有已证的通用深度修复参数或 `Gui.set_depth_test` 函数。

**来源：** 这些实现说明已对照审阅过的 `HD2-EagleDirectionProbe` 1.10.0 发布源码核验。其主文件 `eagle_direction_probe.lua` 的 SHA-256 为 `7562c947f525d915e3f1a0198556e736b56a0f76508a522a986cbb2e3ffdf8c2`；相关轮廓与填充渲染代码位于 `occlusion_outline.lua` 和 `solid_renderer.lua`。另有人在游戏中实测了局部遮挡行为和清理效果。此处未记录游戏 fingerprint，因此这些资源/build 行为仅适用于该案例，其他目标仍需重新核实。
