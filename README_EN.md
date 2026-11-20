# WinCare Manager

[Türkçe](README.md) · **Version:** 0.2.0 · **Platform:** Windows 10/11 (64-bit) · **UI:** Türkçe / English · **Runs:** locally, offline

WinCare Manager is a Windows maintenance and management tool. It analyses the system, performs safe maintenance and records every change so it can be undone.

## Modules

Overview · Junk File Cleanup (moves selected files to the **Recycle Bin**) · Startup Programs (enable/disable, never delete) · Process Manager · Registry (read-only viewer + key backup) · Windows Services (read-only) · Disk Management (usage + physical disk health) · Backup & Restore (SHA-256 verified `.reg` backups) · System Diagnostics (health checks + event log) · Automatic Maintenance (**optional, off by default**; scheduled analysis only) · Operation History (SQLite) · Settings.

## Safety principles

- **Dry run is on by default.** Operations are only planned and recorded until you turn it off in Settings.
- The UI never touches the system directly. Every change goes through the operation engine: admin check, validation, backup, execution and logging.
- No permanent deletion. Windows folders, Program Files, symlinks and junctions are excluded from cleanup and re-checked right before execution.
- No registry "cleaner". The only registry change is the startup approval flag, and the key is backed up before each change.
- Backups are verified with SHA-256 before a restore, and the current state is backed up first.
- Administrator rights are requested only on demand (UAC).

## Installing (users)

Download `WinCareManager-Setup-<version>.exe` from the [Releases page](https://github.com/sametbesni/WinCare-Manager/releases/latest) and run it (or use the portable ZIP). By default it installs for the current user without administrator rights, creates a **desktop shortcut** (optional) and a Start menu entry, and registers in Windows Apps for uninstalling. SmartScreen may warn because the installer is not code-signed yet.

## Development setup

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\setup_windows.ps1
```

Then double-click `run_windows.bat`.

## Tests and EXE

```powershell
.\.venv\Scripts\python.exe -m pytest
.\scripts\build_windows.ps1
```

For the installer, install [Inno Setup 6](https://jrsoftware.org/isinfo.php) and run `.\scripts\build_installer.ps1`; the output is `dist\installer\WinCareManager-Setup-<version>.exe`.

The portable output is `dist\WinCare Manager\WinCare Manager.exe`. Distribute the whole `dist\WinCare Manager` folder; Python does not need to be installed on the target machine.

## Data

`%LOCALAPPDATA%\WinCareManager\` holds `settings.json`, `history.db`, `backups\` and `logs\wincare.log`.

## Automatic Maintenance

Off by default. When turned on, it registers the `WinCareManager AutoMaintenance` task in Windows Task Scheduler. The task runs under your account without administrator rights, only while you are signed in and on AC power. It starts the app without a window using `--maintenance`. The app only analyses; it never deletes or changes anything. The report is shown the next time you open the app. Turning the feature off deletes the task.

## Uninstalling

If you used the installer, uninstall from Windows Settings → Apps. This removes the app, its shortcuts and the maintenance task, and asks whether to delete your data (default: no).

For the portable folder version:

1. Go to **Settings → Uninstalling the program → "Prepare for uninstall"**. This deletes the automatic maintenance task, if any.
2. Close the app.
3. Delete the program folder.
4. Optionally, delete `%LOCALAPPDATA%\WinCareManager\` (settings, history, backups).

Changes you made with the app, such as disabled startup entries, are not reverted automatically. Revert them before uninstalling if you want.

## Privacy

There is no network access, telemetry, account system or external services. All data stays on this computer.

## Contributing

Contributions are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) first. Report security issues as described in [SECURITY.md](SECURITY.md).

## License

[MIT](LICENSE)
