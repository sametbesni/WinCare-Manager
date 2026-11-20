from __future__ import annotations

import json
import logging

from PySide6.QtWidgets import QPlainTextEdit, QTabWidget

from app.i18n import K
from ui.pages.base import BasePage
from ui.widgets import SortItem, make_table, muted_label

STATUS_KEYS = {
    "running": K("status_running"), "success": K("status_success"), "partial": K("status_partial"),
    "failed": K("status_failed"), "cancelled": K("status_cancelled"), "dry_run": K("status_dry_run"),
    "blocked": K("status_blocked"), "interrupted": K("status_interrupted"),
}
KIND_KEYS = {
    "cleaner.recycle": K("kind_cleaner"), "startup.enable": K("kind_startup_enable"),
    "startup.disable": K("kind_startup_disable"), "backup.create": K("kind_backup_create"),
    "backup.restore": K("kind_backup_restore"),
    "maintenance.analysis": K("kind_maintenance_analysis"), "maintenance.schedule": K("kind_maintenance_schedule"),
    "maintenance.unschedule": K("kind_maintenance_unschedule"), "app.prepare_uninstall": K("kind_prepare_uninstall"),
}


class HistoryPage(BasePage):
    title_key = K("page_history")
    subtitle_key = K("subtitle_history")

    def __init__(self, ctx) -> None:
        super().__init__(ctx)
        self.root.addWidget(muted_label(self.t("history_description")))
        tabs = QTabWidget()
        self.table = make_table([self.t("history_time"), self.t("history_kind"), self.t("history_summary"),
                                 self.t("history_status"), self.t("history_targets"), self.t("history_id")],
                                stretch=(2,))
        self.table.itemSelectionChanged.connect(self._show_details)
        tabs.addTab(self.table, self.t("history_operations_tab"))
        self.viewer = QPlainTextEdit()
        self.viewer.setReadOnly(True)
        self.viewer.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.viewer.setPlaceholderText(self.t("history_empty"))
        tabs.addTab(self.viewer, self.t("history_log_tab"))
        self.root.addWidget(tabs, 1)
        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setMaximumHeight(130)
        self.details.setPlaceholderText(self.t("history_details_placeholder"))
        self.root.addWidget(self.details)
        self._records = []

    def refresh(self) -> None:
        self._records = self.ctx.history.recent()
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self._records))
        for row, r in enumerate(self._records):
            when = SortItem(r.started_at.replace("T", " "), r.started_at)
            when.setData(256, row)
            self.table.setItem(row, 0, when)
            self.table.setItem(row, 1, SortItem(self.t(KIND_KEYS[r.kind]) if r.kind in KIND_KEYS else r.kind))
            self.table.setItem(row, 2, SortItem(r.summary))
            status = self.t(STATUS_KEYS.get(r.status, r.status))
            if r.dry_run and r.status != "dry_run":
                status += " · " + self.t("status_dry_run")
            self.table.setItem(row, 3, SortItem(status))
            self.table.setItem(row, 4, SortItem(str(r.target_count), r.target_count, align_right=True))
            self.table.setItem(row, 5, SortItem(r.id[:8]))
        self.table.setSortingEnabled(True)

        log_file = self.ctx.config.log_file
        try:
            if log_file.is_file():
                content = log_file.read_text(encoding="utf-8", errors="replace")
                self.viewer.setPlainText(content[-100_000:])
                self.viewer.verticalScrollBar().setValue(self.viewer.verticalScrollBar().maximum())
            else:
                self.viewer.clear()
        except OSError as exc:
            logging.exception("Application log could not be read.")
            self.viewer.setPlainText(self.t("history_read_error", error=str(exc)))

    def _show_details(self) -> None:
        row = self.table.currentRow()
        item = self.table.item(row, 0) if row >= 0 else None
        index = item.data(256) if item else None
        if index is None or index >= len(self._records):
            return
        r = self._records[index]
        info = {
            "id": r.id, "kind": r.kind, "status": r.status, "dry_run": r.dry_run,
            "started_at": r.started_at, "finished_at": r.finished_at, "backup_id": r.backup_id,
            "details": r.details,
        }
        self.details.setPlainText(json.dumps(info, ensure_ascii=False, indent=2))

    def on_show(self) -> None:
        self.refresh()
