"""Kayıt defteri: salt okunur inceleme, dışa aktarma (yedek) ve içe aktarma (geri yükleme).

Bu modül kayıt defterinden rastgele değer silen bir "temizleyici" içermez.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from core.winproc import run_command

try:
    import winreg
except ImportError:  # Windows dışı (testler)
    winreg = None  # type: ignore[assignment]

HIVE_NAMES = ("HKCU", "HKLM", "HKCR", "HKU", "HKCC")


def _hive(name: str) -> int:
    if winreg is None:
        raise OSError("Registry is only available on Windows.")
    mapping = {
        "HKCU": winreg.HKEY_CURRENT_USER,
        "HKLM": winreg.HKEY_LOCAL_MACHINE,
        "HKCR": winreg.HKEY_CLASSES_ROOT,
        "HKU": winreg.HKEY_USERS,
        "HKCC": winreg.HKEY_CURRENT_CONFIG,
    }
    if name not in mapping:
        raise ValueError(f"Unknown hive: {name}")
    return mapping[name]


def _view_flag() -> int:
    return getattr(winreg, "KEY_WOW64_64KEY", 0) if winreg else 0


@dataclass(frozen=True)
class RegistryValue:
    name: str
    type_name: str
    data: str


def _type_name(value_type: int) -> str:
    names = {
        winreg.REG_SZ: "REG_SZ",
        winreg.REG_EXPAND_SZ: "REG_EXPAND_SZ",
        winreg.REG_DWORD: "REG_DWORD",
        winreg.REG_QWORD: "REG_QWORD",
        winreg.REG_BINARY: "REG_BINARY",
        winreg.REG_MULTI_SZ: "REG_MULTI_SZ",
        winreg.REG_NONE: "REG_NONE",
    }
    return names.get(value_type, f"TYPE_{value_type}")


def format_data(value_type: int | None, data: object) -> str:
    if isinstance(data, bytes):
        shown = data[:64].hex(" ")
        return shown + (" …" if len(data) > 64 else "")
    if isinstance(data, list):
        return "; ".join(str(item) for item in data)
    if isinstance(data, int) and winreg and value_type in (winreg.REG_DWORD, winreg.REG_QWORD):
        return f"0x{data:08x} ({data})"
    return "" if data is None else str(data)


def normalize_path(path: str) -> str:
    return path.strip().strip("\\").replace("/", "\\")


def key_exists(hive: str, path: str) -> bool:
    try:
        with winreg.OpenKey(_hive(hive), normalize_path(path), 0, winreg.KEY_READ | _view_flag()):
            return True
    except OSError:
        return False


def read_key(hive: str, path: str) -> tuple[list[str], list[RegistryValue]]:
    """Return (subkeys, values) of a key. Read-only."""
    subkeys: list[str] = []
    values: list[RegistryValue] = []
    with winreg.OpenKey(_hive(hive), normalize_path(path), 0, winreg.KEY_READ | _view_flag()) as key:
        index = 0
        while True:
            try:
                subkeys.append(winreg.EnumKey(key, index))
            except OSError:
                break
            index += 1
        index = 0
        while True:
            try:
                name, data, value_type = winreg.EnumValue(key, index)
            except OSError:
                break
            values.append(RegistryValue(name or "(Default)", _type_name(value_type), format_data(value_type, data)))
            index += 1
    subkeys.sort(key=str.casefold)
    values.sort(key=lambda v: v.name.casefold())
    return subkeys, values


def full_key_name(hive: str, path: str) -> str:
    path = normalize_path(path)
    return f"{hive}\\{path}" if path else hive


def export_key(hive: str, path: str, destination: Path) -> None:
    """Export a key to a .reg file with reg.exe (64-bit view)."""
    if not normalize_path(path):
        raise ValueError("Refusing to export a whole hive.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    result = run_command(["reg", "export", full_key_name(hive, path), str(destination), "/y", "/reg:64"])
    if result.returncode != 0 or not destination.is_file():
        raise RuntimeError((result.stderr or result.stdout or "reg export failed").strip())


def import_file(reg_file: Path) -> None:
    if os.name != "nt":
        raise OSError("Registry import is only available on Windows.")
    result = run_command(["reg", "import", str(reg_file), "/reg:64"])
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "reg import failed").strip())


def read_binary_value(hive: str, path: str, name: str) -> bytes | None:
    try:
        with winreg.OpenKey(_hive(hive), path, 0, winreg.KEY_READ | _view_flag()) as key:
            data, value_type = winreg.QueryValueEx(key, name)
            return bytes(data) if isinstance(data, (bytes, bytearray)) else None
    except OSError:
        return None


def write_binary_value(hive: str, path: str, name: str, data: bytes | None) -> None:
    """Write (or delete when data is None) a REG_BINARY value."""
    access = winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE | _view_flag()
    with winreg.CreateKeyEx(_hive(hive), path, 0, access) as key:
        if data is None:
            try:
                winreg.DeleteValue(key, name)
            except FileNotFoundError:
                pass
        else:
            winreg.SetValueEx(key, name, 0, winreg.REG_BINARY, data)
