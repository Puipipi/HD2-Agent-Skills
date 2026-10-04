---
name: hd2-mission-entry
description: 在 Windows 上启动 Helldivers 2 并把它从舰船驱动进入一局任务——窗口聚焦、按键/鼠标注入、这套流程依赖的模组、星图选任务、简报配装，以及每一步的验证证据。当 agent 需要无人值守地启动 HD2 并进入任务时使用（性能测试、模组验证、玩法录制）。
---

# HD2 任务进入（无人值守）

目标：从冷启动开始，把游戏**带着已知配装送进任务**，每一步都有可验证的证据。本文来自真实实机运行；
下面每个坐标和坑都是实际撞到并确认过的。

## 0. 前置条件

### 工具（随本 skill 的 `scripts/` 一起提供）

| 工具 | 作用 |
|---|---|
| `hd2_window.py` | **按进程 id** 找到游戏顶层窗口、聚焦它，并验证前台确实切换成功。 |
| `hd2_verified_input.py` | 按住一个键（或组合键）指定时长，**每次注入前都检查聚焦**，重复之间再复查一次前台。 |
| `hd2_click.py` | 在**游戏自己会移动光标**的情况下点击一个逻辑坐标——设置、立即验证、用相对位移纠正、先悬停、再点击。 |

```powershell
python -B scripts/hd2_window.py                    # 列出游戏窗口和句柄
python -B scripts/hd2_window.py focus              # 还原+聚焦，并报告是否匹配
python -B scripts/hd2_verified_input.py space 0.15 --repeat 8 --interval 0.25
python -B scripts/hd2_click.py 1410 795 --settle=0.9
```

要求：Windows、Python 3.8+，以及**游戏以同一用户身份运行**（否则无法聚焦它）。这些工具不会改权限
或系统设置。`hd2_window.py` 必须和另外两个放在同一目录——它们都导入它。

**绝不要用裸 `SendKeys`**：按键会落进当前拥有焦点的任意窗口。

### 本流程依赖的游戏模组

自动操作依赖模组来打开各个界面。没有它们，点击会落在空处——这是"流程突然不work了"最常见的原因。

| 模组 | 为什么需要 | 要求 |
|---|---|---|
| **Ship Station Hotkeys**（v1.7+，GUID `3d8fdb82-9df6-4dc9-a538-5f94fc60a2e7`；原名 *Galactic Menu Hotkey*） | 提供 `Tab` → 星图、`F1` → 军械库、`F5` → 控制中心、`F6` → 舰船管理、`F8` → 选完任务后直接进绝地空降仓。本 skill 要读的 `GalacticMenuHotkey.log` 就是它写的。 | Bingus Shared Loader **v17+** |
| **Stratagem MultiSelect**（v2 BSL，GUID `874d84d7-fa8a-4d48-832d-dc3cc374cd49`） | 允许**同一个**战备填进全部四个槽位，这正是"点同一个战备 4 次"能构成合法配装的原因。没有它就必须选四个不同的。 | Bingus Shared Loader **v18+** |
| Bingus Shared Loader | 加载上面两个。 | v18+ 可覆盖两者；v17 是 Ship Station Hotkeys 的下限 |
| *（可选）* Mod Bindings Menu v2.0 | 只在需要**改绑**那六个快捷键（含手柄）时才要。用默认键就不需要。 | Bingus v17+ |

任何一项缺失或被停用，先解决它，再去怀疑流程本身。先在管理器里确认它们**已启用且已部署**，再用日志
确认（§2）——`Tab` 快捷键缺失会让星图根本不开，之后每一次点击都落在舰船上。

### 环境

