from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout, QWidget

from app.context import AppContext


class BasePage(QWidget):
    """Tüm sayfaların ortak temeli.

    title_key / subtitle_key : üst çubukta gösterilen başlık çeviri anahtarları
    auto_refresh             : True ise ayarlardaki aralıkla otomatik yenilenir
    """

    title_key = ""
    subtitle_key = ""
    auto_refresh = False

    def __init__(self, ctx: AppContext) -> None:
        super().__init__()
        self.ctx = ctx
        self.t = ctx.t
        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(0, 0, 0, 0)
        self.root.setSpacing(12)
        self._busy = False
        self._loaded_once = False

    def refresh(self) -> None:
        """Verileri yeniden yükle."""

    def on_show(self) -> None:
        """Sayfa açıldığında çağrılır; ilk açılışta verileri yükler."""
        if not self._loaded_once:
            self._loaded_once = True
            self.refresh()
