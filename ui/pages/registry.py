from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLineEdit, QPushButton, QSplitter

from PySide6.QtCore import Qt

from app.i18n import K
from core import registry
from core.engine import ExecutionOutcome, OperationPlan
from ui.pages.base import BasePage
from ui.widgets import SortItem, make_table, muted_label, show_info, show_operation_result

FAVORITES = [
    ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Run"),
    ("HKLM", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"),
    ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved"),
    ("HKLM", r"SOFTWARE\Microsoft\Windows NT\CurrentVersion"),
    ("HKLM", r"SYSTEM\CurrentControlSet\Services"),
]


class RegistryPage(BasePage):
    """Salt okunur kayıt defteri görüntüleyici + anahtar yedekleme."""

    title_key = K("page_registry")
    subtitle_key = K("subtitle_registry")

    def __init__(self, ctx) -> None:
        super().__init__(ctx)
        self.root.addWidget(muted_label(self.t("registry_info")))

        bar = QHBoxLayout()
        self.hive_combo = QComboBox()
        self.hive_combo.addItems(list(registry.HIVE_NAMES))
        self.path_edit = QLineEdit(FAVORITES[0][1])
        self.path_edit.setPlaceholderText(self.t("registry_path_placeholder"))
        self.path_edit.returnPressed.connect(self.refresh)
        up_button = QPushButton(self.t("registry_up"))
        up_button.setObjectName("SecondaryButton")
        up_button.clicked.connect(self._go_up)
        open_button = QPushButton(self.t("registry_open"))
        open_button.clicked.connect(self.refresh)
        self.backup_button = QPushButton(self.t("registry_backup_key"))
        self.backup_button.setObjectName("SecondaryButton")
        self.backup_button.clicked.connect(self._backup)
        bar.addWidget(self.hive_combo)
        bar.addWidget(self.path_edit, 1)
        bar.addWidget(up_button)
        bar.addWidget(open_button)
        bar.addWidget(self.backup_button)
        self.root.addLayout(bar)

        fav_bar = QHBoxLayout()
        fav_bar.addWidget(muted_label(self.t("registry_favorites"), wrap=False))
        self.fav_combo = QComboBox()
        self.fav_combo.addItem("—", None)
        for hive, path in FAVORITES:
            self.fav_combo.addItem(f"{hive}\\{path}", (hive, path))
        self.fav_combo.activated.connect(self._open_favorite)
        fav_bar.addWidget(self.fav_combo, 1)
        self.root.addLayout(fav_bar)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.subkeys = make_table([self.t("registry_subkeys")], stretch=(0,))
        self.subkeys.itemDoubleClicked.connect(self._enter_subkey)
        self.values = make_table([self.t("registry_value_name"), self.t("registry_value_type"),
                                  self.t("registry_value_data")], stretch=(2,))
        splitter.addWidget(self.subkeys)
        splitter.addWidget(self.values)
        splitter.setSizes([280, 720])
        self.root.addWidget(splitter, 1)
        self.status = muted_label("", wrap=False)
        self.root.addWidget(self.status)

    def _current(self) -> tuple[str, str]:
        return self.hive_combo.currentText(), registry.normalize_path(self.path_edit.text())

    def refresh(self) -> None:
        hive, path = self._current()
        try:
            subkeys, values = registry.read_key(hive, path)
        except OSError as exc:
            self.subkeys.setRowCount(0)
            self.values.setRowCount(0)
            self.status.setText(self.t("registry_open_failed", error=str(exc)))
            return
        self.subkeys.setSortingEnabled(False)
        self.subkeys.setRowCount(len(subkeys))
        for row, name in enumerate(subkeys):
            self.subkeys.setItem(row, 0, SortItem(name))
        self.subkeys.setSortingEnabled(True)
        self.values.setSortingEnabled(False)
        self.values.setRowCount(len(values))
        for row, value in enumerate(values):
            self.values.setItem(row, 0, SortItem(value.name))
            self.values.setItem(row, 1, SortItem(value.type_name))
            self.values.setItem(row, 2, SortItem(value.data))
        self.values.setSortingEnabled(True)
        self.status.setText(self.t("registry_status", key=registry.full_key_name(hive, path),
                                   subkeys=len(subkeys), values=len(values)))

    def _enter_subkey(self, item) -> None:
        hive, path = self._current()
        name = self.subkeys.item(item.row(), 0).text()
        self.path_edit.setText(f"{path}\\{name}" if path else name)
        self.refresh()

    def _go_up(self) -> None:
        _hive, path = self._current()
        self.path_edit.setText(path.rsplit("\\", 1)[0] if "\\" in path else "")
        self.refresh()

    def _open_favorite(self) -> None:
        data = self.fav_combo.currentData()
        if not data:
            return
        hive, path = data
        self.hive_combo.setCurrentText(hive)
        self.path_edit.setText(path)
        self.refresh()

    def _backup(self) -> None:
        hive, path = self._current()
        if not path:
            show_info(self, self.t("warning_title"), self.t("registry_backup_need_path"))
            return
        key = registry.full_key_name(hive, path)
        holder: dict[str, str] = {}

        def execute() -> ExecutionOutcome:
            record = self.ctx.backups.create_registry_backup(hive, path, self.t("registry_manual_backup"))
            holder["id"] = record.backup_id
            return ExecutionOutcome(1, 0, {"key": key, "backup_id": record.backup_id, "size": record.size})

        plan = OperationPlan(kind="backup.create", summary=key, targets=[key], execute=execute,
                             respects_dry_run=False)
        result = self.ctx.engine.run(plan, dry_run=False)
        if holder.get("id"):
            result.backup_id = holder["id"]
        show_operation_result(self, self.ctx, result)
