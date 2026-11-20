from __future__ import annotations

import json
import os
import time
from pathlib import Path

from app.config_manager import ConfigManager
from app.i18n import Translator
from core.cleaner import scan_temporary_files, validate_targets
from core.system_info import format_bytes, format_uptime


def test_format_bytes() -> None:
    assert format_bytes(0) == "0 B"
    assert format_bytes(1024) == "1.0 KB"
    assert format_bytes(1024 * 1024) == "1.0 MB"


def test_format_uptime_locales() -> None:
    assert format_uptime(90061, "tr_TR") == "1 gün 1 saat 1 dakika"
    assert format_uptime(90061, "en_US") == "1d 1h 1m"


def test_config_persists_only_supported_settings(tmp_path: Path) -> None:
    config = ConfigManager(tmp_path)
    config.set("language", "en_US")
    config.set("refresh_interval_seconds", 5)
    loaded = ConfigManager(tmp_path)
    assert loaded.get("language") == "en_US"
    assert loaded.get("refresh_interval_seconds") == 5
    data = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))
    assert "unknown_setting" not in data


def test_invalid_settings_fall_back_to_safe_defaults(tmp_path: Path) -> None:
    (tmp_path / "settings.json").write_text(
        json.dumps({"language": "invalid", "refresh_interval_seconds": 100,
                    "dry_run": "no", "temp_min_age_hours": -5}),
        encoding="utf-8",
    )
    config = ConfigManager(tmp_path)
    assert config.get("language") == "tr_TR"
    assert config.get("refresh_interval_seconds") == 10
    assert config.get("dry_run") is True          # geçersiz değer -> güvenli varsayılan
    assert config.get("temp_min_age_hours") == 1


def test_dry_run_is_on_by_default(tmp_path: Path) -> None:
    assert ConfigManager(tmp_path).get("dry_run") is True


def test_cleaner_scan_is_read_only_and_respects_age(tmp_path: Path) -> None:
    old_file = tmp_path / "old.tmp"
    new_file = tmp_path / "new.tmp"
    old_file.write_bytes(b"older temporary data")
    new_file.write_bytes(b"new data")
    old_time = time.time() - 3 * 24 * 60 * 60
    os.utime(old_file, (old_time, old_time))

    result = scan_temporary_files([tmp_path], older_than_seconds=24 * 60 * 60)
    assert len(result.files) == 1
    assert Path(result.files[0].path) == old_file
    assert result.total_bytes == old_file.stat().st_size
    assert old_file.exists()
    assert new_file.exists()


def test_cleaner_does_not_follow_symlinks(tmp_path: Path) -> None:
    outside = tmp_path.parent / f"{tmp_path.name}_outside.tmp"
    outside.write_text("do not include", encoding="utf-8")
    old_time = time.time() - 3 * 24 * 60 * 60
    os.utime(outside, (old_time, old_time))
    link = tmp_path / "link.tmp"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        outside.unlink(missing_ok=True)
        return
    result = scan_temporary_files([tmp_path], older_than_seconds=24 * 60 * 60)
    assert all(Path(item.path) != outside for item in result.files)
    assert outside.exists()
    outside.unlink(missing_ok=True)


def test_validate_targets_blocks_paths_outside_allowed_roots(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    inside = root / "a.tmp"
    inside.write_text("x", encoding="utf-8")
    outside = tmp_path / "b.tmp"
    outside.write_text("y", encoding="utf-8")
    report = validate_targets([str(inside), str(outside), str(root / "gone.tmp")], [root])
    assert [p.name for p in report.valid] == ["a.tmp"]
    assert report.violations == (str(outside),)
    assert report.missing == (str(root / "gone.tmp"),)


def test_validate_targets_blocks_windows_folder() -> None:
    windir = os.environ.get("WINDIR")
    if not windir:
        return
    target = str(Path(windir) / "notepad.exe")
    report = validate_targets([target], [Path(windir)])
    assert report.valid == ()


def test_locale_files_have_matching_keys_and_expected_default() -> None:
    tr = Translator("tr_TR")
    en = Translator("en_US")
    assert set(tr._strings) == set(en._strings)
    assert tr.language == "tr_TR"
    assert tr.tr("nav_dashboard") == "Genel Bakış"
    assert en.tr("nav_dashboard") == "Overview"


def test_unknown_locale_falls_back_to_turkish() -> None:
    translator = Translator("fr_FR")
    assert translator.language == "tr_TR"
    assert translator.tr("language_turkish") == "Türkçe"
