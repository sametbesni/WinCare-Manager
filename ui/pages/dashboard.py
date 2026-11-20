from __future__ import annotations

from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel

from app.i18n import K
from core.diagnostics import health_checks, overall_level
from core.disks import list_partitions
from core.system_info import format_bytes, format_uptime, get_system_snapshot
from ui.pages.base import BasePage
from ui.widgets import Card, GaugeWidget, InfoRow, muted_label, section_label

LEVEL_OBJECTS = {"ok": "OkText", "warning": "WarningText", "critical": "CriticalText"}
LEVEL_KEYS = {"ok": K("health_level_ok"), "warning": K("health_level_warning"), "critical": K("health_level_critical")}


class DashboardPage(BasePage):
    title_key = K("page_dashboard")
    subtitle_key = K("subtitle_dashboard")
    auto_refresh = True

    def __init__(self, ctx) -> None:
        super().__init__(ctx)

        gauges = QHBoxLayout()
        gauges.setSpacing(12)
        self.cpu_gauge = GaugeWidget(self.t("cpu"))
        self.memory_gauge = GaugeWidget(self.t("memory"))
        self.disk_gauge = GaugeWidget(self.t("disk"))
        for gauge in (self.cpu_gauge, self.memory_gauge, self.disk_gauge):
            card = Card()
            card.layout_box.addWidget(gauge)
            gauges.addWidget(card, 1)

        side = Card()
        side.layout_box.addWidget(section_label(self.t("health_title")))
        self.health_badge = QLabel("—")
        self.health_badge.setObjectName("MetricValue")
        side.layout_box.addWidget(self.health_badge)
        self.health_list = muted_label("")
        side.layout_box.addWidget(self.health_list)
        side.layout_box.addStretch(1)
        side.layout_box.addWidget(muted_label(self.t("uptime")))
        self.uptime_value = QLabel("—")
        self.uptime_value.setObjectName("SmallValue")
        side.layout_box.addWidget(self.uptime_value)
        gauges.addWidget(side, 1)
        self.root.addLayout(gauges)

        info_card = Card()
        info_card.layout_box.addWidget(section_label(self.t("system_information")))
        grid = QGridLayout()
        grid.setHorizontalSpacing(28)
        grid.setVerticalSpacing(12)
        self.rows = {
            "hostname": InfoRow(self.t("computer_name"), "—"),
            "os": InfoRow(self.t("operating_system"), "—"),
            "arch": InfoRow(self.t("architecture"), "—"),
            "cores": InfoRow(self.t("cpu_cores"), "—"),
            "processor": InfoRow(self.t("processor"), "—"),
            "memory": InfoRow(self.t("memory_total"), "—"),
        }
        for index, row in enumerate(self.rows.values()):
            grid.addWidget(row, index // 2, index % 2)
        info_card.layout_box.addLayout(grid)
        self.root.addWidget(info_card)

        note = Card()
        note.layout_box.addWidget(section_label(self.t("quick_overview")))
        note.layout_box.addWidget(muted_label(self.t("quick_overview_body")))
        self.root.addWidget(note)
        self.root.addStretch(1)

    def refresh(self) -> None:
        snap = get_system_snapshot()
        partitions = list_partitions()
        self.cpu_gauge.set_value(snap.cpu_percent, self.t("cores_caption", count=snap.logical_cores))
        self.memory_gauge.set_value(snap.memory_percent, f"{format_bytes(snap.memory_used)} / {format_bytes(snap.memory_total)}")
        self.disk_gauge.set_value(snap.disk_percent, f"{format_bytes(snap.disk_used)} / {format_bytes(snap.disk_total)}")
        self.uptime_value.setText(format_uptime(snap.uptime_seconds, self.ctx.translator.language))

        checks = health_checks(snap, partitions)
        level = overall_level(checks)
        self.health_badge.setText(self.t(LEVEL_KEYS[level]))
        self.health_badge.setObjectName(LEVEL_OBJECTS[level])
        self.health_badge.setStyleSheet("font-size: 20pt; font-weight: 700;")
        self.health_badge.style().unpolish(self.health_badge)
        self.health_badge.style().polish(self.health_badge)
        self.health_list.setText("\n".join("• " + self.t(c.key, **c.params) for c in checks))

        self.rows["hostname"].value_label.setText(snap.hostname)
        self.rows["os"].value_label.setText(snap.os_name)
        self.rows["arch"].value_label.setText(snap.architecture)
        self.rows["cores"].value_label.setText(self.t("cores_value", physical=snap.physical_cores, logical=snap.logical_cores))
        self.rows["processor"].value_label.setText(snap.processor or self.t("unknown"))
        self.rows["memory"].value_label.setText(format_bytes(snap.memory_total))

    def on_show(self) -> None:
        self.refresh()