- 游戏目录：`D:\Program Files (x86)\Steam\steamapps\common\Helldivers 2`（按需调整）。
- Steam 在运行，游戏**没有**在运行（检查 `Get-Process helldivers2`）。
- 日志目录：`%LOCALAPPDATA%\CowboyBingus\Helldivers2\Logs\` 与
  `%APPDATA%\Arrowhead\Helldivers2\`。

## 1. 启动游戏并跳过片头

```powershell
Start-Process "steam://rungameid/553850"
Start-Sleep -Seconds 20
python -B scripts/hd2_verified_input.py space 0.15 --repeat 8 --interval 0.25
Start-Sleep -Seconds 35
python -B scripts/hd2_verified_input.py space 0.15 --repeat 8 --interval 0.25
```

- **出现片头画面（城市航拍）说明你按太早了。** 继续按。
- 如果工具报 `Game did not become foreground`，说明窗口还没起来：等一会儿再试。不要假设按键已经送达。
- 游戏窗口标题里有 `™`，所以按标题子串匹配会失败——因此要**按进程 id + EnumWindows** 定位
  （`hd2_window.py` 就是这么做的；它会退化到标题，再退化到第一个可见窗口，因为类名在不同 build 上
  报告也不一致）。

## 2. 按 Tab 之前先确认舰船就绪（强制）

```powershell
Get-Content "$env:LOCALAPPDATA\CowboyBingus\Helldivers2\Logs\GalacticMenuHotkey.log" -Tail 4
```

就绪 = **以下三条全部出现**：

- `World detection: galaxy table present`
- `Super Destroyer detected.`
- `Native ship menu presenters ready for current game build.`

**然后用截图做视觉确认**——只有 `Super Destroyer detected` 时你还不能真正操作。继续之前先截图舰船内部
（能看到 SES 名称 + `R 采购` 提示）。

> 太早按 `Tab` 会让星图提示卡在舰船 HUD 上。

## 3. 星图 → 选任务

```powershell
python -B scripts/hd2_verified_input.py tab 0.15 --repeat 1
Start-Sleep -Seconds 6
# A/D 把选择挪到任务/星球节点上
python -B scripts/hd2_verified_input.py d 0.15 --repeat 2 --interval 0.5
```

- `GalacticMenuHotkey.log` 会确认：`Galactic Map shortcut detected; entering native presenter 15.`
  **没有这一行就说明 Ship Station Hotkeys 没被加载/启用**——停下来先修它。
- **`Tab` 能打开星图但不能关掉它。** 注入 `Esc` / 右键也**不能**关（已验证）。别在这上面浪费回合。
- **选中任务 = 用鼠标点任务/飞船标记。**
  在 1707×1067 逻辑布局的星图上，点击**逻辑坐标 (1410, 795)**：
  ```powershell
  python -B scripts/hd2_click.py 1410 795 --settle=0.9
  ```
  成功后星图会自己关闭，日志出现
  `Hellpod shortcut detected; opening the briefing.`
- 悬停面板**跟随光标**；看起来像按钮的文字往往只是提示。要**点节点本身**。

## 4. 简报 → 配装 → 部署

简报出现后等 **0.6–0.8 秒**，然后（全部为逻辑坐标，1707×1067）。
这里 `--settle` 是必需的：简报网格只在"见过"指针之后才会激活槽位，而 `hd2_click.py` 会在点击前用这段
悬停时间。

```powershell
python -B scripts/hd2_click.py 840 600 --settle=0.9      # 任务地图落点
python -B scripts/hd2_click.py  85 779 --settle=0.9      # 战备槽 -> 打开战备选择
python -B scripts/hd2_click.py 128 477 --settle=0.6      # 第一个战备；点 4 次填满 4 个槽
python -B scripts/hd2_verified_input.py b 0.15 --repeat 3 --interval 0.7   # 部署
```

- 点**同一个**战备 4 次之所以可行，是**因为装了 Stratagem MultiSelect**（见 §0）。在原生配装上这么做
  会变成一个槽满、三个空——这是另一种失败，看起来像"按了部署没反应"。
- `b` 就是"部署"。如果简报从没打开，日志里会出现
  `select a mission first` 或 `presenter is busy (15/14)`——那说明星图还开着（见 §3）。
- **坐标与布局绑定。** 分辨率/HUD 缩放一变就要重新推导。
- `hd2_click.py` 会打印 `target=... before=... landed=... locked=...`：`landed=False` 或
  `locked=False` 说明游戏把指针挪走了，这一下点到了别处。

## 5. 确认你真的进了任务

截图：地面场景、左上角 `战略配备`、罗盘、右下角弹药数。
日志侧：`World detection: galaxy table absent`（说明你已经离开舰船）。

要拿出特定武器，按槽位键（例如 `3` = 支援武器）。**用截图确认**——槽位选择**并非**每次都生效
（已知失败模式：模组日志里 `gate.active=false,status=outside_c4`，而 HUD 还显示旧武器）。

## 6. 回到舰船

- 有些确认框需要**长按**（`mouse_left` 按住约 1.5 秒）；短按只会选中按钮：
  ```powershell
  python -B scripts/hd2_verified_input.py mouse_left 1.5 --repeat 1
  ```
- 如果星图卡住，可靠的回法就是**重启游戏**——注入 `Esc` 在那里无效。

## 花过真时间的坑（不要再学一遍）

| 症状 | 原因 / 修法 |
|---|---|
| 按键毫无反应 | 目标窗口不在前台。**每次注入前**都验证聚焦。 |
| `Tab` 没反应，日志里也没有快捷键行 | **Ship Station Hotkeys 没被加载/启用**（§0），不是坐标问题。 |
| 点 4 次只填了一个战备槽 | **缺 Stratagem MultiSelect**（§0）。 |
| 点击落在目标旁边 | 游戏会重新居中光标；`hd2_click.py` 会验证并纠正。若它报 `landed=False`，要重新推导坐标——不要盲目重试。 |
| 星图里 `Esc` 无效 | 那里不接受注入的 Esc。改用点击，或重启。 |
| `Tab` 关不掉星图 | 设计如此；用鼠标点任务节点。 |
| 屏幕上还是片头动画 | Space 按太早——继续按。 |
| 按标题找不到窗口 | 标题里有 `™`；要按 pid 枚举。 |
| HUD 文字被打进了别的应用 | 没有聚焦检查的裸 `SendKeys`（例如打进了 Arsenal 搜索框）。 |
| 操作落在了完全错误的界面 | 某个前置模组变了或被停用了——先重读 §0，再去重新推导坐标。 |

## 哪些验证过、哪些没有

- 坐标、按键序列和失败模式来自这套序列的真实运行。
- 工具已在"无游戏"条件下尽力验证（能编译、能导入、入口点齐全），但**它们的点击与聚焦行为必须游戏
  在运行才能确认**——离线没有任何办法证明一次点击真的落到了目标上。
- 模组前置条件读自已安装的 manifest，**不是**为本文档专门跑出来的：Ship Station Hotkeys v1.7
  （Bingus v17+）、Stratagem MultiSelect v2 BSL（Bingus v18+）、Mod Bindings Menu v2.0 可选。
