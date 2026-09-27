param([ValidateRange(1024,65535)][int]$Port = 8554)
$ErrorActionPreference = 'Stop'
$binary = Join-Path $PSScriptRoot 'mediamtx.exe'
if (!(Test-Path $binary)) { throw 'Run this script from the complete Windows release folder.' }
# Undo only automatic block rules for this copy of our video server.
Get-NetFirewallApplicationFilter | Where-Object { $_.Program -eq $binary } | Get-NetFirewallRule | Where-Object { $_.Direction -eq 'Inbound' -and $_.Action -eq 'Block' } | Disable-NetFirewallRule
$name = "RemoteEyeContactPortable-$Port"
Get-NetFirewallRule -Name $name -ErrorAction SilentlyContinue | Remove-NetFirewallRule
New-NetFirewallRule -Name $name -DisplayName "Remote Eye Contact TCP $Port" -Direction Inbound -Action Allow -Protocol TCP -LocalPort $Port -RemoteAddress LocalSubnet,100.64.0.0/10,fd7a:115c:a1e0::/48 -Profile Any | Out-Null
