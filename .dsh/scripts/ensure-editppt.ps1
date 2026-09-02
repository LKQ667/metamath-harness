[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$RepoRoot
)

$ErrorActionPreference = 'Stop'
$runtimeRoot = Join-Path $RepoRoot '.dsh\runtime'
$uvHome = Join-Path $runtimeRoot 'uv'
$toolDir = Join-Path $runtimeRoot 'tools'
$binDir = Join-Path $runtimeRoot 'bin'
$pythonDir = Join-Path $runtimeRoot 'python'
$cacheDir = Join-Path $runtimeRoot 'cache'
$cliRoot = Join-Path $RepoRoot '.dsh\skills\image-to-editable-ppt\cli'
$editPpt = Join-Path $binDir 'editppt.exe'
$marker = Join-Path $runtimeRoot 'editppt-source.sha256'

if (-not (Test-Path -LiteralPath (Join-Path $cliRoot 'pyproject.toml'))) {
    throw "缺少 editppt 源码：$cliRoot"
}

New-Item -ItemType Directory -Path $runtimeRoot, $uvHome, $toolDir, $binDir, $pythonDir, $cacheDir -Force | Out-Null

$sourceLines = Get-ChildItem -LiteralPath $cliRoot -Recurse -File |
    Where-Object { $_.FullName -notmatch '[\\/](__pycache__|tests)[\\/]' -and $_.Extension -notin @('.pyc', '.pyo') } |
    Sort-Object FullName |
    ForEach-Object {
        $relative = $_.FullName.Substring($cliRoot.Length).TrimStart('\', '/')
        "$relative $((Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash)"
    }
$sha = [Security.Cryptography.SHA256]::Create()
$fingerprint = ([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes(($sourceLines -join "`n"))))).Replace('-', '').ToLowerInvariant()
$installedFingerprint = if (Test-Path -LiteralPath $marker) { (Get-Content -LiteralPath $marker -Raw).Trim() } else { '' }

if ((Test-Path -LiteralPath $editPpt) -and $installedFingerprint -eq $fingerprint) {
    & $editPpt --help *> $null
    if ($LASTEXITCODE -eq 0) {
        Write-Host '    editppt 已是当前版本（跳过）' -ForegroundColor Green
        exit 0
    }
}

$uv = Join-Path $uvHome 'uv.exe'
if (-not (Test-Path -LiteralPath $uv)) {
    $systemUv = Get-Command uv -ErrorAction SilentlyContinue
    if ($systemUv) {
        $uv = $systemUv.Source
    } else {
        $arch = [Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString()
        $assetName = switch ($arch) {
            'X64' { 'uv-x86_64-pc-windows-msvc.zip' }
            'Arm64' { 'uv-aarch64-pc-windows-msvc.zip' }
            default { throw "暂不支持的 Windows 架构：$arch" }
        }
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        $headers = @{ 'User-Agent' = 'MetaMath-Harness-Installer' }
        $release = Invoke-RestMethod -Uri 'https://api.github.com/repos/astral-sh/uv/releases/latest' -Headers $headers
        $asset = $release.assets | Where-Object { $_.name -eq $assetName } | Select-Object -First 1
        if (-not $asset -or -not $asset.digest -or $asset.digest -notmatch '^sha256:([0-9a-fA-F]{64})$') {
            throw "无法取得 uv 官方安装包及 SHA-256：$assetName"
        }
        $expectedHash = $Matches[1].ToLowerInvariant()
        $tempDir = Join-Path $runtimeRoot ('.uv-download-' + [Guid]::NewGuid().ToString('N'))
        New-Item -ItemType Directory -Path $tempDir | Out-Null
        try {
            $archive = Join-Path $tempDir $assetName
            Invoke-WebRequest -Uri $asset.browser_download_url -Headers $headers -OutFile $archive -UseBasicParsing
            $actualHash = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant()
            if ($actualHash -ne $expectedHash) { throw 'uv 安装包 SHA-256 校验失败。' }
            Expand-Archive -LiteralPath $archive -DestinationPath $tempDir -Force
            $downloadedUv = Get-ChildItem -LiteralPath $tempDir -Recurse -File -Filter 'uv.exe' | Select-Object -First 1
            if (-not $downloadedUv) { throw 'uv 官方安装包内未找到 uv.exe。' }
            Copy-Item -LiteralPath $downloadedUv.FullName -Destination (Join-Path $uvHome 'uv.exe') -Force
            $uv = Join-Path $uvHome 'uv.exe'
        } finally {
            if (Test-Path -LiteralPath $tempDir) { Remove-Item -LiteralPath $tempDir -Recurse -Force }
        }
    }
}

$env:UV_TOOL_DIR = $toolDir
$env:UV_TOOL_BIN_DIR = $binDir
$env:UV_PYTHON_INSTALL_DIR = $pythonDir
$env:UV_CACHE_DIR = $cacheDir
& $uv tool install --force --python 3.12 $cliRoot
if ($LASTEXITCODE -ne 0) { throw "uv 安装 editppt 失败（退出码 $LASTEXITCODE）。" }
if (-not (Test-Path -LiteralPath $editPpt)) { throw "安装完成后未找到：$editPpt" }
& $editPpt --help *> $null
if ($LASTEXITCODE -ne 0) { throw 'editppt 安装后自检失败。' }
Set-Content -LiteralPath $marker -Value $fingerprint -Encoding UTF8
Write-Host '    editppt 已安装到项目隔离运行时' -ForegroundColor Green
