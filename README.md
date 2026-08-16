# MetaMath Harness

基于 DeepSeek Harness `0.1.0-rc.6` 的数学建模增强套件。不修改官方包，全部能力通过"外置插件 + 用户级 Preset + 手动 Skill 卡片 + Profile 接线"组合接入。

## 目录结构

```text
plugins/dsh-mathmodel/   外置 Mathmodel 插件（源码、测试、脚本、文档）
.dsh/.agent-presets/     Agent Preset：mathmodel（数学建模）、imagegen（标准生图）
.dsh/profiles/web/       Web Profile 接线（package.json、pnpm-lock、cordis.patch.yml）
.dsh/skills/             17 个手动 Skill，多数带 mathmodel-card.yml 参数卡片
portable/                Windows 便携版构建、启动、自检脚本
install.ps1              一键安装并启动（含自动安装官方 DSH 本体）
构建便携版.ps1            构建便携运行包入口
启动-DeepSeek-Harness.cmd 便携版启动入口
依赖自检.cmd              依赖预检入口
```

## 环境要求

- Windows 10/11 x64
- Node.js >= 22（未安装可一行解决：`winget install OpenJS.NodeJS`）
- Git（未安装可一行解决：`winget install Git.Git`）
- 官方 DeepSeek Harness **无需预装**——安装脚本会自动从 npm 安装 `@deepseek-ai/dsh@0.1.0-rc.6`
- 可选：Python 3、TeX Live（XeLaTeX）、Draw.io、Poppler——论文与绘图链路由插件预检提示按需安装

## 一键安装并启动

```powershell
git clone https://github.com/LKQ667/metamath-harness.git
cd metamath-harness
.\install.ps1
```

脚本自动完成：检查 Node/Git → 确保 pnpm → 安装官方 DeepSeek Harness 本体 → 构建 Mathmodel 插件 → 安装 Web Profile 依赖 → 启动并打开浏览器（http://127.0.0.1:3080）。

常用参数：

```powershell
.\install.ps1 -NoStart      # 只安装，不启动
.\install.ps1 -StartOnly    # 日常启动（跳过安装，秒起）
.\install.ps1 -Port 3081    # 换端口
```

首次使用请在 Web 设置中配置自己的模型供应商与 API Key（Key 只存本机，不进仓库）。

插件详细用法、升级与回滚见 [`plugins/dsh-mathmodel/README.md`](plugins/dsh-mathmodel/README.md)。

## 便携版（免安装）

- `构建便携版.ps1`：构建 Windows 便携运行包（首次会下载并校验 Node、Python、TeX Live、Draw.io、Poppler 等运行时，需约 20 GB 临时空间）；
- `启动-DeepSeek-Harness.cmd`：启动便携 Web 服务；
- `依赖自检.cmd`：依赖预检。

详见 [`portable/README.md`](portable/README.md)。

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
