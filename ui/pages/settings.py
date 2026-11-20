from __future__ import annotations

import os

from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFormLayout, QHBoxLayout, QLabel,
                               QPushButton, QSpinBox)

from app import __version__, admin
from app.i18n import K
from ui.pages.base import BasePage
from ui.pages.maintenance import prepare_uninstall
from ui.widgets import Card, muted_label, section_label, show_info


class SettingsPage(BasePage):
    title_key = K("page_settings")
    subtitle_key = K("subtitle_settings")

    def __init__(self, ctx, on_language_changed, on_saved) -> None:
        super().__init__(ctx)
        self.on_language_changed = on_language_changed
        self.on_saved = on_saved
        config = ctx.config

        card = Card()
        card.layout_box.addWidget(section_label(self.t("settings_general")))
        form = QFormLayout()
        form.setVerticalSpacing(14)
        form.setHorizontalSpacing(24)
        self.language_combo = QComboBox()
        self.language_combo.addItem(self.t("language_turkish"), "tr_TR")
        self.language_combo.addItem(self.t("language_english"), "en_US")
        self.language_combo.setCurrentIndex(max(0, self.language_combo.findData(config.get("language"))))
        self.refresh_combo = QComboBox()
        for seconds in (1, 2, 3, 5, 10):
            self.refresh_combo.addItem(f"{seconds} {self.t('seconds')}", seconds)
        self.refresh_combo.setCurrentIndex(max(0, self.refresh_combo.findData(config.get("refresh_interval_seconds"))))
        self.user_check = QCheckBox(self.t("settings_show_user"))
        self.user_check.setMinimumWidth(0)
        self.user_check.setChecked(bool(config.get("show_process_username")))
        form.addRow(self.t("settings_language"), self.language_combo)
        form.addRow(self.t("settings_refresh"), self.refresh_combo)
        form.addRow("", self.user_check)
        card.layout_box.addLayout(form)
        self.root.addWidget(card)

        safety = Card()
        safety.layout_box.addWidget(section_label(self.t("settings_safety")))
        self.dry_run_check = QCheckBox(self.t("settings_dry_run"))
        self.dry_run_check.setChecked(bool(config.get("dry_run")))
        safety.layout_box.addWidget(self.dry_run_check)
        safety.layout_box.addWidget(muted_label(self.t("settings_dry_run_note")))
        age_row = QHBoxLayout()
        age_label = QLabel(self.t("settings_temp_age"))
        age_label.setWordWrap(True)
        age_row.addWidget(age_label, 1)
        self.age_spin = QSpinBox()
        self.age_spin.setRange(1, 720)
        self.age_spin.setSuffix(" " + self.t("hours"))
        self.age_spin.setValue(int(config.get("temp_min_age_hours")))
        age_row.addWidget(self.age_spin)
        safety.layout_box.addLayout(age_row)

        admin_row = QHBoxLayout()
        is_admin = admin.is_admin()
        admin_label = QLabel(self.t("settings_admin_yes") if is_admin else self.t("settings_admin_no"))
        admin_label.setWordWrap(True)
        admin_row.addWidget(admin_label, 1)
        if not is_admin:
            elevate = QPushButton(self.t("settings_relaunch_admin"))
            elevate.setObjectName("SecondaryButton")
            elevate.clicked.connect(self._relaunch_admin)
            admin_row.addWidget(elevate)
        safety.layout_box.addLayout(admin_row)
        safety.layout_box.addWidget(muted_label(self.t("settings_admin_note")))
        self.root.addWidget(safety)

        save_row = QHBoxLayout()
        save_row.addStretch(1)
        self.save_button = QPushButton(self.t("save_settings"))
        self.save_button.clicked.connect(self.save)
        save_row.addWidget(self.save_button)
        self.root.addLayout(save_row)

        about = Card()
        about.layout_box.addWidget(section_label(self.t("about_title")))
        about.layout_box.addWidget(muted_label(self.t("about_body", version=__version__)))
        data_row = QHBoxLayout()
        data_row.addWidget(muted_label(self.t("settings_data_folder", path=str(config.data_dir))), 1)
        open_button = QPushButton(self.t("open_folder"))
        open_button.setObjectName("SecondaryButton")
        open_button.clicked.connect(lambda: os.startfile(config.data_dir))  # noqa: S606
        data_row.addWidget(open_button)
        about.layout_box.addLayout(data_row)
        self.root.addWidget(about)

        uninstall = Card()
        uninstall.layout_box.addWidget(section_label(self.t("uninstall_title")))
        uninstall_row = QHBoxLayout()
        uninstall_row.addWidget(muted_label(self.t("uninstall_explain")), 1)
        uninstall_button = QPushButton(self.t("uninstall_prepare"))
        uninstall_button.setObjectName("SecondaryButton")
        uninstall_button.clicked.connect(lambda: prepare_uninstall(self, self.ctx))
        uninstall_row.addWidget(uninstall_button)
        uninstall.layout_box.addLayout(uninstall_row)
        self.root.addWidget(uninstall)
        self.root.addStretch(1)

    def save(self) -> None:
        config = self.ctx.config
        config.set("refresh_interval_seconds", int(self.refresh_combo.currentData()))
        config.set("show_process_username", self.user_check.isChecked())
        config.set("dry_run", self.dry_run_check.isChecked())
        config.set("temp_min_age_hours", self.age_spin.value())
        language = str(self.language_combo.currentData())
        if language != config.get("language"):
            config.set("language", language)
            self.on_language_changed(language)
            return
        self.on_saved()

    def _relaunch_admin(self) -> None:
        if admin.relaunch_as_admin():
            QApplication.quit()
        else:
            show_info(self, self.t("warning_title"), self.t("settings_admin_failed"), error=True)

    def on_show(self) -> None:
        pass
