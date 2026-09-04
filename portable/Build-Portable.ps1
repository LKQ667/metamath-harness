[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$ProjectRoot,
    [switch]$ReuseCache,
    [switch]$SkipLargeRuntime
)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
Set-StrictMode -Version Latest
$powerShellHost = (Get-Process -Id $PID).Path

$ProjectRoot = [IO.Path]::GetFullPath($ProjectRoot)
$portableDir = Join-Path $ProjectRoot 'portable'
$manifestPath = Join-Path $portableDir 'runtime-manifest.json'
$manifest = Get-Content -Raw -LiteralPath $manifestPath | ConvertFrom-Json
$cache = Join-Path $ProjectRoot '.portable-cache'
$workRoot = Join-Path $ProjectRoot '.portable-build'
$staging = Join-Path $workRoot 'DeepSeekHarness-portable-win-x64'
$unpack = Join-Path $workRoot 'zip-retest\DeepSeekHarness-portable-win-x64'
$dist = Join-Path $ProjectRoot 'dist'
$finalDir = Join-Path $dist 'DeepSeekHarness-portable-win-x64'
$finalZip = Join-Path $dist 'DeepSeekHarness-portable-win-x64.zip'
$twentyGb = 20GB
$eightGb = 8GB
$sevenGb = 7GB

