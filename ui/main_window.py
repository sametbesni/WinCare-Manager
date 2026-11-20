from __future__ import annotations

import logging
from datetime import datetime

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QMainWindow, QPushButton, QScrollArea,
                               QStackedWidget, QStatusBar, QVBoxLayout, QWidget)

from app import __version__, admin
from app.context import AppContext
from app.i18n import K
from ui.pages.backup import BackupPage
from ui.pages.base import BasePage
from ui.pages.cleaner import CleanerPage
from ui.pages.dashboard import DashboardPage
from ui.pages.diagnostics import DiagnosticsPage
from ui.pages.disks import DisksPage
from ui.pages.history import HistoryPage
from ui.pages.maintenance import MaintenancePage
from ui.pages.processes import ProcessesPage
from ui.pages.registry import RegistryPage
from ui.pages.services import ServicesPage
from ui.pages.settings import SettingsPage
from ui.pages.startup import StartupPage

# (sayfa kimliği, isteğe bağlı simge, menü çeviri anahtarı) – planlanan Türkçe menü sırası
NAV_ITEMS = [
    ("dashboard", "", K("nav_dashboard")),
    ("cleaner", "", K("nav_cleaner")),
    ("startup", "", K("nav_startup")),
    ("processes", "", K("nav_processes")),
    ("registry", "", K("nav_registry")),
    ("services", "", K("nav_services")),
    ("disks", "", K("nav_disks")),
    ("backup", "", K("nav_backup")),
    ("diagnostics", "", K("nav_diagnostics")),
    ("maintenance", "", K("nav_maintenance")),
    ("history", "", K("nav_history")),
]


