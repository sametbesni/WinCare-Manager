"""İşlem geçmişi (SQLite). Her işlem benzersiz bir kimlikle kaydedilir."""
from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

STATUSES = (
    "running", "success", "partial", "failed", "cancelled",
    "dry_run", "blocked", "interrupted",
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS operations (
    id            TEXT PRIMARY KEY,
    kind          TEXT NOT NULL,
    summary       TEXT NOT NULL,
    status        TEXT NOT NULL,
    dry_run       INTEGER NOT NULL DEFAULT 0,
    target_count  INTEGER NOT NULL DEFAULT 0,
    started_at    TEXT NOT NULL,
    finished_at   TEXT,
    backup_id     TEXT,
    details       TEXT
);
CREATE INDEX IF NOT EXISTS idx_operations_started ON operations(started_at);
"""


@dataclass(frozen=True)
class OperationRecord:
    id: str
    kind: str
    summary: str
    status: str
    dry_run: bool
    target_count: int
    started_at: str
    finished_at: str | None
    backup_id: str | None
    details: dict


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class HistoryStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        # Her çağrıda yeni bağlantı: arka plan iş parçacıklarından güvenle kullanılabilir.
        return sqlite3.connect(self.db_path, timeout=10)

    def start(self, kind: str, summary: str, target_count: int, dry_run: bool) -> str:
        op_id = uuid.uuid4().hex
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO operations (id, kind, summary, status, dry_run, target_count, started_at) "
                "VALUES (?, ?, ?, 'running', ?, ?, ?)",
                (op_id, kind, summary, int(dry_run), target_count, _now()),
            )
        return op_id

    def finish(self, op_id: str, status: str, details: dict | None = None, backup_id: str | None = None) -> None:
        if status not in STATUSES:
            raise ValueError(f"Unknown status: {status}")
        with self._connect() as conn:
            conn.execute(
                "UPDATE operations SET status = ?, finished_at = ?, backup_id = ?, details = ? WHERE id = ?",
                (status, _now(), backup_id, json.dumps(details or {}, ensure_ascii=False), op_id),
            )

    def mark_interrupted(self) -> int:
        """Önceki oturumda yarım kalan işlemleri tespit eder ve işaretler."""
        with self._connect() as conn:
            cursor = conn.execute(
                "UPDATE operations SET status = 'interrupted', finished_at = ? WHERE status = 'running'",
                (_now(),),
            )
            return cursor.rowcount

    def recent(self, limit: int = 500) -> list[OperationRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, kind, summary, status, dry_run, target_count, started_at, finished_at, backup_id, details "
                "FROM operations ORDER BY started_at DESC, rowid DESC LIMIT ?",
                (limit,),
            ).fetchall()
        records = []
        for row in rows:
            try:
                details = json.loads(row[9]) if row[9] else {}
            except json.JSONDecodeError:
                details = {}
            records.append(OperationRecord(row[0], row[1], row[2], row[3], bool(row[4]), row[5], row[6], row[7], row[8], details))
        return records

    def get(self, op_id: str) -> OperationRecord | None:
        return next((r for r in self.recent(10_000) if r.id == op_id), None)
