@echo off
REM ────────────────────────────────────────────────────────────────────────
REM FlashTool — Windows launcher
REM ────────────────────────────────────────────────────────────────────────
echo.
echo  ⚡ FlashTool — G6-family ROM Flash Tool
echo  ─────────────────────────────────
echo.

REM Check for admin rights
net session >nul 2>&1
if %errorLevel% NEQ 0 (
    echo  ⚠️  Running without administrator privileges.
    echo  Some operations may require elevated access.
    echo.
)

REM Navigate to project root
cd /d "%~dp0\.."

REM Check Python
python --version >nul 2>&1
if %errorLevel% NEQ 0 (
    echo  ❌ Python not found. Please install Python 3.8+ from python.org
    pause
    exit /b 1
)

REM Check adb/fastboot
where adb >nul 2>&1
if %errorLevel% EQU 0 (
    echo  ✅ adb found
) else (
    echo  ⚠️  adb not in PATH. Please add platform-tools to PATH.
)

where fastboot >nul 2>&1
if %errorLevel% EQU 0 (
    echo  ✅ fastboot found
) else (
    echo  ⚠️  fastboot not in PATH. Please add platform-tools to PATH.
)

REM Install dependencies
echo.
echo  📦 Checking dependencies...
pip install -q -r requirements.txt 2>nul

REM Launch
echo.
echo  🚀 Launching FlashTool...
python main.py

pause
