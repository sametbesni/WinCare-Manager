from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from app.i18n import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES

DEFAULTS: dict[str, Any] = {
    "language": DEFAULT_LANGUAGE,
    "refresh_interval_seconds": 2,
    "show_process_username": True,
    # Deneme modu: işlemler planlanır ve kaydedilir, fakat sisteme uygulanmaz.
    "dry_run": True,
    "temp_min_age_hours": 24,
    # Otomatik Bakım isteğe bağlıdır ve varsayılan olarak KAPALIDIR.
    "auto_maintenance_enabled": False,
    "auto_maintenance_frequency": "weekly",
    "auto_maintenance_day": "MON",
    "auto_maintenance_time": "10:00",
    # Kullanıcının gördüğü son bakım raporunun kimliği (yeni rapor bildirimi için).
    "maintenance_report_seen": "",
}


class ConfigManager:
    """Reads and writes user preferences in the local application data folder."""

    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = data_dir or self._default_data_dir()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.config_path = self.data_dir / "settings.json"
        self._settings = dict(DEFAULTS)
        self.load()

    @staticmethod
    def _default_data_dir() -> Path:
        if os.name == "nt":
            base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
            return base / "WinCareManager"
        return Path.home() / ".local" / "share" / "wincare-manager"

    @property
    def backups_dir(self) -> Path:
        return self.data_dir / "backups"

    @property
    def history_db(self) -> Path:
        return self.data_dir / "history.db"

    @property
    def log_file(self) -> Path:
        return self.data_dir / "logs" / "wincare.log"

    def load(self) -> None:
        if not self.config_path.exists():
            self.save()
            return
        try:
            # utf-8-sig: Not Defteri / PowerShell ile kaydedilen dosyalardaki BOM kabul edilir.
            loaded = json.loads(self.config_path.read_text(encoding="utf-8-sig"))
            if isinstance(loaded, dict):
                self._settings.update({k: v for k, v in loaded.items() if k in DEFAULTS})
        except (OSError, json.JSONDecodeError):
            logging.exception("Settings file could not be read; defaults will be used.")
            self._settings = dict(DEFAULTS)
        self._validate()

    def _validate(self) -> None:
        s = self._settings
        if s.get("language") not in SUPPORTED_LANGUAGES:
            s["language"] = DEFAULT_LANGUAGE
        s["refresh_interval_seconds"] = self._clamp_int(s.get("refresh_interval_seconds"), 2, 1, 10)
        s["temp_min_age_hours"] = self._clamp_int(s.get("temp_min_age_hours"), 24, 1, 720)
        if s.get("auto_maintenance_frequency") not in ("daily", "weekly"):
            s["auto_maintenance_frequency"] = DEFAULTS["auto_maintenance_frequency"]
        if s.get("auto_maintenance_day") not in ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"):
            s["auto_maintenance_day"] = DEFAULTS["auto_maintenance_day"]
        if not self._valid_time(s.get("auto_maintenance_time")):
            s["auto_maintenance_time"] = DEFAULTS["auto_maintenance_time"]
        if not isinstance(s.get("maintenance_report_seen"), str):
            s["maintenance_report_seen"] = ""
        for key in ("dry_run", "show_process_username", "auto_maintenance_enabled"):
            if not isinstance(s.get(key), bool):
                s[key] = DEFAULTS[key]

    @staticmethod
    def _valid_time(value: Any) -> bool:
        if not isinstance(value, str) or value.count(":") != 1:
            return False
        hour, minute = value.split(":")
        return hour.isdigit() and minute.isdigit() and int(hour) < 24 and int(minute) < 60

    @staticmethod
    def _clamp_int(value: Any, default: int, low: int, high: int) -> int:
        try:
            number = int(value)
        except (TypeError, ValueError):
            number = default
        return min(high, max(low, number))

    def save(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        temporary = self.config_path.with_suffix(".tmp")
        try:
            with temporary.open("w", encoding="utf-8", newline="\n") as file:
                json.dump(self._settings, file, ensure_ascii=False, indent=2)
                file.write("\n")
                file.flush()
                os.fsync(file.fileno())
            temporary.replace(self.config_path)
        except OSError:
            temporary.unlink(missing_ok=True)
            raise

    def get(self, key: str, default: Any = None) -> Any:
        return self._settings.get(key, default)

    def set(self, key: str, value: Any) -> None:
        if key not in DEFAULTS:
            raise KeyError(f"Unsupported setting: {key}")
        self._settings[key] = value
        self._validate()
        self.save()

    def as_dict(self) -> dict[str, Any]:
        return dict(self._settings)
