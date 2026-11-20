@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo Python Launcher not found. Install Python 3.10+ and run: py -m pip install -r requirements.txt
  pause
  exit /b 2
)
echo Verifying PES-15 package files...
py -m pes15 verify-package
if errorlevel 1 (echo Verification FAILED.& pause & exit /b 1)
echo Running all PES-15 unit, migration, store, and concurrency tests...
py -m unittest discover -s tests -v
if errorlevel 1 (echo Tests FAILED.& pause & exit /b 1)
echo All PES-15 checks PASSED.
pause
