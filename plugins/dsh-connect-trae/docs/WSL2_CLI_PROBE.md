# WSL2 / Linux 环境排查备忘：Trae CLI 登录探测

> 对应 issue #5（WSL2 中通过 `traecli` 登录后插件显示「未登录」）。
> 本文档的目标是**用一轮问答拿到真实路径**，而不是让用户走完整套排查流程。

## 背景：为什么 CLI 登录此前完全不工作

插件原本只认**桌面包**的位置：

```
~/.config/<Trae 目录名>/User/globalStorage/storage.json
```

这份文件里 key 为 `iCubeAuthInfo://icube.cloudide` 的值是 **AES 加密**的，
插件用 `src/decrypt.ts` 解密后取出 token。

但 `traecli` 是另一个产品，它写的是**自己的家目录**，内容是**未加密的裸 JWT**：

```
~/.trae-cn/trae-jwt-token      # CN 版 CLI，实测（macOS）
```

两者路径、文件名、格式全都不同。只装 CLI（或只用 CLI 登录）的机器上
**根本不存在 `storage.json`**，所以插件恒显「未登录」。

WSL2 用户特别容易踩中这一点：WSL2 里通常只装 `traecli`，不会装 Linux 桌面版 IDE。

## 现已支持的探测位置

插件现在会把下面这些**全部并列探测**，任一命中即可登录：

| 来源 | 路径 |
| --- | --- |
| CLI | `~/.trae-cn/trae-jwt-token`（CN） |
| CLI | `~/.trae/trae-jwt-token`（回退） |
| 桌面版 | `$XDG_CONFIG_HOME` 或 `~/.config` 下 `trae-cn/`、`Trae CN/` 的 `User/globalStorage/storage.json` |
| 桌面版 | 其余 edition 的同构路径（仅 `cn` / `solo` 会被采用） |

> **Linux 桌面版目录名 `trae-cn` / `Trae CN` 都未经真机验证**，
> 因此采用多候选并列探测：猜错不会漏掉真实安装，只会多一条「文件不存在」。

## 如果升级后仍然显示「未登录」

插件卡片现在会显示一个可折叠的 **「已检查的路径」** 列表，
逐条列出探测过的路径及其失败类型（`文件不存在` / `无法读取` / `格式无法识别`）。

请把列表里**除你自己家目录用户名外**的内容截图或贴回来，
并额外执行下面这一条命令确认实际布局：

```bash
ls -d ~/.trae* ~/.config/*[Tt]rae* 2>/dev/null
```

**这条命令只列目录名，不会输出任何 token，可以放心贴出来。**

如果有输出，再补一条（确认文件在不在）：

```bash
ls -la ~/.trae-cn/trae-jwt-token ~/.trae/trae-jwt-token 2>/dev/null
```

### ⚠️ 不要贴出这些内容

- `cat ~/.trae-cn/trae-jwt-token` 的**输出**（那就是 token 本身）
- `storage.json` 里 `iCubeAuthInfo://icube.cloudide` 的 **value**

目录名、文件是否存在、卡片上的失败类型说明，这些都是安全的。

## 临时解决办法

如果实际路径与上表都不同，可以用插件配置项直接指定：

```yaml
authFile: /home/<你的用户名>/.trae-cn/trae-jwt-token
edition: cn
```

`authFile` 现在会**同时**按桌面版文档和 CLI token 两种格式解析，
所以指向 `storage.json` 或 `trae-jwt-token` 都可以，不必事先判断。

## 相关文档

- `docs/WINDOWS_TOKEN_PROBE.md` —— Windows 真机的同类排查（加密头、目录名验证）
