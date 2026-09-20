# MetaMath Harness launcher (development workspace)
# Use -NoBrowser for maintenance tests.
[CmdletBinding()]
param(
    [int]$Port = 3080,
    [switch]$NoBrowser
)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$hostName = '127.0.0.1'
$webUrl = "http://${hostName}:$Port"
$env:DSH_HOME = Join-Path $root '.dsh'
$dshEntry = Join-Path $env:APPDATA 'npm\node_modules\@deepseek-ai\dsh\lib\bin.js'
$logDirectory = Join-Path $env:DSH_HOME 'runtime\logs'
$stdoutLog = Join-Path $logDirectory 'web.stdout.log'
$stderrLog = Join-Path $logDirectory 'web.stderr.log'
$stateDirectory = Join-Path $env:DSH_HOME 'runtime\launcher'
$ownerFile = Join-Path $stateDirectory "$Port.json"

function Get-DshListenerPid {
    $endpoint = [regex]::Escape("${hostName}:$Port")
    $pattern = "^\s*TCP\s+$endpoint\s+0\.0\.0\.0:0\s+\S+\s+(\d+)\s*$"
    $pids = @(
        & "$env:SystemRoot\System32\netstat.exe" -ano -p tcp |
            ForEach-Object { if ($_ -match $pattern) { [int]$Matches[1] } }
    )
    if ($pids.Count -gt 1) { throw "端口 $Port 出现多个监听进程；已拒绝继续。" }
    if ($pids.Count -eq 1) { return [int]$pids[0] }
    return $null
}

function Assert-DshOwner([int]$ListenerPid) {
    if (-not (Test-Path -LiteralPath $ownerFile -PathType Leaf)) {
        throw "端口 $Port 已被占用，但缺少本项目启动记录；为避免复用其他 DSH 实例，已停止。"
    }
    $owner = Get-Content -LiteralPath $ownerFile -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($ListenerPid -ne $owner.processId -or $owner.repo -ne $root -or
        $owner.entry -ne $dshEntry -or $owner.port -ne $Port) {
        throw "端口 $Port 的进程与本项目启动记录不符；已拒绝复用。"
    }
    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $ListenerPid"
    if (-not $process -or $process.CreationDate.ToUniversalTime().ToString('o') -ne $owner.createdAt -or
        $process.CommandLine -notmatch [regex]::Escape($dshEntry)) {
        throw "端口 $Port 的 DSH 进程身份不符或 PID 已复用；已拒绝复用。"
    }
}

# Every server instance prints a fresh bootstrap token URL at startup; a plain
# URL only works while the browser still holds a valid session cookie. Open
# the token URL from the latest startup log so the browser always
# authenticates, even after a restart or upgrade invalidated the old cookie.
function Get-DshTokenUrl {
    foreach ($log in @($stdoutLog, $stderrLog)) {
        if (-not (Test-Path -LiteralPath $log)) { continue }
        $match = Get-Content -LiteralPath $log -Tail 200 -Encoding UTF8 -ErrorAction SilentlyContinue |
            Select-String -Pattern 'dsh web:\s+(http://\S+token=\S+)' | Select-Object -Last 1
        if ($match) { return $match.Matches[0].Groups[1].Value }
    }
    return $null
}

function Wait-DshTokenUrl([int]$TimeoutMs = 3000) {
    $watch = [Diagnostics.Stopwatch]::StartNew()
    do {
        $url = Get-DshTokenUrl
        if ($url) { return $url }
        Start-Sleep -Milliseconds 100
    } while ($watch.ElapsedMilliseconds -lt $TimeoutMs)
    return $null
}
function Remove-OrphanedCredentialLock {
    $lockPath = Join-Path $env:DSH_HOME '.credentials.yaml.lock'
    if (-not (Test-Path -LiteralPath $lockPath -PathType Leaf)) { return }

    $text = (Get-Content -LiteralPath $lockPath -Raw -Encoding UTF8 -ErrorAction SilentlyContinue).Trim()
    $lockPid = 0
    if (-not [int]::TryParse($text, [ref]$lockPid) -or $lockPid -le 0) {
        throw "检测到无法识别所有者的凭据写锁：$lockPath；为避免破坏并发写入，已停止。"
    }

    $owner = Get-CimInstance Win32_Process -Filter "ProcessId = $lockPid" -ErrorAction SilentlyContinue
    if ($owner -and $owner.CommandLine -match [regex]::Escape($dshEntry)) {
        throw "凭据文件正在由另一个 DSH 进程（PID $lockPid）写入；请稍后重试。"
    }
    if ($owner) {
        throw "凭据写锁 PID $lockPid 当前属于其他进程；为避免误删活跃锁，已停止。"
    }

    # dsh-atomic-write intentionally leaves orphan recovery to the operator.
    # Only a lock whose recorded PID no longer exists is removed here; the
    # credential file itself is never read, modified or deleted.
    Remove-Item -LiteralPath $lockPath -Force
}

