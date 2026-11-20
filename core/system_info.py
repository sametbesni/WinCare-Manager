from __future__ import annotations

import os
import platform
import socket
import time
from dataclasses import dataclass
from pathlib import Path

import psutil

# psutil'in ilk cpu_percent çağrısı her zaman 0 döndürür; modül yüklenirken ölçümü başlat.
psutil.cpu_percent(interval=None)


def format_bytes(value: int | float) -> str:
    amount = max(0.0, float(value))
    units = ("B", "KB", "MB", "GB", "TB", "PB")
    for unit in units:
        if amount < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(amount)} {unit}"
            return f"{amount:.1f} {unit}"
        amount /= 1024
    return f"{amount:.1f} PB"


def format_uptime(seconds: float, language: str = "tr_TR") -> str:
    total_minutes = max(0, int(seconds // 60))
    days, remainder = divmod(total_minutes, 1440)
    hours, minutes = divmod(remainder, 60)
    if language == "en_US":
        parts = []
        if days:
            parts.append(f"{days}d")
        if hours:
            parts.append(f"{hours}h")
        parts.append(f"{minutes}m")
        return " ".join(parts)
    parts = []
    if days:
        parts.append(f"{days} gün")
    if hours:
        parts.append(f"{hours} saat")
    parts.append(f"{minutes} dakika")
    return " ".join(parts)


def system_drive_path() -> Path:
    if os.name == "nt":
        return Path(os.environ.get("SystemDrive", "C:") + "\\")
    return Path("/")


def windows_version_label() -> str:
    """'Windows 11 23H2 (build 22631)' gibi okunabilir bir sürüm etiketi."""
    if os.name != "nt":
        return f"{platform.system()} {platform.release()}"
    build = 0
    display = ""
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion") as key:
            build = int(winreg.QueryValueEx(key, "CurrentBuildNumber")[0])
            try:
                display = str(winreg.QueryValueEx(key, "DisplayVersion")[0])
            except OSError:
                display = ""
    except (OSError, ValueError):
        build = int(platform.version().split(".")[-1] or 0) if platform.version() else 0
    name = "Windows 11" if build >= 22000 else "Windows 10" if build >= 10240 else f"Windows {platform.release()}"
    return f"{name} {display} (build {build})".replace("  ", " ")


@dataclass(frozen=True)
class SystemSnapshot:
    cpu_percent: float
    memory_percent: float
    memory_used: int
    memory_total: int
    disk_percent: float
    disk_used: int
    disk_total: int
    uptime_seconds: float
    os_name: str
    os_version: str
    architecture: str
    processor: str
    hostname: str
    physical_cores: int
    logical_cores: int


def get_system_snapshot() -> SystemSnapshot:
    memory = psutil.virtual_memory()
    try:
        disk = psutil.disk_usage(str(system_drive_path()))
    except (OSError, PermissionError):
        disk = psutil.disk_usage(str(Path.home().anchor or "/"))

    return SystemSnapshot(
        cpu_percent=psutil.cpu_percent(interval=None),
        memory_percent=memory.percent,
        memory_used=memory.used,
        memory_total=memory.total,
        disk_percent=disk.percent,
        disk_used=disk.used,
        disk_total=disk.total,
        uptime_seconds=max(0.0, time.time() - psutil.boot_time()),
        os_name=windows_version_label(),
        os_version=platform.version() or platform.release(),
        architecture=platform.machine(),
        processor=platform.processor() or "—",
        hostname=socket.gethostname(),
        physical_cores=psutil.cpu_count(logical=False) or 0,
        logical_cores=psutil.cpu_count() or 0,
    )
