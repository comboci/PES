@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
set "OUT=%TEMP%\PES15-Demo-%RANDOM%-%RANDOM%"
where py >nul 2>nul
if errorlevel 1 (
  echo Python Launcher not found. Install Python 3.10+ and run: py -m pip install -r requirements.txt
  pause
  exit /b 2
)
echo Running PES-15 isolated Project Evolution demo...
py tools\evaluate_portfolio_builder.py --output-dir "%OUT%"
if errorlevel 1 (
  echo Demo FAILED. Check Python and jsonschema dependency: py -m pip install -r requirements.txt
  pause
  exit /b 1
)
echo Demo PASS. Output: %OUT%
pause
