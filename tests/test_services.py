"""Hizmet başlatma/durdurma güvenlik kuralları. Gerçek hizmetlere dokunulmaz."""
from __future__ import annotations

import pytest

from core import services
from core.engine import OperationEngine, OperationPlan, ExecutionOutcome
from core.services import ServiceEntry, control_problems
from database.history import HistoryStore


def _entry(name: str = "Spooler", status: str = "running", start_type: str = "automatic") -> ServiceEntry:
    return ServiceEntry(name, name, status, start_type, "C:\\Windows\\System32\\spoolsv.exe")


@pytest.mark.parametrize("name", ["WinDefend", "windefend", "RpcSs", "mpssvc", "EventLog", "wuauserv"])
def test_critical_services_are_protected(name: str) -> None:
    assert services.is_protected(name)
    assert control_problems(_entry(name), "stop", has_active_dependents=False) == ["service_protected"]


def test_ordinary_service_can_be_stopped() -> None:
    assert not services.is_protected("Spooler")
    assert control_problems(_entry(), "stop", has_active_dependents=False) == []


def test_service_with_running_dependents_is_not_stopped() -> None:
    assert control_problems(_entry(), "stop", has_active_dependents=True) == ["service_has_dependents"]


def test_stop_requires_running_and_start_requires_stopped() -> None:
    assert control_problems(_entry(status="stopped"), "stop", False) == ["service_wrong_state"]
    assert control_problems(_entry(status="running"), "start", False) == ["service_wrong_state"]
    assert control_problems(_entry(status="stopped"), "start", False) == []


def test_disabled_service_is_not_started() -> None:
    assert control_problems(_entry(status="stopped", start_type="disabled"), "start", False) == ["service_disabled"]


def test_protected_service_can_still_be_started() -> None:
    # Başlatmak güvenlidir; yalnızca durdurma engellenir.
    assert control_problems(_entry("WinDefend", status="stopped"), "start", False) == []


def test_unknown_action_is_rejected() -> None:
    assert control_problems(_entry(), "delete", False) == ["service_invalid_action"]
    with pytest.raises(ValueError):
        services.control_service("Spooler", "delete")


def test_service_operation_is_blocked_without_admin(tmp_path) -> None:
    called = []
    engine = OperationEngine(HistoryStore(tmp_path / "h.db"), is_admin=lambda: False)
    plan = OperationPlan("service.stop", "Spooler", ["Spooler"],
                         execute=lambda: called.append(1) or ExecutionOutcome(1), requires_admin=True)
    assert engine.run(plan, dry_run=False).status == "blocked"
    assert not called


def test_service_operation_changes_nothing_in_dry_run(tmp_path) -> None:
    called = []
    engine = OperationEngine(HistoryStore(tmp_path / "h.db"), is_admin=lambda: True)
    plan = OperationPlan("service.stop", "Spooler", ["Spooler"],
                         execute=lambda: called.append(1) or ExecutionOutcome(1), requires_admin=True)
    assert engine.run(plan, dry_run=True).status == "dry_run"
    assert not called
