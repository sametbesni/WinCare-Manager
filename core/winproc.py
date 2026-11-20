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
    )
    text = completed.stdout.decode("utf-8", errors="replace").strip().lstrip("﻿")
    if not text:
        return []
    data = json.loads(text)
    if isinstance(data, dict):
        return [data]
    return [item for item in data if isinstance(item, dict)]
