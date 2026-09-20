; Inno Setup script: wraps the PyInstaller one-folder build into one Setup.exe.
; Build:  ISCC.exe installer\LedgerOCR.iss   ->  installer\Output\LedgerOCR-Setup.exe
; Nothing else is installed: OCR is Windows' own. Tesseract, if present, is used as a second opinion.

#define AppName "LedgerOCR"
#define AppVersion "0.2.0"
#define AppExe "LedgerOCR.exe"

[Setup]
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppName}
PrivilegesRequired=lowest
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
DisableDirPage=yes
OutputDir=Output
OutputBaseFilename=LedgerOCR-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#AppExe}
MinVersion=10.0
#ifdef SIGN
SignTool=ledgerocrsign
#endif

[Files]
Source: "dist\LedgerOCR\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "..\README.txt"; DestDir: "{app}"; Flags: ignoreversion isreadme

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Launch {#AppName} now"; Flags: nowait postinstall skipifsilent
