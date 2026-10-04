---
name: hd2-crash-reporting-and-settings
description: 通过编辑 data/settings.ini 来开关《绝地潜兵2》的崩溃上报、转储写入与崩溃截图,并清理它在 AppData 里留下的崩溃文件夹。当崩溃反馈弹窗妨碍你游玩、当你调试模组需要崩溃转储、或者你需要知道这几个键里哪一个改的是引擎行为而不只是上报时使用。
---

# HD2 崩溃上报,以及控制它的 settings.ini 键

[English](https://github.com/Puipipi/HD2-Agent-Skills/blob/main/skills/hd2-crash-reporting-and-settings/SKILL.md) / 简体中文

这里有两条内容:人们想关掉崩溃弹窗时会去找的那四个键,以及**其中一个和另外三个性质不同**的原因。

## 来源与置信度

下面的键名、值、行号与路径都是**从一台真实安装上读出来的**(build 25480438,`helldivers2.exe` 1.8.46015.0)——
见文末的记录。

**未验证:** 关掉这些是否真的能让弹窗不再出现。要确认这一点必须真的触发一次崩溃,而这里没有人为制造崩溃。
所以请把"弹窗不再出现"当作**预期效果**,而不是本仓库测出来的结论。

## 文件位置

```
<游戏目录>\data\settings.ini          # 例如 D:\...\steamapps\common\Helldivers 2\data\settings.ini
```

Steam → 右键游戏 → 管理 → 浏览本地文件。

引擎是 Autodesk Stingray,这就是它的配置格式:`键 = 值`,并按 `block { ... }` 分组嵌套。
**层级很关键** —— 见下面的陷阱。

## 四个键

被检查的那台安装上的实测值,以及各自所处的位置:

| 键 | 原值 | 层级 | 作用 |
|---|---|---|---|
| `crs_enabled` | `true` | `win32` 的直属子项 | 整个崩溃上报系统 |
| `crash_dump` | `true` | `win32` 的直属子项 | 崩溃时写出 `.dmp` 文件 |
| `capture_image` | `true` | 嵌套的 **`crs`** 块内 | 崩溃时的截图 |
| `floating_point_exceptions` | `true` | `win32` 的直属子项 | **不是上报** —— 见下 |

陷阱在于:`crs_enabled` 与 `crs { ... }` 是**不同层级上的两个不同东西**。前者是 `win32` 上的一个布尔值;
后者是一个块。与转储有关的键在那个块**内部**:

```ini
win32 = {
	crs_enabled = true                     # 第 74 行
	floating_point_exceptions = true       # 第 75 行
	crash_dump = true                      # 第 82 行
	crs = {                                # <- 这是一个块,不是上面那个开关
		data_path = "%APPDATA%/Arrowhead/Helldivers2/crash_data"
		capture_image = true               # 第 89 行
		kill_timeout_seconds = -1
		capture_video = false              # 默认已经是关的
	}
	panic_folder_path = "%APPDATA%/Arrowhead/Helldivers2/panic/"
}
crash_dump_path = "%APPDATA%/Arrowhead/Helldivers2/dumps/dump-%DATE%-%TIME%-%SESSION%-%HOSTNAME%.dmp"
```

那些只说"把 `crs_enabled` 设为 false"、却不说清是**哪一个** `crs` 的手改教程,很容易让人改错地方。
两个都真实存在,各干各的活。

另外这些也存在,值得知道,虽然通常不会去改:

- `capture_video` —— 默认已经是 `false`。打开它会让崩溃付出的代价大得多。
- `local_console_log` —— 控制台日志的落点,也就是模组开发者真正会去读的那个文件。
- `panic_folder_path`、`data_path`、`crash_dump_path` —— 各类输出的落点。

## `floating_point_exceptions` 不是上报开关

另外三个只决定诊断信息**是否被记录**。这一个决定一次算术故障**是否会让进程当场停下**。

- **`true`** —— 浮点故障会上报,你当场崩溃,拿到的调用栈直接指向成因。
- **`false`** —— 故障不上报。坏值继续往下流。可见结果只是换了地方:崩溃变成一个错值、一个被污染的状态、
  或者稍后在**无关**位置才发生的故障。

所以关掉它可能让 bug **更难查**,而不只是更安静。如果你在调模组,就让它开着。如果你只是想让弹窗别打扰
游玩,那要明白:你同时移掉的是一道正确性检查,而不只是一条通知。

**价值:** 它让一个响亮、可归因的失败,不至于变成一个安静、会被归错对象的失败。

## 安全地操作

用脚本而不是编辑器,因为这里有三种**静默**的失败方式:

```powershell
python -B scripts/hd2_settings.py --show        # 当前值,带行号
python -B scripts/hd2_settings.py --off --dry-run
python -B scripts/hd2_settings.py --off                  # 四个全关
python -B scripts/hd2_settings.py --off --keys crs_enabled,crash_dump,capture_image
python -B scripts/hd2_settings.py --restore <备份文件>
```

它会在游戏运行时拒绝编辑,写出带时间戳的备份,并**重新读取文件**来确认改动,而不是相信写入本身。

### 三种静默的失败方式

1. **在游戏运行时编辑。** 游戏退出时会重写 `settings.ini`,你的改动会**无声消失**,没有任何报错。
   先关游戏。脚本会检查进程并在必要时拒绝,除非你显式传 `--force`。
2. **改错了那个 `crs`。** 见上面的层级陷阱。
3. **把换行符重写了。** 这一条把工具的第一个版本坑了:该文件用的是 **CRLF**,而文本模式的"读—改—写"
   会把它全部 190 个换行符变成 LF。结果是文件少了 186 字节、四个键**确实**改了、而任何 diff 工具都会
   报告整个文件被重写。工具现在按**字节**读写,所以磁盘上的差异只有它真正编辑的那几行。

### 用证据证明改动,而不是相信它

对一个 191 行的文件做四处键改动,应当**恰好改动 4 行、恰好增加 4 字节**(`true` → `false`)。
如果文件变小了,换行符被重写了。如果差异行更多,说明有什么东西把这些值当文本处理并重排了。

```powershell
# 字节差必须是 +4,CRLF 数量必须不变
python -c "a=open(r'<备份>','rb').read(); b=open(r'<游戏目录>\data\settings.ini','rb').read();
print(len(b)-len(a), a.count(b'\r\n'), b.count(b'\r\n'))"
```

## 清理已经生成的东西

下面这些文件夹是**输出**,不是配置。删掉是安全的,游戏会重建它们。

```
%APPDATA%\Arrowhead\Helldivers2\
    crash_data\        <- crs 的 data_path
    dumps\             <- crash_dump_path    (.dmp 文件)
    panic\             <- panic_folder_path
    shader_cache\      <- 无关,别随手删
    saves\             <- 你的存档,永远不要删
    user_settings.config、logs\
```

删除 `crash_data` 与 `dumps` 是常见的清理动作。**`saves\` 是你的进度,不要碰** —— 也不要让任何
"清空崩溃文件夹"的说法说服你把整个 `Helldivers2` 目录清掉。`%APPDATA%` 是隐藏的;
在资源管理器里开启 查看 → 显示 → 隐藏的项目。

## 与模组的相互作用

- **`local_console_log`** 是模组 `print` 类输出最终落到的位置。如果一个模组看起来什么都没打印,
  先检查这个路径、以及该目录是否存在,再去怀疑模组本身。
- **关掉崩溃上报,等于拿掉了模组把游戏搞崩时你需要的证据。** 请留一份你所改设置的记录,并在提交模组
  bug 之前把上报打开 —— 一份写着"它崩了"、但转储被关掉的报告,是没法处理的。
- **`floating_point_exceptions = false` 会让模组的 bug 看起来像游戏的 bug。** 一个本来会当场崩溃的
  模组内部故障,改为污染状态并在稍后浮现,而浮现的位置往往会被归咎于游戏或另一个模组。如果某个 bug
  时有时无、很难定位,把这一项改回 `true` 是一个很便宜的第一个实验。

## 这个 skill 做不到什么

- 它**不能**让游戏不崩溃。它只是让游戏**不告诉你**。
- 它**不碰**完整性校验。HD2 跑着 nProtect GameGuard;这里编辑的是游戏自己也会重写的普通配置文件,
  这和改进程内存是两回事,但第三方工具的风险仍由你自己承担。
- 它**不影响**游戏内的设置界面。这里有些键同时也会出现在游戏自己的选项里;游戏可能在退出时写回它
  自己的值,从而撤销你的手改。

## 记录

从被检查的那台安装读出(build 25480438):

```
win32 = {
	crs_enabled = true                     L74
	floating_point_exceptions = true       L75
	...
	crash_dump = true                      L82
	crs = {
		data_path = "%APPDATA%/Arrowhead/Helldivers2/crash_data"
		capture_image = true               L89
		capture_video = false              L91
	}
	panic_folder_path = "%APPDATA%/Arrowhead/Helldivers2/panic/"   L99
}
crash_dump_path = ".../dumps/dump-%DATE%-%TIME%-%SESSION%-%HOSTNAME%.dmp"   L140
```

执行 `--off` 后,经**字节级**验证:5351 → 5355 字节(**+4**),190 → 190 个 CRLF,
且恰好 4 行不同(74、75、82、89)。第一次尝试把全部 190 个换行符都重写了,已从备份还原 ——
上面的 CRLF 陷阱就是这么被发现的。
