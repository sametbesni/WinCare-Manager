from __future__ import annotations

import sys
from pathlib import Path


def get_resource_path(relative_path: str) -> Path:
    """Return a bundled resource path in source and PyInstaller builds."""
    bundle_dir = getattr(sys, "_MEIPASS", None)
    if bundle_dir:
        return Path(bundle_dir) / relative_path
    return Path(__file__).resolve().parent.parent / relative_path
