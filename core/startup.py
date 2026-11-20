"""Başlangıç programları.

Okuma: Run anahtarları (HKCU, HKLM 64/32 bit) ve Başlangıç klasörleri.
Değişiklik: Girdiler SİLİNMEZ. Windows Görev Yöneticisi'nin kullandığı
``StartupApproved`` anahtarı üzerinden etkinleştirilir / devre dışı bırakılır.
Bu sayede değişiklik her zaman geri alınabilir.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path

from core import registry

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APPROVED_BASE = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved"


@dataclass(frozen=True)
class StartupEntry:
    name: str
    command: str
    source: str
    enabled: bool
    approved_hive: str
    approved_subkey: str
    approved_value: str


def is_enabled_flag(data: bytes | None) -> bool:
    """StartupApproved verisi: ilk bayt çift (0x02, 0x06) = etkin, tek (0x03) = devre dışı."""
    if not data:
        return True
    return data[0] % 2 == 0


def approved_bytes(enabled: bool, now: float | None = None) -> bytes:
    if enabled:
        return bytes([0x02] + [0] * 11)
    filetime = int(((now if now is not None else time.time()) + 11644473600) * 10_000_000)
    return bytes([0x03, 0, 0, 0]) + filetime.to_bytes(8, "little")


def _read_run_values(hive: str, view_flag: int) -> list[tuple[str, str]]:
    import winreg

    hive_handle = winreg.HKEY_CURRENT_USER if hive == "HKCU" else winreg.HKEY_LOCAL_MACHINE
    values: list[tuple[str, str]] = []
    try:
        with winreg.OpenKey(hive_handle, RUN_KEY, 0, winreg.KEY_READ | view_flag) as key:
            index = 0
            while True:
                try:
                    name, command, _ = winreg.EnumValue(key, index)
                except OSError:
                    break
                values.append((str(name), str(command)))
                index += 1
    except OSError:
        pass
    return values


def list_startup_entries() -> list[StartupEntry]:
    """Read startup locations only."""
    if os.name != "nt":
        return []
    import winreg

    entries: list[StartupEntry] = []
    view64 = getattr(winreg, "KEY_WOW64_64KEY", 0)
    view32 = getattr(winreg, "KEY_WOW64_32KEY", 0)

    locations = [
        ("HKCU", view64, "current_user", "Run"),
        ("HKLM", view64, "local_machine", "Run"),
        ("HKLM", view32, "local_machine_32", "Run32"),
    ]
    seen: set[tuple[str, str, str]] = set()
    for hive, view, source, approved_leaf in locations:
        approved_key = f"{APPROVED_BASE}\\{approved_leaf}"
        for name, command in _read_run_values(hive, view):
            key = (hive, name.casefold(), command.casefold())
            if key in seen:
                continue
            seen.add(key)
            state = registry.read_binary_value(hive, approved_key, name)
            entries.append(StartupEntry(name, command, source, is_enabled_flag(state), hive, approved_key, name))

    folders = []
    if os.environ.get("APPDATA"):
        folders.append((Path(os.environ["APPDATA"]) / "Microsoft/Windows/Start Menu/Programs/Startup",
                        "user_startup_folder", "HKCU"))
    if os.environ.get("PROGRAMDATA"):
        folders.append((Path(os.environ["PROGRAMDATA"]) / "Microsoft/Windows/Start Menu/Programs/Startup",
                        "all_users_startup_folder", "HKLM"))
    for folder, source, hive in folders:
        approved_key = f"{APPROVED_BASE}\\StartupFolder"
        try:
            for path in folder.iterdir():
                if not path.is_file() or path.name.lower() == "desktop.ini":
                    continue
                state = registry.read_binary_value(hive, approved_key, path.name)
                entries.append(StartupEntry(path.stem, str(path), source, is_enabled_flag(state),
                                            hive, approved_key, path.name))
        except OSError:
            continue

    return sorted(entries, key=lambda item: item.name.casefold())


def set_enabled(entry: StartupEntry, enabled: bool) -> bytes | None:
    """Change the StartupApproved flag. Returns the previous raw value (for undo)."""
    previous = registry.read_binary_value(entry.approved_hive, entry.approved_subkey, entry.approved_value)
    registry.write_binary_value(entry.approved_hive, entry.approved_subkey, entry.approved_value,
                                approved_bytes(enabled))
    return previous
