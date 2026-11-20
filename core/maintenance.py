"""Otomatik Bakım: planlı, salt okunur sistem analizi.

Kurallar:
- Varsayılan olarak KAPALIDIR; kullanıcı açıkça etkinleştirmelidir.
- Yalnızca analiz yapar: dosya silmez, kayıt defterini ve ayarları değiştirmez.
- Zamanlama, mevcut kullanıcı adına ve yönetici yetkisi olmadan Windows Görev
  Zamanlayıcı'ya kaydedilir; bilgisayar başında kullanıcı yokken çalışmaz.
- Sonuç ``maintenance/last_report.json`` dosyasına ve işlem geçmişine yazılır,
  uygulama bir sonraki açılışta kullanıcıya bildirir.
"""
from __future__ import annotations

import json
import logging
import os
import sys
import tempfile
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from xml.sax.saxutils import escape

from app.i18n import K
from core.winproc import run_command

TASK_NAME = "WinCareManager AutoMaintenance"
FREQUENCIES = ("daily", "weekly")
WEEKDAYS = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")
_XML_DAYS = {"MON": "Monday", "TUE": "Tuesday", "WED": "Wednesday", "THU": "Thursday",
             "FRI": "Friday", "SAT": "Saturday", "SUN": "Sunday"}
JUNK_WARNING_BYTES = 1024 ** 3  # 1 GB
STARTUP_WARNING_COUNT = 15


# --------------------------------------------------------------------------- rapor

@dataclass
class Finding:
    level: str  # ok, warning, critical
    key: str    # çeviri anahtarı
    params: dict = field(default_factory=dict)


@dataclass
class MaintenanceReport:
    report_id: str
    created_at: str
    trigger: str  # scheduled, manual
    level: str
    findings: list[Finding]
    junk_files: int = 0
    junk_bytes: int = 0
    startup_enabled: int = 0
    error_events: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "MaintenanceReport":
        findings = [Finding(**f) for f in data.get("findings", []) if isinstance(f, dict)]
        return cls(
            report_id=str(data.get("report_id", "")),
            created_at=str(data.get("created_at", "")),
            trigger=str(data.get("trigger", "manual")),
            level=str(data.get("level", "ok")),
            findings=findings,
            junk_files=int(data.get("junk_files", 0)),
            junk_bytes=int(data.get("junk_bytes", 0)),
            startup_enabled=int(data.get("startup_enabled", 0)),
            error_events=int(data.get("error_events", 0)),
        )


def _overall(findings: list[Finding]) -> str:
    levels = {f.level for f in findings}
    if "critical" in levels:
        return "critical"
    if "warning" in levels:
        return "warning"
    return "ok"


def run_analysis(temp_min_age_hours: int = 24, trigger: str = "manual") -> MaintenanceReport:
    """Sistemi analiz eder. Hiçbir şeyi değiştirmez; her adım bağımsız olarak hata toleranslıdır."""
    from core import cleaner, diagnostics, disks, startup, system_info

    findings: list[Finding] = []
    junk_files = junk_bytes = startup_enabled = error_events = 0

    try:
        snapshot = system_info.get_system_snapshot()
        partitions = disks.list_partitions()
        for check in diagnostics.health_checks(snapshot, partitions):
            if check.level != "ok":
                findings.append(Finding(check.level, check.key, dict(check.params)))
    except Exception:
        logging.exception("Maintenance: health checks failed.")

    try:
        for disk in disks.list_physical_disks():
            if disk.health and disk.health.lower() not in ("healthy", "0"):
                findings.append(Finding("critical", K("maint_disk_unhealthy"), {"name": disk.name}))
    except Exception:
        logging.exception("Maintenance: physical disk check failed.")

    try:
        result = cleaner.scan_temporary_files(older_than_seconds=int(temp_min_age_hours) * 3600)
        junk_files, junk_bytes = len(result.files), result.total_bytes
        if junk_bytes >= JUNK_WARNING_BYTES:
            findings.append(Finding("warning", K("maint_junk_large"),
                                    {"size": system_info.format_bytes(junk_bytes)}))
    except Exception:
        logging.exception("Maintenance: junk scan failed.")

    try:
        startup_enabled = sum(1 for e in startup.list_startup_entries() if e.enabled)
        if startup_enabled >= STARTUP_WARNING_COUNT:
            findings.append(Finding("warning", K("maint_startup_many"), {"count": startup_enabled}))
    except Exception:
        logging.exception("Maintenance: startup check failed.")

    try:
        error_events = len(diagnostics.recent_events(hours=24))
        if error_events >= 20:
            findings.append(Finding("warning", K("maint_events_many"), {"count": error_events}))
    except Exception:
        logging.exception("Maintenance: event log check failed.")

    return MaintenanceReport(
        report_id=uuid.uuid4().hex[:12],
        created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        trigger=trigger,
        level=_overall(findings),
        findings=findings,
        junk_files=junk_files,
        junk_bytes=junk_bytes,
        startup_enabled=startup_enabled,
        error_events=error_events,
    )


def report_path(data_dir: Path) -> Path:
    return data_dir / "maintenance" / "last_report.json"


def save_report(data_dir: Path, report: MaintenanceReport) -> Path:
    path = report_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)
    return path


