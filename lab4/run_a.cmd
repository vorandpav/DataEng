@echo off
cd /d "%~dp0"
set COORDINATOR_ID=A
set FENCING=1
py coordinator.py --throttle 2.0
