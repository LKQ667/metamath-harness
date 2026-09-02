# MetaMath Harness 一键安装与启动
# 前提：Node.js >= 22 与 Git（缺失时脚本会给出 winget 一行安装指引）
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
$DshVersion = '0.1.1-rc.2'
$EditPptBin = Join-Path $Repo '.dsh\runtime\bin'
$env:PATH = "$EditPptBin;$env:PATH"

function Step([string]$msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Ok([string]$msg)   { Write-Host "    $msg" -ForegroundColor Green }
function Fail([string]$msg) { Write-Host "    $msg" -ForegroundColor Red; exit 1 }

if (-not $StartOnly) {
    # ---------- 1. 前置工具检查 ----------
    Step '检查前置工具（Node.js >= 22）'
    if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
        Fail "未找到 Node.js。请先安装 Node >= 22（winget install OpenJS.NodeJS.LTS，或从 https://nodejs.org 下载 MSI），完成后重新打开终端再执行本脚本。"
    }
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        Write-Host '    提示：未检测到 Git，可继续安装；以后如需 git pull 更新，请自行安装 Git。' -ForegroundColor Yellow
    }
    $nodeMajor = [int]((node --version).TrimStart('v').Split('.')[0])
    if ($nodeMajor -lt 22) { Fail "Node.js 版本过低（当前主版本 $nodeMajor，需要 >= 22）。请运行：winget install OpenJS.NodeJS" }
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
    Step '构建本地插件（数学建模 / API Key 号池 / 跨会话知识库）'
    $localPlugins = @('dsh-mathmodel', 'dsh-api-key-pool', 'dsh-knowledge-sqlite')
    foreach ($pluginName in $localPlugins) {
        $pluginDir = Join-Path $Repo "plugins\$pluginName"
        Push-Location $pluginDir
        try {
            npm install --no-fund --no-audit 2>&1 | Select-Object -Last 1 | Write-Host
            if ($LASTEXITCODE -ne 0) { Fail "插件依赖安装失败：$pluginName" }
            npm run build 2>&1 | Select-Object -Last 1 | Write-Host
            if ($LASTEXITCODE -ne 0 -or -not (Test-Path (Join-Path $pluginDir 'lib\index.js'))) { Fail "插件构建失败：$pluginName" }
        } finally {
            Pop-Location
        }
    }
    Ok '三个本地插件构建完成'

    # ---------- 5. 安装 Web Profile 依赖 ----------
    Step '安装 Web Profile 依赖（原生 3080 / 独立号池 3081）'
    $profileDirs = @('.dsh\profiles\web', '.dsh-key-pool\profiles\web-key-pool')
    foreach ($relativeProfile in $profileDirs) {
        Push-Location (Join-Path $Repo $relativeProfile)
        try {
            pnpm install --frozen-lockfile 2>&1 | Select-Object -Last 1 | Write-Host
            if ($LASTEXITCODE -ne 0) { pnpm install 2>&1 | Select-Object -Last 1 | Write-Host }
            if ($LASTEXITCODE -ne 0) { Fail "Profile 依赖安装失败：$relativeProfile" }
        } finally {
            Pop-Location
        }
    }
    Ok '两个 Profile 依赖就绪'

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
Step "启动 Web 界面（端口 $Port）"
$env:DSH_HOME = Join-Path $Repo '.dsh'
Ok "DSH_HOME = $env:DSH_HOME"

# 毫秒级端口探活（Test-NetConnection 在网卡较多的机器上单次可达 13 秒）
$portOpen = $false
$tcp = New-Object Net.Sockets.TcpClient
try {
    $task = $tcp.ConnectAsync('127.0.0.1', $Port)
    if ($task.Wait(500) -and $tcp.Connected) { $portOpen = $true }
} catch {} finally { $tcp.Close() }

if ($portOpen) {
    Ok "端口 $Port 已有服务监听，直接复用"
} else {
    # 优先直接拉起 node（省去嵌套 PowerShell 冷启动约 1 秒），找不到时回退原方式
    $started = $false
    $dshCmd = Get-Command dsh -ErrorAction SilentlyContinue
    $nodeCmd = Get-Command node -ErrorAction SilentlyContinue
    if ($dshCmd -and $nodeCmd) {
        $dshBin = Join-Path (Split-Path $dshCmd.Source -Parent) 'node_modules\@deepseek-ai\dsh\lib\bin.js'
        if (Test-Path $dshBin) {
            $server = Start-Process -WindowStyle Minimized -PassThru -FilePath $nodeCmd.Source -ArgumentList @($dshBin, 'web', '--port', "$Port")
            Ok "服务进程已启动（PID $($server.Id)，关闭其窗口即可停止服务）"
            $started = $true
        }
    }
    if (-not $started) {
        $server = Start-Process -WindowStyle Minimized -PassThru powershell -ArgumentList @(
            '-NoLogo', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-NoExit', '-Command',
            "`$env:DSH_HOME = '$env:DSH_HOME'; dsh web --port $Port"
        )
        Ok "服务进程已启动（PID $($server.Id)，关闭其窗口即可停止服务）"
    }
}

$ready = $false
foreach ($i in 1..900) {
    try { $r = Invoke-WebRequest "http://127.0.0.1:$Port" -UseBasicParsing -TimeoutSec 1; if ($r.StatusCode -eq 200) { $ready = $true; break } } catch { Start-Sleep -Milliseconds 100 }
}
if (-not $ready) { Fail "服务在 90 秒内未就绪。请检查弹出的 PowerShell 窗口中的错误信息。" }
Ok '服务已就绪'
Start-Process "http://127.0.0.1:$Port"
Write-Host "`n==> MetaMath Harness 已启动：http://127.0.0.1:$Port`n" -ForegroundColor Cyan
Write-Host "    首次使用请在 Web 设置中配置自己的模型供应商与 API Key（Key 只存本机）。`n" -ForegroundColor Yellow
