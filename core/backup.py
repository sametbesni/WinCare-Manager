"""Yedekleme ve geri yükleme.

Her yedek bir dosya (.reg) ve onun SHA-256 özetini içeren bir manifest (.json)
olarak saklanır. Geri yüklemeden önce bütünlük doğrulanır.
"""
from __future__ import annotations

import hashlib
import json
import logging
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from core import registry


class BackupIntegrityError(RuntimeError):
    pass


@dataclass(frozen=True)
class BackupRecord:
    backup_id: str
    created_at: str
    key: str
    file_name: str
    sha256: str
    size: int
    description: str

    @property
    def hive(self) -> str:
        return self.key.split("\\", 1)[0]


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


class BackupStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def new_id() -> str:
        return datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]

    def file_path(self, record: BackupRecord) -> Path:
        return self.root / record.file_name

    def register(self, file: Path, key: str, description: str, backup_id: str | None = None) -> BackupRecord:
        file = file.resolve()
        if file.parent != self.root.resolve():
            raise ValueError("Backup file must be inside the backup folder.")
        record = BackupRecord(
            backup_id=backup_id or self.new_id(),
            created_at=datetime.now().isoformat(timespec="seconds"),
            key=key,
            file_name=file.name,
            sha256=sha256_of(file),
            size=file.stat().st_size,
            description=description,
        )
        manifest = self.root / f"{record.backup_id}.json"
        manifest.write_text(json.dumps(asdict(record), ensure_ascii=False, indent=2), encoding="utf-8")
        return record

    def create_registry_backup(self, hive: str, path: str, description: str) -> BackupRecord:
        backup_id = self.new_id()
        target = self.root / f"{backup_id}.reg"
        registry.export_key(hive, path, target)
        record = self.register(target, registry.full_key_name(hive, path), description, backup_id)
        logging.info("Registry backup %s created for %s", record.backup_id, record.key)
        return record

    def list(self) -> list[BackupRecord]:
        records: list[BackupRecord] = []
        for manifest in self.root.glob("*.json"):
            try:
                data = json.loads(manifest.read_text(encoding="utf-8"))
                records.append(BackupRecord(**data))
            except (OSError, json.JSONDecodeError, TypeError):
                logging.warning("Unreadable backup manifest: %s", manifest)
        return sorted(records, key=lambda r: r.created_at, reverse=True)

    def get(self, backup_id: str) -> BackupRecord | None:
        return next((r for r in self.list() if r.backup_id == backup_id), None)

    def verify(self, record: BackupRecord) -> bool:
        path = self.file_path(record)
        try:
            return path.is_file() and sha256_of(path) == record.sha256
        except OSError:
            return False

    def restore(self, record: BackupRecord) -> None:
        if not self.verify(record):
            raise BackupIntegrityError(record.backup_id)
        registry.import_file(self.file_path(record))
        logging.info("Registry backup %s restored to %s", record.backup_id, record.key)
