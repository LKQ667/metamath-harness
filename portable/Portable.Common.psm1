Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Test-PathWithin {
    param([Parameter(Mandatory)][string]$Root, [Parameter(Mandatory)][string]$Candidate)
    $rootFull = [IO.Path]::GetFullPath($Root).TrimEnd('\') + '\'
    $candidateFull = [IO.Path]::GetFullPath($Candidate)
    return $candidateFull.StartsWith($rootFull, [StringComparison]::OrdinalIgnoreCase)
}

function Get-ShortWindowsPath {
    param([Parameter(Mandatory)][string]$Path)
    if ($Path -cmatch '^[\x00-\x7F]+$') { return $Path }
    if (-not ('DshPortable.NativePaths' -as [type])) {
        Add-Type -TypeDefinition @'
using System;
using System.Text;
using System.Runtime.InteropServices;
namespace DshPortable { public static class NativePaths {
  [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
  static extern uint GetShortPathName(string longPath, StringBuilder shortPath, uint size);
  public static string Short(string path) { var b=new StringBuilder(32768); var n=GetShortPathName(path,b,(uint)b.Capacity); return n>0 ? b.ToString() : path; }
} }
'@
    }
    $full = [IO.Path]::GetFullPath($Path)
    $short = [DshPortable.NativePaths]::Short($full)
    if ($short -cmatch '^[\x00-\x7F]+$') { return $short }
    $portableRoot = $env:DSH_PORTABLE_ROOT
    if ($portableRoot -and (Test-PathWithin -Root $portableRoot -Candidate $full)) {
        $alias = New-PortableAsciiAlias -Root $portableRoot
        return Join-Path $alias ([IO.Path]::GetRelativePath($portableRoot, $full))
    }
    return $full
}

function New-PortableAsciiAlias {
    param([Parameter(Mandatory)][string]$Root)
    $rootFull = [IO.Path]::GetFullPath($Root)
    if ($rootFull -cmatch '^[\x00-\x7F]+$') { return $rootFull }
    if ($env:DSH_PORTABLE_ALIAS_DRIVE -and (Test-Path "$($env:DSH_PORTABLE_ALIAS_DRIVE)\")) {
        return "$($env:DSH_PORTABLE_ALIAS_DRIVE)\"
    }
    foreach ($letter in [char[]]'ZYXWVUTSRQP') {
        $drive = "$letter`:"
        if (Test-Path "$drive\") { continue }
        & (Join-Path $env:SystemRoot 'System32\subst.exe') $drive $rootFull
        if ($LASTEXITCODE -eq 0 -and (Test-Path "$drive\")) {
            $env:DSH_PORTABLE_ALIAS_DRIVE = $drive
            return "$drive\"
        }
    }
    throw '非 ASCII 解压路径需要临时盘符别名，但没有可用盘符。'
}

function Get-PortableLayout {
    param([Parameter(Mandatory)][string]$Root)
    $rootFull = [IO.Path]::GetFullPath($Root)
    [ordered]@{
        Root = $rootFull
        Runtime = Join-Path $rootFull 'runtime'
        App = Join-Path $rootFull 'app'
        Data = Join-Path $rootFull 'data'
        DshHome = Join-Path $rootFull 'data\dsh-home'
        Logs = Join-Path $rootFull 'data\logs'
        Node = Join-Path $rootFull 'runtime\node\node.exe'
        Python = Join-Path $rootFull 'runtime\python\python.exe'
        Drawio = Join-Path $rootFull 'runtime\drawio\draw.io.exe'
        XeLaTex = Join-Path $rootFull 'runtime\texlive\bin\windows\xelatex.exe'
        PdfInfo = Join-Path $rootFull 'runtime\poppler\Library\bin\pdfinfo.exe'
        DshCli = Join-Path $rootFull 'app\dsh\lib\bin.js'
    }
}

function Initialize-PortableData {
    param([Parameter(Mandatory)][hashtable]$Layout)
    New-Item -ItemType Directory -Force -Path $Layout.Data, $Layout.Logs | Out-Null
    if (-not (Test-Path -LiteralPath $Layout.DshHome)) {
        $template = Join-Path $Layout.App 'dsh-home-template'
        if (-not (Test-Path -LiteralPath $template)) { throw "发行版缺少初始化模板：$template" }
        Copy-Item -LiteralPath $template -Destination $Layout.DshHome -Recurse
    }
}

function Set-PortableEnvironment {
    param([Parameter(Mandatory)][hashtable]$Layout)
    $env:DSH_PORTABLE_ROOT = $Layout.Root
    $processRoot = New-PortableAsciiAlias -Root $Layout.Root
    $processRuntime = Join-Path $processRoot 'runtime'
    $env:DSH_HOME = $Layout.DshHome
    $env:DSH_RUNTIME_ROOT = $Layout.Runtime
    $env:DSH_RUNTIME_ALIAS_ROOT = $processRuntime
    $env:DSH_PORTABLE_STRICT = '1'
    $env:DRAWIO_CLI = Join-Path $processRuntime 'drawio\draw.io.exe'
    $env:MATH_PAPER_CN_RUNTIME = $Layout.Runtime
    $env:PYTHONHOME = Join-Path $Layout.Runtime 'python'
    $env:PYTHONPYCACHEPREFIX = Join-Path $Layout.Data 'cache\python'
    $env:MPLCONFIGDIR = Join-Path $Layout.Data 'cache\matplotlib'
    $env:TEXMFVAR = Join-Path $Layout.Data 'cache\texlive\texmf-var'
    $env:TEXMFCONFIG = Join-Path $Layout.Data 'cache\texlive\texmf-config'
    $paths = @(
        (Join-Path $processRuntime 'node'),
        (Join-Path $processRuntime 'python'),
        (Join-Path $processRuntime 'python\Scripts'),
        (Join-Path $processRuntime 'texlive\bin\windows'),
        (Join-Path $processRuntime 'poppler\Library\bin'),
        (Join-Path $processRuntime 'drawio'),
        (Join-Path $env:SystemRoot 'System32')
    )
    $env:PATH = ($paths -join ';')
    foreach ($dir in @($env:PYTHONPYCACHEPREFIX, $env:MPLCONFIGDIR, $env:TEXMFVAR, $env:TEXMFCONFIG)) {
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
    }
}

function Test-PortablePortOwner {
    param([Parameter(Mandatory)][hashtable]$Layout, [int]$Port = 3080)
    $connection = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $connection) { return [ordered]@{ occupied = $false; sameDistribution = $false; pid = $null } }
    $process = Get-CimInstance Win32_Process -Filter "ProcessId=$($connection.OwningProcess)" -ErrorAction SilentlyContinue
    $command = [string]$process.CommandLine
    $processRoot = if ($env:DSH_PORTABLE_ALIAS_DRIVE) { "$($env:DSH_PORTABLE_ALIAS_DRIVE)\" } else { $Layout.Root }
    $processCli = Join-Path $processRoot 'app\dsh\lib\bin.js'
    $sameNode = $process -and (Test-PathWithin -Root $processRoot -Candidate ([string]$process.ExecutablePath))
    $sameCli = $command.IndexOf($processCli, [StringComparison]::OrdinalIgnoreCase) -ge 0
    [ordered]@{ occupied = $true; sameDistribution = ($sameNode -and $sameCli); pid = $connection.OwningProcess }
}

Export-ModuleMember -Function Test-PathWithin, Get-ShortWindowsPath, New-PortableAsciiAlias, Get-PortableLayout, Initialize-PortableData, Set-PortableEnvironment, Test-PortablePortOwner
