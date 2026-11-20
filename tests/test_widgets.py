"""Tablo bileşeni: sütunlar yalnızca ilk doldurmada boyutlanır (donma hatasına karşı)."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

QtWidgets = pytest.importorskip("PySide6.QtWidgets")
from PySide6.QtWidgets import QApplication, QHeaderView  # noqa: E402

from ui.widgets import SortItem, make_table  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _fill(table, rows: int, text: str) -> None:
    table.setSortingEnabled(False)
    table.setRowCount(rows)
    for row in range(rows):
        table.setItem(row, 0, SortItem(text))
        table.setItem(row, 1, SortItem(str(row), row))
    table.setSortingEnabled(True)


def test_columns_are_not_resized_on_every_change(app) -> None:
    table = make_table(["a", "b", "path"], stretch=(2,))
    header = table.horizontalHeader()
    # "İçeriğe göre boyutla" modu kullanılmamalı: her hücre değişiminde tüm satırları ölçer.
    assert header.sectionResizeMode(0) == QHeaderView.ResizeMode.Interactive
    assert header.sectionResizeMode(2) == QHeaderView.ResizeMode.Stretch


def test_columns_fit_once_and_keep_user_width(app) -> None:
    table = make_table(["a", "b", "path"], stretch=(2,))
    _fill(table, 0, "")
    assert not table._sized  # boş tablo boyutlanmaz
    _fill(table, 5, "kısa")
    assert table._sized
    table.setColumnWidth(0, 123)  # kullanıcı genişliği değiştirdi
    _fill(table, 5, "çok daha uzun bir metin " * 5)
    assert table.columnWidth(0) == 123


def test_fitted_width_is_capped(app) -> None:
    table = make_table(["a", "b"])
    _fill(table, 3, "x" * 500)
    assert table.columnWidth(0) <= table.MAX_COLUMN_WIDTH
