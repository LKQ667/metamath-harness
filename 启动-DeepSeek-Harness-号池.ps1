# DeepSeek Harness 号池启动器（隔离 Profile：web-key-pool @ 3081）
# 独立 DSH_HOME=.dsh-key-pool，与原生 3080 完全隔离；
# 端口占用时只信任号池健康端点返回 profile=web-key-pool 才复用。
[CmdletBinding()]
param(
    [int]$Port = 3081,
    [switch]$NoBrowser
)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$hostName = '127.0.0.1'
$webUrl = "http://${hostName}:$Port"
$healthUrl = "http://${hostName}:$Port/api/dsh-api-key-pool/health"
$env:DSH_HOME = Join-Path $root '.dsh-key-pool'
$dshEntry = Join-Path $env:APPDATA 'npm\node_modules\@deepseek-ai\dsh\lib\bin.js'
$logDirectory = Join-Path $env:LOCALAPPDATA 'DeepSeekHarness\key-pool\logs'
$stdoutLog = Join-Path $logDirectory 'web-key-pool.stdout.log'
$stderrLog = Join-Path $logDirectory 'web-key-pool.stderr.log'

function Test-DshPort {
    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $task = $client.ConnectAsync($hostName, $Port)
        return $task.Wait(250) -and $client.Connected
    }
    catch {
        return $false
    }
    finally {
        $client.Dispose()
    }
}

function Test-PoolHealth {
    if (-not (Test-DshPort)) { return $false }
    try {
        $response = Invoke-RestMethod -Uri $healthUrl -Method Get -TimeoutSec 3
        return $response.ok -eq $true -and $response.profile -eq 'web-key-pool'
    }
    catch {
        return $false
    }
}

# 端口已监听时，只有号池健康端点确认 profile=web-key-pool 才复用；
# 其他服务占用该端口则明确失败，绝不误复用。
if (Test-DshPort) {
    $isPool = Test-PoolHealth
    if (-not $isPool) {
        Add-Type -AssemblyName PresentationFramework
        [System.Windows.MessageBox]::Show(
            "端口 $Port 已被其他服务占用（非 web-key-pool 号池实例），拒绝复用。`n请检查该端口或换用 -Port 指定其他端口。",
            'DeepSeek Harness 号池') | Out-Null
        exit 1
    }
    if (-not $NoBrowser) { Start-Process $webUrl }
    exit 0
}

$nodeCommand = (Get-Command node.exe -ErrorAction Stop).Source
if (-not (Test-Path -LiteralPath $dshEntry)) {
    Add-Type -AssemblyName PresentationFramework
    [System.Windows.MessageBox]::Show("DSH entry was not found: $dshEntry", 'DeepSeek Harness 号池') | Out-Null
    exit 1
}

New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
$server = Start-Process -FilePath $nodeCommand `
    -ArgumentList @($dshEntry, '--profile', 'web-key-pool', '--host', $hostName, '--port', $Port, '--no-open') `
    -WorkingDirectory $root `
    -WindowStyle Hidden `
    -RedirectStandardOutput $stdoutLog `
    -RedirectStandardError $stderrLog `
    -PassThru

$ready = $false
for ($attempt = 0; $attempt -lt 450; $attempt++) {
    Start-Sleep -Milliseconds 100
    if (Test-PoolHealth) {
        $ready = $true
        break
    }
    if ($server.HasExited) { break }
}

if (-not $ready) {
    Add-Type -AssemblyName PresentationFramework
    $detail = if (Test-Path -LiteralPath $stderrLog) {
        (Get-Content -LiteralPath $stderrLog -Tail 8) -join "`n"
    } else {
        'No error log was generated.'
    }
    [System.Windows.MessageBox]::Show("DeepSeek Harness 号池未能在 45 秒内启动。`n`n$detail`n`nLog: $stderrLog", 'DeepSeek Harness 号池') | Out-Null
    exit 1
}

if (-not $NoBrowser) { Start-Process $webUrl }
