"""İşlem motoru ve güvenlik katmanı.

Arayüz sisteme hiçbir zaman doğrudan değişiklik yapmaz. Her değişiklik bir
``OperationPlan`` olarak bu motora verilir ve şu adımlardan geçer:

1. Kayıt      – benzersiz işlem kimliği oluşturulur, geçmişe "running" yazılır.
2. Yetki      – yönetici gerektiren işlem, yetki yoksa engellenir.
3. Doğrulama  – plan kendi güvenlik kontrollerini çalıştırır.
4. Deneme     – deneme modu açıksa burada durulur, hiçbir şey değişmez.
5. Yedekleme  – geri alınabilir değişiklikler için yedek alınır; yedek
                alınamazsa işlem uygulanmaz.
6. Uygulama   – işlem gerçekleştirilir.
7. Sonuç      – sonuç ve ayrıntılar geçmişe yazılır.

Kullanıcı onayı, işlem motoruna gönderilmeden önce arayüzde alınır.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable

from app import admin
from app.i18n import K
from database.history import HistoryStore


@dataclass
class ExecutionOutcome:
    succeeded: int
    failed: int = 0
    details: dict = field(default_factory=dict)


@dataclass
class OperationPlan:
    kind: str
    summary: str
    targets: list[str]
    execute: Callable[[], ExecutionOutcome]
    validate: Callable[[], list[str]] | None = None
    backup: Callable[[], str | None] | None = None
    requires_admin: bool = False
    # Yedek alma gibi sistemi değiştirmeyen işlemler deneme modundan etkilenmez.
    respects_dry_run: bool = True


@dataclass
class OperationResult:
    operation_id: str
    status: str
    succeeded: int = 0
    failed: int = 0
    message_key: str = ""
    details: dict = field(default_factory=dict)
    backup_id: str | None = None


class OperationEngine:
    def __init__(self, history: HistoryStore, is_admin: Callable[[], bool] = admin.is_admin) -> None:
        self.history = history
        self._is_admin = is_admin

    def run(self, plan: OperationPlan, *, dry_run: bool) -> OperationResult:
        dry = dry_run and plan.respects_dry_run
        op_id = self.history.start(plan.kind, plan.summary, len(plan.targets), dry)

        def done(status: str, message_key: str, details: dict | None = None, *,
                 succeeded: int = 0, failed: int = 0, backup_id: str | None = None) -> OperationResult:
            info = dict(details or {})
            self.history.finish(op_id, status, info, backup_id)
            logging.info("Operation %s [%s] %s -> %s", op_id, plan.kind, plan.summary, status)
            return OperationResult(op_id, status, succeeded, failed, message_key, info, backup_id)

        try:
            if plan.requires_admin and not self._is_admin():
                return done("blocked", K("op_needs_admin"))

            problems = plan.validate() if plan.validate else []
            if problems:
                return done("blocked", K("op_validation_failed"), {"problems": problems[:50]})

            if dry:
                return done("dry_run", K("op_dry_run"), {"targets": plan.targets[:200]})

            backup_id = None
            if plan.backup:
                try:
                    backup_id = plan.backup()
                except Exception as exc:  # yedek yoksa işlem yok
                    logging.exception("Backup before operation failed.")
                    return done("failed", K("op_backup_failed"), {"error": str(exc)})

            outcome = plan.execute()
            if outcome.failed == 0:
                status, key = "success", K("op_success")
            elif outcome.succeeded:
                status, key = "partial", K("op_partial")
            else:
                status, key = "failed", K("op_failed")
            return done(status, key, outcome.details, succeeded=outcome.succeeded,
                        failed=outcome.failed, backup_id=backup_id)
        except Exception as exc:
            logging.exception("Operation %s failed.", op_id)
            return done("failed", K("op_failed"), {"error": str(exc)})

    def record_cancelled(self, plan: OperationPlan) -> None:
        """Kullanıcının onaylamadığı işlemleri de geçmişe yazar."""
        op_id = self.history.start(plan.kind, plan.summary, len(plan.targets), False)
        self.history.finish(op_id, "cancelled")