def load_report(data_dir: Path) -> MaintenanceReport | None:
    path = report_path(data_dir)
    if not path.is_file():
        return None
    try:
        return MaintenanceReport.from_dict(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError):
        logging.exception("Maintenance report could not be read.")
        return None


# --------------------------------------------------------------------- zamanlama

def launch_command() -> tuple[str, str, str]:
    """Görevin çalıştıracağı (program, argümanlar, çalışma klasörü)."""
    if getattr(sys, "frozen", False):
        exe = Path(sys.executable)
        return str(exe), "--maintenance", str(exe.parent)
    project = Path(__file__).resolve().parent.parent
    python = Path(sys.executable)
    pythonw = python.with_name("pythonw.exe")
    program = pythonw if pythonw.is_file() else python
    return str(program), f'"{project / "main.py"}" --maintenance', str(project)


def _next_start(time_text: str) -> str:
    hour, minute = (int(part) for part in time_text.split(":"))
    start = datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)
    if start <= datetime.now():
        start += timedelta(days=1)
    return start.strftime("%Y-%m-%dT%H:%M:%S")


def validate_schedule(frequency: str, day: str, time_text: str) -> list[str]:
    problems = []
    if frequency not in FREQUENCIES:
        problems.append(f"frequency: {frequency}")
    if day not in WEEKDAYS:
        problems.append(f"day: {day}")
    try:
        hour, minute = (int(part) for part in time_text.split(":"))
        if not (0 <= hour < 24 and 0 <= minute < 60):
            raise ValueError
    except ValueError:
        problems.append(f"time: {time_text}")
    return problems


def build_task_xml(frequency: str, day: str, time_text: str,
                   command: tuple[str, str, str] | None = None, user: str | None = None) -> str:
    program, arguments, workdir = command or launch_command()
    if frequency == "daily":
        schedule = "<ScheduleByDay><DaysInterval>1</DaysInterval></ScheduleByDay>"
    else:
        schedule = (f"<ScheduleByWeek><DaysOfWeek><{_XML_DAYS[day]} /></DaysOfWeek>"
                    "<WeeksInterval>1</WeeksInterval></ScheduleByWeek>")
    user_xml = f"<UserId>{escape(user)}</UserId>" if user else ""
    return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>WinCare Manager otomatik bakim: yalnizca analiz yapar, hicbir seyi silmez veya degistirmez.</Description>
  </RegistrationInfo>
  <Triggers>
    <CalendarTrigger>
      <StartBoundary>{_next_start(time_text)}</StartBoundary>
      <Enabled>true</Enabled>
      {schedule}
    </CalendarTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      {user_xml}
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>true</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>true</StopIfGoingOnBatteries>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <ExecutionTimeLimit>PT1H</ExecutionTimeLimit>
    <Priority>7</Priority>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{escape(program)}</Command>
      <Arguments>{escape(arguments)}</Arguments>
      <WorkingDirectory>{escape(workdir)}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"""


def _current_user() -> str | None:
    name = os.environ.get("USERNAME")
    domain = os.environ.get("USERDOMAIN")
    if not name:
        return None
    return f"{domain}\\{name}" if domain else name


def task_exists() -> bool:
    if os.name != "nt":
        return False
    try:
        return run_command(["schtasks", "/Query", "/TN", TASK_NAME], timeout=30).returncode == 0
    except (OSError, ValueError):
        return False


def register_task(frequency: str, day: str, time_text: str) -> None:
    problems = validate_schedule(frequency, day, time_text)
    if problems:
        raise ValueError("; ".join(problems))
    xml = build_task_xml(frequency, day, time_text, user=_current_user())
    handle, name = tempfile.mkstemp(suffix=".xml", prefix="wincare_task_")
    os.close(handle)
    path = Path(name)
    try:
        path.write_text(xml, encoding="utf-16")
        completed = run_command(["schtasks", "/Create", "/TN", TASK_NAME, "/XML", str(path), "/F"], timeout=60)
    finally:
        path.unlink(missing_ok=True)
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout).strip() or "schtasks /Create failed")


def remove_task() -> bool:
    """Görevi siler. Görev zaten yoksa False döner (hata sayılmaz)."""
    if not task_exists():
        return False
    completed = run_command(["schtasks", "/Delete", "/TN", TASK_NAME, "/F"], timeout=60)
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout).strip() or "schtasks /Delete failed")
    return True


# ------------------------------------------------------------------ çalıştırma

def analyze_and_record(history, data_dir: Path, temp_min_age_hours: int, trigger: str) -> MaintenanceReport:
    """Analizi çalıştırır, raporu kaydeder ve işlem geçmişine yazar."""
    op_id = history.start("maintenance.analysis", trigger, 0, False)
    try:
        report = run_analysis(temp_min_age_hours, trigger)
        save_report(data_dir, report)
    except Exception as exc:
        logging.exception("Maintenance analysis failed.")
        history.finish(op_id, "failed", {"error": str(exc)})
        raise
    history.finish(op_id, "success", {
        "report_id": report.report_id,
        "level": report.level,
        "findings": [asdict(f) for f in report.findings],
        "junk_files": report.junk_files,
        "junk_bytes": report.junk_bytes,
    })
    return report