# Reuse only a fully identified running service. For an interactive launch,
# prefer the token URL persisted with the owner record (same verified
# instance); the log scan stays as the fail-closed fallback for records
# written before that field existed.
$listenerPid = Get-DshListenerPid
if ($listenerPid) {
    Assert-DshOwner $listenerPid
    if (-not $NoBrowser) {
        $owner = Get-Content -LiteralPath $ownerFile -Raw -Encoding UTF8 | ConvertFrom-Json
        $openUrl = if ($owner.tokenUrl) { $owner.tokenUrl } else { Wait-DshTokenUrl }
        if (-not $openUrl) { throw 'DSH 正在监听，但尚未产生认证 URL；已拒绝打开未认证页面。' }
        Start-Process $openUrl
    }
    exit 0
}

$nodeCommand = (Get-Command node.exe -ErrorAction Stop).Source
Remove-OrphanedCredentialLock
if (-not (Test-Path -LiteralPath $dshEntry)) {
    Add-Type -AssemblyName PresentationFramework
    [System.Windows.MessageBox]::Show("DSH entry was not found: $dshEntry", 'MetaMath Harness') | Out-Null
    exit 1
}

New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
New-Item -ItemType Directory -Path $stateDirectory -Force | Out-Null
$server = Start-Process -FilePath $nodeCommand `
    -ArgumentList @($dshEntry, 'web', '--host', $hostName, '--port', $Port, '--no-open') `
    -WorkingDirectory $root `
    -WindowStyle Hidden `
    -RedirectStandardOutput $stdoutLog `
    -RedirectStandardError $stderrLog `
    -PassThru
$serverProcess = $null
for ($attempt = 0; $attempt -lt 20 -and -not $serverProcess; $attempt++) {
    $serverProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $($server.Id)"
    if (-not $serverProcess) { Start-Sleep -Milliseconds 100 }
}
if (-not $serverProcess) { throw '无法确认 DSH 服务进程身份。' }
@{ repo = $root; entry = $dshEntry; port = $Port; processId = $server.Id; createdAt = $serverProcess.CreationDate.ToUniversalTime().ToString('o') } |
    ConvertTo-Json | Set-Content -LiteralPath $ownerFile -Encoding UTF8

$ready = $false
$openUrl = $null
for ($attempt = 0; $attempt -lt 450; $attempt++) {
    Start-Sleep -Milliseconds 100
    if ($server.HasExited) { break }
    $openUrl = Get-DshTokenUrl
    if ($openUrl) {
        $listenerPid = Get-DshListenerPid
        if ($listenerPid) {
            Assert-DshOwner $listenerPid
            $ready = $true
            break
        }
    }
}

if (-not $ready) {
    Add-Type -AssemblyName PresentationFramework
    $detail = if (Test-Path -LiteralPath $stderrLog) {
        (Get-Content -LiteralPath $stderrLog -Tail 8) -join "`n"
    } else {
        'No error log was generated.'
    }
    $failedProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $($server.Id)" -ErrorAction SilentlyContinue
    if ($failedProcess -and $failedProcess.CommandLine -match [regex]::Escape($dshEntry)) {
        Stop-Process -Id $server.Id -Force -ErrorAction SilentlyContinue
    }
    Remove-Item -LiteralPath $ownerFile -Force -ErrorAction SilentlyContinue
    [System.Windows.MessageBox]::Show("MetaMath Harness did not start within 45 seconds.`n`n$detail`n`nLog: $stderrLog", 'MetaMath Harness') | Out-Null
    exit 1
}

# Persist the authenticated URL with the owner record so a later hot start
# opens instantly without depending on the log tail window.
@{ repo = $root; entry = $dshEntry; port = $Port; processId = $server.Id; createdAt = $serverProcess.CreationDate.ToUniversalTime().ToString('o'); tokenUrl = $openUrl } |
    ConvertTo-Json | Set-Content -LiteralPath $ownerFile -Encoding UTF8

if (-not $NoBrowser) {
    Start-Process $openUrl
}
