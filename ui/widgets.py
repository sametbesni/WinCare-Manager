from __future__ import annotations

from typing import Iterable

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractItemView, QFrame, QHBoxLayout, QHeaderView, QLabel, QMessageBox,
    QProgressBar, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from app.context import AppContext
from core.engine import OperationResult


class Card(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self.layout_box = QVBoxLayout(self)
        self.layout_box.setContentsMargins(18, 16, 18, 16)
        self.layout_box.setSpacing(10)


def section_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("SectionTitle")
    return label


def muted_label(text: str, wrap: bool = True) -> QLabel:
    label = QLabel(text)
    label.setObjectName("Muted")
    label.setWordWrap(wrap)
    return label


class MetricCard(Card):
    def __init__(self, title: str, value: str = "—", detail: str = "") -> None:
        super().__init__()
        self.title_label = QLabel(title)
        self.title_label.setObjectName("MetricCaption")
        self.value_label = QLabel(value)
        self.value_label.setObjectName("MetricValue")
        self.detail_label = muted_label(detail)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setTextVisible(False)
        self.layout_box.addWidget(self.title_label)
        self.layout_box.addWidget(self.value_label)
        self.layout_box.addWidget(self.progress)
        self.layout_box.addWidget(self.detail_label)
        self.layout_box.addStretch(1)


class InfoRow(QWidget):
    def __init__(self, label: str, value: str) -> None:
        super().__init__()
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        left = muted_label(label, wrap=False)
        right = QLabel(value)
        right.setObjectName("SmallValue")
        right.setWordWrap(True)
        right.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        right.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        row.addWidget(left, 1)
        row.addWidget(right, 2)
        self.value_label = right


def level_color(percent: float) -> QColor:
    if percent >= 90:
        return QColor("#f26d6d")
    if percent >= 75:
        return QColor("#f3b54a")
    return QColor("#4d9af2")


class GaugeWidget(QWidget):
    """Yay şeklinde yüzde göstergesi."""

    def __init__(self, title: str) -> None:
        super().__init__()
        self.title = title
        self.value = 0.0
        self.caption = ""
        self.setMinimumSize(170, 170)

    def set_value(self, value: float, caption: str = "", title: str | None = None) -> None:
        self.value = max(0.0, min(100.0, float(value)))
        self.caption = caption
        if title is not None:
            self.title = title
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802 (Qt API)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        side = min(self.width(), self.height()) - 16
        rect = QRectF((self.width() - side) / 2, (self.height() - side) / 2 + 4, side, side)
        thickness = max(8.0, side / 13)

        pen = QPen(QColor("#26364d"), thickness, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawArc(rect, 225 * 16, -270 * 16)

        pen.setColor(level_color(self.value))
        painter.setPen(pen)
        painter.drawArc(rect, 225 * 16, int(-270 * 16 * self.value / 100))

        painter.setPen(QColor("#ffffff"))
        font = QFont(self.font())
        font.setPointSizeF(max(12.0, side / 7.5))
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(rect.adjusted(0, -side * 0.08, 0, 0), Qt.AlignmentFlag.AlignCenter, f"{self.value:.0f}%")

        font.setBold(False)
        font.setPointSizeF(max(8.0, side / 17))
        painter.setFont(font)
        painter.setPen(QColor("#95a6bf"))
        painter.drawText(rect.adjusted(0, side * 0.16, 0, 0), Qt.AlignmentFlag.AlignCenter, self.title)
        if self.caption:
            painter.drawText(rect.adjusted(0, side * 0.72, 0, 0), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                             self.caption)
        painter.end()


class SortItem(QTableWidgetItem):
    """Sayısal değerleri sayı olarak sıralayan tablo hücresi (metin olarak değil)."""

    def __init__(self, text: str, sort_value: float | int | str | None = None, align_right: bool = False) -> None:
        super().__init__(text)
        self.sort_value = sort_value if sort_value is not None else text.casefold()
        if align_right:
            self.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

    def __lt__(self, other: QTableWidgetItem) -> bool:
        other_value = getattr(other, "sort_value", other.text().casefold())
        try:
            return self.sort_value < other_value  # type: ignore[operator]
        except TypeError:
            return str(self.sort_value) < str(other_value)


def make_table(headers: Iterable[str], stretch: Iterable[int] = (), sortable: bool = True) -> QTableWidget:
    headers = list(headers)
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setAlternatingRowColors(True)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.verticalHeader().setVisible(False)
    table.setSortingEnabled(sortable)
    table.setWordWrap(False)
    header = table.horizontalHeader()
    header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    for column in stretch:
        header.setSectionResizeMode(column, QHeaderView.ResizeMode.Stretch)
    return table


def ask_confirmation(parent: QWidget, ctx: AppContext, title: str, text: str, details: str = "") -> bool:
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Warning)
    box.setWindowTitle(title)
    box.setText(text)
    if details:
        box.setDetailedText(details)
    yes = box.addButton(ctx.t("button_yes"), QMessageBox.ButtonRole.YesRole)
    no = box.addButton(ctx.t("button_no"), QMessageBox.ButtonRole.NoRole)
    box.setDefaultButton(no)
    box.exec()
    return box.clickedButton() is yes


def show_info(parent: QWidget, title: str, text: str, error: bool = False) -> None:
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Critical if error else QMessageBox.Icon.Information)
    box.setWindowTitle(title)
    box.setText(text)
    box.exec()


def show_operation_result(parent: QWidget, ctx: AppContext, result: OperationResult) -> None:
    lines = [ctx.t(result.message_key, succeeded=result.succeeded, failed=result.failed)]
    problems = result.details.get("problems")
    if problems:
        lines.append("")
        lines.extend(str(p) for p in problems[:10])
    if result.details.get("error"):
        lines.append(str(result.details["error"]))
    if result.backup_id:
        lines.append(ctx.t("op_backup_created", backup_id=result.backup_id))
    lines.append("")
    lines.append(ctx.t("op_id", operation_id=result.operation_id[:8]))
    show_info(parent, ctx.t("op_result_title"), "\n".join(lines),
              error=result.status in {"failed", "blocked"})
