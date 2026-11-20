"""Windows hizmetleri (salt okunur)."""
from __future__ import annotations

import logging
from dataclasses import dataclass

import psutil


@dataclass(frozen=True)
class ServiceEntry:
    name: str
    display_name: str
    status: str       # running, stopped, paused, start_pending, ...
    start_type: str   # automatic, manual, disabled
    binpath: str


def list_services() -> list[ServiceEntry]:
    if not hasattr(psutil, "win_service_iter"):
        return []
    services: list[ServiceEntry] = []
    for service in psutil.win_service_iter():
        try:
            info = service.as_dict()
            services.append(ServiceEntry(
                name=str(info.get("name") or ""),
                display_name=str(info.get("display_name") or ""),
                status=str(info.get("status") or ""),
                start_type=str(info.get("start_type") or ""),
                binpath=str(info.get("binpath") or ""),
            ))
        except (psutil.Error, OSError):
            continue
        except Exception:
            logging.exception("A service entry could not be read.")
    return sorted(services, key=lambda s: s.display_name.casefold())
