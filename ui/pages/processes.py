from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLineEdit

from app.i18n import K
from core.processes import ProcessEntry, list_processes
from core.signatures import CACHE, SignatureInfo
from ui.pages.base import BasePage
from ui.widgets import SortItem, make_table, muted_label
from ui.worker import run_async

COL_NAME, COL_PID, COL_CPU, COL_MEM, COL_USER, COL_SIGN, COL_SIGNER, COL_PATH = range(8)
SIGN_KEYS = {
    "valid": K("sign_valid"),
    "unsigned": K("sign_unsigned"),
    "invalid": K("sign_invalid"),
    "untrusted": K("sign_untrusted"),
    "unknown": K("sign_unknown"),
}
# Sıralamada dikkat gerektirenler üstte toplansın.
SIGN_ORDER = {"invalid": 0, "untrusted": 1, "unsigned": 2, "unknown": 3, "valid": 4, "pending": 5}
ATTENTION_COLOR = QColor("#f3c77b")
CRITICAL_COLOR = QColor("#f28b8b")
SIGN_BATCH = 10


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
        self.search.setMinimumWidth(240)
        self.attention_only = QCheckBox(self.t("sign_filter_attention"))
        self.attention_only.toggled.connect(self._apply_filter)
        self.count_label = muted_label("", wrap=False)
        toolbar.addWidget(self.search, 2)
        toolbar.addWidget(self.attention_only)
        toolbar.addStretch(1)
        toolbar.addWidget(self.count_label)
        self.root.addLayout(toolbar)
        self.root.addWidget(muted_label(self.t("process_read_only") + " " + self.t("sign_note")))

        self.table = make_table(
            [self.t("process_name"), self.t("pid"), self.t("cpu_column"), self.t("memory_column"),
             self.t("user_column"), self.t("sign_column"), self.t("signer_column"), self.t("path_column")],
            stretch=(COL_PATH,),
        )
        self.table.sortByColumn(COL_MEM, Qt.SortOrder.DescendingOrder)
        self.root.addWidget(self.table, 1)
        self._entries: list[ProcessEntry] = []
        self._sign_busy = False
        self._signer_width_set = False

    # ------------------------------------------------------------------ liste

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
        if current >= 0 and self.table.item(current, COL_PID):
            selected_pid = self.table.item(current, COL_PID).text()
        scroll = self.table.verticalScrollBar().value()

        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(entries))
        for row, e in enumerate(entries):
            self.table.setItem(row, COL_NAME, SortItem(e.name))
            self.table.setItem(row, COL_PID, SortItem(str(e.pid), e.pid, align_right=True))
            self.table.setItem(row, COL_CPU, SortItem(f"{e.cpu_percent:.1f}", e.cpu_percent, align_right=True))
            self.table.setItem(row, COL_MEM, SortItem(f"{e.memory_mb:.1f}", e.memory_mb, align_right=True))
            self.table.setItem(row, COL_USER, SortItem(e.username))
            self.table.setItem(row, COL_PATH, SortItem(e.exe))
            self._set_signature(row, e.exe)
        self.table.setSortingEnabled(True)
        if not self._signer_width_set and self.table.rowCount():
            # Sütunlar imzalar henüz denetlenirken boyutlanır; yayıncı adlarına yer bırak.
            self._signer_width_set = True
            self.table.setColumnWidth(COL_SIGNER, max(self.table.columnWidth(COL_SIGNER), 220))

        if selected_pid:
            for row in range(self.table.rowCount()):
                if self.table.item(row, COL_PID).text() == selected_pid:
                    self.table.selectRow(row)
                    break
        self._apply_filter()
        self.table.verticalScrollBar().setValue(scroll)
        self._check_next_batch()

    # ------------------------------------------------------------------- imza

    def _set_signature(self, row: int, path: str) -> None:
        info = CACHE.get(path) if path else None
        if info is not None:
            state, signer = info.status, info.signer
            text = self.t(SIGN_KEYS[state])
        elif path and path[1:3] == ":\\":
            state, signer, text = "pending", "", self.t("sign_checking")
        else:
            state, signer, text = "unknown", "", "—"
        sign_item = SortItem(text, SIGN_ORDER.get(state, 9))
        sign_item.setData(Qt.ItemDataRole.UserRole, state)
        signer_item = SortItem(signer)
        if signer:
            signer_item.setToolTip(signer)
        if state in ("invalid", "untrusted"):
            sign_item.setForeground(CRITICAL_COLOR)
        elif state == "unsigned":
            sign_item.setForeground(ATTENTION_COLOR)
        if isinstance(info, SignatureInfo) and info.needs_attention:
            sign_item.setToolTip(self.t("sign_attention_tip"))
        self.table.setItem(row, COL_SIGN, sign_item)
        self.table.setItem(row, COL_SIGNER, signer_item)

    def _check_next_batch(self) -> None:
        if self._sign_busy:
            return
        batch = CACHE.missing([e.exe for e in self._entries])[:SIGN_BATCH]
        if not batch:
            return
        self._sign_busy = True
        run_async(lambda: CACHE.check_missing(batch), self._batch_done, self._batch_failed)

    def _batch_done(self, _count: int) -> None:
        self._sign_busy = False
        # Hücreleri tek tek güncellemek, sütun genişlikleri her seferinde yeniden
        # hesaplandığı için pencereyi saniyelerce donduruyordu. Tabloyu mevcut
        # verilerle tek seferde yeniden çizmek çok daha hızlıdır; _fill bir sonraki
        # grubu da başlatır.
        if self._entries and not self._busy:
            self._fill(self._entries)
        else:
            self._check_next_batch()

    def _batch_failed(self, _error: str) -> None:
        self._sign_busy = False

    # ---------------------------------------------------------------- filtre

    def _apply_filter(self) -> None:
        needle = self.search.text().strip().casefold()
        attention = self.attention_only.isChecked()
        visible = flagged = 0
        for row in range(self.table.rowCount()):
            name = self.table.item(row, COL_NAME)
            path = self.table.item(row, COL_PATH)
            sign = self.table.item(row, COL_SIGN)
            state = sign.data(Qt.ItemDataRole.UserRole) if sign else ""
            is_flagged = state in ("unsigned", "invalid", "untrusted")
            flagged += int(is_flagged)
            match = not needle or (name and needle in name.text().casefold()) or \
                (path and needle in path.text().casefold())
            if attention and not is_flagged:
                match = False
            self.table.setRowHidden(row, not match)
            visible += int(bool(match))
        self.count_label.setText(self.t("count_label", count=visible) + " · " +
                                 self.t("sign_flagged_count", count=flagged))
