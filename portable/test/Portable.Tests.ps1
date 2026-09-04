$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
Import-Module (Join-Path $root 'Portable.Common.psm1') -Force
$temp = Join-Path $env:TEMP ("dsh-portable-test-" + [Guid]::NewGuid().ToString('N'))
$environmentNames = @(
    'PATH','DSH_PORTABLE_ROOT','DSH_HOME','DSH_RUNTIME_ROOT','DSH_RUNTIME_ALIAS_ROOT','DSH_PORTABLE_STRICT',
    'DRAWIO_CLI','MATH_PAPER_CN_RUNTIME','PYTHONHOME','PYTHONPYCACHEPREFIX','MPLCONFIGDIR','TEXMFVAR','TEXMFCONFIG'
)
$savedEnvironment = @{}
foreach ($name in $environmentNames) { $savedEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') }
$savedPath = $savedEnvironment['PATH']
New-Item -ItemType Directory -Force -Path $temp | Out-Null
try {
    $layout = Get-PortableLayout -Root $temp
    if (-not (Test-PathWithin -Root $temp -Candidate (Join-Path $temp 'runtime\node\node.exe'))) { throw '根内路径判定失败' }
    if (Test-PathWithin -Root $temp -Candidate (Join-Path (Split-Path $temp -Parent) 'escape.exe')) { throw '越界路径未被拒绝' }
    $template = Join-Path $layout.App 'dsh-home-template'
    New-Item -ItemType Directory -Force -Path $template | Out-Null
    Set-Content -LiteralPath (Join-Path $template 'marker.txt') -Value 'fixture' -Encoding utf8
    $paperTemplate = Join-Path $template '往年优秀论文\国赛\2023\A题'
    New-Item -ItemType Directory -Force -Path $paperTemplate | Out-Null
    $paper = Join-Path $paperTemplate 'fixture.pdf'
    [IO.File]::WriteAllBytes($paper, [Text.Encoding]::ASCII.GetBytes('%PDF-portable-fixture'))
    $paperHash = (Get-FileHash -LiteralPath $paper -Algorithm SHA256).Hash.ToLowerInvariant()
    [ordered]@{
        schema='dsh.excellent-papers.catalog/v1'
        competitions=[ordered]@{ '国赛'=@('CUMCM') }
        papers=@([ordered]@{path='国赛/2023/A题/fixture.pdf';competition='国赛';year=2023;problem='A';priority=100;sha256=$paperHash})
    } | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $template '往年优秀论文\catalog.json') -Encoding utf8
    Initialize-PortableData -Layout $layout
    if (-not (Test-Path -LiteralPath (Join-Path $layout.DshHome 'marker.txt'))) { throw '首次 data 初始化失败' }
    $materializedPaper = Join-Path $layout.DshHome '往年优秀论文\国赛\2023\A题\fixture.pdf'
    if (-not (Test-Path -LiteralPath $materializedPaper)) { throw '优秀论文库未从模板物化到 data/dsh-home' }
    if ((Get-FileHash -LiteralPath $materializedPaper -Algorithm SHA256).Hash.ToLowerInvariant() -ne $paperHash) { throw '优秀论文首次物化哈希不一致' }
    $bytes = [IO.File]::ReadAllBytes($materializedPaper)
    if ([Text.Encoding]::ASCII.GetString($bytes, 0, 5) -ne '%PDF-') { throw '优秀论文物化结果不是实际 PDF' }
    Set-Content -LiteralPath (Join-Path $layout.DshHome 'preserve.txt') -Value 'user' -Encoding utf8
    Initialize-PortableData -Layout $layout
    if (-not (Test-Path -LiteralPath (Join-Path $layout.DshHome 'preserve.txt'))) { throw '重复初始化覆盖用户数据' }
    Set-PortableEnvironment -Layout $layout
    if ($env:DSH_PORTABLE_STRICT -ne '1' -or $env:PATH -match [regex]::Escape($savedPath)) { throw '严格环境配置失败' }
    $expectedSystem32 = Join-Path $env:SystemRoot 'System32'
    if (($env:PATH -split ';') -notcontains $expectedSystem32) { throw '严格环境缺少 Windows System32 基础工具目录' }
    'Portable.Common：PASS'
} finally {
    foreach ($name in $environmentNames) { [Environment]::SetEnvironmentVariable($name, $savedEnvironment[$name], 'Process') }
    if (Test-Path -LiteralPath $temp) { Remove-Item -LiteralPath $temp -Recurse -Force }
}
