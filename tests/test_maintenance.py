"""Otomatik Bakım testleri. Gerçek zamanlanmış görev oluşturulmaz."""
from __future__ import annotations

import xml.etree.ElementTree as ET

import main
from app.config_manager import ConfigManager
from core import maintenance
from core.maintenance import Finding, MaintenanceReport
from database.history import HistoryStore

NS = {"t": "http://schemas.microsoft.com/windows/2004/02/mit/task"}
COMMAND = ("C:\\Program Files\\WinCare & Co\\WinCare Manager.exe", "--maintenance", "C:\\Program Files\\WinCare & Co")


def _report(report_id: str = "abc") -> MaintenanceReport:
    return MaintenanceReport(report_id, "2026-11-20 10:00:00", "manual", "warning",
                             [Finding("warning", "maint_junk_large", {"size": "2 GB"})], junk_files=5, junk_bytes=10)


def test_auto_maintenance_is_off_by_default(tmp_path) -> None:
    config = ConfigManager(tmp_path)
    assert config.get("auto_maintenance_enabled") is False


def test_invalid_schedule_settings_fall_back_to_defaults(tmp_path) -> None:
    (tmp_path / "settings.json").write_text(
        '{"auto_maintenance_enabled": "yes", "auto_maintenance_time": "25:99",'
        ' "auto_maintenance_frequency": "hourly", "auto_maintenance_day": "XYZ"}', encoding="utf-8")
    config = ConfigManager(tmp_path)
    assert config.get("auto_maintenance_enabled") is False
    assert config.get("auto_maintenance_time") == "10:00"
    assert config.get("auto_maintenance_frequency") == "weekly"
    assert config.get("auto_maintenance_day") == "MON"


def test_validate_schedule() -> None:
    assert maintenance.validate_schedule("weekly", "FRI", "23:59") == []
    assert maintenance.validate_schedule("hourly", "FRI", "10:00")
    assert maintenance.validate_schedule("daily", "FRI", "24:00")
    assert maintenance.validate_schedule("daily", "FRI", "abc")


def test_weekly_task_xml_is_valid_and_escaped() -> None:
    xml = maintenance.build_task_xml("weekly", "WED", "09:30", command=COMMAND, user="PC\\user")
    root = ET.fromstring(xml.split("\n", 1)[1])  # UTF-16 bildirimi olmadan ayrıştır
    assert root.find(".//t:ScheduleByWeek/t:DaysOfWeek/t:Wednesday", NS) is not None
    assert root.find(".//t:Exec/t:Command", NS).text == COMMAND[0]
    assert root.find(".//t:Exec/t:Arguments", NS).text == "--maintenance"
    assert root.find(".//t:RunLevel", NS).text == "LeastPrivilege"
    assert root.find(".//t:StartBoundary", NS).text.endswith("09:30:00")


def test_daily_task_xml() -> None:
    xml = maintenance.build_task_xml("daily", "MON", "00:05", command=COMMAND)
    root = ET.fromstring(xml.split("\n", 1)[1])
    assert root.find(".//t:ScheduleByDay/t:DaysInterval", NS).text == "1"
    assert root.find(".//t:ScheduleByWeek", NS) is None
    assert root.find(".//t:UserId", NS) is None


def test_report_round_trip(tmp_path) -> None:
    assert maintenance.load_report(tmp_path) is None
    maintenance.save_report(tmp_path, _report())
    loaded = maintenance.load_report(tmp_path)
    assert loaded == _report()


def test_corrupt_report_is_ignored(tmp_path) -> None:
    path = maintenance.report_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text("{bozuk", encoding="utf-8")
    assert maintenance.load_report(tmp_path) is None


def test_analyze_and_record_writes_history(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(maintenance, "run_analysis", lambda hours, trigger: _report("r1"))
    history = HistoryStore(tmp_path / "history.db")
    report = maintenance.analyze_and_record(history, tmp_path, 24, "scheduled")
    assert report.report_id == "r1"
    record = history.recent()[0]
    assert record.kind == "maintenance.analysis"
    assert record.status == "success"
    assert maintenance.load_report(tmp_path).report_id == "r1"


def test_scheduled_run_does_nothing_when_disabled(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    called = []
    monkeypatch.setattr(maintenance, "run_analysis", lambda *a: called.append(a))
    assert main.run_scheduled_maintenance() == 0
    assert not called
    assert maintenance.load_report(tmp_path / "WinCareManager") is None


def test_scheduled_run_analyses_when_enabled(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    ConfigManager(tmp_path / "WinCareManager").set("auto_maintenance_enabled", True)
    monkeypatch.setattr(maintenance, "run_analysis", lambda hours, trigger: _report("sched"))
    assert main.run_scheduled_maintenance() == 0
    assert maintenance.load_report(tmp_path / "WinCareManager").report_id == "sched"


def test_settings_with_bom_are_read(tmp_path) -> None:
    (tmp_path / "settings.json").write_bytes(b'\xef\xbb\xbf{"auto_maintenance_enabled": true}')
    assert ConfigManager(tmp_path).get("auto_maintenance_enabled") is True


def test_file_log_is_added_even_if_another_handler_exists(tmp_path) -> None:
    import logging
    from logging.handlers import RotatingFileHandler

    from app.logger import configure_logging

    root = logging.getLogger()
    saved = root.handlers[:]
    stray = logging.StreamHandler()
    root.handlers = [stray]
    try:
        log_file = configure_logging(tmp_path)
        assert any(isinstance(h, RotatingFileHandler) for h in root.handlers)
        configure_logging(tmp_path)  # ikinci çağrı işleyiciyi çoğaltmamalı
        assert sum(isinstance(h, RotatingFileHandler) for h in root.handlers) == 1
        assert log_file.parent.is_dir()
    finally:
        for handler in root.handlers:
            if handler not in saved:
                handler.close()
        root.handlers = saved
