from __future__ import annotations

import os
from pathlib import Path

import pytest

from core.backup import BackupIntegrityError, BackupStore
from core.startup import approved_bytes, is_enabled_flag


def test_backup_register_verify_and_detect_tampering(tmp_path: Path) -> None:
    store = BackupStore(tmp_path / "backups")
    file = store.root / "x.reg"
    file.write_text("Windows Registry Editor Version 5.00\n", encoding="utf-16")
    record = store.register(file, "HKCU\\Software\\Test", "test")
    assert store.list()[0].backup_id == record.backup_id
    assert store.verify(record)

    file.write_text("tampered", encoding="utf-16")
    assert not store.verify(record)
    with pytest.raises(BackupIntegrityError):
        store.restore(record)


def test_backup_file_must_be_inside_store(tmp_path: Path) -> None:
    store = BackupStore(tmp_path / "backups")
    outside = tmp_path / "evil.reg"
    outside.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError):
        store.register(outside, "HKCU\\X", "test")


def test_startup_approved_flags_round_trip() -> None:
    assert is_enabled_flag(None)
    assert is_enabled_flag(approved_bytes(True))
    assert not is_enabled_flag(approved_bytes(False))
    assert is_enabled_flag(bytes([0x06] + [0] * 11))
    assert len(approved_bytes(False, now=0)) == 12


@pytest.mark.skipif(os.name != "nt", reason="Windows registry")
def test_registry_export_and_read_on_windows(tmp_path: Path) -> None:
    from core import registry

    import uuid
    import winreg

    subkeys, _values = registry.read_key("HKCU", "Software")
    assert subkeys
    # Makinenin durumuna bağlı kalmamak için geçici, teste özel bir anahtar kullanılır.
    path = rf"Software\WinCareManagerTest-{uuid.uuid4().hex[:8]}"
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, path) as key:
        winreg.SetValueEx(key, "Example", 0, winreg.REG_SZ, "value")
    try:
        store = BackupStore(tmp_path / "backups")
        record = store.create_registry_backup("HKCU", path, "test")
        assert store.verify(record)
        assert record.key.startswith("HKCU\\")
        assert "Example" in Path(store.root / f"{record.backup_id}.reg").read_text(encoding="utf-16")
    finally:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, path)
