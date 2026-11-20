from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QPushButton

from app.i18n import K
from core.diagnostics import EventEntry, health_checks, recent_events
from core.disks import list_partitions
from core.system_info import get_system_snapshot
from ui.pages.base import BasePage
from ui.widgets import Card, SortItem, make_table, muted_label, section_label
from ui.worker import run_async

LEVEL_OBJECTS = {"ok": "OkText", "warning": "WarningText", "critical": "CriticalText"}
EVENT_LEVEL_KEYS = {1: K("event_critical"), 2: K("event_error"), 3: K("event_warning")}


class DiagnosticsPage(BasePage):
    title_key = K("page_diagnostics")
    subtitle_key = K("subtitle_diagnostics")

    def __init__(self, ctx) -> None:
        super().__init__(ctx)
        health = Card()
        health.layout_box.addWidget(section_label(self.t("health_title")))
        self.health_box = health.layout_box
        self.health_labels: list[QLabel] = []
        self.root.addWidget(health)

        events = Card()
        head = QHBoxLayout()
        head.addWidget(section_label(self.t("events_title")), 1)
        self.range_combo = QComboBox()
        for hours, key in ((24, K("range_24h")), (72, K("range_3d")), (168, K("range_7d"))):
            self.range_combo.addItem(self.t(key), hours)
        self.warnings_combo = QComboBox()
        self.warnings_combo.addItem(self.t("events_errors_only"), False)
        self.warnings_combo.addItem(self.t("events_with_warnings"), True)
        load = QPushButton(self.t("events_load"))
        load.clicked.connect(self._load_events)
        head.addWidget(self.range_combo)
        head.addWidget(self.warnings_combo)
        head.addWidget(load)
        events.layout_box.addLayout(head)
        self.events_status = muted_label("", wrap=False)
        events.layout_box.addWidget(self.events_status)
        self.table = make_table([self.t("event_time"), self.t("event_level"), self.t("event_log"),
                                 self.t("event_source"), self.t("event_id"), self.t("event_message")],
                                stretch=(5,))
        self.table.itemSelectionChanged.connect(self._show_message)
        events.layout_box.addWidget(self.table, 1)
        self.message = muted_label("")
        events.layout_box.addWidget(self.message)
        self.root.addWidget(events, 1)
        self._events: list[EventEntry] = []

    def refresh(self) -> None:
        for label in self.health_labels:
            label.deleteLater()
        self.health_labels = []
        checks = health_checks(get_system_snapshot(), list_partitions())
        for check in checks:
            label = QLabel("● " + self.t(check.key, **check.params))
            label.setObjectName(LEVEL_OBJECTS[check.level])
            label.setWordWrap(True)
            self.health_box.addWidget(label)
            self.health_labels.append(label)
        self._load_events()

    def _load_events(self) -> None:
        if self._busy:
            return
        self._busy = True
        hours = int(self.range_combo.currentData())
        warnings = bool(self.warnings_combo.currentData())
        self.events_status.setText(self.t("loading"))
        run_async(lambda: recent_events(hours, 300, warnings), self._fill, lambda _e: self._fill([]))

    def _fill(self, events: list[EventEntry]) -> None:
        self._busy = False
        self._events = events
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(events))
        for row, e in enumerate(events):
            time_item = SortItem(e.time)
            time_item.setData(256, row)
            self.table.setItem(row, 0, time_item)
            level_text = self.t(EVENT_LEVEL_KEYS[e.level]) if e.level in EVENT_LEVEL_KEYS else str(e.level)
            self.table.setItem(row, 1, SortItem(level_text, e.level))
            self.table.setItem(row, 2, SortItem(e.log))
            self.table.setItem(row, 3, SortItem(e.source))
            self.table.setItem(row, 4, SortItem(str(e.event_id), e.event_id, align_right=True))
            self.table.setItem(row, 5, SortItem(e.message))
        self.table.setSortingEnabled(True)
        self.events_status.setText(self.t("events_count", count=len(events)) if events else self.t("events_none"))
        self.message.setText("")

    def _show_message(self) -> None:
        row = self.table.currentRow()
        item = self.table.item(row, 0) if row >= 0 else None
        index = item.data(256) if item else None
        if index is not None and index < len(self._events):
            e = self._events[index]
            self.message.setText(f"{e.source} ({e.event_id}): {e.message}")
