; Employee Tracker Installer Script
; Requires Inno Setup 6.x (free): https://jrsoftware.org/isinfo.php

#define MyAppName "Employee Tracker"
#define MyAppVersion "1.0"
#define MyAppPublisher "Your Company"
#define MyAppExeName "EmployeeTracker.exe"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=output
OutputBaseFilename=EmployeeTrackerSetup
SetupIconFile=app_icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
DiskSpanning=yes
SlicesPerDisk=1
DiskSliceSize=max

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "enablecamera"; Description: "Enable camera access for this app (recommended)"; GroupDescription: "System Configuration:"; Flags: checkedonce

[Files]
; Main application
Source: "dist\EmployeeTracker.exe"; DestDir: "{app}"; Flags: ignoreversion
; Note: YOLO model (yolov8n.pt) is downloaded on first run by ultralytics
; Camera setup script
Source: "enable_camera.ps1"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; Enable camera access after installation (if user checked the option)
Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -File ""{app}\enable_camera.ps1"""; StatusMsg: "Configuring camera access..."; Flags: runhidden; Tasks: enablecamera
; Launch app after install
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
// Show a message about camera permissions
procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = wpFinished then
  begin
    MsgBox('Installation complete!' + #13#10 + #13#10 +
           'If you see a camera permission prompt, please click "Allow".' + #13#10 +
           'The app needs camera access to monitor employee presence.',
           mbInformation, MB_OK);
  end;
end;
