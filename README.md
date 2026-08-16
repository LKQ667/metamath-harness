# MetaMath Harness

基于 DeepSeek Harness `0.1.0-rc.6` 的数学建模增强套件。**无需预装任何 DeepSeek 相关软件**，安装脚本会自动装好官方本体、插件和全部依赖。

## 🚀 三步装好（普通 Windows 10/11 电脑）

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

```powershell
.\install.ps1
```

看到浏览器自动打开 `http://127.0.0.1:3080` 就成功了。首次使用请在网页设置里填自己的模型供应商和 API Key（Key 只存本机）。

### 服务器 / 没有 winget 和 Git 的机器

Node 改用官网安装包：到 https://nodejs.org 下载 LTS（≥22）MSI 安装，然后直接用上面的"第 2 步替代版"下载本项目，再跑 `.\install.ps1`。

### 日常启动（装过一次之后）

```powershell
cd metamath-harness    # 进入项目目录
.\install.ps1 -StartOnly
```

其他参数：`-NoStart` 只装不启动｜`-Port 3081` 换端口

---

## 安装脚本做了什么

检查 Node → 确保 pnpm → 从官方 npm 安装 DeepSeek Harness 本体 → 构建 Mathmodel 插件 → 安装 Web 依赖 → 启动并打开浏览器。全程无需人工干预；所有内容都装在项目文件夹内，删文件夹即完整卸载。

## 目录结构

```text
install.ps1              一键安装并启动脚本
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

Python 3、TeX Live（XeLaTeX）、Draw.io、Poppler——用于论文与绘图链路，缺了也不影响安装启动，插件预检会提示按需安装。

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

## 许可

`plugins/dsh-mathmodel` 为 MIT；其余配置与脚本基于 DeepSeek Harness 插件范式编写，仅供学习与研究使用。
