; Inno Setup Script for ed-telemetry (Windows)
[Setup]
AppName=ed-telemetry
AppVersion=0.12.1
DefaultDirName={localappdata}\Programs\ed-telemetry
DefaultGroupName=ed-telemetry
OutputBaseFilename=ed-telemetry-setup

[Files]
Source: "dist\ed-telemetry.exe"; DestDir: "{app}"; Flags: ignoreversion

[Run]
Filename: "{app}\ed-telemetry.exe"; Parameters: "service install"; Flags: runhidden
