"""Windows hizmetleri: listeleme ve kontrollü başlatma/durdurma.

Güvenlik kuralları:
- Kritik Windows hizmetleri (``PROTECTED_SERVICES``) asla durdurulmaz.
- Başka çalışan hizmetlerin bağlı olduğu bir hizmet durdurulmaz (zincirleme
  durmayı önlemek için).
- Devre dışı bırakılmış hizmet başlatılmaz; başlangıç türü değiştirilmez.
- Başlatma/durdurma yalnızca işlem motoru üzerinden, onay ve yönetici
  yetkisiyle yapılır; deneme modunda hiçbir şey değişmez.
"""
from __future__ import annotations

import ctypes
import logging
import os
import time
from ctypes import wintypes
from dataclasses import dataclass

import psutil

from app.i18n import K

# Durdurulması sistemi kararsız ya da güvensiz bırakabilecek hizmetler (küçük harf).
PROTECTED_SERVICES = frozenset(name.lower() for name in (
    # Çekirdek
    "RpcSs", "RpcEptMapper", "DcomLaunch", "LSM", "SamSs", "PlugPlay", "Power", "ProfSvc",
    "BrokerInfrastructure", "SystemEventsBroker", "CoreMessagingRegistrar", "StateRepository",
    "UserManager", "gpsvc", "Winmgmt", "EventLog", "Schedule", "CryptSvc", "KeyIso", "VaultSvc",
    "TimeBrokerSvc", "AppXSvc", "camsvc", "Dhcp", "Dnscache", "nsi", "netprofm", "NlaSvc",
    "LanmanWorkstation", "AudioEndpointBuilder", "Audiosrv", "Themes", "FontCache",
    "TrustedInstaller", "msiserver", "wuauserv", "UsoSvc", "WaaSMedicSvc",
    # Güvenlik
    "WinDefend", "WdNisSvc", "Sense", "SecurityHealthService", "wscsvc", "mpssvc", "BFE",
    "EFS", "SgrmBroker", "WinHttpAutoProxySvc",
))

ACTIONS = ("start", "stop")


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


def is_protected(name: str) -> bool:
    return name.lower() in PROTECTED_SERVICES


def control_problems(entry: ServiceEntry, action: str, has_active_dependents: bool) -> list[str]:
    """Bir başlatma/durdurma isteğinin neden yapılamayacağını çeviri anahtarları olarak döner."""
    if action not in ACTIONS:
        return [K("service_invalid_action")]
    if action == "stop":
        if is_protected(entry.name):
            return [K("service_protected")]
        if entry.status != "running":
            return [K("service_wrong_state")]
        if has_active_dependents:
            return [K("service_has_dependents")]
        return []
    if entry.start_type == "disabled":
        return [K("service_disabled")]
    if entry.status != "stopped":
        return [K("service_wrong_state")]
    return []


# ----------------------------------------------------------------- Win32 SCM

SC_MANAGER_CONNECT = 0x0001
SERVICE_QUERY_STATUS = 0x0004
SERVICE_ENUMERATE_DEPENDENTS = 0x0008
SERVICE_START = 0x0010
SERVICE_STOP = 0x0020
SERVICE_CONTROL_STOP = 0x00000001
SERVICE_ACTIVE = 0x00000001
SERVICE_STOPPED = 0x00000001
SERVICE_RUNNING = 0x00000004
ERROR_MORE_DATA = 234
ERROR_SERVICE_ALREADY_RUNNING = 1056
ERROR_SERVICE_NOT_ACTIVE = 1062


class SERVICE_STATUS(ctypes.Structure):  # noqa: N801 (Win32 adı)
    _fields_ = [
        ("dwServiceType", wintypes.DWORD),
        ("dwCurrentState", wintypes.DWORD),
        ("dwControlsAccepted", wintypes.DWORD),
        ("dwWin32ExitCode", wintypes.DWORD),
        ("dwServiceSpecificExitCode", wintypes.DWORD),
        ("dwCheckPoint", wintypes.DWORD),
        ("dwWaitHint", wintypes.DWORD),
    ]


