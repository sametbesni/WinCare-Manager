from __future__ import annotations

import logging
from dataclasses import dataclass

import psutil

_CPU_COUNT = psutil.cpu_count() or 1


@dataclass(frozen=True)
class ProcessEntry:
    name: str
    pid: int
    cpu_percent: float  # tüm çekirdeklere göre (0–100)
    memory_mb: float
    username: str
    exe: str


def list_processes(limit: int = 400, include_username: bool = True) -> list[ProcessEntry]:
    """Read-only process list.

    psutil.process_iter, Process nesnelerini önbelleğe aldığı için cpu_percent
    ikinci çağrıdan itibaren gerçek değer döndürür.
    """
    attrs = ["pid", "name", "memory_info", "exe"]
    if include_username:
        attrs.append("username")
    entries: list[ProcessEntry] = []
    for process in psutil.process_iter(attrs, ad_value=None):
        try:
            info = process.info
            if not info.get("pid"):  # PID 0: System Idle Process (boşta CPU göstergesi)
                continue
            memory_info = info.get("memory_info")
            entries.append(
                ProcessEntry(
                    name=str(info.get("name") or "?"),
                    pid=int(info.get("pid") or 0),
                    cpu_percent=float(process.cpu_percent(interval=None)) / _CPU_COUNT,
                    memory_mb=(memory_info.rss / (1024 * 1024)) if memory_info else 0.0,
                    username=str(info.get("username") or ""),
                    exe=str(info.get("exe") or ""),
                )
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, OSError):
            continue
        except Exception:
            logging.exception("A process entry could not be read.")
    return sorted(entries, key=lambda item: item.memory_mb, reverse=True)[:limit]
