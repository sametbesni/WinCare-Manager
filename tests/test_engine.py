from __future__ import annotations

from pathlib import Path

from core.engine import ExecutionOutcome, OperationEngine, OperationPlan
from database.history import HistoryStore


def _engine(tmp_path: Path, admin: bool = False) -> OperationEngine:
    return OperationEngine(HistoryStore(tmp_path / "h.db"), is_admin=lambda: admin)


def _plan(calls: list[str], **kwargs) -> OperationPlan:
    def execute() -> ExecutionOutcome:
        calls.append("execute")
        return ExecutionOutcome(1)

    return OperationPlan(kind="test.op", summary="test", targets=["a"], execute=execute, **kwargs)


def test_dry_run_never_executes(tmp_path: Path) -> None:
    calls: list[str] = []
    engine = _engine(tmp_path)
    result = engine.run(_plan(calls, backup=lambda: calls.append("backup") or "b1"), dry_run=True)
    assert result.status == "dry_run"
    assert calls == []
    record = engine.history.recent()[0]
    assert record.status == "dry_run" and record.dry_run


def test_admin_required_is_blocked_without_admin(tmp_path: Path) -> None:
    calls: list[str] = []
    result = _engine(tmp_path, admin=False).run(_plan(calls, requires_admin=True), dry_run=False)
    assert result.status == "blocked"
    assert calls == []


def test_validation_problems_block_execution(tmp_path: Path) -> None:
    calls: list[str] = []
    result = _engine(tmp_path).run(_plan(calls, validate=lambda: ["C:\\Windows\\x"]), dry_run=False)
    assert result.status == "blocked"
    assert result.details["problems"] == ["C:\\Windows\\x"]
    assert calls == []


def test_backup_runs_before_execute_and_failure_stops_operation(tmp_path: Path) -> None:
    calls: list[str] = []
    engine = _engine(tmp_path)
    ok = engine.run(_plan(calls, backup=lambda: calls.append("backup") or "b1"), dry_run=False)
    assert calls == ["backup", "execute"]
    assert ok.status == "success" and ok.backup_id == "b1"

    calls.clear()

    def broken_backup() -> str:
        raise RuntimeError("disk full")

    failed = engine.run(_plan(calls, backup=broken_backup), dry_run=False)
    assert failed.status == "failed"
    assert calls == []


def test_partial_and_exception_statuses(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    partial = engine.run(OperationPlan("t", "s", ["a", "b"], lambda: ExecutionOutcome(1, 1)), dry_run=False)
    assert partial.status == "partial"

    def boom() -> ExecutionOutcome:
        raise OSError("nope")

    failed = engine.run(OperationPlan("t", "s", ["a"], boom), dry_run=False)
    assert failed.status == "failed"
    assert engine.history.recent()[0].status == "failed"


def test_backups_ignore_dry_run_when_plan_allows(tmp_path: Path) -> None:
    calls: list[str] = []
    result = _engine(tmp_path).run(_plan(calls, respects_dry_run=False), dry_run=True)
    assert result.status == "success"
    assert calls == ["execute"]


def test_interrupted_operations_are_detected(tmp_path: Path) -> None:
    history = HistoryStore(tmp_path / "h.db")
    history.start("test.op", "left running", 1, False)
    assert history.mark_interrupted() == 1
    assert history.recent()[0].status == "interrupted"
    assert history.mark_interrupted() == 0
