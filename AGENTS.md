# AGENTS.md — 给 AI IDE 的自动化安装指引

当用户把本仓库链接发给你并要求"安装 / 部署 MetaMath Harness"时，按以下步骤执行（Windows）：

1. **前置检查**：`node -v`（需 >= 22）与 `git --version`。缺失时引导用户运行 `winget install OpenJS.NodeJS.LTS` 或 `winget install Git.Git`，装完后提醒重开终端再继续。
2. **克隆并安装**（在仓库根目录）：
   ```powershell
   .\install.ps1
   ```
   若 PowerShell 报"禁止运行脚本"（ExecutionPolicy Restricted），改用：
   ```powershell
   .\install.cmd
   ```
   脚本会自动完成：安装官方 DeepSeek Harness 本体（npm 全局）→ 构建 Mathmodel 插件 → 安装 Web 依赖 → 创建桌面快捷方式 → 启动并打开浏览器。
3. **验收标准**：
   - 桌面出现「MetaMath Harness」快捷方式；
   - `http://127.0.0.1:3080` 返回 200 且浏览器已打开。
4. **提醒用户**：首次使用需在 Web 设置中配置自己的模型供应商与 API Key（Key 只存本机，绝不外传）。
5. **日常启动**：双击桌面快捷方式，或运行 `.\install.ps1 -StartOnly`。

## 硬性禁止

- 严禁读取、打印或提交 `.env`、`.credentials.yaml`、`storages/`、`sessions/`、`logs/` 等用户状态与凭据文件；
- 严禁把任何 API Key / Token 写入文件、代码或对话记录；
- 严禁自动执行 `git push` 等远程写操作。
