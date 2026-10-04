---
name: hd2-bingus-toolchain-setup
description: 通过在本地机器上定位 Bingus/MDL 的 addon 打包工具（build_addon.py、archive.py）而不是再分发它们，把它们放到构建所期望的位置 —— 搜索显式路径、每个已安装 mod 的 scripts/tools/vendor 文件夹以及本地检出，把找到的内容以清单形式报告，并且只在被要求时才复制。当构建以 "No module named build_addon" 失败时使用，或者在搭建一个新的 mod 仓库时使用。
---

# hd2-bingus-toolchain-setup —— 打包工具链就位

> **置信度:** 查找步骤在本仓库验证过;复制后构建、以及 `--url` 路径都没跑过。

[English](https://github.com/YC426/HD2-Agent-Skills/blob/main/skills/hd2-bingus-toolchain-setup/SKILL.md) / 简体中文

`scripts/fetch_bingus_tools.py` 找到那两个编码了加载器 addon 信封的第三方文件，并把它们
复制到 `vendor/bingus/`。

**为什么这是一个工具而不是随附文件：** 它们是他人的代码，而本仓库刻意不再分发它们。该
工具不会让你自己去翻找，而是到它们在你机器上现实地已经存在的地方去找。

## 前置条件

| 需要 | 原因 | 缺失时 |
|---|---|---|
| Python 3.8+ | 该脚本 | — |
| **本机某处的 `build_addon.py` + `archive.py`** | 它们是构建依赖；它们不随本仓库发布 | 以退出码 1 结束并给出说明：向加载器作者获取，或者传入 `--from` |
| 一个 Bingus/MDL 安装，如果依赖自动发现 | 工具正是在那里被找到的 | 用你已获得的副本配合 `--from <folder>` |
| 网络，**仅当**你传入 `--url` | 显式选择加入的下载 | 从不自动使用 |

## 使用

```powershell
# 这台机器上已有什么？（不复制任何东西）
python -B scripts/fetch_bingus_tools.py --list

# 把完整的一套复制进一次构建：
python -B scripts/fetch_bingus_tools.py --dest work/standalone/vendor/bingus

# 从你获得的某个特定位置：
python -B scripts/fetch_bingus_tools.py --from "D:\src\bingus" --dest work/standalone/vendor/bingus

# 显式下载（从不自动；发布前请先验证）：
python -B scripts/fetch_bingus_tools.py --url https://<host>/<path> --dest ... 
```

退出码：`0` 已复制（或成功列出），`1` 什么也没找到，`2` 因目标非空而拒绝 —— 如果你确实
想覆盖，请传入 `--force`。

## 它按什么顺序查找

1. `--from <path>` —— 一个显式的文件或文件夹
2. 每一个已安装的 mod 文件夹：`%LOCALAPPDATA%\hd2arsenal\mods\*\scripts|tools|vendor|vendor/bingus`
   —— 加载器和若干 mod 把它们作为 `scripts/build_addon.py` 发布
3. 本地检出自己的 `vendor/bingus`、`tools` 和 `scripts` 文件夹

它为每个候选位置按必需文件报告一个 `OK` / `--` 标记，因此只找到一部分是显而易见的，而不
会在构建时变成意外。

## 运行之后

这些工具是第三方的。请把它们**排除在你发布的任何东西之外**，并记录来源：

```markdown
# THIRD_PARTY_NOTICES.md
The addon packaging tools (`build_addon.py`, `archive.py`) were obtained from <source>
and are not redistributed here. Obtain them with the appropriate upstream permission.
```

如果该文件夹中已经含有它们，脚本会拒绝覆盖 —— 版本部分不同，正是两次构建开始对同一个归档
产生分歧的原因。

## 局限

- 它不验证它所复制的工具：它们可能是较旧或打过补丁的版本。如果构建随后产出的包被管理器
  拒绝，请与一个已知良好的发行版对照。
- `archive.py` 可能引用加载器作者自己树中的可选构建输入（一个 LuaJIT 二进制、一个启动
  blob）。打包一个普通 addon 不需要它们；如果你的构建需要，构建会说明。
- `--url` 不执行任何签名或哈希验证。这是刻意的 —— 工具无法知道正确的哈希 —— 但这意味着
  显式下载是你的责任。

## 另见

`hd2-addon-build`（消费者）、`hd2-addon-package-inspector`（验证输出）、
`writing-mod-tools`（先搜索再询问；绝不重新分发你无权分发的东西）。
