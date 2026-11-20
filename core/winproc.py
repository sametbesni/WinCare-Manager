"""Windows komut satırı araçlarını pencere açmadan çalıştırma yardımcıları."""
from __future__ import annotations

import json
import os
import subprocess
from typing import Any

CREATE_NO_WINDOW = 0x08000000


def run_command(args: list[str], timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding="oem" if os.name == "nt" else "utf-8",
        errors="replace",
        timeout=timeout,
        creationflags=CREATE_NO_WINDOW if os.name == "nt" else 0,
    )


def powershell_env() -> dict[str, str]:
    """Windows PowerShell 5.1 için yalnızca kendi modül klasörlerini içeren ortam.

    Bilgisayarda PowerShell 7 (pwsh) kuruluysa PSModulePath, onun modül
    klasörlerini de içerebilir. Windows PowerShell 5.1 bu durumda çekirdek
    modüllerin (ör. Microsoft.PowerShell.Security) yanlış sürümünü yüklemeye
    çalışır; "already present" tür verisi hatasıyla imza denetimi gibi
    komutlar başarısız olur. Değişkeni silmek yetmez, çünkü Windows onu sistem
    ayarlarından yeniden oluşturur; bu yüzden 5.1'in varsayılan yolu açıkça verilir.
    """
    env = dict(os.environ)
    system_root = env.get("SystemRoot") or env.get("SYSTEMROOT") or r"C:\Windows"
    program_files = env.get("ProgramFiles") or env.get("PROGRAMFILES") or r"C:\Program Files"
    documents = os.path.join(os.path.expanduser("~"), "Documents")
    env["PSModulePath"] = os.pathsep.join([
        os.path.join(documents, "WindowsPowerShell", "Modules"),
        os.path.join(program_files, "WindowsPowerShell", "Modules"),
        os.path.join(system_root, "system32", "WindowsPowerShell", "v1.0", "Modules"),
    ])
    return env


def run_powershell_json(script: str, timeout: int = 60) -> list[dict[str, Any]]:
    """Run a PowerShell snippet whose output is ConvertTo-Json; always returns a list."""
    if os.name != "nt":
        return []
    wrapped = (
        "$ErrorActionPreference='SilentlyContinue';"
        "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8;" + script
    )
    completed = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", wrapped],
        capture_output=True,
        timeout=timeout,
        creationflags=CREATE_NO_WINDOW,
        env=powershell_env(),
    )
    text = completed.stdout.decode("utf-8", errors="replace").strip().lstrip("﻿")
    if not text:
        return []
    data = json.loads(text)
    if isinstance(data, dict):
        return [data]
    return [item for item in data if isinstance(item, dict)]