function Assert-SafeBuildPath([string]$Path) {
    $full = [IO.Path]::GetFullPath($Path)
    if (-not $full.StartsWith(($ProjectRoot.TrimEnd('\') + '\'), [StringComparison]::OrdinalIgnoreCase)) {
        throw "拒绝操作项目外路径：$full"
    }
    if ($full -in @($ProjectRoot, [IO.Path]::GetPathRoot($ProjectRoot))) { throw "拒绝操作宽泛路径：$full" }
    return $full
}

function Reset-BuildDirectory([string]$Path) {
    $safe = Assert-SafeBuildPath $Path
    if (Test-Path -LiteralPath $safe) { Remove-Item -LiteralPath $safe -Recurse -Force }
    New-Item -ItemType Directory -Force -Path $safe | Out-Null
}

function Get-VerifiedDownload($component) {
    $leaf = [Uri]::UnescapeDataString(([Uri]$component.url).Segments[-1])
    $target = Join-Path $cache $leaf
    if (-not (Test-Path -LiteralPath $target)) { Invoke-WebRequest -UseBasicParsing -Uri $component.url -OutFile $target }
    if ($component.sha256 -notmatch '^[0-9a-fA-F]{64}$') { throw "$($component.id) 缺少固定 SHA-256，拒绝运行。" }
    $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $target).Hash.ToLowerInvariant()
    if ($actual -ne $component.sha256.ToLowerInvariant()) { throw "$($component.id) SHA-256 校验失败。" }
    return $target
}

function Expand-ZipFlat([string]$Archive, [string]$Destination) {
    $temporary = "$Destination.extract"
    Reset-BuildDirectory $temporary
    Expand-Archive -LiteralPath $Archive -DestinationPath $temporary -Force
    $children = @(Get-ChildItem -LiteralPath $temporary -Force)
    $source = if ($children.Count -eq 1 -and $children[0].PSIsContainer) { $children[0].FullName } else { $temporary }
    New-Item -ItemType Directory -Force -Path $Destination | Out-Null
    Copy-Item -Path (Join-Path $source '*') -Destination $Destination -Recurse -Force
    Remove-Item -LiteralPath $temporary -Recurse -Force
}

function Copy-Tree([string]$Source, [string]$Destination, [string[]]$ExcludeDirs = @(), [string[]]$ExcludeFiles = @()) {
    New-Item -ItemType Directory -Force -Path $Destination | Out-Null
    $args = @($Source, $Destination, '/E', '/COPY:DAT', '/DCOPY:DAT', '/R:1', '/W:1', '/NFL', '/NDL', '/NJH', '/NJS', '/NP')
    if ($ExcludeDirs.Count) { $args += '/XD'; $args += $ExcludeDirs }
    if ($ExcludeFiles.Count) { $args += '/XF'; $args += $ExcludeFiles }
    & robocopy.exe @args | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "复制失败：$Source -> $Destination（robocopy=$LASTEXITCODE）" }
}

function Get-ExcellentPaperRecords([string]$LibraryRoot) {
    $root = [IO.Path]::GetFullPath($LibraryRoot).TrimEnd('\')
    $catalogPath = Join-Path $root 'catalog.json'
    if (-not (Test-Path -LiteralPath $catalogPath -PathType Leaf)) { throw "优秀论文库缺少 catalog.json：$root" }
    $catalog = Get-Content -Raw -LiteralPath $catalogPath -Encoding utf8 | ConvertFrom-Json
    if ($catalog.schema -ne 'dsh.excellent-papers.catalog/v1') { throw "优秀论文 catalog schema 无效：$root" }
    $records = foreach ($paper in @($catalog.papers)) {
        $relative = [string]$paper.path
        if ([IO.Path]::IsPathRooted($relative) -or $relative -match '(^|[/\\])\.\.([/\\]|$)' -or $relative -match '\\') { throw "优秀论文路径非法：$relative" }
        $file = [IO.Path]::GetFullPath((Join-Path $root ($relative -replace '/', '\')))
        if (-not $file.StartsWith(($root + '\'), [StringComparison]::OrdinalIgnoreCase)) { throw "优秀论文路径逃逸：$relative" }
        if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { throw "优秀论文文件缺失：$relative" }
        $stream = [IO.File]::OpenRead($file)
        try { $buffer = [byte[]]::new(5); $read = $stream.Read($buffer, 0, 5) } finally { $stream.Dispose() }
        if ($read -ne 5 -or [Text.Encoding]::ASCII.GetString($buffer) -ne '%PDF-') { throw "优秀论文不是实际 PDF：$relative" }
        $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $file).Hash.ToLowerInvariant()
        if ($actual -ne ([string]$paper.sha256).ToLowerInvariant()) { throw "优秀论文 SHA-256 不一致：$relative" }
        "$relative|$actual"
    }
    $diskCount = @(Get-ChildItem -LiteralPath $root -File -Filter '*.pdf' -Recurse).Count
    if ($diskCount -ne @($records).Count) { throw "优秀论文磁盘数量与 catalog 不一致：disk=$diskCount catalog=$(@($records).Count)" }
    return @($records | Sort-Object)
}

function Assert-SameExcellentPaperLibrary([string]$Expected, [string]$Actual) {
    $expectedRecords = @(Get-ExcellentPaperRecords $Expected)
    $actualRecords = @(Get-ExcellentPaperRecords $Actual)
    $difference = @(Compare-Object $expectedRecords $actualRecords)
    if ($difference.Count -ne 0) { throw "优秀论文库分发副本与源目录不一致：$Actual" }
}

function Install-NodeAndPython {
    $node = $manifest.components | Where-Object id -eq 'node'
    $python = $manifest.components | Where-Object id -eq 'python'
    Expand-ZipFlat (Get-VerifiedDownload $node) (Join-Path $staging $node.installPath)
    $pyArchive = Get-VerifiedDownload $python
    $pyTarget = Join-Path $staging $python.installPath
    New-Item -ItemType Directory -Force -Path $pyTarget | Out-Null
    & tar.exe -xzf $pyArchive -C (Split-Path $pyTarget -Parent)
    if ($LASTEXITCODE -ne 0) { throw 'Python 独立发行版解压失败。' }
    $expanded = Join-Path (Split-Path $pyTarget -Parent) 'python'
    if (-not (Test-Path -LiteralPath (Join-Path $pyTarget 'python.exe')) -and (Test-Path -LiteralPath $expanded)) {
        Move-Item -LiteralPath $expanded -Destination $pyTarget
    }
    $pythonExe = Join-Path $pyTarget 'python.exe'
    & $pythonExe -m pip install --disable-pip-version-check --no-input --no-cache-dir ($manifest.pythonPackages.PSObject.Properties | ForEach-Object { "$($_.Name)==$($_.Value)" })
    if ($LASTEXITCODE -ne 0) { throw 'Python 固定依赖安装失败。' }
}

function Install-Drawio {
    $component = $manifest.components | Where-Object id -eq 'drawio'
    Expand-ZipFlat (Get-VerifiedDownload $component) (Join-Path $staging $component.installPath)
}

function Install-Poppler {
    $component = $manifest.components | Where-Object id -eq 'poppler'
    $package = Get-VerifiedDownload $component
    $micromamba = $manifest.components | Where-Object id -eq 'micromamba'
    $micromambaArchive = Get-VerifiedDownload $micromamba
    $microDir = Join-Path $workRoot 'micromamba'
    Reset-BuildDirectory $microDir
    & tar.exe -xjf $micromambaArchive -C $microDir 'Library/bin/micromamba.exe'
    if ($LASTEXITCODE -ne 0) { throw 'micromamba 解压失败。' }
    $micro = Join-Path $microDir 'Library\bin\micromamba.exe'
    $prefix = Join-Path $staging $component.installPath
    $env:MAMBA_ROOT_PREFIX = Join-Path $workRoot 'mamba-root'
    & $micro create -y -p $prefix -c conda-forge "poppler=26.05.0" --no-rc
    if ($LASTEXITCODE -ne 0) { throw 'Poppler 26.05.0 运行环境解析失败。' }
    if (-not (Test-Path -LiteralPath (Join-Path $prefix 'Library\bin\pdfinfo.exe'))) { throw 'Poppler 环境缺少 pdfinfo.exe。' }
    Copy-Item -LiteralPath $package -Destination (Join-Path $prefix 'conda-meta\locked-poppler-package.conda')
}

function Install-TexLive {
    $component = $manifest.components | Where-Object id -eq 'texlive'
    $zip = Join-Path $cache 'install-tl.zip'
    $checksum = Join-Path $cache 'install-tl.zip.sha512'
    Invoke-WebRequest -UseBasicParsing -Uri $component.url -OutFile $zip
    Invoke-WebRequest -UseBasicParsing -Uri 'https://mirror.ctan.org/systems/texlive/tlnet/install-tl.zip.sha512' -OutFile $checksum
    $expected = ((Get-Content -Raw -LiteralPath $checksum) -split '\s+')[0].ToLowerInvariant()
    $actual = (Get-FileHash -Algorithm SHA512 -LiteralPath $zip).Hash.ToLowerInvariant()
    if ($expected -ne $actual) { throw 'TeX Live 安装器 SHA-512 校验失败。' }
    $installer = Join-Path $workRoot 'install-tl'
    Reset-BuildDirectory $installer
    Expand-Archive -LiteralPath $zip -DestinationPath $installer -Force
    $installScript = Get-ChildItem -LiteralPath $installer -Filter 'install-tl-windows.bat' -Recurse | Select-Object -First 1
    if (-not $installScript) { throw 'TeX Live 安装器缺少 install-tl-windows.bat。' }
    $texdir = Join-Path $staging $component.installPath
    if (Test-Path -LiteralPath $texdir) { Reset-BuildDirectory $texdir }
    $profileText = Get-Content -Raw -LiteralPath (Join-Path $portableDir 'texlive.profile')
    $replacements = @{
        '__TEXDIR__'=$texdir; '__TEXMFCONFIG__'=(Join-Path $texdir 'texmf-config'); '__TEXMFHOME__'=(Join-Path $texdir 'texmf-home');
        '__TEXMFLOCAL__'=(Join-Path $texdir 'texmf-local'); '__TEXMFSYSCONFIG__'=(Join-Path $texdir 'texmf-config');
        '__TEXMFSYSVAR__'=(Join-Path $texdir 'texmf-var'); '__TEXMFVAR__'=(Join-Path $texdir 'texmf-var')
    }
    foreach ($entry in $replacements.GetEnumerator()) { $profileText = $profileText.Replace($entry.Key, ($entry.Value -replace '\\','/')) }
    $profile = Join-Path $workRoot 'texlive.generated.profile'
    Set-Content -LiteralPath $profile -Value $profileText -Encoding utf8
    & cmd.exe /d /c $installScript.FullName -profile $profile -repository 'https://mirror.ctan.org/systems/texlive/tlnet'
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath (Join-Path $texdir 'bin\windows\tlmgr.bat'))) { throw 'TeX Live 2026 portable 安装失败。' }
    $tlmgr = Join-Path $texdir 'bin\windows\tlmgr.bat'
    $packages = @('latexmk','ctex','collection-langchinese','collection-xetex','amsmath','algorithms','algorithm2e','algorithmicx','ifoddpage','relsize','pgf','booktabs','multirow','caption','titlesec','appendix','listings','fandol','tex-gyre','unicode-math','physics','siunitx','esint','needspace','zhlineskip','makecell')
    & cmd.exe /d /c $tlmgr install @packages
    if ($LASTEXITCODE -ne 0) { throw 'TeX Live 必需宏包安装失败。' }
    Set-Content -LiteralPath (Join-Path $texdir 'INSTALLER.sha512') -Value $actual -Encoding ascii
    Set-Content -LiteralPath (Join-Path $texdir 'INSTALLER.sha256') -Value (Get-FileHash -Algorithm SHA256 -LiteralPath $zip).Hash.ToLowerInvariant() -Encoding ascii
}

function Copy-Application {
    $app = Join-Path $staging 'app'
    New-Item -ItemType Directory -Force -Path $app | Out-Null
    [ordered]@{ name='deepseek-harness-portable-app'; private=$true; dependencies=[ordered]@{ '@deepseek-ai/dsh'='0.1.0-rc.6' } } |
        ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $app 'package.json') -Encoding utf8
    $npm = Join-Path $staging 'runtime\node\npm.cmd'
    if ($SkipLargeRuntime) { $npm = (Get-Command npm.cmd).Source }
    Push-Location $app
    try { & $npm install --omit=dev --ignore-scripts --no-audit --no-fund --save-exact } finally { Pop-Location }
    if ($LASTEXITCODE -ne 0) { throw 'DSH 生产依赖物化失败。' }
    Copy-Tree (Join-Path $app 'node_modules\@deepseek-ai\dsh') (Join-Path $app 'dsh')
    Copy-Tree (Join-Path $ProjectRoot 'plugins') (Join-Path $app 'plugins') @('node_modules')
    $template = Join-Path $app 'dsh-home-template'
    Reset-BuildDirectory $template
    foreach ($name in @('.agent-presets','skills','profiles')) {
        $source = Join-Path $ProjectRoot ".dsh\$name"
        if (Test-Path -LiteralPath $source) {
            $excluded = @('.git','logs','cache','sessions','storages','Overall-goal','openspec')
            if ($name -eq 'profiles') { $excluded += 'node_modules' }
            Copy-Tree $source (Join-Path $template $name) $excluded @('.credentials.yaml','.anonymous-user-id','.env','.env.*','*.log')
        }
    }
    $paperLibrary = Join-Path $ProjectRoot '.dsh\往年优秀论文'
    $paperTemplate = Join-Path $template '往年优秀论文'
    Copy-Tree $paperLibrary $paperTemplate
    Assert-SameExcellentPaperLibrary $paperLibrary $paperTemplate
    $plugin = Join-Path $app 'plugins\dsh-mathmodel'
    Push-Location $plugin
    try { & $npm install --omit=dev --ignore-scripts --no-audit --no-fund; & $npm run build } finally { Pop-Location }
    if ($LASTEXITCODE -ne 0) { throw 'Mathmodel 插件生产依赖物化或构建失败。' }
    $profile = Join-Path $template 'profiles\web'
    Push-Location $profile
    try { & $npm install --omit=dev --ignore-scripts --no-audit --no-fund --install-links=true } finally { Pop-Location }
    if ($LASTEXITCODE -ne 0) { throw 'Web Profile 依赖物化失败。' }
    Copy-Item -LiteralPath (Join-Path $portableDir 'README.md') -Destination (Join-Path $app 'README.md')
    Copy-Item -LiteralPath (Join-Path $portableDir 'Portable.Common.psm1'), (Join-Path $portableDir 'Start-Portable.ps1'), (Join-Path $portableDir 'Test-Portable.ps1'), (Join-Path $portableDir 'Remove-PortableAlias.ps1'), (Join-Path $portableDir 'secret-scan-allowlist.json') -Destination (Join-Path $staging 'portable') -Force
    Copy-Item -LiteralPath (Join-Path $ProjectRoot '启动-DeepSeek-Harness.cmd'), (Join-Path $ProjectRoot '依赖自检.cmd') -Destination $staging -Force
}

function Assert-NoExternalLinks([string]$Root) {
    $bad = @(Get-ChildItem -LiteralPath $Root -Force -Recurse -Attributes ReparsePoint -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName)
    if ($bad) { throw "发行版包含链接或重解析点：$($bad -join ', ')" }
}

function Assert-Sanitized([string]$Root) {
    $forbiddenNames = @('.credentials.yaml','.anonymous-user-id')
    $badNames = Get-ChildItem -LiteralPath $Root -Force -Recurse -File | Where-Object {
        $relative = [IO.Path]::GetRelativePath($Root, $_.FullName)
        $_.Name -in $forbiddenNames -or $_.Name -like '.env*' -or
            (($relative -match '^(?:data|app\\dsh-home-template)\\') -and $relative -match '\\(sessions|storages|Overall-goal|openspec|logs|cache)\\')
    }
    if ($badNames) { throw "发行版包含禁止文件：$($badNames[0].FullName)" }
    $extensions = @('.md','.json','.yml','.yaml','.js','.mjs','.cjs','.ts','.tsx','.py','.ps1','.cmd','.tex','.txt')
    $allowlist = Get-Content -Raw -LiteralPath (Join-Path $portableDir 'secret-scan-allowlist.json') | ConvertFrom-Json
    $patterns = [ordered]@{
        privateKey = '(?i)-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'
        token = '(?i)(?<![A-Za-z0-9])(?:sk-(?=[A-Za-z0-9_\-]{24,})(?=[A-Za-z0-9_\-]*[0-9])[A-Za-z0-9_\-]{24,}|AIza[A-Za-z0-9_\-]{30,}|ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})'
        credentialUrl = '(?i)https?://[^\s/:]{3,}:[^\s/@]{12,}@'
        absolutePath = '(?i)(?:F:\\|D:\\python|E:\\texlive|\\Users\\Lenovo|codex-runtimes)'
    }
    $scanRoots = @((Join-Path $Root 'app'), (Join-Path $Root 'portable')) | Where-Object { Test-Path -LiteralPath $_ }
    $scanFiles = @($scanRoots | ForEach-Object { Get-ChildItem -LiteralPath $_ -Recurse -File })
    $scanFiles += @(Get-ChildItem -LiteralPath $Root -File)
    foreach ($file in $scanFiles | Where-Object Extension -in $extensions) {
        $relative = [IO.Path]::GetRelativePath($Root, $file.FullName)
        if ($relative -match '(?i)(^|\\)test(s)?\\|\\test_[^\\]+$|fixtures?|snapshots?|check_no_absolute_paths\.py$|check_paper_internal_paths\.py$|quick_validate\.py$|auto-checklist\.md$') { continue }
        $allowed = $allowlist.files | Where-Object { $_.path -eq $relative -and $_.sha256 -eq (Get-FileHash -Algorithm SHA256 -LiteralPath $file.FullName).Hash.ToLowerInvariant() }
        if ($allowed) { continue }
        $text = Get-Content -Raw -LiteralPath $file.FullName -ErrorAction SilentlyContinue
        foreach ($rule in $patterns.GetEnumerator()) {
            if ($relative -match '(?i)\\node_modules\\' -and $rule.Key -in @('privateKey','credentialUrl','absolutePath')) { continue }
            if ($text -match $rule.Value) { throw "安全扫描命中：$relative（规则 $($rule.Key)，未输出敏感正文）" }
        }
    }
}

function Get-DirectorySize([string]$Root) {
    [long](Get-ChildItem -LiteralPath $Root -Recurse -File | Measure-Object Length -Sum).Sum
}

function Write-ReleaseManifest {
    $components = foreach ($component in $manifest.components | Where-Object id -ne 'micromamba') {
        $path = Join-Path $staging $component.installPath
        $sha256 = $component.sha256
        if ($component.id -eq 'texlive' -and (Test-Path -LiteralPath (Join-Path $path 'INSTALLER.sha256'))) {
            $sha256 = (Get-Content -Raw -LiteralPath (Join-Path $path 'INSTALLER.sha256')).Trim()
        }
        [ordered]@{ id=$component.id; version=$component.version; source=$component.url; sha256=$sha256; license=$component.license; installPath=$component.installPath; installedBytes=if(Test-Path $path){Get-DirectorySize $path}else{0} }
    }
    [ordered]@{ schema='dsh.portable.release/v1'; createdAt=[DateTime]::UtcNow.ToString('o'); platform='win-x64'; dsh='0.1.0-rc.6'; components=@($components); pythonPackages=$manifest.pythonPackages } |
        ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $staging 'RELEASE-MANIFEST.json') -Encoding utf8
}

$drive = Get-PSDrive -Name ([IO.Path]::GetPathRoot($ProjectRoot).TrimEnd(':\'))
if ($drive.Free -lt $twentyGb) { throw '目标盘可用空间不足 20 GB，拒绝开始构建。' }
New-Item -ItemType Directory -Force -Path $cache, $workRoot | Out-Null
if (-not ($ReuseCache -and (Test-Path -LiteralPath (Join-Path $staging 'app\dsh\lib\bin.js')))) {
    Reset-BuildDirectory $staging
}
New-Item -ItemType Directory -Force -Path (Join-Path $staging 'portable'), (Join-Path $staging 'runtime'), (Join-Path $staging 'data\logs') | Out-Null

if ($SkipLargeRuntime) {
    foreach ($relative in @('runtime\node\node.exe','runtime\python\python.exe','runtime\drawio\draw.io.exe','runtime\texlive\bin\windows\xelatex.exe','runtime\texlive\bin\windows\latexmk.exe','runtime\poppler\Library\bin\pdfinfo.exe','runtime\poppler\Library\bin\pdftoppm.exe')) {
        $target = Join-Path $staging $relative; New-Item -ItemType Directory -Force -Path (Split-Path $target -Parent) | Out-Null; Set-Content -LiteralPath $target -Value 'test fixture' -Encoding ascii
    }
} else {
    if (-not ($ReuseCache -and (Test-Path -LiteralPath (Join-Path $staging 'runtime\python\python.exe')) -and (Test-Path -LiteralPath (Join-Path $staging 'runtime\node\node.exe')))) { Install-NodeAndPython }
    if (-not ($ReuseCache -and (Test-Path -LiteralPath (Join-Path $staging 'runtime\drawio\draw.io.exe')))) { Install-Drawio }
    if (-not ($ReuseCache -and (Test-Path -LiteralPath (Join-Path $staging 'runtime\poppler\Library\bin\pdfinfo.exe')))) { Install-Poppler }
    if (-not ($ReuseCache -and (Test-Path -LiteralPath (Join-Path $staging 'runtime\texlive\bin\windows\xelatex.exe')))) { Install-TexLive }
}
foreach ($relative in @('app','portable','data')) {
    Reset-BuildDirectory (Join-Path $staging $relative)
}
New-Item -ItemType Directory -Force -Path (Join-Path $staging 'data\logs') | Out-Null
Copy-Application
Write-ReleaseManifest
foreach ($oldReport in @('SELFTEST.json','SELFTEST-UNPACKED.json')) {
    $oldReportPath = Join-Path $staging $oldReport
    if (Test-Path -LiteralPath $oldReportPath) { Remove-Item -LiteralPath $oldReportPath -Force }
}
Assert-NoExternalLinks $staging
Assert-Sanitized $staging
$size = Get-DirectorySize $staging
if ($size -gt $eightGb) { throw "解压体积超过 8 GB 硬门：$size 字节。" }
if ($size -gt $sevenGb) {
    Get-ChildItem -LiteralPath $staging -Directory | ForEach-Object { [pscustomobject]@{ Component=$_.Name; Bytes=Get-DirectorySize $_.FullName } } | Sort-Object Bytes -Descending | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $staging 'SIZE-WARNING.json') -Encoding utf8
}
if (-not $SkipLargeRuntime) {
    & $powerShellHost -NoLogo -NoProfile -ExecutionPolicy Bypass -File (Join-Path $staging 'portable\Test-Portable.ps1') -Root $staging -Json | Set-Content -LiteralPath (Join-Path $staging 'SELFTEST.json') -Encoding utf8
    if ($LASTEXITCODE -ne 0) { throw 'staging 依赖自检失败。' }
}

$candidateZip = Join-Path $workRoot 'DeepSeekHarness-portable-win-x64.zip'
if (Test-Path -LiteralPath $candidateZip) { Remove-Item -LiteralPath $candidateZip -Force }
Push-Location $workRoot
try { & (Join-Path $env:SystemRoot 'System32\tar.exe') -a --options 'zip:compression=store' -cf $candidateZip (Split-Path $staging -Leaf) } finally { Pop-Location }
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $candidateZip)) { throw 'ZIP 创建失败。' }
Reset-BuildDirectory (Split-Path $unpack -Parent)
& (Join-Path $env:SystemRoot 'System32\tar.exe') -xf $candidateZip -C (Split-Path $unpack -Parent)
if ($LASTEXITCODE -ne 0) { throw 'ZIP 解压复测失败。' }
Assert-NoExternalLinks $unpack
Assert-Sanitized $unpack
Assert-SameExcellentPaperLibrary (Join-Path $ProjectRoot '.dsh\往年优秀论文') (Join-Path $unpack 'app\dsh-home-template\往年优秀论文')
if (-not $SkipLargeRuntime) {
    & $powerShellHost -NoLogo -NoProfile -ExecutionPolicy Bypass -File (Join-Path $unpack 'portable\Test-Portable.ps1') -Root $unpack -Json | Set-Content -LiteralPath (Join-Path $unpack 'SELFTEST-UNPACKED.json') -Encoding utf8
    if ($LASTEXITCODE -ne 0) { throw 'ZIP 解压复测失败。' }
}
if ($SkipLargeRuntime) { Write-Host '测试构建通过；SkipLargeRuntime 模式不发布 dist。'; exit 0 }

New-Item -ItemType Directory -Force -Path $dist | Out-Null
if (Test-Path -LiteralPath $finalDir) { throw "正式目录已存在，安全策略拒绝覆盖：$finalDir" }
if (Test-Path -LiteralPath $finalZip) { throw "正式 ZIP 已存在，安全策略拒绝覆盖：$finalZip" }
Move-Item -LiteralPath $staging -Destination $finalDir
Move-Item -LiteralPath $candidateZip -Destination $finalZip
Write-Host "便携版发布完成：$finalDir"
Write-Host "ZIP：$finalZip"