class MainWindow(QMainWindow):
    def __init__(self, ctx: AppContext, startup_message: str = "") -> None:
        super().__init__()
        self.ctx = ctx
        self.current_page = "dashboard"
        self.nav_buttons: dict[str, QPushButton] = {}
        self.pages: dict[str, BasePage] = {}

        self.setWindowTitle("WinCare Manager" + ("  [" + ctx.t("admin_badge") + "]" if admin.is_admin() else ""))
        self.setMinimumSize(1100, 700)
        self.resize(1320, 840)

        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._on_timer)
        self.refresh_timer.start(int(ctx.config.get("refresh_interval_seconds", 2)) * 1000)

        self._build_ui()
        self.statusBar().showMessage(startup_message or self.t("footer_ready"), 8000)

    def t(self, key: str, **kwargs: object) -> str:
        return self.ctx.t(key, **kwargs)

    def _nav_button(self, page_id: str, symbol: str, key: str) -> QPushButton:
        button = QPushButton(f"{symbol}   {self.t(key)}" if symbol else self.t(key))
        button.setObjectName("NavButton")
        button.setCheckable(True)
        button.setAutoExclusive(True)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(lambda _checked=False, target=page_id: self.switch_page(target))
        self.nav_buttons[page_id] = button
        return button

    def _build_ui(self) -> None:
        central = QWidget()
        outer = QHBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(250)
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(14, 20, 14, 14)
        side_layout.setSpacing(4)
        brand = QLabel(self.t("app_name"))
        brand.setObjectName("Brand")
        side_layout.addWidget(brand)
        subtitle = QLabel(self.t("app_subtitle"))
        subtitle.setObjectName("Muted")
        subtitle.setWordWrap(True)
        side_layout.addWidget(subtitle)
        side_layout.addSpacing(16)

        self.nav_buttons = {}
        for page_id, symbol, key in NAV_ITEMS:
            side_layout.addWidget(self._nav_button(page_id, symbol, key))
        side_layout.addStretch(1)
        side_layout.addWidget(self._nav_button("settings", "", K("nav_settings")))

        self.mode_label = QLabel()
        self.mode_label.setWordWrap(True)
        side_layout.addWidget(self.mode_label)
        version = QLabel(self.t("version", version=__version__))
        version.setObjectName("Muted")
        side_layout.addWidget(version)
        outer.addWidget(sidebar)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(22, 18, 22, 10)
        content_layout.setSpacing(14)

        topbar = QFrame()
        topbar.setObjectName("TopBar")
        topbar_layout = QHBoxLayout(topbar)
        topbar_layout.setContentsMargins(18, 12, 18, 12)
        title_box = QVBoxLayout()
        self.page_title = QLabel()
        self.page_title.setObjectName("PageTitle")
        self.page_subtitle = QLabel()
        self.page_subtitle.setObjectName("Muted")
        title_box.addWidget(self.page_title)
        title_box.addWidget(self.page_subtitle)
        topbar_layout.addLayout(title_box, 1)
        pill = QLabel(f"●  {self.t('local_only')}")
        pill.setObjectName("PillText")
        topbar_layout.addWidget(pill)
        refresh_button = QPushButton(self.t("refresh"))
        refresh_button.setObjectName("SecondaryButton")
        refresh_button.clicked.connect(self.refresh_current_page)
        topbar_layout.addWidget(refresh_button)
        content_layout.addWidget(topbar)

        self.stack = QStackedWidget()
        content_layout.addWidget(self.stack, 1)
        outer.addWidget(content, 1)

        ctx = self.ctx
        self.pages = {
            "dashboard": DashboardPage(ctx),
            "cleaner": CleanerPage(ctx),
            "startup": StartupPage(ctx),
            "processes": ProcessesPage(ctx),
            "registry": RegistryPage(ctx),
            "services": ServicesPage(ctx),
            "disks": DisksPage(ctx),
            "backup": BackupPage(ctx),
            "diagnostics": DiagnosticsPage(ctx),
            "maintenance": MaintenancePage(ctx),
            "history": HistoryPage(ctx),
            "settings": SettingsPage(ctx, self._on_language_changed, self._on_settings_saved),
        }
        for page_id, page in self.pages.items():
            if page_id == "settings":
                # Ayarlar sayfası küçük ekranlarda kaydırılabilir olsun.
                scroll = QScrollArea()
                scroll.setWidgetResizable(True)
                scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
                scroll.setWidget(page)
                self.stack.addWidget(scroll)
            else:
                self.stack.addWidget(page)

        self.setCentralWidget(central)
        self.setStatusBar(QStatusBar())
        self._update_mode_label()
        self.switch_page(self.current_page)

    def _update_mode_label(self) -> None:
        if self.ctx.dry_run:
            self.mode_label.setText("◐  " + self.t("mode_dry_run"))
            self.mode_label.setObjectName("WarningText")
        else:
            self.mode_label.setText("●  " + self.t("mode_live"))
            self.mode_label.setObjectName("OkText")
        self.mode_label.style().unpolish(self.mode_label)
        self.mode_label.style().polish(self.mode_label)

    def switch_page(self, page_id: str) -> None:
        page = self.pages.get(page_id)
        if page is None:
            return
        self.current_page = page_id
        container = page.parentWidget().parentWidget() if page_id == "settings" else page
        self.stack.setCurrentWidget(container)
        self.nav_buttons[page_id].setChecked(True)
        self.page_title.setText(self.t(page.title_key))
        self.page_subtitle.setText(self.t(page.subtitle_key))
        try:
            page.on_show()
        except Exception:
            logging.exception("Page %s could not be shown.", page_id)

    def refresh_current_page(self) -> None:
        try:
            self.pages[self.current_page].refresh()
        except Exception:
            logging.exception("Page refresh failed.")
        self.statusBar().showMessage(self.t("footer_updated", time=datetime.now().strftime("%H:%M:%S")), 4000)

    def _on_timer(self) -> None:
        page = self.pages.get(self.current_page)
        if page is not None and page.auto_refresh and self.isVisible() and not self.isMinimized():
            try:
                page.refresh()
            except Exception:
                logging.exception("Automatic refresh failed.")

    def _on_language_changed(self, language: str) -> None:
        self.ctx.translator.set_language(language)
        self.current_page = "settings"
        self._build_ui()
        self.statusBar().showMessage(self.t("settings_saved"), 4000)

    def _on_settings_saved(self) -> None:
        self.refresh_timer.setInterval(int(self.ctx.config.get("refresh_interval_seconds", 2)) * 1000)
        self._update_mode_label()
        self.statusBar().showMessage(self.t("settings_saved"), 4000)
