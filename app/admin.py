"""Yönetici yetkisi kontrolü ve isteğe bağlı UAC yükseltmesi.

Uygulama sürekli yönetici olarak çalışmaz; yalnızca kullanıcı istediğinde
UAC üzerinden yeniden başlatılır.
"""
from __future__ import annotations

import ctypes
import logging
import os
import subprocess
import sys
from pathlib import Path


def is_admin() -> bool:
    if os.name != "nt":
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


def relaunch_as_admin() -> bool:
    """Start a new elevated instance. Returns True if UAC accepted the request."""
    if os.name != "nt":
        return False
    if getattr(sys, "frozen", False):
        executable = sys.executable
        params = subprocess.list2cmdline(sys.argv[1:])
    else:
        executable = sys.executable
        main_script = Path(__file__).resolve().parent.parent / "main.py"
        params = subprocess.list2cmdline([str(main_script), *sys.argv[1:]])
    try:
        result = ctypes.windll.shell32.ShellExecuteW(None, "runas", executable, params, None, 1)
    except OSError:
        logging.exception("Elevation request failed.")
        return False
    return int(result) > 32
