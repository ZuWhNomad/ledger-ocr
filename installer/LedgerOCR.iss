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
; PKG-P1-1: code-sign the generated Setup.exe when a signing tool is supplied.
; build_installer.ps1 passes /DSIGN and /Sledgerocrsign="<signtool cmd> $f" only when a
; cert is configured; with no cert this directive is absent and the build stays unsigned.
#ifdef SIGN
SignTool=ledgerocrsign
#endif

[Files]
; the frozen one-folder app (built by PyInstaller into dist\LedgerOCR)
Source: "dist\LedgerOCR\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
; helper + docs
Source: "install_tesseract.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "install_ollama.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "uninstall_cleanup.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\GETTING_STARTED.txt"; DestDir: "{app}"; Flags: ignoreversion isreadme

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"
; PKG-P2-6: OFF by default (downloads ~2 GB) and run non-blocking below so the wizard
; never looks hung on a slow connection.
Name: "errorchecker"; Description: "Also set up the optional smart error-checker (downloads ~2 GB in the background)"; GroupDescription: "Optional:"; Flags: unchecked

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\Getting Started"; Filename: "{app}\GETTING_STARTED.txt"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
; BASE: install the Tesseract OCR engine so scans/photos work out of the box. Runs in its own
; window and does NOT block the wizard; born-digital PDFs already work without waiting for it.
Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -NoProfile -File ""{app}\install_tesseract.ps1"""; \
  Flags: shellexec nowait; StatusMsg: "Installing the OCR engine so scans and photos work (about 50 MB)..."
; optional error-checker setup -- runs in its own window and does NOT block the wizard
; (PKG-P2-6). The app is already fully installed by this point.
Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -NoProfile -File ""{app}\install_ollama.ps1"""; \
  Tasks: errorchecker; Flags: shellexec nowait; StatusMsg: "Starting the optional error-checker download (you can keep using the app)..."
; launch the app at the end
Filename: "{app}\{#AppExe}"; Description: "Launch {#AppName} now"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; PKG-P2-5: on uninstall, offer to remove the ~2 GB pulled model (and Ollama, only if we
; installed it). Runs before the app files are deleted so the script is still present.
Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -NoProfile -File ""{app}\uninstall_cleanup.ps1"""; \
  Flags: shellexec waituntilterminated runhidden; RunOnceId: "LedgerOCRCleanup"
