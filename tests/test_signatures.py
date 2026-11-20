"""Dijital imza bilgisi testleri."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from core import signatures
from core.signatures import SignatureCache, SignatureInfo, map_status, parse_rows


@pytest.mark.parametrize("raw, expected", [
    ("Valid", "valid"), ("NotSigned", "unsigned"), ("HashMismatch", "invalid"),
    ("NotTrusted", "untrusted"), ("UnknownError", "unknown"), ("Error", "unknown"), ("", "unknown"),
])
def test_status_mapping(raw: str, expected: str) -> None:
    assert map_status(raw) == expected


def test_parse_rows_drops_signer_for_unsigned() -> None:
    rows = [
        {"Path": "C:\\A\\a.exe", "Status": "Valid", "Signer": "Contoso"},
        {"Path": "C:\\A\\b.exe", "Status": "NotSigned", "Signer": "ignored"},
        {"Status": "Valid"},  # yolu olmayan satır yok sayılır
    ]
    result = parse_rows(rows)
    assert len(result) == 2
    assert SignatureInfo("valid", "Contoso") in result.values()
    assert SignatureInfo("unsigned", "") in result.values()


def test_attention_flags() -> None:
    assert SignatureInfo("unsigned").needs_attention
    assert SignatureInfo("invalid").needs_attention
    assert not SignatureInfo("valid", "Microsoft Windows").needs_attention
    assert not SignatureInfo("unknown").needs_attention


def test_cache_skips_non_file_process_names(tmp_path) -> None:
    cache = SignatureCache()
    exe = tmp_path / "tool.exe"
    exe.write_bytes(b"MZ")
    assert cache.missing(["Registry", "MemCompression", "", str(exe)]) == [str(exe)]


def test_cache_invalidates_when_file_changes(tmp_path, monkeypatch) -> None:
    exe = tmp_path / "tool.exe"
    exe.write_bytes(b"MZ")
    calls: list[list[str]] = []

    def fake_check(paths):
        calls.append(list(paths))
        return {os.path.normcase(os.path.normpath(p)): SignatureInfo("unsigned") for p in paths}

    monkeypatch.setattr(signatures, "check_signatures", fake_check)
    cache = SignatureCache()
    assert cache.check_missing([str(exe)]) == 1
    assert cache.get(str(exe)) == SignatureInfo("unsigned")
    assert cache.check_missing([str(exe)]) == 0  # önbellekten
    exe.write_bytes(b"MZ-changed")  # boyut değişti
    assert cache.get(str(exe)) is None
    assert cache.check_missing([str(exe)]) == 1
    assert len(calls) == 2


def test_failed_check_is_recorded_as_unknown(tmp_path, monkeypatch) -> None:
    exe = tmp_path / "tool.exe"
    exe.write_bytes(b"MZ")

    def boom(_paths):
        raise RuntimeError("powershell failed")

    monkeypatch.setattr(signatures, "check_signatures", boom)
    cache = SignatureCache()
    cache.check_missing([str(exe)])
    assert cache.get(str(exe)) == signatures.UNKNOWN


@pytest.mark.skipif(os.name != "nt", reason="Windows Authenticode")
def test_real_signature_check_on_windows(tmp_path) -> None:
    unsigned = tmp_path / "unsigned.exe"
    unsigned.write_bytes(b"MZ" + b"\0" * 64)
    explorer = Path(os.environ.get("WINDIR", "C:\\Windows")) / "explorer.exe"
    results = signatures.check_signatures([str(unsigned), str(explorer), sys.executable])
    key = lambda p: os.path.normcase(os.path.normpath(str(p)))  # noqa: E731
    assert results[key(unsigned)].status in ("unsigned", "unknown")
    assert results[key(explorer)].status == "valid"
    assert results[key(explorer)].signer


def test_missing_files_are_ordered_small_first(tmp_path) -> None:
    big = tmp_path / "big.exe"
    small = tmp_path / "small.exe"
    big.write_bytes(b"MZ" * 5000)
    small.write_bytes(b"MZ")
    assert SignatureCache().missing([str(big), str(small)]) == [str(small), str(big)]


def test_powershell_env_drops_pwsh_module_path(monkeypatch) -> None:
    from core.winproc import powershell_env

    monkeypatch.setenv("PSModulePath", r"C:\Program Files\PowerShell\7\Modules")
    parts = [part.lower().rstrip("\\") for part in powershell_env()["PSModulePath"].split(os.pathsep)]
    assert not any("powershell\\7" in part for part in parts)
    assert any(part.endswith("windowspowershell\\v1.0\\modules") for part in parts)
