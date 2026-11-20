from __future__ import annotations

import logging
import sys

from app import APP_NAME, __version__
from app.config_manager import ConfigManager
from app.logger import configure_logging

MAINTENANCE_FLAG = "--maintenance"


def run_scheduled_maintenance() -> int:
    """Görev Zamanlayıcı tarafından pencere açmadan çağrılır. Yalnızca analiz yapar."""
    from core.maintenance import analyze_and_record
    from database.history import HistoryStore

    config = ConfigManager()
    configure_logging(config.data_dir)
    if not config.get("auto_maintenance_enabled"):
        # Kullanıcı özelliği kapattıysa ama görev kalmışsa hiçbir şey yapma.
        logging.info("Scheduled maintenance skipped: feature is disabled.")
        return 0
    logging.info("Scheduled maintenance analysis started.")
    try:
        report = analyze_and_record(HistoryStore(config.history_db), config.data_dir,
                                    int(config.get("temp_min_age_hours")), "scheduled")
    except Exception:
        return 1
    logging.info("Scheduled maintenance finished: %s, %d finding(s).", report.level, len(report.findings))
    return 0


def main() -> int:
    if MAINTENANCE_FLAG in sys.argv[1:]:
        return run_scheduled_maintenance()

    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication

    from app.context import AppContext
    from app.paths import get_resource_path
    from core.maintenance import load_report
    from ui.main_window import MainWindow
    from ui.styles import load_stylesheet

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_NAME)
    app.setApplicationVersion(__version__)

    config = ConfigManager()
    configure_logging(config.data_dir)
    logging.info("%s %s starting", APP_NAME, __version__)

    icon_path = get_resource_path("assets/app.ico")
    if icon_path.is_file():
        app.setWindowIcon(QIcon(str(icon_path)))
    try:
        app.setStyleSheet(load_stylesheet())
    except OSError:
        logging.exception("Theme could not be loaded; continuing with the default style.")

    ctx = AppContext.create(config)
    interrupted = ctx.history.mark_interrupted()
    message = ""
    if interrupted:
        logging.warning("%d interrupted operation(s) detected from a previous session.", interrupted)
        message = ctx.t("interrupted_found", count=interrupted)
    report = load_report(config.data_dir)
    if report and report.report_id != config.get("maintenance_report_seen") and not message:
        message = ctx.t("maint_new_report", count=len(report.findings))

    window = MainWindow(ctx, message)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
