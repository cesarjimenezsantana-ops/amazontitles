# Focus Amazon Tools Desktop Builds

Focus Amazon Tools is distributed as a self-contained desktop application. Users do not need Python, Flask, or Excel installed. The application opens in a native window and starts an HTTP server on a random `127.0.0.1` port only while the window is open. Windows uses Electron with a bundled Python processing service; macOS currently uses pywebview.

## User data

Processed files, temporary uploads, ZIP downloads, and logs are stored outside the installation folder:

- macOS: `~/Library/Application Support/Focus Amazon Tools`
- Windows: `%LOCALAPPDATA%\Focus Amazon Tools`

Job folders older than 14 days are removed when the desktop application starts. Downloaded ZIP files remain in the user's normal Downloads folder.

## Optional OpenAI optimization

Users can add their own OpenAI API key from **AI settings**. The key is kept in process memory only and is cleared when the app closes. Deployments may instead provide `OPENAI_API_KEY` in the environment. Individual AI suggestions remain drafts until the user applies the reviewed changes.

## Build macOS

Run this command on a Mac:

```bash
./scripts/build_macos.sh
```

The installer is created in `dist/FocusAmazonTools-1.1.6-macOS-<architecture>.dmg`. The version defaults to `version.py`; set `APP_VERSION` only to override it.

For public distribution without Gatekeeper warnings, set `MACOS_SIGNING_IDENTITY`, `APPLE_ID`, `APPLE_TEAM_ID`, and `APPLE_APP_PASSWORD` before building. The script signs and notarizes the DMG when all notarization values are available.

## Build Windows

Install Python 3.12 and Node.js 22, then run in PowerShell:

```powershell
.\scripts\build_windows.ps1
```

The build creates both:

- `dist\FocusAmazonTools-Setup-1.1.6.exe` — per-user installer.
- `dist\FocusAmazonTools-Portable-1.1.6-Windows-x64.exe` — portable executable that runs without installation.

Electron bundles its own browser runtime, so WebView2 is not required. The portable file can be copied directly to another Windows x64 computer.

## Automated builds

The GitHub Actions workflow in `.github/workflows/build-installers.yml` builds:

- Windows x64 installer and portable executable
- macOS Apple Silicon installer
- macOS Intel installer

Run it manually with a version number or push a tag such as `v1.1.6`. Each installer is uploaded as a workflow artifact.

To build both installers without maintaining two computers, upload this project to a GitHub repository, open **Actions → Build desktop installers → Run workflow**, enter the version, and download the three generated artifacts when the run finishes.

PyInstaller is not a cross-compiler, so Windows and macOS packages must be built on their matching operating systems. The workflow handles this automatically.

## Distribution signing

Unsigned local builds are suitable for testing. Public installers should be signed with an Apple Developer ID on macOS and a trusted code-signing certificate on Windows. Signing credentials are intentionally not stored in this project.
