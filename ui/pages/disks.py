from __future__ import annotations

from PySide6.QtWidgets import QProgressBar

from app.i18n import K
from core.disks import PhysicalDisk, list_partitions, list_physical_disks
from core.system_info import format_bytes
from ui.pages.base import BasePage
from ui.widgets import Card, SortItem, make_table, muted_label, section_label
from ui.worker import run_async

HEALTH_KEYS = {"Healthy": K("disk_health_healthy"), "Warning": K("disk_health_warning"),
               "Unhealthy": K("disk_health_unhealthy")}


class DisksPage(BasePage):
    title_key = K("page_disks")
    subtitle_key = K("subtitle_disks")

    def __init__(self, ctx) -> None:
        super().__init__(ctx)
        volumes = Card()
        volumes.layout_box.addWidget(section_label(self.t("disk_volumes")))
        self.volume_table = make_table([self.t("disk_drive"), self.t("disk_fs"), self.t("disk_total"),
                                        self.t("disk_used"), self.t("disk_free"), self.t("disk_usage")],
                                       stretch=(5,))
        volumes.layout_box.addWidget(self.volume_table)
        self.root.addWidget(volumes, 1)

        physical = Card()
        physical.layout_box.addWidget(section_label(self.t("disk_physical")))
        physical.layout_box.addWidget(muted_label(self.t("disk_physical_info")))
        self.physical_table = make_table([self.t("disk_model"), self.t("disk_media"), self.t("disk_bus"),
                                          self.t("disk_total"), self.t("disk_health"), self.t("disk_operational")],
                                         stretch=(0,))
        physical.layout_box.addWidget(self.physical_table)
        self.physical_status = muted_label("", wrap=False)
        physical.layout_box.addWidget(self.physical_status)
        self.root.addWidget(physical, 1)

    def refresh(self) -> None:
        parts = list_partitions()
        self.volume_table.setSortingEnabled(False)
        self.volume_table.setRowCount(len(parts))
        for row, p in enumerate(parts):
            self.volume_table.setItem(row, 0, SortItem(p.mountpoint))
            self.volume_table.setItem(row, 1, SortItem(p.fstype))
            self.volume_table.setItem(row, 2, SortItem(format_bytes(p.total), p.total, align_right=True))
            self.volume_table.setItem(row, 3, SortItem(format_bytes(p.used), p.used, align_right=True))
            self.volume_table.setItem(row, 4, SortItem(format_bytes(p.free), p.free, align_right=True))
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(int(p.percent))
            bar.setFormat(f"{p.percent:.0f}%")
            bar.setTextVisible(True)
            if p.percent >= 90:
                bar.setObjectName("DangerBar")
            self.volume_table.setItem(row, 5, SortItem("", p.percent))
            self.volume_table.setCellWidget(row, 5, bar)
        self.volume_table.setSortingEnabled(True)

        if self._busy:
            return
        self._busy = True
        self.physical_status.setText(self.t("loading"))
        run_async(list_physical_disks, self._fill_physical, lambda _e: self._fill_physical([]))

    def _fill_physical(self, disks: list[PhysicalDisk]) -> None:
        self._busy = False
        self.physical_table.setSortingEnabled(False)
        self.physical_table.setRowCount(len(disks))
        for row, d in enumerate(disks):
            self.physical_table.setItem(row, 0, SortItem(d.name))
            self.physical_table.setItem(row, 1, SortItem(d.media_type))
            self.physical_table.setItem(row, 2, SortItem(d.bus_type))
            self.physical_table.setItem(row, 3, SortItem(format_bytes(d.size), d.size, align_right=True))
            self.physical_table.setItem(row, 4, SortItem(self.t(HEALTH_KEYS[d.health]) if d.health in HEALTH_KEYS else d.health))
            self.physical_table.setItem(row, 5, SortItem(d.operational))
        self.physical_table.setSortingEnabled(True)
        self.physical_status.setText("" if disks else self.t("disk_physical_unavailable"))
