from __future__ import annotations

import os

from PySide6.QtWidgets import QHBoxLayout, QPushButton

from app.i18n import K
from core import registry
from core.backup import BackupRecord
from core.engine import ExecutionOutcome, OperationPlan
from core.startup import APPROVED_BASE, RUN_KEY
from core.system_info import format_bytes
from ui.pages.base import BasePage
from ui.widgets import (SortItem, ask_confirmation, make_table, muted_label, show_info,
                        show_operation_result)


class BackupPage(BasePage):
    title_key = K("page_backup")
    subtitle_key = K("subtitle_backup")

    def __init__(self, ctx) -> None:
        super().__init__(ctx)
        self.root.addWidget(muted_label(self.t("backup_info")))

        bar = QHBoxLayout()
        self.quick_button = QPushButton(self.t("backup_quick_startup"))
        self.quick_button.clicked.connect(self._quick_backup)
        self.verify_button = QPushButton(self.t("backup_verify"))
        self.verify_button.setObjectName("SecondaryButton")
        self.verify_button.clicked.connect(self._verify)
        self.restore_button = QPushButton(self.t("backup_restore"))
        self.restore_button.setObjectName("DangerButton")
        self.restore_button.clicked.connect(self._restore)
        folder_button = QPushButton(self.t("open_folder"))
        folder_button.setObjectName("SecondaryButton")
        folder_button.clicked.connect(lambda: os.startfile(self.ctx.backups.root))  # noqa: S606
        self.count_label = muted_label("", wrap=False)
        bar.addWidget(self.count_label, 1)
        for button in (self.quick_button, self.verify_button, self.restore_button, folder_button):
            bar.addWidget(button)
        self.root.addLayout(bar)

        self.table = make_table([self.t("backup_date"), self.t("backup_key"), self.t("backup_description"),
                                 self.t("file_size"), self.t("backup_id_column")], stretch=(1,))
        self.table.itemSelectionChanged.connect(self._update_buttons)
        self.root.addWidget(self.table, 1)
        self._records: list[BackupRecord] = []
        self._update_buttons()

    def refresh(self) -> None:
        self._records = self.ctx.backups.list()
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self._records))
        for row, r in enumerate(self._records):
            date = SortItem(r.created_at.replace("T", " "), r.created_at)
            date.setData(256, row)
            self.table.setItem(row, 0, date)
            self.table.setItem(row, 1, SortItem(r.key))
            self.table.setItem(row, 2, SortItem(r.description))
            self.table.setItem(row, 3, SortItem(format_bytes(r.size), r.size, align_right=True))
            self.table.setItem(row, 4, SortItem(r.backup_id))
        self.table.setSortingEnabled(True)
        self.count_label.setText(self.t("count_label", count=len(self._records)))
        self._update_buttons()

    def _selected(self) -> BackupRecord | None:
        row = self.table.currentRow()
        if row < 0 or not self.table.item(row, 0):
            return None
        index = self.table.item(row, 0).data(256)
        return self._records[index] if index is not None and index < len(self._records) else None

    def _update_buttons(self) -> None:
        has = self._selected() is not None
        self.verify_button.setEnabled(has)
        self.restore_button.setEnabled(has)

    def _quick_backup(self) -> None:
        keys = [("HKCU", RUN_KEY), ("HKCU", APPROVED_BASE), ("HKLM", RUN_KEY), ("HKLM", APPROVED_BASE)]
        existing = [(h, p) for h, p in keys if registry.key_exists(h, p)]
        created: list[str] = []

        def execute() -> ExecutionOutcome:
            failed = []
            for hive, path in existing:
                try:
                    record = self.ctx.backups.create_registry_backup(hive, path, self.t("backup_quick_description"))
                    created.append(record.backup_id)
                except Exception as exc:  # bir anahtar başarısız olsa da diğerleri denenir
                    failed.append(f"{hive}\\{path}: {exc}")
            return ExecutionOutcome(len(created), len(failed), {"backups": created, "errors": failed})

        plan = OperationPlan(kind="backup.create", summary=self.t("backup_quick_startup"),
                             targets=[registry.full_key_name(h, p) for h, p in existing],
                             execute=execute, respects_dry_run=False)
        result = self.ctx.engine.run(plan, dry_run=False)
        show_operation_result(self, self.ctx, result)
        self.refresh()

    def _verify(self) -> None:
        record = self._selected()
        if not record:
            return
        ok = self.ctx.backups.verify(record)
        show_info(self, self.t("backup_verify"),
                  self.t("backup_verify_ok") if ok else self.t("backup_verify_failed"), error=not ok)

    def _restore(self) -> None:
        record = self._selected()
        if not record:
            return
        store = self.ctx.backups
        hive, _, path = record.key.partition("\\")

        def validate() -> list[str]:
            return [] if store.verify(record) else [self.t("backup_verify_failed")]

        def backup() -> str | None:
            # Geri yüklemeden önce mevcut durumun da yedeğini al (geri dönüş noktası).
            if path and registry.key_exists(hive, path):
                return store.create_registry_backup(hive, path, self.t("backup_before_restore")).backup_id
            return None

        def execute() -> ExecutionOutcome:
            store.restore(record)
            return ExecutionOutcome(1, 0, {"restored": record.backup_id, "key": record.key})

        plan = OperationPlan(kind="backup.restore", summary=record.key, targets=[record.key],
                             execute=execute, validate=validate, backup=backup,
                             requires_admin=record.hive == "HKLM")
        text = self.t("backup_restore_confirm", key=record.key, date=record.created_at.replace("T", " "))
        if self.ctx.dry_run:
            text += "\n\n" + self.t("dry_run_notice")
        if not ask_confirmation(self, self.ctx, self.t("confirm_title"), text):
            self.ctx.engine.record_cancelled(plan)
            return
        result = self.ctx.engine.run(plan, dry_run=self.ctx.dry_run)
        show_operation_result(self, self.ctx, result)
        self.refresh()

    def on_show(self) -> None:
        self.refresh()
