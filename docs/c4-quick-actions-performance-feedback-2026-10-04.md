# C4 Quick Actions 性能反馈 / Author feedback

**状态 / Status**: 2026-10-04 提交至原作者仓库 — [`etxp/HD2-C4-Quick-Actions` issue #1](https://github.com/etxp/HD2-C4-Quick-Actions/issues/1)。
中文在前、英文在后（作者为中文使用者）。下文英文段落即为 issue 正文所用的版本。

---

## 中文反馈（给作者）

你好！我们在排查 Helldivers 2 里 C4 Quick Actions 的偶发 CPU 开销／掉帧，把已经量到的数据先交给你，也许对你有用；如果看起来与你们的路径无关，直接关掉就好。

我们实测的安装版本是 **1.11**（模组自身的 `Catalog.version` / `Config.version`）。我们阅读的是 Nexus 分发版的打包源码，行号与仓库 `src/` 不同。

**现象。** 投掷与引爆都正常。早期用户测试里，从 C4 切到主武器、把手中的 C4 投出、或打开战略配备界面时，帧率会立即恢复。有些记录是主武器约 160 FPS、持 C4 约 120–140，但严重程度不稳定，不能稳定复现。焦点切换、死亡／重生／重新拾取 C4 也伴随症状变化。

**读数。** 我们的计数器在三个完整前台区间里记录到 **每次 Lua 更新约 1,263–1,271 次对 `api.read` 的调用**（含 before/after-original-update 的工作）。这是调用次数，不是 CPU 时间，也不是渲染帧数。抽样到的前台调用点轨迹反复包含：

- `ActionBackend` 的 fetch → `ActionReader.snapshot`（经 `base.snapshot`）；
- before/after 的两次瞄准输入门同步；
- `cap.same` 的复验，同时喂给开火输入门与 `AutoReload.step`。

这些符号我们在仓库源码里核对过：`ActionBackend.snapshot`、`ActionReader.snapshot`（`cap.same = e.checked`）、`ContextReader.snapshot`（`snapshot_budget`：reads ≤ 768、bytes ≤ 32768）、`AimInputGate`、`AimInputState`、`AutoReload`。

**想请你看看常态路径的四个点：**

1. `cap.same`（缓存的 capability）失败有多频繁？哪些字段变化会强制整份重新抓取？
2. 输入门的维持能否使用比“完整 action/ammo/reload 快照”更小的 capability，同时在获取、原生动作与恢复时仍然做完整的新鲜校验？
3. 重复的绑定／映射扫描能否在未变化时跳过整表扫描，并在绑定变化、切枪、失焦、重生时可靠失效？
4. 碰撞密集的实体／组件哈希查找能否改用扫描内局部分块读取，配合逐项读取回退，并对每个访问到的条目做校验？

**已经试过、但没解决的方向。** 把 ability-template 扫描批量化，在一次合成回放里有效；但把批量化扩展到 rounds/reload 模板，在我们实际任务里没有明显降低主读取量，所以那些模板解释不了剩余开销。盲目降低更新频率会有漏输入或延迟恢复的风险。

**边界（重要）。** 最新测试用的是 SmoothBoot 3.0.39（我们自己的 Lua 调度模组，带有针对 C4 的运行时适配）。我们从未修改 C4 的文件，也**没有建立只有 C4 的干净基线**，所以这不能证明是 C4 单独造成了这个回退。我们最新的同任务顺序前台测试中位数是**主武器 149 FPS、持 C4 148 FPS**；之后的焦点测试段恢复到 160–163，那次没有观察到持续性的严重下降。因此我们不能宣称永久修复，也没有定位到单一根因。四项基本动作——投掷／引爆 C4，以及切枪后的主武器开火／瞄准——在当前环境全部通过。

我们可以提供调用点轨迹和带时间戳的 FPS／读取计数日志。请问需要哪些更有针对性的数据？

## English feedback (for the author)

Hi! We've been investigating intermittent CPU overhead/FPS drops with HD2 C4 Quick Actions. The installed source we tested is version 1.11.

Throw and detonate both work correctly. Earlier user tests repeatedly showed FPS recovering immediately when switching from C4 to a primary weapon, throwing the held C4, or opening the stratagem interface. Some runs were around 160 FPS with a primary versus 120–140 with C4, but the severity varies and does not reproduce consistently. Focus changes and death/respawn/repicking C4 have also coincided with changes in the symptom.

The latest tests used SmoothBoot 3.0.39, which has C4-specific runtime adapters. We never edited C4's files. We have not established a clean C4-only baseline, so this is not proof that C4 alone causes the regression.

Our read counter still recorded approximately **1,263–1,271 calls to C4's api.read per Lua update**, including before/after-original-update work, in three complete foreground intervals. This is a call count, not CPU time or render frames. A sampled foreground call-site trace repeatedly included:

- ActionBackend's fetch → ActionReader.snapshot, through base.snapshot;
- the before/after aim input-gate sync calls;
- cap.same revalidation feeding the fire input gate and AutoReload.step.

We verified those symbols against this repository's `src/`: `ActionBackend.snapshot`, `ActionReader.snapshot` (`cap.same = e.checked`), `ContextReader.snapshot` (`snapshot_budget`: reads ≤ 768, bytes ≤ 32768), `AimInputGate`, `AimInputState`, `AutoReload`.

Could you review the steady-state path, especially:

1. How frequently the cached capability fails `cap.same`, and which changing fields force a complete refetch?
2. Whether input-gate maintenance can use a smaller capability than the complete action/ammo/reload snapshot, while keeping fresh full validation for acquisition, native actions and restoration?
3. Whether repeated binding/map scans can avoid full scans when unchanged, with reliable invalidation on binding changes, weapon switches, focus loss and respawn?
4. Whether collision-heavy entity/component hash lookups can use fresh scan-local block reads, with individual-read fallback and validation of every visited entry?

Batching ability-template scans helped a synthetic replay. Extending batching to rounds/reload templates did **not** noticeably reduce the main read count in our actual mission, so those templates do not explain the remaining overhead there. Blindly lowering update frequency risks missing inputs or delaying restoration.

For context, our latest sequential same-mission foreground tests had medians of **149 FPS with a primary and 148 with C4**. Later focus-test segments recovered to 160–163, with no persistent severe drop observed that time. Therefore, we cannot claim a permanent fix or identify one confirmed root cause. All four basic actions—C4 throw/detonate and primary fire/aim after switching—passed with our current setup.

We can provide the source call-site trace and timestamped FPS/read-counter logs. Please let us know what targeted data would help.

---

## 中文解释与已确认边界

- 可推广的是设计经验：先检查触发条件、减少无关扫描、复用布局元数据、只在当前扫描内分块读取、明确状态变化时的失效规则。
- 不能安全自动推广的是具体适配：不知道第三方模组每个回调的语义，就不能保证节流后不漏输入、不改变时序、不延迟清理或状态恢复。当前Smooth的C4适配绑定已识别的原实现，不能让所有类似模组自动获得同样效果。
- C4运行正常与C4性能已经解决是两件事。3.0.39的四项基本动作实际通过，剩余读取量/偶发性能问题仍未解决。
- 没有证明CPU瓶颈、GPU瓶颈或“C4本身单独导致”的根因。Watchdog是Lua回调归因和窗口统计，不是完整CPU/GPU剖析；它的60秒窗口可能混前后台/武器切换，不能拿黄色提示直接证明功能错误。
- 用户已要求停止继续尝试不通用的优化。2026-10-04 用户指示把本反馈归档到本仓库，并提交到原作者仓库（`etxp/HD2-C4-Quick-Actions` issue #1）。

## 实测证据索引

测试PID48404，2026-10-04 12:29:27本地启动，Smooth ready3.0.39。同进程中完成主武器/C4顺序测试与焦点测试。

| 记录 | 连续前台秒数 | 样本数 | 最低/中位/最高FPS |
|---|---:|---:|---|
| 主武器 | 46.480 | 186 | 111 / 149 / 161 |
| C4 | 41.676 | 167 | 131 / 148 / 155 |
| 焦点记录前台段1 | 25.133 | 101 | 136 / 157 / 164 |
| 焦点记录前台段2 | 40.697 | 163 | 138 / 155 / 164 |
| 焦点记录前台段3 | 52.816 | 211 | 142 / 160 / 164 |

焦点记录另12.325秒/50样本中位161.5、15.836秒/64样本中位160。多次切换的准确动作时间未知，不能把所有段落强行归类为指定的站立/跑动。上述测试未开CPU/read采样诊断，仅只读GamePP帧率和正常日志。

完整前台读取区间（UTC）：

- 主武器04:34:09→04:34:33：322读/更新。
- C4焦点记录04:42:12→04:42:35：1263.33读/更新。
- C4焦点记录04:42:59→04:43:22：1265.51读/更新。
- C4焦点记录04:43:22→04:43:44：1271.11读/更新。

每个区间1800次Lua更新，calls1800、skipped0、errors0。GamePP render FPS与Lua更新计数不是同一指标。

主要文件（项目相对路径）：

- `outputs/validated-2026-10-04/gamepp-fps/3.0.39-c4-primary-comparison.json`
- `outputs/validated-2026-10-04/gamepp-fps/3.0.39-focus-20261004T044026Z/foreground-analysis.json`及`fps.csv`
- `outputs/validated-2026-10-03/c4-read-pool/3.0.39-extension-templates/mixed-weapons-20261004T043913Z/result.json`（用户四项正常确认）
- `outputs/validated-2026-10-04/c4-template-reads/read-sites-20261004T035551Z/foreground-read-analysis.json`（3.38前台调用采样；诊断期间FPS不可用于收益验收）

对应本地1.11源码路径`work/c4-current/9ba626afa44a3aa3.patch_0.lua`：ActionReader1612、PhaseSnapshot1930–1941、ActionBackend1960–1971、AutoReload2430、AimInputState2670、AimInputGate2829、before tick3106/3107、after3128/3129/3137。行号仅对应本地提取版，作者仓库格式可能不同。原文件SHA256 `528870dc4dadcfb5be7967938b95e18e6c14670920bfe01e3761c3d94afc412c`。

## 停止时的版本与未发布实验

保留已安装3.0.39候选，源码本地Git`00f8ac8`，工作区干净。安装slot318 payload SHA256仍`0c9217cc42612f98c24cd502de1480d7822ff0790e0a82e1f7f7f8658b0d602f`，没有再次部署，没有改C4原文件。所有采样辅助已结束。

停止前新哈希碰撞分块实验只在独立VM模拟过：128项碰撞局部快照195→77次native读，19项错误/新鲜度合同通过，但没有完整性能测量和实际游戏验证，**未部署、未发布**。生产源码的这段实验已撤回；补丁与测试副本归档在`outputs/validated-2026-10-04/c4-lookup-reads/undeployed-experiment.patch`和`test_c4_lookup_reads.py.txt`，不属于正式版本。

完整原ActionReader的resource-ammo/on-foot独立VM回放用于评估pointer buffer复用：分配小幅减少但耗时不稳定，未采用/未部署。`outputs/validated-2026-10-04/c4-full-action/game-pointer-benchmark.json`不是实际C4性能证据，不能用于宣称游戏修复。
