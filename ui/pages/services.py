from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLineEdit

from app.i18n import K
from core.services import ServiceEntry, list_services
from ui.pages.base import BasePage
from ui.widgets import SortItem, make_table, muted_label
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
        bar.addWidget(self.search, 2)
        bar.addWidget(muted_label(self.t("services_read_only")), 3)
        bar.addWidget(self.count_label)
        self.root.addLayout(bar)
        self.table = make_table([self.t("service_display_name"), self.t("service_name"), self.t("service_status"),
                                 self.t("service_start_type"), self.t("path_column")], stretch=(4,))
        self.root.addWidget(self.table, 1)

    def refresh(self) -> None:
        if self._busy:
            return
        self._busy = True
        self.count_label.setText(self.t("loading"))
        run_async(list_services, self._fill, lambda _e: setattr(self, "_busy", False))

    def _fill(self, services: list[ServiceEntry]) -> None:
        self._busy = False
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(services))
        for row, s in enumerate(services):
            self.table.setItem(row, 0, SortItem(s.display_name))
            self.table.setItem(row, 1, SortItem(s.name))
            self.table.setItem(row, 2, SortItem(self.t(STATUS_KEYS[s.status]) if s.status in STATUS_KEYS else s.status))
            self.table.setItem(row, 3, SortItem(self.t(START_KEYS[s.start_type]) if s.start_type in START_KEYS else s.start_type))
            self.table.setItem(row, 4, SortItem(s.binpath))
        self.table.setSortingEnabled(True)
        self._apply_filter()

    def _apply_filter(self) -> None:
        needle = self.search.text().strip().casefold()
        visible = 0
        for row in range(self.table.rowCount()):
            text = " ".join(self.table.item(row, c).text() for c in (0, 1)).casefold()
            hidden = bool(needle) and needle not in text
            self.table.setRowHidden(row, hidden)
            visible += int(not hidden)
        self.count_label.setText(self.t("count_label", count=visible))
