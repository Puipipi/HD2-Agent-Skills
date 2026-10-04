---
name: hd2-mod-release-operations
description: 打包并发布一个 Helldivers 2 Bingus/MDL Lua mod —— 项目布局与包命名、多资源归档、固定的七步发布流程、GitHub push 与 Release 发布、token 存放在哪里，以及会破坏 HTTPS 与代理访问的本地/沙箱网络坑。适用于发布一个 HD2 mod、切分或重新切分一次发布，或排查失败的 push、上传或 403 时使用。
---

# HD2 mod 发布运维

> **置信度:** 读来的;§1 逐项列出状态,包括哪些是环境特定的。

[English](https://github.com/YC426/HD2-Agent-Skills/blob/main/skills/hd2-mod-release-operations/SKILL.md) / 简体中文

这是 HD2 mod 工作中偏运维的那一半：项目如何布局、包如何命名与归档、一次发布实际由哪七步
组成，以及网络上会坏在哪里。下面的每一个数字都是来自某位作者的机器与仓库
（`junze0910/junze-hd2-lua-mod`）的证据；某个值若属于本地而非通用情况，文中会说明。

## 1. 范围与来源 —— 相信一个数字之前先读这里

| 项目 | 状态 |
|---|---|
| 代理地址 `127.0.0.1:6382` | **环境特定，测量于 2026-10-03**，在作者的机器上。请重新读取注册表（见 §10），不要把它硬编码。 |
| `Invoke-RestMethod` / `curl.exe` 的 HTTPS 失败 | **沙箱/主机特定**，不是通用的 Windows 规则。在此主机上证书存储被锁定，因此每个 PowerShell HTTPS 客户端都失败；在普通机器上它可能正常工作。 |
| §8 与 §3 中的日期（`2026-10-02`、`2026-10-04`） | 带日期的具体事件，保留它们是因为它们解释了这条规则为何存在。 |
| 以 `2b8e6c51-…` / `7f2c8a04-…` 引用的 manifest GUID | 在来源中被截断；它们是 mod 身份标识，不是密钥。 |
| `.patch_N` 字节布局（§6） | 已经过字节级往返验证。 |

## 2. 项目布局与两条产物线

每个 mod 的布局 —— 约定式的，这样构建线与发布线才能保持一致：

```
<mod>/
  src/            主源码（拆分出的模块也放在这里）
  build.py        打包（默认输出 -> hd2-mod\build\；--release 还会复制到 dist\）
  guid.txt        稳定的 GUID，与源码放在一起
  DESIGN.md       工程笔记（设计细节放到 hd2-mod\docs\）
  test/           离线回归（lupa，无需游戏）
```

两条产物线，绝不混用：

| 路径 | 角色 | 是否纳入追踪 |
|---|---|---|
| `hd2-mod\build\` | 工作构建区；当前版本的 zip 直接放在根目录下 | 未追踪 |
| `hd2-mod\build\_deprecated\` | 被放弃的产物，其名称里带着原因 | 未追踪 |
| `hd2-mod\build\_old\` | 更早的产物 | 未追踪 |
| `hd2-mod\build\_probes\` | 侦察 / 探测包 | 未追踪 |
| `junze-hd2-lua-mod\dist\` | 发布区，随 git 仓库分发，并附带 `SHA256SUMS.txt` | **已追踪** |

不要在某个 mod 子目录里创建你自己的 `dist/` 或 `build/` —— mod 本地的 `dist/`
会与纳入追踪的发布线打架。

## 3. 命名：包、归档产物、GUID

| 规则 | 取值 / 形式 | 为何存在 |
|---|---|---|
| 包名 | `<Mod-Name>-v<X.Y.Z>.zip`，**纯 ASCII** | mod 管理器把 manifest 的 `Name` 当作文件夹名；中文字符会产生「目标名/目录名或卷标语法不正确」并导致安装失败 |
| 绝不覆盖此前的包 | 把旧包连同原因移入 `_deprecated\`。在 **2026-10-02**，那个显示"page 5 tab crashes"的包被覆盖了，证据随之丢失 | 被覆盖的产物无法再被诊断 |
| 跳过对完全相同重建的归档 | 先写入 `.tmp`，再与现有产物做字节比较；字节完全相同意味着**不要归档** | 否则 `_deprecated` 会被一次毫无损失的重建淹没在噪声里 |
| 归档名 | `<original name>_被同名重建覆盖_<timestamp>[_index].zip` | 时间戳只有秒级精度，所以同一秒内的重建会撞名 —— 序号是必需的 |
| 已弃用名要写明原因 | `AC8-Rack-Backpack-v1_census无门控+漏WriteCopy.zip`、`TD-110-Co-Op-v1.3_复查有bug.zip`、`TD-110-Co-Op-v1.7_射界未收紧.zip`、`More-Balanced-Exosuit-Emancipator-v1.0_兜底无退避.zip` | 名称里不写原因，同一个错误就会被重复 |
| manifest GUID | 永不改变（例如 AC-8 的 `2b8e6c51-…`、实弹狗的 `7f2c8a04-…`） | GUID 一旦改变，管理器会把升级当成一个新 mod，与旧版本并排安装 |
| Patch slot 编号 | 绝不硬编码 `patch_N`。HD2 Mod Manager 会自行分配并重排 slot（实测：安装一个新 mod 会改变其他 mod 的编号）。手工安装时取当前最大编号 **+ 1**，再用时间戳 / 大小辨认你自己的归档 | 硬编码的 slot 在管理器重排 mod 编号后就失效了 |

## 4. addon 信封与发现

入口文件的第一行必须是：

```lua
-- HD2-Addon: mods/<author>/<module>
```

- 无 BOM，在 **256 字节**以内，且为**明文**。编译成字节码会丢掉这一行注释，
  从而破坏自动发现 —— 一个被编译成字节码的 addon 从未被发现过。
- 如果无论如何都要发布字节码实现，就打包**两个资源**，并让入口为
  `return require('..._impl')`。
- 加载器的职责是发现 + `require` + 记录日志。它**从不修改内存**；内存
  工作是 addon 自己的代码做的。把一次内存写入误归因于加载器，意味着你在调试
  错误的组件。

构建可安装 ZIP 的命令：

```powershell
python tools/build_addon.py --name mods/<author>/<name> --entry x.lua --guid <stable UUID> --display-name "name" --output build/X.zip
```

## 5. 多资源归档

只有**入口**携带 `-- HD2-Addon:` 声明。加载器的发现逻辑（`discover.lua`）
只接受"声明的名字 == 资源名字哈希"，所以把模块也一并声明，会把每个
模块都变成独立的 addon —— 在管理器里就是 N 个分开的 mod。

- **不要用 `tools/build_addon.py --extra` 做多资源打包**：它也会给每个 extra 加上
  声明头。自己写脚本。
- 打包之后，把归档读回来，确认只有入口携带该声明。
- 没有该声明的模块可以编译成字节码（更小、更快）。
- 参考示例：`hd2-mod/junze-hd2-lua-mod/menu-panel/` = **6** 个资源（入口 + 5 个模块）。

## 6. `.patch_N` 归档格式（字节级）

载体文件是 `data/9ba626afa44a3aa3.patch_<N>`。

| 偏移 | 大小 | 布局 |
|---|---|---|
| `+0` | 72 字节 | `<III20sQQ24s` = magic `0xF0000011`、`1`、count、20×0、totalSize (Q)、`0`、24×0 |
| `+72` | 32 字节 × 类型数 | `<IIQIIII` = `0, 0, typeHash, count, 0, 16, 16` —— 这里的 `count` 决定描述符表的大小 |
| `+104` | 80 字节 × count | `<7Q6I` = `nameHash, typeHash, offset, 0, 0, 0, 0, length, 0, 0, 16, 16, index` |

数据区 = `align16(104 + 80*count)`；每个资源按 16 字节对齐。资源体为
`u32 bodyLen + u32 version(=2) + body`。

资源类型标记：

- Lua 资源类型标签 = `0xA14E8DFA2CD117E2`
- 加载器占用的资源 = `core/wwise/lua/wwise_flow_callbacks` = `0x7251FDD9BB62480A`

两者都是识别归档中 Lua 资源、并避开加载器自身资源所必需的。

## 7. 发布清单（固定的七步）

1. **在源码中编辑 `local VERSION`** —— 唯一的真相来源。然后
   `python tools\build_mod.py --list` 查看 key 名称，再 `python tools\build_mod.py <key>`。
   Scanner 用自己的 `hd2-scanner\build.py`（多资源归档）。两者都不覆盖：
   同名或旧版本会自动进入 `build\_deprecated\`，而字节完全相同
   的内容既不会被重建也不会被归档。
2. **把新包复制到 `dist\`**；把被取代的旧包移入
   `build\_deprecated\from_dist\`。
3. **重新计算 `dist\SHA256SUMS.txt`** —— 小写哈希 + **两个空格** + 文件名，这样
   `sha256sum -c` 能直接对它工作。
4. **更新 `README.md`**（安装表 + 发布线说明）和 **`RELEASE-NOTES.md`**
   （新增小节；发布脚本从这里提取正文）。
5. `git add -A` → 提交（中文，带 `release:` / `docs:` 前缀）→ `git tag -a <tag> -m "…"`。
6. `push` —— **必须走代理**，见 §10。
7. `python tools\gh_publish.py`（为该发布线创建 Release，只附带该线的
   包和它自己的 `SHA256SUMS.txt`；可重复执行），然后 `python tools\gh_verify.py`。

发布线与标签：

| 发布线（标签前缀） | 含义 |
|---|---|
| `core` | 前置条件 |
| `infantry` | 步兵 |
| `vehicle` | 载具 |
| `logistics` | 后勤，保留 |

标签形如 `core-v2.0`。**标签版本 ≠ 包版本** —— 包各自独立演进
（AC-8 是 2.0，Scanner 是 0.7.0）。按发布线打标签，才让相互独立的包能按
各自的节奏发布。

## 8. GitHub Release 机制

| 规则 | 细节 | 原因 |
|---|---|---|
| `gh_publish.py` 从不覆盖同名附件 | 它只上传尚不存在的名字；同名附件（尤其是 `SHA256SUMS.txt`）会被跳过。每当附件集合发生变化（版本变化、删除了旧包），**先在 release 页面删除同名 / 多余的旧附件**，再运行它 | 过期的校验和文件列出了已经不存在的包（**2026-10-04** 踩到） |
| `gh_verify.py` 比较 API digest | 它使用 `assets[].digest`，不下载附件，因为代理到 `objects.githubusercontent.com` 的 TLS 经常是坏的（会下载的那个版本拿到 SSL EOF） | 通过代理下载附件失败；digest 这条路更快且不受影响 |
| 标签的指向不可回收 | 一旦推送，就不要删除标签或改变它指向的对象 —— 不要 `git tag -f` + force push。一条空的发布线只占用一个标签加一个占位 Release，没有包（`logistics-v0.1alpha` 就是这样留下的） | 移动标签会破坏"一次发布包含什么"的可复现性。*(冲突：这与"强制移动标签来修正一次发布"的常见习惯相矛盾；来源保留这条禁令。)* |
| 标签之上的 release 内容是可变的，但有一个告诫 | 为补丁包更换附件：删除旧附件 → 上传新包 → 重新计算该线的 `SHA256SUMS.txt`；标题和正文也可以改 —— 在正文里留一行 `附件已更新（日期）`。`tools\gh_refresh_releases.py` 是幂等的、可重复运行的。**告诫：** "Source code (zip)" 快照是该标签当时的树，因此正文里的下载链接必须指向 **`main` 分支的 `dist/`**，而不是指向标签快照 | 标签快照是冻结的，指向它的链接会把过期的包交给用户 |
| 两种重切方式，不要混用 | 可变的 release 内容（见上）**或**一个新的补丁标签（例如 `infantry-v2.0.1`），当用户仍应能拿到旧包时后者有用 | 两种都可行；混用会让用户不确定哪个产物才是当前的 |
| 不要用 `git push --tags` | 一个历史上打错成大写 `V1.0` 的标签在本地仍然存在 | 推送所有标签会把那个打错的标签也发布出去 |

## 9. token 存放在哪里

把 token 放在**工作区之外的 secrets 目录**里，绝不放在仓库中：

- 那个目录有自己的 `.gitignore`，内容为 `*`。
- token 文件的第一个非注释行就是 token。
- 脚本先读环境变量 **`GH_PAT`**，再回退到那个文件。
- 绝不要把 token 写进 skill 文档，也绝不要回显它：当你必须展示一条携带它的命令
  时，把凭据替换为 `***`。把 token 挡在仓库之外，正是防止
  意外发布的关键。

作用域坑：

| token | 结果 |
|---|---|
| Classic token（作用域 `repo`）或一个 fine-grained token | 两者都可用 |
| 限定到本仓库、带 `Contents: Read and write` 的 fine-grained token | 最干净 |
| 任何只读作用域 | **总是 403**：API 报告 `Resource not accessible by personal access token`，git 报告 `denied to <user>` |
| 仓库访问设置为 `Public repositories (read-only)` | 读公开仓库仍然可用，写入永远不行 |

只读作用域的 token 会产生看起来像权限或网络问题的 403 —— 先检查
作用域，再去调试网络。

## 10. 网络坑（本地与沙箱）

**坑 1 —— 在这台主机上 PowerShell HTTPS 是坏的（沙箱/主机特定）。** 证书
存储被锁定 —— `schannel: AcquireCredentialsHandle failed: SEC_E_NO_CREDENTIALS` —— 所以连
`https://github.com` 都会让 `Invoke-RestMethod` / `curl.exe` 返回 `HTTP=000`。出站
访问请**只用 git（自带 OpenSSL）和 python（自带 OpenSSL）**。这是这台
沙箱机器的属性，不是通用的 Windows 规则。

**坑 2 —— 代理只存在于 WinINET 注册表里。** 它由 VPN 客户端设置，既不在
环境变量里，也不在 git config 里：

```
HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings -> ProxyServer
```

**2026-10-03** 测得为 `127.0.0.1:6382`（一个有日期、机器特定的值 —— 请重新读取
注册表）。按工具注入：

```powershell
git -c http.proxy=http://127.0.0.1:6382 push <url>
$env:HTTPS_PROXY='http://127.0.0.1:6382'    # python
```

没有这个，git 和 python 就没有配置任何代理，完全无法访问
GitHub。

**坑 3 —— push 用一次性的内联凭据，绝不持久化。** URL 形如
`https://x-access-token:<token>@github.com/junze0910/junze-hd2-lua-mod.git`：它完成
push 的认证，而不把 token 写进 git config。回显这类命令时，把 token
替换为 `***`。`sh.exe: couldn't create signal pipe` 是 MSYS 噪声，可以忽略。

## 11. 必须落盘的诊断

这里只包含日志中面向发布的那一半 —— 一次运行之后磁盘上必须存在什么，以及
用户在哪里找到它。

| 规则 | 细节 | 原因 |
|---|---|---|
| 共享日志目录 | `%LOCALAPPDATA%/CowboyBingus/Helldivers2/Logs` | 加载器和写日志的 mod 共同使用的固定位置 |
| `loader.open_log` **只**接受 `.log` 名 | 加载器检查 `if type(name) ~= 'string' or not name:match('^[%w_-]+%.log$') then return nil end`。`.txt` 及其他所有扩展名都返回 `nil`，调用方若用 `pcall` 包住它，就会得到一个静默缺失的文件。每个 dump 都用 `.log`，例如 `SSProbe_dump.log` / `SSProbe_table.log` | 主日志正常而 dump 文件从不出现 —— 在怀疑扫描逻辑之前先检查文件名规则 |
| 批量诊断绕开日志环 | 把批量诊断输出通过一个单独的 `dump()` 直接写盘 | 400 行的环上限静默吃掉了 census / dump 内容 |

## 12. 未解决

在发布、打包或面向发布的日志材料中，没有任何内容自相矛盾。唯一保留下来的
矛盾是 §8 里的标签规则：来源禁止强制移动标签，同时指出这是常见习惯 ——
禁令被保留，该习惯并未与之调和。
