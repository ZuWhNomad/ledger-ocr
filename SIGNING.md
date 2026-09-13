# Code signing LedgerOCR

The installer and the frozen app are **unsigned by default**. On a fresh machine Windows
SmartScreen then shows a blue *"Windows protected your PC"* prompt, and the user must click
**More info → Run anyway** (documented for them in `GETTING_STARTED.md`). Signing the build with
a certificate you trust removes that friction and lets the app accrue SmartScreen reputation.

Signing is **fully optional** and **opt-in**: `build_installer.ps1` signs automatically when a
certificate is provided through environment variables and otherwise builds unsigned with a printed
note. Nothing about the app depends on it.

## What you need

- A **code-signing certificate**. For SmartScreen to trust it immediately, an **EV** (or an
  OV/standard cert that has built reputation) from a public CA is best; a self-signed cert will be
  trusted only on machines where you've installed it into *Trusted Root* + *Trusted Publishers*.
- **`signtool.exe`** from the Windows 10/11 SDK. `build_installer.ps1` finds it on `PATH` or under
  `…\Windows Kits\10\bin\**\x64\signtool.exe`.

## How to sign

Set **one** of these before running the build, then run `build_installer.ps1` as usual.

**A cert already in your Windows certificate store (by SHA-1 thumbprint):**

```powershell
$env:CODESIGN_THUMBPRINT = "AB12CD34...EF"   # thumbprint of the signing cert
powershell -ExecutionPolicy Bypass -File installer\build_installer.ps1
```

**A `.pfx` file:**

```powershell
$env:CODESIGN_PFX  = "C:\certs\ledgerocr.pfx"
$env:CODESIGN_PASS = "<pfx password>"
powershell -ExecutionPolicy Bypass -File installer\build_installer.ps1
```

Optional: `$env:CODESIGN_TS` overrides the RFC3161 timestamp URL (default
`http://timestamp.digicert.com`). Timestamping is always applied so signatures stay valid after
the certificate expires.

## What gets signed

With signing configured, the build signs **both**:

1. the frozen **`LedgerOCR.exe`** (before it is packed into the installer), and
2. the generated **`LedgerOCR-Setup.exe`** (Inno Setup signs it via the `SignTool` directive,
   which `build_installer.ps1` enables by passing `/DSIGN` and the `signtool` command to `ISCC`).

Both are signed with `/fd sha256` (file digest), `/tr <timestamp>` + `/td sha256` (RFC3161
timestamp). Verify afterwards with:

```powershell
signtool verify /pa /all installer\Output\LedgerOCR-Setup.exe
```

## Security note

Keep the `.pfx` and its password out of the repo and off shared build logs. Prefer the
store-thumbprint method (or a hardware token / EV cert) on a controlled build machine. The
`CODESIGN_PASS` value is passed to `signtool` on its command line, so only sign on a machine you
trust.
