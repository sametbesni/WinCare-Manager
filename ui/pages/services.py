from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QHeaderView, QLineEdit, QPushButton

from app.i18n import K
from core import services
from core.engine import ExecutionOutcome, OperationPlan
from core.services import ServiceEntry, list_services
from ui.pages.base import BasePage
from ui.widgets import SortItem, ask_confirmation, make_table, muted_label, show_info, show_operation_result
from ui.worker import run_async

STATUS_KEYS = {
    "running": K("service_running"),
    "stopped": K("service_stopped"),
    "paused": K("service_paused"),
    "start_pending": K("service_pending"),
    "stop_pending": K("service_pending"),
    "continue_pending": K("service_pending"),
    "pause_pending": K("service_pending"),
}
START_KEYS = {
    "automatic": K("start_automatic"),
    "manual": K("start_manual"),
    "disabled": K("start_disabled"),
}


class ServicesPage(BasePage):
    title_key = K("page_services")
    subtitle_key = K("subtitle_services")

    def __init__(self, ctx) -> None:
        super().__init__(ctx)
        bar = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText(self.t("search_placeholder"))
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._apply_filter)
        self.count_label = muted_label("", wrap=False)
        self.start_button = QPushButton(self.t("service_start"))
        self.start_button.setObjectName("SecondaryButton")
        self.start_button.clicked.connect(lambda: self._control("start"))
        self.stop_button = QPushButton(self.t("service_stop"))
        self.stop_button.setObjectName("DangerButton")
        self.stop_button.clicked.connect(lambda: self._control("stop"))
        bar.addWidget(self.search, 2)
        bar.addWidget(self.count_label)
        bar.addStretch(1)
        bar.addWidget(self.start_button)
        bar.addWidget(self.stop_button)
        self.root.addLayout(bar)
        self.root.addWidget(muted_label(self.t("services_control_note")))
        self.table = make_table([self.t("service_display_name"), self.t("service_name"), self.t("service_status"),
                                 self.t("service_start_type"), self.t("path_column")], stretch=(4,))
        # Uzun görünen adlar diğer sütunları ekran dışına itmesin; kullanıcı genişliği ayarlayabilir.
        header = self.table.horizontalHeader()
        for column, width in ((0, 340), (1, 200)):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Interactive)
            self.table.setColumnWidth(column, width)
        self.table.itemSelectionChanged.connect(self._update_buttons)
        self.root.addWidget(self.table, 1)
        self._entries: dict[str, ServiceEntry] = {}
        self._update_buttons()

    # ------------------------------------------------------------------ liste

    def refresh(self) -> None:
        if self._busy:
            return
        self._busy = True
        self.count_label.setText(self.t("loading"))
        run_async(list_services, self._fill, lambda _e: setattr(self, "_busy", False))

    def _fill(self, entries: list[ServiceEntry]) -> None:
        self._busy = False
        selected = self._selected()
        self._entries = {s.name: s for s in entries}
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(entries))
        for row, s in enumerate(entries):
            name_item = SortItem(s.display_name)
            name_item.setData(Qt.ItemDataRole.UserRole, s.name)
            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, SortItem(s.name))
            self.table.setItem(row, 2, SortItem(self.t(STATUS_KEYS[s.status]) if s.status in STATUS_KEYS else s.status))
            self.table.setItem(row, 3, SortItem(self.t(START_KEYS[s.start_type]) if s.start_type in START_KEYS else s.start_type))
            self.table.setItem(row, 4, SortItem(s.binpath))
        self.table.setSortingEnabled(True)
        if selected:
            for row in range(self.table.rowCount()):
                if self.table.item(row, 0).data(Qt.ItemDataRole.UserRole) == selected.name:
                    self.table.selectRow(row)
                    break
        self._apply_filter()
        self._update_buttons()

    def _apply_filter(self) -> None:
        needle = self.search.text().strip().casefold()
        visible = 0
        for row in range(self.table.rowCount()):
            text = " ".join(self.table.item(row, c).text() for c in (0, 1)).casefold()
            hidden = bool(needle) and needle not in text
            self.table.setRowHidden(row, hidden)
            visible += int(not hidden)
        self.count_label.setText(self.t("count_label", count=visible))

    def _selected(self) -> ServiceEntry | None:
        rows = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        if not rows:
            return None
        name = self.table.item(rows[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        return self._entries.get(name)

    def _update_buttons(self) -> None:
        entry = self._selected()
        self.start_button.setEnabled(bool(entry) and not self._busy and entry.status == "stopped"
                                     and entry.start_type != "disabled")
        self.stop_button.setEnabled(bool(entry) and not self._busy and entry.status == "running"
                                    and not services.is_protected(entry.name))

    # ---------------------------------------------------------------- işlemler

    def _control(self, action: str) -> None:
        entry = self._selected()
        if entry is None or self._busy:
            show_info(self, self.t("warning_title"), self.t("service_select_first"))
            return

        def validate() -> list[str]:
            dependents = False
            if action == "stop" and not services.is_protected(entry.name):
                try:
                    dependents = services.has_active_dependents(entry.name)
                except OSError:
                    return [self.t("service_dependents_unknown", name=entry.display_name)]
            return [self.t(key, name=entry.display_name)
                    for key in services.control_problems(entry, action, dependents)]

        def execute() -> ExecutionOutcome:
            previous = services.control_service(entry.name, action)
            return ExecutionOutcome(1, details={"service": entry.name, "previous_status": previous,
                                                "action": action})

        plan = OperationPlan(
            kind=f"service.{action}",
            summary=f"{entry.display_name} ({entry.name})",
            targets=[entry.name],
            validate=validate,
            execute=execute,
            requires_admin=True,
        )
        question_key = K("service_confirm_start") if action == "start" else K("service_confirm_stop")
        question = self.t(question_key, name=entry.display_name)
        if not ask_confirmation(self, self.ctx, self.t("confirm_title"), question, entry.binpath):
            self.ctx.engine.record_cancelled(plan)
            return
        self._busy = True
        self._update_buttons()
        self.count_label.setText(self.t("service_working", name=entry.display_name))
        dry_run = self.ctx.dry_run
        run_async(lambda: self.ctx.engine.run(plan, dry_run=dry_run), self._control_done,
                  self._control_failed)

    def _control_done(self, result) -> None:
        self._busy = False
        show_operation_result(self, self.ctx, result)
        self.refresh()

    def _control_failed(self, error: str) -> None:
        self._busy = False
        show_info(self, self.t("warning_title"), error, error=True)
        self.refresh()
