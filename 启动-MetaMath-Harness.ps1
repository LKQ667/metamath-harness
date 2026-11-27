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
$dshCommand = Get-Command dsh.cmd -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
if ($dshCommand) {
    $pathEntry = Join-Path (Split-Path $dshCommand.Source -Parent) 'node_modules\@deepseek-ai\dsh\lib\bin.js'
    if (Test-Path -LiteralPath $pathEntry -PathType Leaf) { $dshEntry = $pathEntry }
}
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
            Select-String -Pattern $pattern |
            ForEach-Object { [int]$_.Matches[0].Groups[1].Value }
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
    if (-not $process -or $process.CommandLine -notmatch [regex]::Escape($dshEntry)) {
        throw "端口 $Port 的 DSH 进程身份不符或 PID 已复用；已拒绝复用。"
    }
    # createdAt 容差比较：JSON 序列化会丢毫秒，字符串精确比对必然误判。
    if (-not $owner.createdAt -or
        [Math]::Abs(((Get-Date $owner.createdAt).ToUniversalTime() - $process.CreationDate.ToUniversalTime()).TotalSeconds) -gt 2) {
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

function Remove-OrphanedDshWeb {
    # 仅清理"本项目端口"的 dsh web 孤儿：上次启动失败后 bin.js 以不同 PID
    # respawn 的监听进程。命令行必须同时匹配本项目 entry、host 与 port；
    # 不匹配的一律不动（保留 fail-closed，绝不误杀其他实例）。
    Get-CimInstance Win32_Process -Filter "Name = 'node.exe'" | Where-Object {
        $_.ProcessId -ne $PID -and
        $_.CommandLine -like "*$dshEntry*" -and
        $_.CommandLine -match "web\s" -and
        $_.CommandLine -match "--host\s+$hostName\s" -and
        $_.CommandLine -match "--port\s+$Port(\s|$)"
    } | ForEach-Object {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }
}

# Reuse only a fully identified running service. For an interactive launch,
# prefer the token URL persisted with the owner record (same verified
# instance); the log scan stays as the fail-closed fallback for records
# written before that field existed.
$listenerPid = Get-DshListenerPid
$reusedHotStart = $false
if ($listenerPid) {
    try {
        Assert-DshOwner $listenerPid
        $reusedHotStart = $true
    } catch {
        # 断言失败可能是上次启动失败遗留的本项目孤儿（bin.js respawn 后 PID
        # 不同）。清掉本项目孤儿后端口应释放；仍被占用则维持 fail-closed。
        Remove-OrphanedDshWeb
        Start-Sleep -Seconds 2
        if (Get-DshListenerPid) { throw }
    }
    if ($reusedHotStart) {
        if (-not $NoBrowser) {
            $owner = Get-Content -LiteralPath $ownerFile -Raw -Encoding UTF8 | ConvertFrom-Json
            $openUrl = if ($owner.tokenUrl) { $owner.tokenUrl } else { Wait-DshTokenUrl }
            if (-not $openUrl) { throw 'DSH 正在监听，但尚未产生认证 URL；已拒绝打开未认证页面。' }
            Start-Process $openUrl
        }
        exit 0
    }
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
$startedAtUtc = [DateTime]::UtcNow
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
for ($attempt = 0; $attempt -lt 900; $attempt++) {
    Start-Sleep -Milliseconds 100
    if ($server.HasExited) { break }
    $openUrl = Get-DshTokenUrl
    if ($openUrl) {
        $listenerPid = Get-DshListenerPid
        if ($listenerPid) {
            # bin.js 可能把监听移交给 respawn 的子进程（监听 PID ≠ 启动 PID）。
            # 以真实监听者覆写 owner 记录后再断言：命令行必须匹配本项目
            # entry+host+port，且创建时间晚于本次启动（PID 复用防护不弱化）。
            $listenerProc = Get-CimInstance Win32_Process -Filter "ProcessId = $listenerPid" -ErrorAction SilentlyContinue
            if ($listenerProc -and
                $listenerProc.CommandLine -match [regex]::Escape($dshEntry) -and
                $listenerProc.CommandLine -match "--host\s+$hostName\s" -and
                $listenerProc.CommandLine -match "--port\s+$Port(\s|$)" -and
                $listenerProc.CreationDate.ToUniversalTime() -ge $startedAtUtc.AddSeconds(-2)) {
                @{ repo = $root; entry = $dshEntry; port = $Port; processId = $listenerPid; createdAt = $listenerProc.CreationDate.ToUniversalTime().ToString('o') } |
                    ConvertTo-Json | Set-Content -LiteralPath $ownerFile -Encoding UTF8
                $listenPidOwner = $listenerPid
                $createdAtOwner = $listenerProc.CreationDate.ToUniversalTime().ToString('o')
                Assert-DshOwner $listenerPid
                $ready = $true
                break
            }
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
    Remove-OrphanedDshWeb
    Remove-Item -LiteralPath $ownerFile -Force -ErrorAction SilentlyContinue
    [System.Windows.MessageBox]::Show("MetaMath Harness did not start within 90 seconds.`n`n$detail`n`nLog: $stderrLog", 'MetaMath Harness') | Out-Null
    exit 1
}

# Persist the authenticated URL with the owner record so a later hot start
# opens instantly without depending on the log tail window. Keep the real
# listener identity (PID + ISO createdAt) so the hot-start assertion matches.
@{ repo = $root; entry = $dshEntry; port = $Port; processId = $listenPidOwner; createdAt = $createdAtOwner; tokenUrl = $openUrl } |
    ConvertTo-Json | Set-Content -LiteralPath $ownerFile -Encoding UTF8

if (-not $NoBrowser) {
    Start-Process $openUrl
}
