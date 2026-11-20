from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLineEdit

from app.i18n import K
from core.processes import ProcessEntry, list_processes
from ui.pages.base import BasePage
from ui.widgets import SortItem, make_table, muted_label
from ui.worker import run_async


class ProcessesPage(BasePage):
    title_key = K("page_processes")
    subtitle_key = K("subtitle_processes")
    auto_refresh = True

    def __init__(self, ctx) -> None:
        super().__init__(ctx)
        toolbar = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText(self.t("search_placeholder"))
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._apply_filter)
        self.count_label = muted_label("", wrap=False)
        toolbar.addWidget(self.search, 2)
        toolbar.addWidget(muted_label(self.t("process_read_only")), 3)
        toolbar.addWidget(self.count_label)
        self.root.addLayout(toolbar)

        self.table = make_table(
            [self.t("process_name"), self.t("pid"), self.t("cpu_column"), self.t("memory_column"),
             self.t("user_column"), self.t("path_column")],
            stretch=(5,),
        )
        self.table.sortByColumn(3, Qt.SortOrder.DescendingOrder)
        self.root.addWidget(self.table, 1)
        self._entries: list[ProcessEntry] = []

    def refresh(self) -> None:
        if self._busy:
            return
        self._busy = True
        include_user = bool(self.ctx.config.get("show_process_username", True))
        run_async(lambda: list_processes(include_username=include_user), self._fill, self._failed)

    def _failed(self, _error: str) -> None:
        self._busy = False

    def _fill(self, entries: list[ProcessEntry]) -> None:
        self._busy = False
        self._entries = entries
        selected_pid = None
        current = self.table.currentRow()
        if current >= 0 and self.table.item(current, 1):
            selected_pid = self.table.item(current, 1).text()
        scroll = self.table.verticalScrollBar().value()

        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(entries))
        for row, e in enumerate(entries):
            self.table.setItem(row, 0, SortItem(e.name))
            self.table.setItem(row, 1, SortItem(str(e.pid), e.pid, align_right=True))
            self.table.setItem(row, 2, SortItem(f"{e.cpu_percent:.1f}", e.cpu_percent, align_right=True))
            self.table.setItem(row, 3, SortItem(f"{e.memory_mb:.1f}", e.memory_mb, align_right=True))
            self.table.setItem(row, 4, SortItem(e.username))
            self.table.setItem(row, 5, SortItem(e.exe))
        self.table.setSortingEnabled(True)

        if selected_pid:
            for row in range(self.table.rowCount()):
                if self.table.item(row, 1).text() == selected_pid:
                    self.table.selectRow(row)
                    break
        self._apply_filter()
        self.table.verticalScrollBar().setValue(scroll)

    def _apply_filter(self) -> None:
        needle = self.search.text().strip().casefold()
        visible = 0
        for row in range(self.table.rowCount()):
            name = self.table.item(row, 0)
            path = self.table.item(row, 5)
            match = not needle or (name and needle in name.text().casefold()) or (path and needle in path.text().casefold())
            self.table.setRowHidden(row, not match)
            visible += int(bool(match))
        self.count_label.setText(self.t("count_label", count=visible))
