# MetaMath Harness

把一个能干活的 AI 助手和一整套数学建模工具装进同一个文件夹，双击就能用。

参加数学建模比赛的同学多半体会过：环境配一天，论文排到凌晨，画图工具东一个西一个。这个项目就是冲着解决这些麻烦来的。底座是 DeepSeek Harness（DeepSeek 官方的本地 AI 编程环境，`0.1.0-rc.6`），我在上面装好了 17 个数学建模 Skill，从技术路线图、论文配图到模型求解都有。不用再一个个找工具、配环境，装完这一个，比赛要用的基本齐了。

## 它好在哪

**开箱即用。** 电脑上只要有 Node.js，双击 `install.cmd`，剩下的安装脚本全包：官方本体、插件、依赖、桌面快捷方式，一次装齐。不需要预装任何 DeepSeek 相关软件。装完双击快捷方式，浏览器自动打开界面，直接开始用。

**对新手友好。** 全程可以不碰命令行。缺 Python、缺 TeX Live 这种事，预检会一条条告诉你缺什么、去哪下、怎么装。README 里每一步都写清楚在什么机器上验证过，出问题照着对就行。

**为数学建模而生。** 17 个 Skill 按比赛流程设计：分析题目、画技术路线图、跑模型、写论文、出配图，各带参数卡片，你确认之后 AI 才动手，不会瞎改你的稿子。切到 mathmodel 预设，AI 就按建模的套路干活。

**自由度高。** 装哪个盘都行（全部文件都在项目文件夹里，C 盘不留东西，删文件夹即完整卸载）；端口能换；模型供应商自己挑，DeepSeek、通义、OpenAI、Gemini 都支持，API Key 只存你自己电脑，不上传任何地方。还能一键构建免安装便携版，整个文件夹拷到别的电脑直接用。

**启动快。** 桌面快捷方式在服务已运行时约 2 秒打开页面（此前约 14 秒）；冷启动（重启电脑后第一次）也只要几秒。

## 最近更新（2026-08-17）

- **启动提速**：快捷方式探活从 `Test-NetConnection`（单次 13 秒）换成毫秒级端口检测，服务启动改直拉 node。服务在跑时双击约 2 秒，冷启动约 4 秒。
- **界面品牌统一**：中央文案改为"大道至简"金属艺术字（透明底），"预览版"徽章移除。纯界面层覆盖，卸载插件即恢复官方样式。
- **内置 10 张壁纸**：皮肤插件新增"壁纸 01–10"十张内置壁纸（压缩后 base64 内嵌，无需外部文件），在设置 → 皮肤里一键切换；自动提取主色适配界面，支持模糊/变暗/面板不透明度微调，刷新后自动恢复。
- **主视觉简化**：中央官方紫鲸鱼图标由插件运行时隐藏（不改官方包），"大道至简"标题与对话框水平居中对齐。

## 界面预览

<p align="center">
  <img src="github展示/微信图片_20260817123927_1956_14.png" width="48%" alt="界面预览1" />
  <img src="github展示/微信图片_20260817123941_1957_14.png" width="48%" alt="界面预览2" />
</p>

<p align="center">
  <img src="github展示/微信图片_20260817123958_1958_14.png" width="48%" alt="界面预览3" />
  <img src="github展示/微信图片_20260817124009_1959_14.png" width="48%" alt="界面预览4" />
</p>

<p align="center">
  <img src="github展示/微信图片_20260817124021_1960_14.png" width="48%" alt="界面预览5" />
  <img src="github展示/微信图片_20260817124034_1961_14.png" width="48%" alt="界面预览6" />
</p>

<p align="center">
  <img src="github展示/微信图片_20260817124052_1962_14.png" width="48%" alt="界面预览7" />
  <img src="github展示/微信图片_20260817124103_1963_14.png" width="48%" alt="界面预览8" />
</p>

<p align="center">
  <img src="github展示/微信图片_20260817124113_1964_14.png" width="48%" alt="界面预览9" />
  <img src="github展示/微信图片_20260817124122_1965_14.png" width="48%" alt="界面预览10" />
</p>

<p align="center">
  <img src="github展示/532ee2ac402c8fe2b10e8ec56cee8b3b.png" width="48%" alt="功能展示1" />
  <img src="github展示/745929ef903362703feb4f952e73272a.png" width="48%" alt="功能展示2" />
</p>

<p align="center">
  <img src="github展示/96214aed34b57d3db5869fd40486fb33.png" width="48%" alt="功能展示3" />
  <img src="github展示/b6a80005509ba5fa051e6292e427e01e.png" width="48%" alt="功能展示4" />
</p>

## 两种获取方式（任选其一）

### 方式一：AI IDE 一键安装（会用 AI IDE 的用户）

把本仓库链接 `https://github.com/LKQ667/metamath-harness` 发给 AI IDE（Trae、Cursor 等），再说一句"帮我安装这个项目"。AI 会按根目录 [`AGENTS.md`](AGENTS.md) 的指引自动完成安装、创建桌面快捷方式并启动，全程无需手动操作。

### 方式二：ZIP 直接下载（普通用户，可装到任意盘符）

到 [Releases 页面](https://github.com/LKQ667/metamath-harness/releases/latest) 下载最新的 `metamath-harness-v*.zip`（已清理测试文件，更小更干净），解压到任意位置（如 `D:\`），进入文件夹**双击 `install.cmd`** 即可。

> 前提同样是 Node.js >= 22（下载安装：https://nodejs.org ，装完重开终端）。

---

## 手动安装（三步，普通 Windows 10/11 电脑）

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

> 若报红字"因为在此系统上禁止运行脚本"，说明系统脚本策略为 Restricted，改用这条（同样任何机器可用）：
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

装到哪个盘，快捷方式就指向哪个盘（实测桌面快捷方式工作目录为 `D:\metamath-harness`），全部文件都在该文件夹内，不会在 C 盘留东西。PowerShell 若报"禁止运行脚本"，把最后一行换成 `.\install.cmd` 即可。

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
.dsh/skills/             17 个手动 Skill，多数带 mathmodel-card.yml 参数卡片
portable/                Windows 便携版构建、启动、自检脚本
构建便携版.ps1            构建便携运行包入口
启动-DeepSeek-Harness.cmd 便携版启动入口
依赖自检.cmd              依赖预检入口
```

## 可选依赖

Python 3、TeX Live（XeLaTeX）、Draw.io、Poppler，用于论文与绘图链路，缺了也不影响安装启动，插件预检会提示按需安装。

插件详细用法、升级与回滚见 [`plugins/dsh-mathmodel/README.md`](plugins/dsh-mathmodel/README.md)。

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

## 支持作者（完全自愿）

这个项目免费开源，没有广告，也没有任何付费功能。如果你用下来确实省了时间，想请作者喝杯咖啡，可以扫下面任意一个码；不扫也完全没关系，所有功能对所有人都一样。

<p align="center">
  <img src="donate-wechat.jpg" width="200" alt="微信赞赏码" />
  <img src="donate-alipay.jpg" width="200" alt="支付宝赞赏码" />
</p>
<p align="center">微信（左）｜支付宝（右）</p>

## 许可

`plugins/dsh-mathmodel` 为 MIT；其余配置与脚本基于 DeepSeek Harness 插件范式编写，仅供学习与研究使用。
