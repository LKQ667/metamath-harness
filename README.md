# MetaMath Harness

基于 DeepSeek Harness `0.1.0-rc.7` 的数学建模增强套件。**无需预装任何 DeepSeek 相关软件**，安装脚本会自动装好官方本体、插件和全部依赖。

## 📦 两种获取方式（任选其一）

### 方式一：AI IDE 一键安装（会用 AI IDE 的用户）

把本仓库链接 `https://github.com/LKQ667/metamath-harness` 发给 AI IDE（Trae、Cursor 等），再说一句"帮我安装这个项目"。AI 会按根目录 [`AGENTS.md`](AGENTS.md) 的指引自动完成安装、创建桌面快捷方式并启动，全程无需手动操作。

### 方式二：ZIP 直接下载（普通用户，可装到任意盘符）

到 [Releases 页面](https://github.com/LKQ667/metamath-harness/releases/latest) 下载最新的 `metamath-harness-v*.zip`（已清理测试文件，更小更干净），解压到任意位置（如 `D:\`），进入文件夹**双击 `install.cmd`** 即可。

> 前提同样是 Node.js >= 22（下载安装：https://nodejs.org ，装完重开终端）。

---

## 🚀 手动安装（三步，普通 Windows 10/11 电脑）

**第 1 步：装 Node.js**（已装可跳过；装完要重开终端）

```powershell
winget install OpenJS.NodeJS.LTS
```

**第 2 步：下载本项目并进入目录**

```powershell
git clone https://github.com/LKQ667/metamath-harness.git
cd metamath-harness
```

> 没有 Git？装一个：`winget install Git.Git`；或者用第 2 步替代版（无需 Git）：
> ```powershell
> Invoke-WebRequest 'https://github.com/LKQ667/metamath-harness/archive/refs/heads/main.zip' -OutFile mmh.zip -UseBasicParsing
> Expand-Archive .\mmh.zip -DestinationPath .
> cd metamath-harness-main
> ```

**第 3 步：一键安装并启动**

在文件夹里**双击 `install.cmd`**（任何机器都能用），或在 PowerShell 里运行：

```powershell
.\install.ps1
```

> 若报红字“因为在此系统上禁止运行脚本”，说明系统脚本策略为 Restricted，改用这条（同样任何机器可用）：
> ```powershell
> powershell -ExecutionPolicy Bypass -File .\install.ps1
> ```

看到浏览器自动打开 `http://127.0.0.1:3080` 就成功了，桌面会同时出现 **「MetaMath Harness」快捷方式**。首次使用请在网页设置里填自己的模型供应商和 API Key（Key 只存本机）。

### 服务器 / 没有 winget 和 Git 的机器

Node 改用官网安装包：到 https://nodejs.org 下载 LTS（≥22）MSI 安装，然后直接用上面的"第 2 步替代版"下载本项目，再双击 `install.cmd`（或跑 `.\install.ps1`）。

### 安装到指定盘符（如 D 盘）

默认装在你**打开终端时所在的目录**。想装到 D 盘（或 E、F 等任意盘），第 2 步前先切过去即可（以下命令已在 Windows 10 + Node 24 真机验证通过）：

```powershell
cd D:\
git clone https://github.com/LKQ667/metamath-harness.git
cd metamath-harness
.\install.ps1
```

ZIP 方式同理：

```powershell
cd D:\
Invoke-WebRequest 'https://github.com/LKQ667/metamath-harness/archive/refs/heads/main.zip' -OutFile mmh.zip -UseBasicParsing
Expand-Archive .\mmh.zip -DestinationPath .
cd metamath-harness-main
.\install.ps1
```

装到哪个盘，快捷方式就指向哪个盘（实测桌面快捷方式工作目录为 `D:\metamath-harness`），全部文件都在该文件夹内，不会在 C 盘留东西。PowerShell 若报“禁止运行脚本”，把最后一行换成 `.\install.cmd` 即可。

### 日常启动（装过一次之后）

**双击桌面的「MetaMath Harness」快捷方式**即可（无需打开终端）。

也可以用命令（PowerShell 或 cmd 均可）：

```powershell
cd metamath-harness    # 进入项目目录
.\install.cmd -StartOnly
```

其他参数：`-NoStart` 只装不启动｜`-Port 3081` 换端口

---

## 安装脚本做了什么

检查 Node → 确保 pnpm → 从官方 npm 安装 DeepSeek Harness 本体 → 构建 Mathmodel 插件 → 安装 Web 依赖 → 创建桌面快捷方式 → 启动并打开浏览器。全程无需人工干预；所有内容都装在项目文件夹内，删文件夹即完整卸载（桌面快捷方式可一并删除）。

## 目录结构

```text
install.ps1              一键安装并启动脚本
install.cmd              双击入口（资源管理器/cmd 可用，自动绕过脚本策略限制）
plugins/dsh-mathmodel/   外置 Mathmodel 插件（源码、测试、脚本、文档）
.dsh/.agent-presets/     Agent Preset：mathmodel（数学建模）、imagegen（标准生图）
.dsh/profiles/web/       Web Profile 接线（package.json、pnpm-lock、cordis.patch.yml）
.dsh/skills/             18 个手动 Skill，其中 12 个带 mathmodel-card.yml 参数卡片
portable/                Windows 便携版构建、启动、自检脚本
构建便携版.ps1            构建便携运行包入口
启动-DeepSeek-Harness.cmd 便携版启动入口
依赖自检.cmd              依赖预检入口
```

## 可选依赖

Python 3、TeX Live（XeLaTeX）、Draw.io、Poppler——用于论文与绘图链路，缺了也不影响安装启动，插件预检会提示按需安装。

插件详细用法、升级与回滚见 [`plugins/dsh-mathmodel/README.md`](plugins/dsh-mathmodel/README.md)。

## 订阅登录（ChatGPT / Claude / Grok）

内置第三方插件 [dsh-plugin-subscriptions](https://github.com/V1ki/dsh-plugin-subscriptions)（npm `0.3.1`，MIT）：在 Web 设置 → 订阅页用 OAuth 登录订阅账号即可作为模型 provider，无需 API Key；登录令牌保存在本机 `~/.dsh/plugins/subscriptions/auth.json`（0600 权限，自动刷新），不进入仓库或归档。默认启用 Claude 与 Grok 路由；ChatGPT (Codex) 路由因其 `image_generate` 工具与本项目 API 生图工具重名而默认关闭，如需启用请先处理工具重名（见项目内 README 3.3a 节说明）。

## 便携版（免安装包）

`构建便携版.ps1` 可构建自带 Node/Python/TeX Live 的完整便携包（解压双击即用，构建需约 20 GB 临时空间），详见 [`portable/README.md`](portable/README.md)。

## 凭据与安全

- API Key 通过插件"受管凭据"保存，支持 `DASHSCOPE_API_KEY`、`OPENAI_API_KEY`、`GEMINI_API_KEY`、`CUSTOM_IMAGE_API_KEY` 四类引用；Key 不写入仓库文件、日志或 Prompt；
- 严禁提交 `.env`、`.credentials.yaml`、`storages/`、`sessions/`、`logs/` 等用户状态（已在 `.gitignore` 中排除）；
- 所有 Skill 卡片确认后仅写入可编辑草稿，绝不自动发送；付费生图需凭据、健康检查、数量上限与用户单次授权同时满足。

## 测试

```powershell
cd plugins/dsh-mathmodel
npm test        # 构建并运行全部单元测试
npm run check   # 全部源码语法检查
```

## 许可

`plugins/dsh-mathmodel` 为 MIT；其余配置与脚本基于 DeepSeek Harness 插件范式编写，仅供学习与研究使用。
