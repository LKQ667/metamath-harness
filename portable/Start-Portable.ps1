[CmdletBinding()]
param([int]$Port = 3080, [switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot 'Portable.Common.psm1') -Force
$layout = Get-PortableLayout -Root (Split-Path $PSScriptRoot -Parent)
Initialize-PortableData -Layout $layout
Set-PortableEnvironment -Layout $layout
$processRoot = if ($env:DSH_PORTABLE_ALIAS_DRIVE) { "$($env:DSH_PORTABLE_ALIAS_DRIVE)\" } else { $layout.Root }
$processNode = Join-Path $processRoot 'runtime\node\node.exe'
$processCli = Join-Path $processRoot 'app\dsh\lib\bin.js'
$processApp = Join-Path $processRoot 'app'

foreach ($required in @($layout.Node, $layout.DshCli)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) { throw "发行版缺少必需文件：$required" }
    if (-not (Test-PathWithin -Root $layout.Root -Candidate $required)) { throw "拒绝使用发行版外路径：$required" }
}

$owner = Test-PortablePortOwner -Layout $layout -Port $Port
if ($owner.occupied) {
    if (-not $owner.sameDistribution) { throw "端口 $Port 已被其他程序占用（PID $($owner.pid)），拒绝误复用。" }
    if (-not $NoBrowser) { Start-Process "http://127.0.0.1:$Port" }
    exit 0
}

$stdout = Join-Path $layout.Logs 'web.stdout.log'
$stderr = Join-Path $layout.Logs 'web.stderr.log'
$arguments = @($processCli, '--profile', 'web', '--host', '127.0.0.1', '--port', [string]$Port)
$process = Start-Process -FilePath $processNode -ArgumentList $arguments -WorkingDirectory $processApp -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru
if ($env:DSH_PORTABLE_ALIAS_DRIVE) {
    $monitor = Join-Path $PSScriptRoot 'Remove-PortableAlias.ps1'
    Start-Process -FilePath (Get-Process -Id $PID).Path -ArgumentList @('-NoLogo','-NoProfile','-WindowStyle','Hidden','-File',$monitor,'-ProcessId',[string]$process.Id,'-Drive',$env:DSH_PORTABLE_ALIAS_DRIVE) -WindowStyle Hidden | Out-Null
}
$deadline = [DateTime]::UtcNow.AddSeconds(45)
do {
    if ($process.HasExited) { throw "Harness 启动失败，退出码 $($process.ExitCode)；请查看 $stderr" }
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$Port" -TimeoutSec 2
        if ($response.StatusCode -eq 200) {
            if (-not $NoBrowser) { Start-Process "http://127.0.0.1:$Port" }
            exit 0
        }
    } catch {}
    Start-Sleep -Milliseconds 500
} while ([DateTime]::UtcNow -lt $deadline)
throw "Harness 在 45 秒内未就绪；请查看 $stderr"
