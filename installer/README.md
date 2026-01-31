# Building the Employee Tracker Installer

## Prerequisites

1. **Python environment** with all dependencies installed
2. **PyInstaller**: `pip install pyinstaller`
3. **Inno Setup 6** (free): Download from https://jrsoftware.org/isdl.php

## Files in this folder

| File | Purpose |
|------|---------|
| `installer.iss` | Inno Setup script (main installer config) |
| `enable_camera.ps1` | PowerShell script to enable camera access |
| `build_installer.bat` | One-click build script |
| `app_icon.ico` | App icon (you need to add this) |

## Building the Installer

### Option 1: Automatic (Recommended)
```batch
cd installer
build_installer.bat
```

### Option 2: Manual Steps

1. **Build the EXE:**
   ```batch
   cd app
   pyinstaller --onefile --windowed --name EmployeeTracker detector.py
   ```

2. **Copy files to installer folder:**
   - `app/dist/EmployeeTracker.exe` → `installer/dist/`
   - `app/yolov8n.pt` → `installer/`

3. **Build installer:**
   - Open `installer.iss` in Inno Setup
   - Click Build → Compile
   - Output: `installer/output/EmployeeTrackerSetup.exe`

## What the Installer Does

1. ✅ Installs `EmployeeTracker.exe` to Program Files
2. ✅ Copies YOLO model (`yolov8n.pt`)
3. ✅ Creates Start Menu and Desktop shortcuts
4. ✅ **Enables camera access** (runs `enable_camera.ps1` as admin)
5. ✅ Offers to launch app after install

## About the SmartScreen Warning

The installer will still show a SmartScreen warning because it's unsigned. To remove this:
- Purchase a code signing certificate (~$200-500/year)
- Or have IT whitelist the installer via Group Policy

Users can bypass by clicking: **"More info"** → **"Run anyway"**
