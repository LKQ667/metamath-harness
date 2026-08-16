param([Parameter(Mandatory)][int]$ProcessId, [Parameter(Mandatory)][ValidatePattern('^[A-Z]:$')][string]$Drive)
$ErrorActionPreference = 'SilentlyContinue'
Wait-Process -Id $ProcessId
& (Join-Path $env:SystemRoot 'System32\subst.exe') $Drive /d | Out-Null
