# MetaMath Harness 一键安装与启动
# 前提：Node.js >= 24.9.0 与 Git（缺失时脚本会给出 winget 一行安装指引）
# 用法：
#   .\install.ps1            安装全部组件并启动 Web 界面（首次推荐）
#   .\install.ps1 -NoStart   只安装，不启动
#   .\install.ps1 -StartOnly 跳过安装，直接启动（日常使用）
#   .\install.ps1 -Port 3081 指定端口（默认 3080）
[CmdletBinding()]
param(
    [switch]$NoStart,
    [switch]$StartOnly,
    [int]$Port = 3080
)

$ErrorActionPreference = 'Stop'
$Repo = $PSScriptRoot
$DshVersion = '0.2.2-rc.5'
$MinimumNodeVersion = [version]'24.9.0'
$EditPptBin = Join-Path $Repo '.dsh\runtime\bin'
$env:PATH = "$EditPptBin;$env:PATH"

function Step([string]$msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Ok([string]$msg)   { Write-Host "    $msg" -ForegroundColor Green }
function Fail([string]$msg) { Write-Host "    $msg" -ForegroundColor Red; exit 1 }

if (-not $StartOnly) {
    # ---------- 1. 前置工具检查 ----------
    Step '检查前置工具（Node.js >= 24.9.0）'
    if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
        Fail "未找到 Node.js。请先安装 Node.js >= 24.9.0（winget install OpenJS.NodeJS.LTS，或从 https://nodejs.org 下载 MSI），完成后重新打开终端再执行本脚本。"
    }
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        Write-Host '    提示：未检测到 Git，可继续安装；以后如需 git pull 更新，请自行安装 Git。' -ForegroundColor Yellow
    }
    $nodeVersion = [version]((node --version).Trim().TrimStart('v'))
    if ($nodeVersion -lt $MinimumNodeVersion) {
        Fail "Node.js 版本过低（当前 $nodeVersion，需要 >= $MinimumNodeVersion）。请运行：winget install OpenJS.NodeJS.LTS"
    }
    $gitInfo = if (Get-Command git -ErrorAction SilentlyContinue) { ' / ' + (git --version) } else { '' }
    Ok "Node $(node --version)$gitInfo"

    # ---------- 2. 确保 pnpm 可用 ----------
    Step '确保 pnpm 可用'
    function Test-Pnpm { try { pnpm --version *> $null; return $true } catch { return $false } }
    if (-not (Test-Pnpm)) {
        try { corepack enable *> $null } catch {}
        if (-not (Test-Pnpm)) { npm install -g pnpm *> $null }
    }
    if (-not (Test-Pnpm)) { Fail 'pnpm 不可用：请手动运行 npm install -g pnpm 后重试。' }
    Ok "pnpm $(pnpm --version)"

    # ---------- 3. 安装官方 DeepSeek Harness 本体 ----------
    Step "确保官方 DeepSeek Harness $DshVersion 已安装"
    $needInstall = $true
    if (Get-Command dsh -ErrorAction SilentlyContinue) {
        $v = (dsh --version 2>$null)
        if ($v -eq $DshVersion) { $needInstall = $false; Ok "已安装官方本体 $v（跳过）" }
    }
    if ($needInstall) {
        npm install -g "@deepseek-ai/dsh@$DshVersion" | Out-Null
        if ((dsh --version 2>$null) -ne $DshVersion) { Fail "官方本体安装失败，请手动运行：npm install -g @deepseek-ai/dsh@$DshVersion" }
        Ok "官方本体安装完成 $(dsh --version)"
    }

    # ---------- 4. 构建本地插件 ----------
    Step '准备本地插件'
    $webDependencies = (Get-Content -LiteralPath (Join-Path $Repo '.dsh\profiles\web\package.json') -Raw -Encoding UTF8 | ConvertFrom-Json).dependencies
    $localPlugins = @(
        @{ Name = 'dsh-mathmodel';            Package = '@deepseek-harness/dsh-mathmodel';      Dir = 'dsh-mathmodel';            Artifact = 'lib\index.js' },
        @{ Name = 'dsh-api-key-pool';         Package = '@deepseek-harness/dsh-api-key-pool';   Dir = 'dsh-api-key-pool';         Artifact = 'lib\index.js' },
        @{ Name = 'dsh-knowledge-sqlite';     Package = 'dsh-knowledge-sqlite';                 Dir = 'dsh-knowledge-sqlite';     Artifact = 'lib\index.js' },
        @{ Name = 'dsh-agy-link';             Package = 'dsh-agy-link';                         Dir = 'dsh-agy-link';             Artifact = 'dist\index.js' },
        @{ Name = 'dsh-workbuddy-connect';    Package = 'dsh-workbuddy-connect';                Dir = 'dsh-workbuddy-connect';    Artifact = 'lib\index.js' },
        @{ Name = 'dsh-connect-trae';         Package = 'dsh-connect-trae';                     Dir = 'dsh-connect-trae';         Artifact = 'lib\index.js' },
        @{ Name = 'dsh-opencode-session';     Package = 'dsh-opencode-session';                 Dir = 'dsh-opencode-session';     Artifact = 'lib\index.js' },
        @{ Name = 'dsh-cline-free-provider';  Package = '@jiesou/dsh-cline-free-provider';      Dir = 'dsh-cline-free-provider';  Artifact = 'lib\index.js' },
        @{ Name = 'dsh-provider-qoder';       Package = 'dsh-provider-qoder';                   Dir = 'dsh-provider-qoder';       Artifact = 'lib\index.js' },
        @{ Name = 'dsh-client-ui-skins'; Package = 'dsh-client-ui-skins'; Dir = 'dsh-client-ui-skins'; Artifact = 'lib\index.js' },
        @{ Name = 'dsh-cline-key-card'; Package = 'dsh-cline-key-card'; Dir = 'dsh-cline-key-card'; Artifact = 'lib\index.js' },
        @{ Name = 'dsh-free-search'; Package = 'dsh-free-search'; Dir = 'dsh-free-search'; Artifact = 'lib\index.js' }
    ) | Where-Object { $webDependencies.($_.Package) -like 'file:*' }
    foreach ($plugin in $localPlugins) {
        $pluginDir = Join-Path $Repo (Join-Path 'plugins' $plugin.Dir)
        $pluginPackage = Get-Content -LiteralPath (Join-Path $pluginDir 'package.json') -Raw -Encoding UTF8 | ConvertFrom-Json
        $artifact = Join-Path $pluginDir $plugin.Artifact
        # 已打包插件可能声明了 build，发行目录只包含运行文件。
        if (-not ($pluginPackage.scripts.build -and (Test-Path -LiteralPath (Join-Path $pluginDir 'src') -PathType Container))) {
            if (-not (Test-Path -LiteralPath $artifact -PathType Leaf)) { Fail "发布包缺少插件入口：$($plugin.Name)" }
            continue
        }
        Push-Location $pluginDir
        try {
            cmd /c "npm install --no-fund --no-audit 2>&1" | Select-Object -Last 1 | Write-Host
            if ($LASTEXITCODE -ne 0) { Fail "插件依赖安装失败：$($plugin.Name)" }
            cmd /c "npm run build 2>&1" | Select-Object -Last 1 | Write-Host
            if ($LASTEXITCODE -ne 0 -or -not (Test-Path $artifact -PathType Leaf)) { Fail "插件构建失败：$($plugin.Name)" }
        } finally {
            Pop-Location
        }
    }
    Ok '本地插件入口就绪'

    # ---------- 5. 安装 Web Profile 依赖 ----------
    Step '安装 Web Profile 依赖（原生 3080 / 独立号池 3081）'
    $profileDirs = @('.dsh\profiles\web', '.dsh-key-pool\profiles\web-key-pool')
    foreach ($relativeProfile in $profileDirs) {
        $profileDir = Join-Path $Repo $relativeProfile
        $profilePackage = Get-Content (Join-Path $profileDir 'package.json') -Raw -Encoding UTF8 | ConvertFrom-Json
        foreach ($dependency in $profilePackage.dependencies.psobject.Properties) {
            if ($dependency.Value -notlike 'file:*') { continue }
            $installed = Join-Path (Join-Path $profileDir 'node_modules') ($dependency.Name -replace '/', '\')
            if (-not (Test-Path -LiteralPath $installed)) { continue }
            $item = Get-Item -LiteralPath $installed -Force
            if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
                Remove-Item -LiteralPath $installed -Force
            } else {
                Remove-Item -LiteralPath $installed -Recurse -Force
            }
        }
        Push-Location $profileDir
        try {
            cmd /c "pnpm install --frozen-lockfile 2>&1" | Select-Object -Last 1 | Write-Host
            if ($LASTEXITCODE -ne 0) { cmd /c "pnpm install 2>&1" | Select-Object -Last 1 | Write-Host }
            if ($LASTEXITCODE -ne 0) { Fail "Profile 依赖安装失败：$relativeProfile" }
        } finally {
            Pop-Location
        }
    }
    Ok '两个 Profile 依赖就绪'

    # pnpm 的 file: 依赖可能复用旧复制品；安装后必须以实际构建入口哈希验收。
    $webModules = Join-Path $Repo '.dsh\profiles\web\node_modules'
    foreach ($plugin in $localPlugins) {
        $sourceArtifact = Join-Path (Join-Path $Repo (Join-Path 'plugins' $plugin.Dir)) $plugin.Artifact
        $installedArtifact = Join-Path (Join-Path $webModules ($plugin.Package -replace '/', '\')) $plugin.Artifact
        if (-not (Test-Path -LiteralPath $installedArtifact)) { Fail "Profile 缺少插件副本：$($plugin.Name)" }
        if ((Get-FileHash $sourceArtifact -Algorithm SHA256).Hash -ne (Get-FileHash $installedArtifact -Algorithm SHA256).Hash) {
            Fail "Profile 插件副本未刷新：$($plugin.Name)"
        }
    }
    Ok '本地插件副本已刷新且哈希一致'

    # ---------- 6. 准备图片转可编辑 PPT 运行时 ----------
    Step '准备图片转可编辑 PPT 运行时（项目内隔离）'
    & (Join-Path $Repo '.dsh\scripts\ensure-editppt.ps1') -RepoRoot $Repo
    if ($LASTEXITCODE -ne 0) { Fail 'editppt 安装失败，请保留上方错误信息并重新运行 install.cmd。' }
    $editPpt = Join-Path $EditPptBin 'editppt.exe'
    if (-not (Test-Path -LiteralPath $editPpt)) { Fail 'editppt 安装不完整：项目内可执行文件不存在。' }
    & $editPpt --help *> $null
    if ($LASTEXITCODE -ne 0) { Fail 'editppt 自检失败，请重新运行 install.cmd。' }
    Ok '图片转可编辑 PPT 组件已就绪（无需预装 Python、uv 或 editppt）'

    # ---------- 7. 创建桌面快捷方式 ----------
    Step '创建桌面快捷方式'
    try {
        $desktop = [Environment]::GetFolderPath('Desktop')
        if ($desktop -and (Test-Path $desktop)) {
            $lnk = Join-Path $desktop 'MetaMath Harness.lnk'
            $shell = New-Object -ComObject WScript.Shell
            $sc = $shell.CreateShortcut($lnk)
            $sc.TargetPath = 'powershell.exe'
            $sc.Arguments = "-NoLogo -NoProfile -ExecutionPolicy Bypass -File `"$Repo\install.ps1`" -StartOnly"
            $sc.WorkingDirectory = $Repo
            $sc.Description = 'MetaMath Harness 日常启动（自动跳过安装，启动后打开浏览器）'
            $ico = Join-Path $Repo 'MetaMath-Harness.ico'
            if (Test-Path $ico) { $sc.IconLocation = "$ico,0" }
            $sc.WindowStyle = 7
            $sc.Save()
            Ok "已创建：$lnk（双击即可日常启动）"
        } else { Write-Host '    未找到桌面目录，已跳过（不影响安装）' -ForegroundColor Yellow }
    } catch { Write-Host "    快捷方式创建失败（不影响安装）：$($_.Exception.Message)" -ForegroundColor Yellow }

    Step '安装完成'
}

if ($NoStart) { Write-Host "`n未启动（-NoStart）。日常启动：.\install.ps1 -StartOnly`n" -ForegroundColor Yellow; exit 0 }

# ---------- 8. 启动 Web ----------
& (Join-Path $Repo '启动-MetaMath-Harness.ps1') -Port $Port
