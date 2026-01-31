@echo off
echo ========================================
echo  Employee Tracker - Build Installer
echo ========================================
echo.

REM Step 1: Build the EXE with PyInstaller
echo [1/3] Building EXE with PyInstaller...
cd /d "%~dp0..\app"
pyinstaller --onefile --windowed --name EmployeeTracker --icon=..\installer\app_icon.ico detector.py
if errorlevel 1 (
    echo ERROR: PyInstaller build failed!
    pause
    exit /b 1
)

REM Step 2: Copy required files to installer folder
echo [2/3] Copying files...
copy /Y "dist\EmployeeTracker.exe" "..\installer\dist\" >nul
copy /Y "yolov8n.pt" "..\installer\" >nul

REM Step 3: Build installer with Inno Setup
echo [3/3] Building installer with Inno Setup...
cd /d "%~dp0"
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
if errorlevel 1 (
    echo ERROR: Inno Setup build failed!
    echo Make sure Inno Setup 6 is installed: https://jrsoftware.org/isdl.php
    pause
    exit /b 1
)

echo.
echo ========================================
echo  BUILD COMPLETE!
echo  Installer: installer\output\EmployeeTrackerSetup.exe
echo ========================================
pause
