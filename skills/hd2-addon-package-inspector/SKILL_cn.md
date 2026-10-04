---
name: hd2-addon-package-inspector
description: 在发布前检查一个构建好的 Helldivers 2 addon ZIP —— manifest 字段与 GUID、Addon 归档的二进制头、条目范围、资源名到哈希的映射、已声明但缺失的图标，以及打包的资源中是否真的含有你构建的那份源码。在一次构建之后、在上传或部署之前使用，或者在 mod 管理器拒绝了一次被构建判定为成功的导入时使用。
---

# hd2-addon-package-inspector —— 归档包体检

> **置信度:** 本仓库已验证 —— 哈希与加载器发布的三条向量一致,不一致就非零退出。见[验证状态](../../docs/verification-status.md)。

[English](https://github.com/Puipipi/HD2-Agent-Skills/blob/main/skills/hd2-addon-package-inspector/SKILL.md) / 简体中文

`scripts/inspect_package.py` 读取的是产物，不是构建日志。一个说「built OK」的构建并未
证明关于该 ZIP 的任何事：加载器会**静默跳过**它无法读取的包，而 mod 站点的「import
failed」什么也告诉不了你。

## 前置条件

| 需要 | 原因 | 缺失时 |
|---|---|---|
| Python 3.8+ | 该脚本 | — |

**不需要 lupa，不需要 LuaJIT，不需要游戏，不需要网络。** 只读：它从不写入，也从不解包
到磁盘。

## 使用

```powershell
python -B scripts/inspect_package.py dist/My-Mod-1.0.0.zip
python -B scripts/inspect_package.py dist/My-Mod-1.0.0.zip --source work/standalone/mymod.lua
python -B scripts/inspect_package.py dist/My-Mod-1.0.0.zip --resource mods/yourauthor/mymod --json
```

退出码 0 = 每项检查都通过；非零 = 某项检查失败，并在 stdout 上指明。它始终打印包大小和
SHA-256，下一位接手的人正是用它来确认手里拿到的确实是你的文件。

## 它检查什么

| 组 | 检查项 |
|---|---|
| structure | `manifest.json`、`README.txt`、恰好一个 `Addon/*.patch_0`、两个附属文件（`.stream`、`.gpu_resources`） |
| manifest | `Version`、`Guid`、`Name` 存在；GUID 是一个 UUID；`Version == 1`；`Options[].Include` 包含 `Addon`；**任何已声明的 `IconPath`/`Image` 都确实被打包**（悬空引用会显示一条空白的管理器条目） |
| archive | magic `0xF0000011`、版本 1、条目数量、每个条目的资源类型、每个条目的数据范围位于文件内、每个资源的 8 字节头（版本 2，正文长度匹配） |
| identity | 资源名 → 64 位哈希的映射能解析到一个真实条目；该名称符合允许的 `mods/<author>/<entry>` 形状 |
| hash self-test | 在上述任何检查之前，先对照**三个已公布的向量**检查名称→哈希的实现（`core/wwise/lua/wwise_flow_callbacks` → `0x7251FDD9BB62480A`、`mods/codex/gun_calibration` → `0x9537023F38D32BCD`、`mods/example_author/example_addon` → `0x835DB1516CA1E1CA`）。如果哈希是错的，下面每一项身份检查都毫无意义，因此工具拒绝继续并退出 1 |
| declaration | 资源带有 `-- HD2-Addon: <name>` 行，并且在给出 `--resource` 时与之匹配 |
| source (`--source`) | 打包的字节中含有你构建的那份源码，并且它的版本字符串与 ZIP 的文件名匹配 |

## 一个值得知道的细节

声明**不在**资源的偏移 0 处。每个资源是一个
`<u32 body length><u32 version=2>` 头，后面跟着条目正文（正文本身以
`-- HD2-Addon:` 行开头）。一个假设这种显而易见布局的校验器会报出虚假的失败 ——
这个工具的第一个版本正是如此。

## 局限

- 它验证的是**信封**，不是 mod：一个包可以通过每一项检查，在运行时仍然什么也不做。
- 它无法证明**管理器**会接受该导入。导入与导出是不同的代码路径，所以请手动确认一次
  （见 `tests/probe-build/README.md`）。
- 它不验证归档中其他 `patch_N` 的编号是否与目标槽位匹配 —— 那是部署者的工作，不是包的。

## 另见

`hd2-addon-build`（产出本工具所检查的东西）、`writing-mod-tools`（读取产物，而不是你自己
的成功消息）。
