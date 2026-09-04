[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$SourceDshHome,
    [Parameter(Mandatory)][string]$StageDshHome,
    [string]$PortableRoot,
    [switch]$Json
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Get-LibraryRecords([string]$DshHome) {
    $library = [IO.Path]::GetFullPath((Join-Path $DshHome '往年优秀论文')).TrimEnd('\')
    $catalogPath = Join-Path $library 'catalog.json'
    if (-not (Test-Path -LiteralPath $catalogPath -PathType Leaf)) { throw "缺少 catalog.json：$library" }
    $catalog = Get-Content -Raw -LiteralPath $catalogPath -Encoding utf8 | ConvertFrom-Json
    if ($catalog.schema -ne 'dsh.excellent-papers.catalog/v1') { throw "catalog schema 无效：$library" }
    $records = foreach ($paper in @($catalog.papers)) {
        $relative = [string]$paper.path
        if ([IO.Path]::IsPathRooted($relative) -or $relative -match '(^|[/\\])\.\.([/\\]|$)' -or $relative -match '\\') { throw "catalog 路径非法：$relative" }
        $file = [IO.Path]::GetFullPath((Join-Path $library ($relative -replace '/', '\')))
        if (-not $file.StartsWith(($library + '\'), [StringComparison]::OrdinalIgnoreCase)) { throw "catalog 路径逃逸：$relative" }
        if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { throw "catalog 文件缺失：$relative" }
        $stream = [IO.File]::OpenRead($file)
        try { $buffer = [byte[]]::new(5); $read = $stream.Read($buffer, 0, 5) } finally { $stream.Dispose() }
        if ($read -ne 5 -or [Text.Encoding]::ASCII.GetString($buffer) -ne '%PDF-') { throw "文件不是实际 PDF：$relative" }
        $hash = (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($hash -ne ([string]$paper.sha256).ToLowerInvariant()) { throw "SHA-256 不一致：$relative" }
        "$relative|$hash"
    }
    $pdfCount = @(Get-ChildItem -LiteralPath $library -File -Filter '*.pdf' -Recurse).Count
    if ($pdfCount -ne @($records).Count) { throw "磁盘 PDF 与 catalog 数量不一致：$library" }
    return @($records | Sort-Object)
}

function Assert-EqualRecords([string[]]$Expected, [string[]]$Actual, [string]$Label) {
    $difference = @(Compare-Object $Expected $Actual)
    if ($difference.Count -ne 0) { throw "$Label 的论文路径或哈希集合不一致" }
}

$source = @(Get-LibraryRecords $SourceDshHome)
$stage = @(Get-LibraryRecords $StageDshHome)
Assert-EqualRecords $source $stage '公开 staging'
$checked = @('source', 'stage')

if ($PortableRoot) {
    $templateHome = Join-Path $PortableRoot 'app\dsh-home-template'
    $template = @(Get-LibraryRecords $templateHome)
    Assert-EqualRecords $source $template '便携模板'
    $checked += 'portable-template'
    $dataHome = Join-Path $PortableRoot 'data\dsh-home'
    if (Test-Path -LiteralPath $dataHome) {
        $data = @(Get-LibraryRecords $dataHome)
        Assert-EqualRecords $source $data '便携首次启动目录'
        $checked += 'portable-data'
    }
}

$result = [ordered]@{schema='dsh.excellent-papers.acceptance/v1';status='pass';count=$source.Count;checked=$checked}
if ($Json) { $result | ConvertTo-Json -Depth 4 } else { "优秀论文分发验收：PASS（$($source.Count) 份；$($checked -join ', ')）" }
