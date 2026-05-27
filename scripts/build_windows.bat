@echo off
REM ────────────────────────────────────────────────────────────────────────
REM FlashTool — Build Windows Installer (.exe)
REM ────────────────────────────────────────────────────────────────────────
echo.
echo  ╔══════════════════════════════════════════════════════╗
echo  ║  ⚡ FlashTool Build — Windows                       ║
echo  ╚══════════════════════════════════════════════════════╝
echo.

cd /d "%~dp0\.."

REM ── Step 1: Setup venv ───────────────────────────────────────────────
echo  📦 [1/3] Setting up build environment...
if not exist ".venv" (
    python -m venv .venv
)
call .venv\Scripts\activate.bat
pip install -q -r requirements.txt
pip install -q pyinstaller

REM ── Step 2: Build with PyInstaller ───────────────────────────────────
echo.
echo  🔨 [2/3] Building standalone .exe with PyInstaller...
pyinstaller FlashTool.spec --clean --noconfirm

if not exist "dist\FlashTool.exe" (
    echo  ❌ Build failed: dist\FlashTool.exe not found
    pause
    exit /b 1
)

echo  ✅ Binary built: dist\FlashTool.exe

REM ── Step 3: Create Inno Setup script ─────────────────────────────────
echo.
echo  📦 [3/3] Generating Inno Setup installer script...

(
echo [Setup]
echo AppName=FlashTool
echo AppVersion=1.1.3
echo DefaultDirName={autopf}\FlashTool
echo DefaultGroupName=FlashTool
echo UninstallDisplayIcon={app}\FlashTool.exe
echo OutputDir=dist\installer
echo OutputBaseFilename=FlashTool_Setup_1.1.3
echo Compression=lzma2
echo SolidCompression=yes
echo PrivilegesRequired=admin
echo.
echo [Files]
echo Source: "dist\FlashTool.exe"; DestDir: "{app}"; Flags: ignoreversion
echo.
echo [Icons]
echo Name: "{group}\FlashTool"; Filename: "{app}\FlashTool.exe"
echo Name: "{commondesktop}\FlashTool"; Filename: "{app}\FlashTool.exe"
echo.
echo [Run]
echo Filename: "{app}\FlashTool.exe"; Description: "Launch FlashTool"; Flags: nowait postinstall skipifsilent
) > dist\FlashTool_InnoSetup.iss

echo  ✅ Inno Setup script: dist\FlashTool_InnoSetup.iss

echo.
echo  ╔══════════════════════════════════════════════════════╗
echo  ║  ✅ Build Complete!                                  ║
echo  ╠══════════════════════════════════════════════════════╣
echo  ║  Standalone: dist\FlashTool.exe                     ║
echo  ║  Inno Setup: dist\FlashTool_InnoSetup.iss           ║
echo  ╚══════════════════════════════════════════════════════╝
echo.
echo  To create a Windows installer (.exe setup):
echo    1. Install Inno Setup: https://jrsoftware.org/isinfo.php
echo    2. Open dist\FlashTool_InnoSetup.iss in Inno Setup
echo    3. Click Compile
echo.
echo  Or just distribute dist\FlashTool.exe as a portable app.
echo.
pause
