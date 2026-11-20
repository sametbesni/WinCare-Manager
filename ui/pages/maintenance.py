from __future__ import annotations

from PySide6.QtCore import QTime
from PySide6.QtWidgets import QCheckBox, QComboBox, QFormLayout, QHBoxLayout, QLabel, QPushButton, QTimeEdit

from app.i18n import K
from core import maintenance
from core.engine import ExecutionOutcome, OperationPlan
from core.system_info import format_bytes
from ui.pages.base import BasePage
from ui.widgets import Card, ask_confirmation, muted_label, section_label, show_info, show_operation_result
from ui.worker import run_async

LEVEL_OBJECTS = {"ok": "OkText", "warning": "WarningText", "critical": "CriticalText"}
LEVEL_KEYS = {"ok": K("maint_level_ok"), "warning": K("maint_level_warning"), "critical": K("maint_level_critical")}
DAY_KEYS = {"MON": K("day_mon"), "TUE": K("day_tue"), "WED": K("day_wed"), "THU": K("day_thu"),
            "FRI": K("day_fri"), "SAT": K("day_sat"), "SUN": K("day_sun")}
TRIGGER_KEYS = {"scheduled": K("maint_trigger_scheduled"), "manual": K("maint_trigger_manual")}


class MaintenancePage(BasePage):
    title_key = K("page_maintenance")
    subtitle_key = K("subtitle_maintenance")

    def __init__(self, ctx) -> None:
        super().__init__(ctx)
        config = ctx.config

        schedule = Card()
        schedule.layout_box.addWidget(section_label(self.t("maint_schedule_title")))
        schedule.layout_box.addWidget(muted_label(self.t("maint_explain")))
        self.status_label = QLabel(self.t("loading"))
        self.status_label.setWordWrap(True)
        schedule.layout_box.addWidget(self.status_label)

        self.enable_check = QCheckBox(self.t("maint_enable"))
        self.enable_check.setChecked(bool(config.get("auto_maintenance_enabled")))
        self.enable_check.toggled.connect(self._update_inputs)
        schedule.layout_box.addWidget(self.enable_check)

        form = QFormLayout()
        form.setHorizontalSpacing(24)
        self.frequency_combo = QComboBox()
        self.frequency_combo.addItem(self.t("maint_daily"), "daily")
        self.frequency_combo.addItem(self.t("maint_weekly"), "weekly")
        self.frequency_combo.setCurrentIndex(max(0, self.frequency_combo.findData(config.get("auto_maintenance_frequency"))))
        self.frequency_combo.currentIndexChanged.connect(self._update_inputs)
        self.day_combo = QComboBox()
        for code in maintenance.WEEKDAYS:
            self.day_combo.addItem(self.t(DAY_KEYS[code]), code)
        self.day_combo.setCurrentIndex(max(0, self.day_combo.findData(config.get("auto_maintenance_day"))))
        self.time_edit = QTimeEdit(QTime.fromString(str(config.get("auto_maintenance_time")), "HH:mm"))
        self.time_edit.setDisplayFormat("HH:mm")
        form.addRow(self.t("maint_frequency"), self.frequency_combo)
        form.addRow(self.t("maint_day"), self.day_combo)
        form.addRow(self.t("maint_time"), self.time_edit)
        schedule.layout_box.addLayout(form)
        schedule.layout_box.addWidget(muted_label(self.t("maint_note_logon")))

        row = QHBoxLayout()
        row.addStretch(1)
        apply_button = QPushButton(self.t("maint_apply"))
        apply_button.clicked.connect(self._apply)
        row.addWidget(apply_button)
        schedule.layout_box.addLayout(row)
        self.root.addWidget(schedule)

        report = Card()
        head = QHBoxLayout()
        head.addWidget(section_label(self.t("maint_report_title")), 1)
        self.run_button = QPushButton(self.t("maint_run_now"))
        self.run_button.setObjectName("SecondaryButton")
        self.run_button.clicked.connect(self._run_now)
        head.addWidget(self.run_button)
        report.layout_box.addLayout(head)
        self.report_meta = muted_label("")
        report.layout_box.addWidget(self.report_meta)
        self.report_box = report.layout_box
        self.report_labels: list[QLabel] = []
        self.root.addWidget(report)
        self.root.addStretch(1)
        self._update_inputs()

    # ------------------------------------------------------------------ görünüm

    def _update_inputs(self) -> None:
        enabled = self.enable_check.isChecked()
        self.frequency_combo.setEnabled(enabled)
        self.time_edit.setEnabled(enabled)
        self.day_combo.setEnabled(enabled and self.frequency_combo.currentData() == "weekly")

    def refresh(self) -> None:
        self._show_report(maintenance.load_report(self.ctx.config.data_dir))
        run_async(maintenance.task_exists, self._show_status, lambda _e: self._show_status(False))

    def on_show(self) -> None:
        super().on_show()
        report = maintenance.load_report(self.ctx.config.data_dir)
        if report and report.report_id != self.ctx.config.get("maintenance_report_seen"):
            self.ctx.config.set("maintenance_report_seen", report.report_id)

    def _schedule_text(self) -> str:
        config = self.ctx.config
        time_text = str(config.get("auto_maintenance_time"))
        if config.get("auto_maintenance_frequency") == "daily":
            return self.t("maint_schedule_daily", time=time_text)
        return self.t("maint_schedule_weekly", day=self.t(DAY_KEYS[str(config.get("auto_maintenance_day"))]),
                      time=time_text)

    def _show_status(self, registered: bool) -> None:
        enabled = bool(self.ctx.config.get("auto_maintenance_enabled"))
        if enabled and registered:
            text, obj = self.t("maint_status_on", schedule=self._schedule_text()), "OkText"
        elif enabled:
            text, obj = self.t("maint_status_missing"), "WarningText"
        elif registered:
            text, obj = self.t("maint_status_leftover"), "WarningText"
        else:
            text, obj = self.t("maint_status_off"), ""
        self.status_label.setText("● " + text)
        self.status_label.setObjectName(obj)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def _show_report(self, report: maintenance.MaintenanceReport | None) -> None:
        for label in self.report_labels:
            label.deleteLater()
        self.report_labels = []
        if report is None:
            self.report_meta.setText(self.t("maint_no_report"))
            return
        self.report_meta.setText(self.t(
            "maint_report_meta", time=report.created_at, trigger=self.t(TRIGGER_KEYS.get(report.trigger, TRIGGER_KEYS["manual"])),
            files=report.junk_files, size=format_bytes(report.junk_bytes), startup=report.startup_enabled,
            events=report.error_events))
        lines = [(report.level, self.t(LEVEL_KEYS.get(report.level, LEVEL_KEYS["ok"])))]
        lines += [(f.level, self.t(f.key, **f.params)) for f in report.findings]
        for level, text in lines:
            label = QLabel("● " + text)
            label.setObjectName(LEVEL_OBJECTS.get(level, ""))
            label.setWordWrap(True)
            self.report_box.addWidget(label)
            self.report_labels.append(label)

    # ------------------------------------------------------------------ işlemler

    def _run_now(self) -> None:
        if self._busy:
            return
        self._busy = True
        self.run_button.setEnabled(False)
        self.report_meta.setText(self.t("maint_running"))
        config = self.ctx.config
        run_async(
            lambda: maintenance.analyze_and_record(self.ctx.history, config.data_dir,
                                                   int(config.get("temp_min_age_hours")), "manual"),
            self._analysis_done, self._analysis_failed)

    def _analysis_done(self, report: maintenance.MaintenanceReport) -> None:
        self._busy = False
        self.run_button.setEnabled(True)
        self.ctx.config.set("maintenance_report_seen", report.report_id)
        self._show_report(report)

    def _analysis_failed(self, error: str) -> None:
        self._busy = False
        self.run_button.setEnabled(True)
        self.report_meta.setText(self.t("maint_run_failed", error=error))

    def _apply(self) -> None:
        enable = self.enable_check.isChecked()
        frequency = str(self.frequency_combo.currentData())
        day = str(self.day_combo.currentData())
        time_text = self.time_edit.time().toString("HH:mm")

        if enable:
            plan = OperationPlan(
                kind="maintenance.schedule",
                summary=f"{frequency} {day if frequency == 'weekly' else ''} {time_text}".replace("  ", " "),
                targets=[maintenance.TASK_NAME],
                validate=lambda: maintenance.validate_schedule(frequency, day, time_text),
                execute=lambda: (maintenance.register_task(frequency, day, time_text), ExecutionOutcome(1))[1],
                # Görev yalnızca analiz yapar; zamanlamanın kendisi kullanıcının açık tercihidir.
                respects_dry_run=False,
            )
            question = self.t("maint_confirm_enable")
        else:
            plan = OperationPlan(
                kind="maintenance.unschedule",
                summary=maintenance.TASK_NAME,
                targets=[maintenance.TASK_NAME],
                execute=lambda: (maintenance.remove_task(), ExecutionOutcome(1))[1],
                respects_dry_run=False,
            )
            question = self.t("maint_confirm_disable")

        if not ask_confirmation(self, self.ctx, self.t("confirm_title"), question):
            self.ctx.engine.record_cancelled(plan)
            return
        result = self.ctx.engine.run(plan, dry_run=self.ctx.dry_run)
        if result.status == "success":
            config = self.ctx.config
            config.set("auto_maintenance_enabled", enable)
            config.set("auto_maintenance_frequency", frequency)
            config.set("auto_maintenance_day", day)
            config.set("auto_maintenance_time", time_text)
        show_operation_result(self, self.ctx, result)
        self.refresh()


def prepare_uninstall(parent, ctx) -> None:
    """Kaldırmadan önce uygulamanın sisteme eklediği tek kalıcı öğeyi (zamanlanmış görev) siler."""
    plan = OperationPlan(
        kind="app.prepare_uninstall",
        summary=maintenance.TASK_NAME,
        targets=[maintenance.TASK_NAME],
        execute=lambda: (maintenance.remove_task(), ExecutionOutcome(1))[1],
        respects_dry_run=False,
    )
    if not ask_confirmation(parent, ctx, ctx.t("confirm_title"), ctx.t("uninstall_confirm")):
        ctx.engine.record_cancelled(plan)
        return
    result = ctx.engine.run(plan, dry_run=ctx.dry_run)
    if result.status != "success":
        show_operation_result(parent, ctx, result)
        return
    ctx.config.set("auto_maintenance_enabled", False)
    show_info(parent, ctx.t("uninstall_title"), ctx.t("uninstall_steps", data=str(ctx.config.data_dir)))
