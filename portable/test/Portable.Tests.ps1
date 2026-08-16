$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
Import-Module (Join-Path $root 'Portable.Common.psm1') -Force
$temp = Join-Path $env:TEMP ("dsh-portable-test-" + [Guid]::NewGuid().ToString('N'))
$savedPath = $env:PATH
New-Item -ItemType Directory -Force -Path $temp | Out-Null
try {
    $layout = Get-PortableLayout -Root $temp
    if (-not (Test-PathWithin -Root $temp -Candidate (Join-Path $temp 'runtime\node\node.exe'))) { throw '根内路径判定失败' }
    if (Test-PathWithin -Root $temp -Candidate (Join-Path (Split-Path $temp -Parent) 'escape.exe')) { throw '越界路径未被拒绝' }
    New-Item -ItemType Directory -Force -Path (Join-Path $layout.App 'dsh-home-template') | Out-Null
    Set-Content -LiteralPath (Join-Path $layout.App 'dsh-home-template\marker.txt') -Value 'fixture' -Encoding utf8
    Initialize-PortableData -Layout $layout
    if (-not (Test-Path -LiteralPath (Join-Path $layout.DshHome 'marker.txt'))) { throw '首次 data 初始化失败' }
    Set-Content -LiteralPath (Join-Path $layout.DshHome 'preserve.txt') -Value 'user' -Encoding utf8
    Initialize-PortableData -Layout $layout
    if (-not (Test-Path -LiteralPath (Join-Path $layout.DshHome 'preserve.txt'))) { throw '重复初始化覆盖用户数据' }
    Set-PortableEnvironment -Layout $layout
    if ($env:DSH_PORTABLE_STRICT -ne '1' -or $env:PATH -match [regex]::Escape($savedPath)) { throw '严格环境配置失败' }
    $expectedSystem32 = Join-Path $env:SystemRoot 'System32'
    if (($env:PATH -split ';') -notcontains $expectedSystem32) { throw '严格环境缺少 Windows System32 基础工具目录' }
    'Portable.Common：PASS'
} finally {
    $env:PATH = $savedPath
    if (Test-Path -LiteralPath $temp) { Remove-Item -LiteralPath $temp -Recurse -Force }
}
