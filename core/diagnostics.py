"""Sistem tanılama: sağlık kontrolleri ve Windows olay günlüğü (salt okunur)."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.i18n import K
from core.disks import Partition
from core.system_info import SystemSnapshot
from core.winproc import run_powershell_json


@dataclass(frozen=True)
class HealthCheck:
    level: str  # ok, warning, critical
    key: str    # çeviri anahtarı
    params: dict = field(default_factory=dict)


def health_checks(snapshot: SystemSnapshot, partitions: list[Partition]) -> list[HealthCheck]:
    checks: list[HealthCheck] = []
    if snapshot.memory_percent >= 90:
        checks.append(HealthCheck("critical", K("health_memory_high"), {"percent": round(snapshot.memory_percent)}))
    elif snapshot.memory_percent >= 80:
        checks.append(HealthCheck("warning", K("health_memory_high"), {"percent": round(snapshot.memory_percent)}))

    for part in partitions:
        free_percent = 100.0 - part.percent
        params = {"drive": part.mountpoint, "percent": round(free_percent)}
        if free_percent < 5:
            checks.append(HealthCheck("critical", K("health_disk_low"), params))
        elif free_percent < 10:
            checks.append(HealthCheck("warning", K("health_disk_low"), params))

    days = int(snapshot.uptime_seconds // 86400)
    if days >= 14:
        checks.append(HealthCheck("warning", K("health_uptime_long"), {"days": days}))

    if snapshot.cpu_percent >= 90:
        checks.append(HealthCheck("warning", K("health_cpu_high"), {"percent": round(snapshot.cpu_percent)}))

    if not checks:
        checks.append(HealthCheck("ok", K("health_all_good")))
    return checks


def overall_level(checks: list[HealthCheck]) -> str:
    levels = {c.level for c in checks}
    if "critical" in levels:
        return "critical"
    if "warning" in levels:
        return "warning"
    return "ok"


@dataclass(frozen=True)
class EventEntry:
    time: str
    log: str
    level: int  # 1 kritik, 2 hata, 3 uyarı
    source: str
    event_id: int
    message: str


def recent_events(hours: int = 24, max_events: int = 200, include_warnings: bool = False) -> list[EventEntry]:
    levels = "1,2,3" if include_warnings else "1,2"
    script = (
        f"Get-WinEvent -FilterHashtable @{{LogName='System','Application';Level={levels};"
        f"StartTime=(Get-Date).AddHours(-{int(hours)})}} -MaxEvents {int(max_events)} | "
        "Select-Object @{n='Time';e={$_.TimeCreated.ToString('yyyy-MM-dd HH:mm:ss')}},"
        "LogName,Level,ProviderName,Id,"
        "@{n='Message';e={if($_.Message){($_.Message -split \"`r?`n\")[0]}else{''}}} | "
        "ConvertTo-Json -Compress"
    )
    try:
        rows = run_powershell_json(script, timeout=90)
    except Exception:
        logging.exception("Event log query failed.")
        return []
    events = []
    for row in rows:
        try:
            events.append(EventEntry(
                time=str(row.get("Time") or ""),
                log=str(row.get("LogName") or ""),
                level=int(row.get("Level") or 0),
                source=str(row.get("ProviderName") or ""),
                event_id=int(row.get("Id") or 0),
                message=str(row.get("Message") or ""),
            ))
        except (TypeError, ValueError):
            continue
    return events
