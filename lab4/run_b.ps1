$env:COORDINATOR_ID = "B"
$env:FENCING = "1"
Set-Location $PSScriptRoot
py coordinator.py --throttle 0.5
