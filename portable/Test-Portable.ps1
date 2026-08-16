[CmdletBinding()]
param([string]$Root = (Split-Path $PSScriptRoot -Parent), [switch]$Json)
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot 'Portable.Common.psm1') -Force
$layout = Get-PortableLayout -Root $Root
Set-PortableEnvironment -Layout $layout
$definitions = @(
    @{ id='node'; path=$layout.Node; args=@('--version') },
    @{ id='python'; path=$layout.Python; args=@('--version') },
    @{ id='xelatex'; path=(Get-ShortWindowsPath $layout.XeLaTex); reportPath=$layout.XeLaTex; args=@('--version') },
    @{ id='latexmk'; path=(Get-ShortWindowsPath (Join-Path $layout.Runtime 'texlive\bin\windows\latexmk.exe')); reportPath=(Join-Path $layout.Runtime 'texlive\bin\windows\latexmk.exe'); args=@('--version') },
    @{ id='drawio'; path=$layout.Drawio; args=@('--version') },
    @{ id='pdftoppm'; path=(Join-Path $layout.Runtime 'poppler\Library\bin\pdftoppm.exe'); args=@('-v') },
    @{ id='pdfinfo'; path=$layout.PdfInfo; args=@('-v') }
)
$items = foreach ($item in $definitions) {
    $reportPath = if ($item.ContainsKey('reportPath')) { $item.reportPath } else { $item.path }
    $inside = Test-PathWithin -Root $layout.Root -Candidate $reportPath
    $exists = Test-Path -LiteralPath $item.path -PathType Leaf
    $exitCode = $null
    if ($inside -and $exists) {
        $p = Start-Process -FilePath $item.path -ArgumentList $item.args -WindowStyle Hidden -Wait -PassThru
        $exitCode = $p.ExitCode
    }
    [ordered]@{ id=$item.id; path=[IO.Path]::GetRelativePath($layout.Root, $reportPath); source='bundled'; insideRoot=$inside; exists=$exists; exitCode=$exitCode; status=if($inside -and $exists -and $exitCode -eq 0){'available'}else{'missing'} }
}
$report = [ordered]@{
    schema='dsh.portable.selftest/v1'
    root='.'
    strict=$true
    status=if(@($items | Where-Object status -ne 'available').Count -eq 0){'ready'}else{'attention'}
    checkedAt=[DateTime]::UtcNow.ToString('o')
    items=@($items)
}
$text = $report | ConvertTo-Json -Depth 5
if ($Json) { $text } else { $report.items | Format-Table id,status,source,path -AutoSize; "状态：$($report.status)" }
if ($report.status -ne 'ready') { exit 1 }
