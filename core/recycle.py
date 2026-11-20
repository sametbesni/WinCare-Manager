"""Dosyaları kalıcı silmek yerine Windows Geri Dönüşüm Kutusu'na taşır."""
from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
from pathlib import Path

FO_DELETE = 0x0003
FOF_SILENT = 0x0004
FOF_NOCONFIRMATION = 0x0010
FOF_ALLOWUNDO = 0x0040
FOF_NOERRORUI = 0x0400


class SHFILEOPSTRUCTW(ctypes.Structure):
    _pack_ = 1 if ctypes.sizeof(ctypes.c_void_p) == 4 else 8
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("wFunc", wintypes.UINT),
        ("pFrom", ctypes.c_void_p),
        ("pTo", ctypes.c_void_p),
        ("fFlags", ctypes.c_uint16),
        ("fAnyOperationsAborted", wintypes.BOOL),
        ("hNameMappings", ctypes.c_void_p),
        ("lpszProgressTitle", ctypes.c_void_p),
    ]


def send_to_recycle_bin(paths: list[Path], chunk_size: int = 100) -> tuple[list[str], list[str]]:
    """Returns (moved, failed). A file counts as moved only if it no longer exists afterwards."""
    if os.name != "nt":
        raise OSError("Recycle Bin is only available on Windows.")
    moved: list[str] = []
    failed: list[str] = []
    for start in range(0, len(paths), chunk_size):
        chunk = [str(p) for p in paths[start:start + chunk_size]]
        buffer = ctypes.create_unicode_buffer("\0".join(chunk) + "\0\0")
        op = SHFILEOPSTRUCTW()
        op.hwnd = None
        op.wFunc = FO_DELETE
        op.pFrom = ctypes.addressof(buffer)
        op.pTo = None
        op.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT | FOF_NOERRORUI
        ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
        for item in chunk:
            (failed if os.path.lexists(item) else moved).append(item)
    return moved, failed
