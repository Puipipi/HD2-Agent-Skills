---
name: hd2-addon-build
description: 把一个 Helldivers 2 的 Bingus/MDL Lua mod 构建成 mod 管理器可导入的 ZIP；当源码未通过某项门禁时拒绝打包 —— LuaJIT 的每函数指令上限（过大的 mod 会被加载器静默跳过）、user32 的 ffi.cdef 声明（它会顶掉另一个 mod 的声明）、被调用但未声明的 C 符号，或缺少游戏内 README 块。用于打包一个 HD2 Lua mod，或者在某个 mod 能加载却什么也不做时使用。
---

# hd2-addon-build —— 构建与打包

> **置信度:** 五道门禁在本仓库跑过,且每一道都被证明会在被触发时失败。信封格式来自加载器自己的工具。**管理器能否导入**该产物,本仓库未验证 —— 见[验证状态](../../docs/verification-status.md)。

[English](https://github.com/YC426/HD2-Agent-Skills/blob/main/skills/hd2-addon-build/SKILL.md) / 简体中文

`scripts/build_mod.py` 把一个明文 Lua 入口转换成 mod 管理器所导入的 addon 信封，
并在源码不适合发布时停止打包。

## 前置条件

| 需要 | 原因 | 缺失时 |
|---|---|---|
| Python 3.8+ | 该脚本 | — |
| **`lupa`**（`python -m pip install lupa`） | `--validate-only` 用 **LuaJIT 2.1** 编译源码。每一项要紧的门禁都依赖它。 | 构建中止；不要退回到普通 Lua 5.1，后者会接受 LuaJIT 将静默丢弃的源码 |
| **`vendor/bingus/build_addon.py` + `archive.py`** | 它们编码了加载器的归档格式。**未随附**（第三方）。 | `hd2-bingus-toolchain-setup` 会把它们取到对应位置 |
| 一个你拥有的 `GUID` | 管理器靠 GUID 识别升级 | 生成一个 UUID，并在**每次发布时复用它** |
| 明文 UTF-8 的源码 | 无 BOM、无字节码、无 `\0` | 加载器会跳过该包 |

不需要：游戏、加载器、网络访问。构建从不部署 —— 部署是一个单独且需要刻意执行的步骤。

## 配置

编辑 `scripts/build_mod.py` 顶部的 CONFIG 块：

```python
MOD_SOURCE   = os.path.join(W, "mymod.lua")        # 你的入口
RESOURCE     = "mods/yourauthor/mymod"             # mods/<author>/<entry>，只允许下划线
GUID         = "…"                                 # 你的 UUID，各次发布复用
DISPLAY_NAME = "My Mod"
ICON         = os.path.join(W, "icon.webp")        # 或 None
README_MARKER = "[===[My Mod - quick guide"        # 游戏内 README 位于源码中
VENDOR       = os.path.join(W, "vendor", "bingus")
```

## 使用

```powershell
python -B scripts/build_mod.py --validate-only    # 只跑门禁，在打包前停止
python -B scripts/build_mod.py                    # -> dist/<Name>-<version>.zip
python -B scripts/build_mod.py --with-source      # 另外产出一个源码包，仅用于评审交接
```

## 它检查什么

五项门禁。前四项作用于源码；第五项作用于构建完成的归档。

1. **LuaJIT 编译。** 每函数 65535 条字节码指令的上限会让加载器**静默**跳过一个过大的
   mod —— 你得到一个「安装得很正常」却什么也不做的 mod，没有任何日志行。普通 Lua 编译会
   接受它。
2. **任何 `ffi.cdef` 中都没有 `user32` 符号。** LuaJIT 的 C 命名空间是进程全局的，而
   `ffi.cdef` 保留*第一条*声明，因此用不同原型重新声明 `GetCursorPos` 会让所有先声明它的
   mod 失效。以硬性拒绝的形式发布。
3. **每个被调用的 C 符号都已声明。** 缺少声明在调用处就是硬错误；它曾经以「点击卡片
   没有任何反应」的形式发布出去。
4. **README 块存在**，并且它会被从源码提取到 `README.txt`，这样游戏内指南就无法与代码
   脱节。
5. **归档内没有类脚本文件。** `.bat`、`.cmd`、`.ps1`、`.vbs`、`.js`、`.exe` 和 `.dll`
   全部被拒绝，检查是在*已完成*的归档上进行的，这样后续改动无法悄悄加回一个；拒绝时会删除
   归档，因此一次失败的发布不会留下任何可供误上传的东西。mod 站点会隔离含脚本的归档 ——
   替代它们的模式见 `hd2-no-quarantine-packaging`（在运行时把辅助程序生成到用户的配置
   文件夹中）。

它还避免两类打包错误：只有当图标文件确实被打包时才声明图标（悬空的 `IconPath` 会显示
一条空白的管理器条目），并且以 CRLF 写入 `README.txt`。

## 输出

```
dist/My-Mod-1.0.0.zip
├─ manifest.json                       Version, Guid, Name, Description, Options[Include:["Addon"]]
├─ Addon/9ba626afa44a3aa3.patch_0      the Lua archive
├─ Addon/9ba626afa44a3aa3.patch_0.stream
├─ Addon/9ba626afa44a3aa3.patch_0.gpu_resources
├─ icon.webp                           only if present
└─ README.txt                          extracted from the source
```

退出码 0 = 门禁通过（并且已打包，除非使用 `--validate-only`）；非零 = 被拒绝，并在 stderr
上指明失败的门禁。

## 验证结果

构建说的是信封*格式良好*；它无法说明管理器会接受它。发布前用
**`hd2-addon-package-inspector`** 检查产物本身，并手动确认一次导入 + 游戏内加载。

## 局限

- 它验证的是信封，不是你 mod 的行为：一个通过全部门禁的 mod 在运行时仍可能做不了任何
  有用的事。
- 如果源码中已经有 `-- HD2-Addon:` 行，`RESOURCE` 必须与之匹配；不匹配会被拒绝，而不是
  被静默重写。
- 构建从不部署。路径与槽位见 `hd2-bingus-mod-development`。
