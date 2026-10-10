---
name: hd2-game-event-identification
description: 根据只读游戏证据识别《地狱潜者 2》的 HUD 标记、战术地图标记、任务目标、敌人标记和战备激活。当 addon 需要区分事件来源、触发者、动作、稳定目标身份、本地化名称或类别，且不能凭通用标签猜测时使用。
---

# HD2 游戏事件识别

[English](https://github.com/Puipipi/HD2-Agent-Skills/blob/main/skills/hd2-game-event-identification/SKILL.md) / 简体中文

本技能用于识别**发生了什么，以及事件指向哪个对象**。到生成规范化事件为止；消息模板、身份权限、队列和冷却策略属于相邻的 [`hd2-event-chat-automation`](../hd2-event-chat-automation/SKILL_cn.md) 技能。需要解析表布局或资源哈希时使用 [`hd2-offline-data-workflow`](../hd2-offline-data-workflow/SKILL_cn.md)；需要窄范围外部只读地址核验时使用 [`hd2-live-memory-probe`](../hd2-live-memory-probe/SKILL_cn.md)；需要读取玩家选择的游戏语言时使用 [`hd2-game-language-autodetect`](../hd2-game-language-autodetect/SKILL_cn.md)。

## 证据与范围

具体参考实现是 [HD2-AutoChat 提交 `4445596a76ed387edc3c09d0d25aa9d06ffd5b11`](https://github.com/Puipipi/HD2-AutoChat/tree/4445596a76ed387edc3c09d0d25aa9d06ffd5b11)。其中的运行时观察逻辑受单一 Steam build 和 `game.dll` 指纹约束。目录结合了当前 build 的组件导出、资源路径和本地化数据；这些社区导出可作为证据，但不是 Arrowhead 官方源码，也不保证未来内容完整。证据类型不同：当前 build 的静态数据、离线 fixture、源码级验证，以及一次用户确认的缓存标记实机捕获。不要把离线 fixture 说成实机确认，也不要推广那一次捕获。

## 识别流程

1. **区分事件来源。** HUD ping ring 和战术地图 pin 是不同来源。参考实现从复制的 actor state 读取地图 pin，因为 Map21 接收端在写入 HUD ring 记录前就返回；普通 HUD ring 另行读取。标记材质相似不能证明事件类型相同。参见[来源说明](https://github.com/Puipipi/HD2-AutoChat/blob/4445596a76ed387edc3c09d0d25aa9d06ffd5b11/src/ping_events.lua#L39-L46)和[map/ring快照代码](https://github.com/Puipipi/HD2-AutoChat/blob/4445596a76ed387edc3c09d0d25aa9d06ffd5b11/src/ping_events.lua#L717-L770)。

2. **将身份字段与显示文本分开。** 分别保留创建者/触发者、生产者 `source`、动作、原生 kind 和本地化 key、稳定 target/entity ID、资源 hash、类别、位置及 session/scene 身份。本地化字符串是展示证据，不能代替实体 ID 或资源身份。地图目标应先通过网络身份解析到当前实体，再解析资源身份；任务目标名称应尽量从当前 objective manager 与 runtime name override 解析。参考路径见[objective名称解析](https://github.com/Puipipi/HD2-AutoChat/blob/4445596a76ed387edc3c09d0d25aa9d06ffd5b11/src/ping_events.lua#L783-L817)和[地图目标解析](https://github.com/Puipipi/HD2-AutoChat/blob/4445596a76ed387edc3c09d0d25aa9d06ffd5b11/src/ping_events.lua#L839-L868)。

3. **先有身份依据，再分配目标或类别。** 空地、空 map-pin 类型、无效或指向自己的 target ID，以及“未知资源 + 通用标签”，都不能证明这是特殊地点。地面式标记仅在资源属于经过审阅的任务目标时接受。“特殊地点”“任务终端”“敌方单位”“普通物资”等原生回退标签不能把未知对象变成建筑、敌人或拾取物。无法解析时，按来源约定保留通用未知或丢弃；不要编造具体目标。参见[target门控及回退](https://github.com/Puipipi/HD2-AutoChat/blob/4445596a76ed387edc3c09d0d25aa9d06ffd5b11/src/ping_events.lua#L819-L870)和[未知目标处理](https://github.com/Puipipi/HD2-AutoChat/blob/4445596a76ed387edc3c09d0d25aa9d06ffd5b11/src/ping_events.lua#L947-L1008)。

4. **用当前任务数据判断目标重要性。** 资源身份可以说明某对象是任务地点，但不能证明它是当前主目标、前置目标或可选目标。参考实现从当前 objective runtime 读取 importance，并只映射已知值；未知值保持 `unknown`。不能从名称、地图标签或静态资源目录推断主/副目标。经审阅的任务目录会标出通用/非特定条目，并记录数据版本及来源哈希，见 [`mission-targets.json`](https://github.com/Puipipi/HD2-AutoChat/blob/4445596a76ed387edc3c09d0d25aa9d06ffd5b11/docs/mission-targets.json)。

5. **区分建筑、拾取物和任务炮弹。** 经审阅的任务建筑包括非法广播塔、撤离信标、指挥碉堡和超级地球旗杆等。CQC-1 唯一真旗是携带武器，不是任务旗杆。弹药、针剂、手雷和样本拾取物属于独立的 `supplies` 类别，可以单独关闭；不要把它们归为建筑。SEAF 火炮有六种资源身份被组件证据确认属于 ObjectiveShell，但其中两种身份无法证明具体炮弹变体。对这类歧义项，必须有具体原生标签才能识别；否则保留未知或抑制。见[特殊目标证据](https://github.com/Puipipi/HD2-AutoChat/blob/4445596a76ed387edc3c09d0d25aa9d06ffd5b11/src/special_targets.lua#L1-L24)、[物资及通用名称集合](https://github.com/Puipipi/HD2-AutoChat/blob/4445596a76ed387edc3c09d0d25aa9d06ffd5b11/src/ping_events.lua#L486-L516)和[物资开关](https://github.com/Puipipi/HD2-AutoChat/blob/4445596a76ed387edc3c09d0d25aa9d06ffd5b11/src/auto_chat.lua#L9397-L9404)。

6. **把上下文标签视为窄范围证据。** `0ABED3586E397289` 超级地球缓存/Salute 坠落舱回退，依据是一次脱敏实机直接目标捕获和匹配的静态资源路径。源码明确说明它是上下文回退，不是官方本地化名称，不能推广。现有证据无法证明碉堡不能被标记，也没有通用规则能说明所有 “Salute” 或碉堡对象都按同一方式解析。应保留为未解决问题，直到目标专属捕获或权威组件证据给出答案。见[范围受限的例外](https://github.com/Puipipi/HD2-AutoChat/blob/4445596a76ed387edc3c09d0d25aa9d06ffd5b11/src/special_targets.lua#L13-L21)。

7. **区分战备召唤与标记，并单独观察无标记成功事件。** 在固定参考 build 中，战备召唤标记需同时满足 `kind == 20`、duration `9999` 和原生 flag `0x2000`；仅凭显示名称或标记类型不足以确认。保留 `action='summon'` 与 `action='mark'`，并区分来源。部分任务战备或动作不会产生 HUD 标记。独立激活观察器检测每个 peer 的激活记录变化；初始快照是基线，只有冷却变化不是新成功事件。两个 producer 应保持分开，并使用各自的来源证据去重。**目标实体出现在世界中，并不能证明是某个玩家成功召唤了它；若没有召唤专属 HUD 证据或能够支持触发者归属的激活记录变化，就不要发出带触发者归属的召唤事件。**这些 flag、布局和偏移绑定于具体 build，不能当成可移植 ABI。见[召唤判定](https://github.com/Puipipi/HD2-AutoChat/blob/4445596a76ed387edc3c09d0d25aa9d06ffd5b11/src/ping_events.lua#L872-L905)、[激活观察器及基线](https://github.com/Puipipi/HD2-AutoChat/blob/4445596a76ed387edc3c09d0d25aa9d06ffd5b11/src/stratagem_events.lua#L1-L10)和[成功状态变化处理](https://github.com/Puipipi/HD2-AutoChat/blob/4445596a76ed387edc3c09d0d25aa9d06ffd5b11/src/stratagem_events.lua#L135-L194)。

8. **按来源生命周期去重，不按目标名称去重。** 对 ring slot，使用观测 token 与 age reset 区分持续标记和新标记；非地图标记上无关的位置/flag变化不应重复发送，而同一目标 age reset 后再次标记应视为新事件。地图 pin 的复制状态有自己的身份与生命周期；参考实现将地图位置变化视为新的标记。任务激活事件按观测 session/peer 记录中的战备 ID 与 activation time 去重。不要重放只存在于初始基线中的事件。区分这些情况的测试见[ring与map去重](https://github.com/Puipipi/HD2-AutoChat/blob/4445596a76ed387edc3c09d0d25aa9d06ffd5b11/work/standalone/tests/test_ping_events.py#L779-L799)和[任务激活事件](https://github.com/Puipipi/HD2-AutoChat/blob/4445596a76ed387edc3c09d0d25aa9d06ffd5b11/work/standalone/tests/test_stratagem_events.py#L59-L75)。

9. **将稳定身份、本地化名称与 UI 分组分开。** 分别保存稳定战备 ID、原生本地化 key、canonical/debug identity、中英文显示名、图标材质 hash 与 UI 颜色/家族。红/蓝/绿 UI 分类不能从 `beacon_color` 推导——该枚举没有绿色；图标 hash 代表材质，不代表目标身份。未知目录项应显式显示 unknown 或 ID 回退，不借用相似名称。“Super Earth Flag” 是任务战备名称；“CQC-1 One True Flag” 是另一件装备，分别见[名称审计](https://github.com/Puipipi/HD2-AutoChat/blob/4445596a76ed387edc3c09d0d25aa9d06ffd5b11/docs/STRATAGEM-NAMES-AUDIT.json#L635-L649)及[CQC-1审计项](https://github.com/Puipipi/HD2-AutoChat/blob/4445596a76ed387edc3c09d0d25aa9d06ffd5b11/docs/STRATAGEM-NAMES-AUDIT.json#L2375-L2390)；mission-catalog测试也会拒绝把近战旗当成旗杆([测试](https://github.com/Puipipi/HD2-AutoChat/blob/4445596a76ed387edc3c09d0d25aa9d06ffd5b11/work/standalone/tests/test_mission_catalog.py#L23-L27))。见[战备分类](https://github.com/Puipipi/HD2-AutoChat/blob/4445596a76ed387edc3c09d0d25aa9d06ffd5b11/src/stratagem_catalog.lua#L67-L86)和[目录行构建](https://github.com/Puipipi/HD2-AutoChat/blob/4445596a76ed387edc3c09d0d25aa9d06ffd5b11/src/stratagem_catalog.lua#L122-L145)。

10. **把飞行作为独立移动特征分类。** 先确认敌对阵营及有效敌人/资源身份，再核对有证据的飞行组件，然后按 `UnitSize` 路由；飞行单位仍可能属于小、中、大或巨型。`UnitSize` 不是护甲或威胁等级。基于当前组件导出的 catalog 可以让新资源进入已知目录，但不能证明未来所有敌人、任务生成物或原生 ping producer 都已覆盖。未知 ID 保持未知；不要默认归为中型，也不要凭名字判断飞行。[覆盖报告](https://github.com/Puipipi/HD2-AutoChat/blob/4445596a76ed387edc3c09d0d25aa9d06ffd5b11/docs/ENEMY-COVERAGE-0.8.0.md#L9-L11)区分了当前导出数据与官方完整性；其中的[分类及自动生成边界](https://github.com/Puipipi/HD2-AutoChat/blob/4445596a76ed387edc3c09d0d25aa9d06ffd5b11/docs/ENEMY-COVERAGE-0.8.0.md#L57-L98)必须一并保留。

## 置信度与验证

逐条标注证据属于：**静态导出/路径证据**、**离线 fixture 证据**、**源码中绑定 build 的观察**或**目标专属实机捕获**。对于原生偏移、flag 和布局，记录准确的游戏/data revision 与 DLL 指纹。离线 fixture 只验证解析器针对 fixture 的行为，不证明实机 producer 行为或完整覆盖。

每种 producer 都要在离线套件中包含反例：空地、未知身份配通用标签、无效/自身目标、不支持的 map 类型、同一活动标记重复轮询、同一目标再次标记、地图 pin 位置变化、初始基线、仅冷却变化、炮弹身份歧义、友军/不可标记敌人、缺失本地化。实机问题报告应记录 producer、build、来源 token/ID、目标资源、本地化 key/value 和处理结果，以便复现分类失败。

当每条发出的事件都保留 producer 与 actor、动作、稳定身份（或明确未知）、类别、展示名来源及去重 token，且每种不支持/歧义情况都具有测试过的未知/丢弃结果时，识别层才算完成。之后把规范化事件交给聊天自动化层，不要在本技能中加入消息、身份或冷却策略。
