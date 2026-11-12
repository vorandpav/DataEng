$env:COORDINATOR_ID = "A"
$env:FENCING = "1"
Set-Location $PSScriptRoot
py coordinator.py --throttle 2.0
