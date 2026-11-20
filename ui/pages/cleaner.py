from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QTableWidgetItem, QVBoxLayout

from app.i18n import K
from core.cleaner import ScanResult, default_scan_roots, scan_temporary_files, validate_targets
from core.engine import ExecutionOutcome, OperationPlan
from core.recycle import send_to_recycle_bin
from core.system_info import format_bytes
from ui.pages.base import BasePage
from ui.widgets import Card, SortItem, ask_confirmation, make_table, muted_label, section_label, show_operation_result
from ui.worker import run_async

CATEGORY_KEYS = {"temp": K("category_temp"), "crash_dumps": K("category_crash_dumps"), "wer": K("category_wer")}


class CleanerPage(BasePage):
    title_key = K("page_cleaner")
    subtitle_key = K("subtitle_cleaner")

    def __init__(self, ctx) -> None:
        super().__init__(ctx)
        self.last_result: ScanResult | None = None

        info = Card()
        info.layout_box.addWidget(section_label(self.t("cleaner_info")))
        hours = int(ctx.config.get("temp_min_age_hours", 24))
        info.layout_box.addWidget(muted_label(self.t("cleaner_info_body", hours=hours)))
        self.root.addWidget(info)

        summary = QHBoxLayout()
        self.files_value = self._summary_card(summary, self.t("scan_files"))
        self.size_value = self._summary_card(summary, self.t("scan_size"))
        self.selected_value = self._summary_card(summary, self.t("scan_selected"))
        self.skipped_value = self._summary_card(summary, self.t("scan_skipped"))
        self.root.addLayout(summary)

        toolbar = QHBoxLayout()
        self.status_label = muted_label("", wrap=False)
        self.scan_button = QPushButton(self.t("scan_now"))
        self.scan_button.setObjectName("SecondaryButton")
        self.scan_button.clicked.connect(self.refresh)
        self.select_all_button = QPushButton(self.t("select_all"))
        self.select_all_button.setObjectName("SecondaryButton")
        self.select_all_button.clicked.connect(lambda: self._set_all(True))
        self.select_none_button = QPushButton(self.t("select_none"))
        self.select_none_button.setObjectName("SecondaryButton")
        self.select_none_button.clicked.connect(lambda: self._set_all(False))
        self.clean_button = QPushButton(self.t("clean_selected"))
        self.clean_button.setObjectName("DangerButton")
        self.clean_button.clicked.connect(self._clean)
        toolbar.addWidget(self.status_label, 1)
        for button in (self.scan_button, self.select_all_button, self.select_none_button, self.clean_button):
            toolbar.addWidget(button)
        self.root.addLayout(toolbar)

        self.table = make_table([self.t("file_path"), self.t("category_column"), self.t("file_size"),
                                 self.t("modified_column")], stretch=(0,))
        self.table.itemChanged.connect(self._update_selection)
        self.root.addWidget(self.table, 1)
        self._set_buttons(False)

    @staticmethod
    def _summary_card(layout: QHBoxLayout, title: str) -> QLabel:
        frame = QFrame()
        frame.setObjectName("Card")
        box = QVBoxLayout(frame)
        box.setContentsMargins(15, 12, 15, 12)
        caption = QLabel(title)
        caption.setObjectName("MetricCaption")
        value = QLabel("—")
        value.setObjectName("MetricValueSmall")
        box.addWidget(caption)
        box.addWidget(value)
        layout.addWidget(frame, 1)
        return value

    def _set_buttons(self, has_rows: bool) -> None:
        self.select_all_button.setEnabled(has_rows)
        self.select_none_button.setEnabled(has_rows)
        self.clean_button.setEnabled(has_rows and bool(self._checked_paths()))

    def refresh(self) -> None:
        if self._busy:
            return
        self._busy = True
        self.scan_button.setEnabled(False)
        self.clean_button.setEnabled(False)
        self.status_label.setText(self.t("loading"))
        seconds = int(self.ctx.config.get("temp_min_age_hours", 24)) * 3600
        run_async(lambda: scan_temporary_files(older_than_seconds=seconds), self._show, self._failed)

    def _failed(self, _error: str) -> None:
        self._busy = False
        self.scan_button.setEnabled(True)
        self.last_result = None
        self.table.setRowCount(0)
        self.status_label.setText(self.t("scan_failed"))
        self._set_buttons(False)

    def _show(self, result: ScanResult) -> None:
        self._busy = False
        self.scan_button.setEnabled(True)
        self.last_result = result
        self.table.blockSignals(True)
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(result.files))
        for row, c in enumerate(result.files):
            path_item = QTableWidgetItem(c.path)
            path_item.setFlags(path_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            path_item.setCheckState(Qt.CheckState.Checked)
            self.table.setItem(row, 0, path_item)
            self.table.setItem(row, 1, SortItem(self.t(CATEGORY_KEYS.get(c.category, c.category))))
            self.table.setItem(row, 2, SortItem(format_bytes(c.size), c.size, align_right=True))
            modified = datetime.fromtimestamp(c.modified_timestamp)
            self.table.setItem(row, 3, SortItem(modified.strftime("%Y-%m-%d %H:%M"), c.modified_timestamp))
        self.table.setSortingEnabled(True)
        self.table.blockSignals(False)

        self.files_value.setText(str(len(result.files)))
        self.size_value.setText(format_bytes(result.total_bytes))
        self.skipped_value.setText(str(result.skipped))
        stamp = datetime.now().strftime("%H:%M:%S")
        self.status_label.setText(
            (self.t("scan_complete") + " · " + stamp) if result.files else self.t("scan_empty"))
        self._update_selection()

    def _rows_checked(self) -> list[int]:
        return [r for r in range(self.table.rowCount())
                if self.table.item(r, 0) and self.table.item(r, 0).checkState() == Qt.CheckState.Checked]

    def _checked_paths(self) -> list[str]:
        return [self.table.item(r, 0).text() for r in self._rows_checked()]

    def _set_all(self, checked: bool) -> None:
        self.table.blockSignals(True)
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for row in range(self.table.rowCount()):
            self.table.item(row, 0).setCheckState(state)
        self.table.blockSignals(False)
        self._update_selection()

    def _update_selection(self, *_args) -> None:
        rows = self._rows_checked()
        size = sum(self.table.item(r, 2).sort_value for r in rows)  # type: ignore[attr-defined]
        self.selected_value.setText(f"{len(rows)} · {format_bytes(size)}")
        self._set_buttons(self.table.rowCount() > 0)

    def _clean(self) -> None:
        paths = self._checked_paths()
        if not paths:
            return
        size = sum(self.table.item(r, 2).sort_value for r in self._rows_checked())  # type: ignore[attr-defined]
        roots = default_scan_roots()

        def validate() -> list[str]:
            return list(validate_targets(paths, roots).violations)

        def execute() -> ExecutionOutcome:
            report = validate_targets(paths, roots)
            moved, failed = send_to_recycle_bin(list(report.valid))
            return ExecutionOutcome(len(moved), len(failed), {
                "moved_bytes_estimate": size,
                "missing": len(report.missing),
                "failed_files": failed[:100],
            })

        plan = OperationPlan(
            kind="cleaner.recycle",
            summary=self.t("cleaner_summary", count=len(paths), size=format_bytes(size)),
            targets=paths,
            execute=execute,
            validate=validate,
        )
        text = self.t("cleaner_confirm", count=len(paths), size=format_bytes(size))
        if self.ctx.dry_run:
            text += "\n\n" + self.t("dry_run_notice")
        if not ask_confirmation(self, self.ctx, self.t("confirm_title"), text, "\n".join(paths[:200])):
            self.ctx.engine.record_cancelled(plan)
            return

        self.clean_button.setEnabled(False)
        self.scan_button.setEnabled(False)
        self.status_label.setText(self.t("cleaning"))
        dry = self.ctx.dry_run
        run_async(lambda: self.ctx.engine.run(plan, dry_run=dry), self._cleaned, self._failed)

    def _cleaned(self, result) -> None:
        show_operation_result(self, self.ctx, result)
        if result.status == "dry_run":
            self.scan_button.setEnabled(True)
            self._update_selection()
            self.status_label.setText(self.t("op_dry_run", succeeded=0, failed=0))
        else:
            self.refresh()