def _advapi():
    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    advapi.OpenSCManagerW.restype = wintypes.HANDLE
    advapi.OpenSCManagerW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD]
    advapi.OpenServiceW.restype = wintypes.HANDLE
    advapi.OpenServiceW.argtypes = [wintypes.HANDLE, wintypes.LPCWSTR, wintypes.DWORD]
    advapi.CloseServiceHandle.argtypes = [wintypes.HANDLE]
    advapi.StartServiceW.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p]
    advapi.ControlService.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(SERVICE_STATUS)]
    advapi.QueryServiceStatus.argtypes = [wintypes.HANDLE, ctypes.POINTER(SERVICE_STATUS)]
    advapi.EnumDependentServicesW.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD,
                                              ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD)]
    return advapi


class _Service:
    """OpenSCManager/OpenService tutamaçlarını güvenle kapatan bağlam yöneticisi."""

    def __init__(self, name: str, access: int) -> None:
        self.name = name
        self.access = access
        self.api = _advapi()
        self.manager = None
        self.handle = None

    def __enter__(self) -> "_Service":
        self.manager = self.api.OpenSCManagerW(None, None, SC_MANAGER_CONNECT)
        if not self.manager:
            raise ctypes.WinError(ctypes.get_last_error())
        self.handle = self.api.OpenServiceW(self.manager, self.name, self.access)
        if not self.handle:
            error = ctypes.get_last_error()
            self.api.CloseServiceHandle(self.manager)
            raise ctypes.WinError(error)
        return self

    def __exit__(self, *_exc) -> None:
        if self.handle:
            self.api.CloseServiceHandle(self.handle)
        if self.manager:
            self.api.CloseServiceHandle(self.manager)

    def state(self) -> int:
        status = SERVICE_STATUS()
        if not self.api.QueryServiceStatus(self.handle, ctypes.byref(status)):
            raise ctypes.WinError(ctypes.get_last_error())
        return int(status.dwCurrentState)


def has_active_dependents(name: str) -> bool:
    """Bu hizmete bağlı ve şu anda çalışan başka hizmet var mı?"""
    if os.name != "nt":
        return False
    with _Service(name, SERVICE_ENUMERATE_DEPENDENTS) as svc:
        needed = wintypes.DWORD(0)
        count = wintypes.DWORD(0)
        ok = svc.api.EnumDependentServicesW(svc.handle, SERVICE_ACTIVE, None, 0,
                                            ctypes.byref(needed), ctypes.byref(count))
        if ok:
            return count.value > 0
        error = ctypes.get_last_error()
        if error == ERROR_MORE_DATA:
            return True
        raise ctypes.WinError(error)


def control_service(name: str, action: str, timeout: float = 30.0) -> str:
    """Hizmeti başlatır veya durdurur ve hedef duruma ulaşmasını bekler.

    Hizmetin önceki durumunu ("running"/"stopped") döner; zaman aşımında TimeoutError.
    """
    if action not in ACTIONS:
        raise ValueError(action)
    if os.name != "nt":
        raise OSError("Windows services are only available on Windows.")
    target = SERVICE_RUNNING if action == "start" else SERVICE_STOPPED
    with _Service(name, SERVICE_QUERY_STATUS | SERVICE_START | SERVICE_STOP) as svc:
        previous = "running" if svc.state() == SERVICE_RUNNING else "stopped"
        if action == "start":
            if not svc.api.StartServiceW(svc.handle, 0, None):
                error = ctypes.get_last_error()
                if error != ERROR_SERVICE_ALREADY_RUNNING:
                    raise ctypes.WinError(error)
        else:
            status = SERVICE_STATUS()
            if not svc.api.ControlService(svc.handle, SERVICE_CONTROL_STOP, ctypes.byref(status)):
                error = ctypes.get_last_error()
                if error != ERROR_SERVICE_NOT_ACTIVE:
                    raise ctypes.WinError(error)
        deadline = time.monotonic() + timeout
        while svc.state() != target:
            if time.monotonic() > deadline:
                raise TimeoutError(f"{name}: {action} did not complete in {int(timeout)} s")
            time.sleep(0.25)
    return previous
