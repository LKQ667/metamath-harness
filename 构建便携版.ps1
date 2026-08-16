[CmdletBinding()]
param([switch]$ReuseCache, [switch]$SkipLargeRuntime)
& (Join-Path $PSScriptRoot 'portable\Build-Portable.ps1') -ProjectRoot $PSScriptRoot -ReuseCache:$ReuseCache -SkipLargeRuntime:$SkipLargeRuntime
exit $LASTEXITCODE
