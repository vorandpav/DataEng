@echo off
cd /d "%~dp0"
set COORDINATOR_ID=B
set FENCING=1
py coordinator.py --throttle 0.5
