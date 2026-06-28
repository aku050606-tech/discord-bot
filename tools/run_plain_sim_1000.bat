@echo off
cd /d "%~dp0\.."
python tools\simulate_land.py --area plain --runs 1000 --seed 1
pause
