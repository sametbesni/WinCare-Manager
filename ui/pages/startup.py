from __future__ import annotations

import os

from PySide6.QtWidgets import QHBoxLayout, QPushButton

from app.i18n import K
from core import registry
from core.engine import ExecutionOutcome, OperationPlan
from core.startup import StartupEntry, list_startup_entries, set_enabled
from ui.pages.base import BasePage
from ui.widgets import SortItem, ask_confirmation, make_table, muted_label, show_operation_result

SOURCE_KEYS = {
    "current_user": K("source_current_user"),
    "local_machine": K("source_local_machine"),
    "local_machine_32": K("source_local_machine_32"),
    "user_startup_folder": K("source_user_startup"),
    "all_users_startup_folder": K("source_all_users_startup"),
}


class StartupPage(BasePage):
    title_key = K("page_startup")
    subtitle_key = K("subtitle_startup")

    def __init__(self, ctx) -> None:
        super().__init__(ctx)
        self.root.addWidget(muted_label(self.t("startup_info")))

        toolbar = QHBoxLayout()
        self.disable_button = QPushButton(self.t("startup_disable"))
        self.disable_button.setObjectName("DangerButton")
        self.enable_button = QPushButton(self.t("startup_enable"))
        self.disable_button.clicked.connect(lambda: self._toggle(False))
        self.enable_button.clicked.connect(lambda: self._toggle(True))
        self.count_label = muted_label("", wrap=False)
        toolbar.addWidget(self.count_label, 1)
        toolbar.addWidget(self.enable_button)
        toolbar.addWidget(self.disable_button)
        self.root.addLayout(toolbar)

        self.table = make_table(
            [self.t("startup_status"), self.t("startup_name"), self.t("startup_command"), self.t("startup_source")],
            stretch=(2,),
        )
        self.table.itemSelectionChanged.connect(self._update_buttons)
        self.root.addWidget(self.table, 1)
        self._entries: list[StartupEntry] = []
        self._update_buttons()

    def refresh(self) -> None:
        if os.name != "nt":
            self.count_label.setText(self.t("windows_only_body"))
            return
        self._entries = list_startup_entries()
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self._entries))
        for row, entry in enumerate(self._entries):
            status = SortItem(self.t("state_enabled") if entry.enabled else self.t("state_disabled"))
            status.setData(256, row)  # Qt.UserRole: _entries içindeki sıra
            status.setForeground(self.palette().text() if entry.enabled else self.palette().mid())
            self.table.setItem(row, 0, status)
            self.table.setItem(row, 1, SortItem(entry.name))
            self.table.setItem(row, 2, SortItem(entry.command))
            self.table.setItem(row, 3, SortItem(self.t(SOURCE_KEYS.get(entry.source, entry.source))))
        self.table.setSortingEnabled(True)
        enabled = sum(e.enabled for e in self._entries)
        self.count_label.setText(self.t("startup_count", total=len(self._entries), enabled=enabled))
        self._update_buttons()

    def _selected(self) -> StartupEntry | None:
        row = self.table.currentRow()
        if row < 0 or not self.table.item(row, 0):
            return None
        index = self.table.item(row, 0).data(256)
        return self._entries[index] if index is not None and index < len(self._entries) else None

    def _update_buttons(self) -> None:
        entry = self._selected()
        self.disable_button.setEnabled(bool(entry and entry.enabled))
        self.enable_button.setEnabled(bool(entry and not entry.enabled))

    def _toggle(self, enable: bool) -> None:
        entry = self._selected()
        if not entry or entry.enabled == enable:
            return
        action = self.t("startup_enable") if enable else self.t("startup_disable")
        text = self.t("startup_confirm", action=action, name=entry.name)
        if self.ctx.dry_run:
            text += "\n\n" + self.t("dry_run_notice")
        plan = self._plan(entry, enable)
        if not ask_confirmation(self, self.ctx, self.t("confirm_title"), text, entry.command):
            self.ctx.engine.record_cancelled(plan)
            return
        result = self.ctx.engine.run(plan, dry_run=self.ctx.dry_run)
        show_operation_result(self, self.ctx, result)
        self.refresh()

    def _plan(self, entry: StartupEntry, enable: bool) -> OperationPlan:
        backups = self.ctx.backups

        def backup() -> str | None:
            # StartupApproved anahtarı yoksa yedeklenecek bir şey yoktur; önceki değer ayrıntılara yazılır.
            if not registry.key_exists(entry.approved_hive, entry.approved_subkey):
                return None
            record = backups.create_registry_backup(entry.approved_hive, entry.approved_subkey,
                                                    f"startup: {entry.name}")
            return record.backup_id

        def execute() -> ExecutionOutcome:
            previous = set_enabled(entry, enable)
            return ExecutionOutcome(1, 0, {
                "name": entry.name,
                "key": registry.full_key_name(entry.approved_hive, entry.approved_subkey),
                "value": entry.approved_value,
                "previous": previous.hex() if previous else None,
                "enabled": enable,
            })

        return OperationPlan(
            kind="startup.enable" if enable else "startup.disable",
            summary=entry.name,
            targets=[entry.name],
            execute=execute,
            backup=backup,
            requires_admin=entry.approved_hive == "HKLM",
        )
