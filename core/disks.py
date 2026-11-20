"""Disk bölümleri ve fiziksel disk sağlık durumu (salt okunur)."""
from __future__ import annotations

import logging
from dataclasses import dataclass

import psutil

from core.winproc import run_powershell_json


@dataclass(frozen=True)
class Partition:
    device: str
    mountpoint: str
    fstype: str
    total: int
    used: int
    free: int
    percent: float


@dataclass(frozen=True)
class PhysicalDisk:
    name: str
    media_type: str
    bus_type: str
    health: str
    operational: str
    size: int


def list_partitions() -> list[Partition]:
    partitions: list[Partition] = []
    for part in psutil.disk_partitions(all=False):
        if "cdrom" in part.opts or not part.fstype:
            continue
        try:
            usage = psutil.disk_usage(part.mountpoint)
        except (OSError, PermissionError):
            continue
        partitions.append(Partition(part.device, part.mountpoint, part.fstype,
                                    usage.total, usage.used, usage.free, usage.percent))
    return partitions


_PHYSICAL_DISK_SCRIPT = (
    "Get-PhysicalDisk | Select-Object FriendlyName,"
    "@{n='MediaType';e={[string]$_.MediaType}},"
    "@{n='BusType';e={[string]$_.BusType}},"
    "@{n='HealthStatus';e={[string]$_.HealthStatus}},"
    "@{n='OperationalStatus';e={[string]($_.OperationalStatus -join ', ')}},"
    "Size | ConvertTo-Json -Compress"
)


def list_physical_disks() -> list[PhysicalDisk]:
    """Windows Storage API üzerinden fiziksel disk sağlığı (SMART özetine dayanır)."""
    try:
        rows = run_powershell_json(_PHYSICAL_DISK_SCRIPT, timeout=45)
    except Exception:
        logging.exception("Physical disk query failed.")
        return []
    disks = []
    for row in rows:
        try:
            size = int(row.get("Size") or 0)
        except (TypeError, ValueError):
            size = 0
        disks.append(PhysicalDisk(
            name=str(row.get("FriendlyName") or "?"),
            media_type=str(row.get("MediaType") or ""),
            bus_type=str(row.get("BusType") or ""),
            health=str(row.get("HealthStatus") or ""),
            operational=str(row.get("OperationalStatus") or ""),
            size=size,
        ))
    return disks
