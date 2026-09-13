; Inno Setup script for LedgerOCR -- wraps the PyInstaller one-folder build into a
; single double-click installer. Build:  ISCC.exe LedgerOCR.iss
; Produces installer\Output\LedgerOCR-Setup.exe

#define AppName "LedgerOCR"
#define AppVersion "0.1.0"
#define AppPublisher "LedgerOCR"
#define AppExe "LedgerOCR.exe"

[Setup]
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
; Per-user install: no admin prompt, luddite-proof.
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

[Files]
; the frozen one-folder app (built by PyInstaller into dist\LedgerOCR)
Source: "dist\LedgerOCR\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
; helper + docs
Source: "install_ollama.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\GETTING_STARTED.md"; DestDir: "{app}"; Flags: ignoreversion isreadme

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"
Name: "errorchecker"; Description: "Install the smart error-checker (recommended, downloads ~2 GB)"; GroupDescription: "Optional:"

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\Getting Started"; Filename: "{app}\GETTING_STARTED.md"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
; optional error-checker setup (visible window so the user sees progress)
Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -NoProfile -File ""{app}\install_ollama.ps1"""; \
  Tasks: errorchecker; Flags: shellexec waituntilterminated; StatusMsg: "Setting up the smart error-checker..."
; launch the app at the end
Filename: "{app}\{#AppExe}"; Description: "Launch {#AppName} now"; Flags: nowait postinstall skipifsilent
