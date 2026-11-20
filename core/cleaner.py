"""Gereksiz dosya analizi ve güvenlik doğrulaması.

Kurallar:
- Yalnızca kullanıcıya ait geçici klasörler taranır; Windows klasörleri kapsam dışıdır.
- Sembolik bağlantılar, junction ve diğer reparse point'ler izlenmez.
- Belirlenen yaştan yeni dosyalar listelenmez.
- Bu modül dosya silmez; silme işlemi doğrulamadan sonra işlem motoru
  tarafından ve Geri Dönüşüm Kutusu'na taşınarak yapılır.
"""
from __future__ import annotations

import os
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ScanTarget:
    path: Path
    category: str  # çeviri anahtarı soneki: "temp", "crash_dumps", "wer"


@dataclass(frozen=True)
class FileCandidate:
    path: str
    size: int
    modified_timestamp: float
    category: str = "temp"


@dataclass(frozen=True)
class ScanResult:
    files: tuple[FileCandidate, ...]
    total_bytes: int
    skipped: int


def default_scan_targets() -> list[ScanTarget]:
    candidates = [ScanTarget(Path(tempfile.gettempdir()), "temp")]
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidates += [
            ScanTarget(Path(local) / "Temp", "temp"),
            ScanTarget(Path(local) / "CrashDumps", "crash_dumps"),
            ScanTarget(Path(local) / "Microsoft" / "Windows" / "WER" / "ReportArchive", "wer"),
        ]
    targets: list[ScanTarget] = []
    seen: set[str] = set()
    for target in candidates:
        try:
            resolved = target.path.resolve(strict=True)
        except OSError:
            continue
        key = os.path.normcase(str(resolved))
        if resolved.is_dir() and key not in seen and not is_protected(resolved):
            targets.append(ScanTarget(resolved, target.category))
            seen.add(key)
    return targets


def default_scan_roots() -> list[Path]:
    return [target.path for target in default_scan_targets()]


def protected_roots() -> list[Path]:
    roots = []
    for var in ("WINDIR", "SystemRoot", "ProgramFiles", "ProgramFiles(x86)", "ProgramData"):
        value = os.environ.get(var)
        if value:
            try:
                roots.append(Path(value).resolve())
            except OSError:
                pass
    return roots


def _is_within(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def is_protected(path: Path) -> bool:
    return any(_is_within(path, root) for root in protected_roots())


def _is_reparse_or_link(path: Path, stat_result: os.stat_result) -> bool:
    if path.is_symlink():
        return True
    attributes = getattr(stat_result, "st_file_attributes", 0)
    return bool(attributes & 0x400)  # FILE_ATTRIBUTE_REPARSE_POINT


def scan_temporary_files(
    roots: list[Path] | list[ScanTarget] | None = None,
    older_than_seconds: int = 24 * 60 * 60,
    max_files: int = 10000,
    max_entries: int = 50000,
) -> ScanResult:
    """Build a dry-run list only. No files are deleted or modified."""
    if roots is None:
        targets = default_scan_targets()
    else:
        targets = [r if isinstance(r, ScanTarget) else ScanTarget(Path(r), "temp") for r in roots]
    now = time.time()
    candidates: list[FileCandidate] = []
    skipped = 0
    inspected = 0

    for target in targets:
        try:
            canonical_root = target.path.resolve(strict=True)
            if not canonical_root.is_dir():
                skipped += 1
                continue
        except OSError:
            skipped += 1
            continue

        for current, dirs, files in os.walk(canonical_root, topdown=True, followlinks=False):
            current_path = Path(current)
            safe_dirs: list[str] = []
            for dirname in dirs:
                child = current_path / dirname
                try:
                    if _is_reparse_or_link(child, child.lstat()):
                        skipped += 1
                        continue
                    if _is_within(child.resolve(strict=True), canonical_root):
                        safe_dirs.append(dirname)
                    else:
                        skipped += 1
                except OSError:
                    skipped += 1
            dirs[:] = safe_dirs

            for filename in files:
                inspected += 1
                if len(candidates) >= max_files or inspected > max_entries:
                    skipped += 1
                    return ScanResult(tuple(candidates), sum(c.size for c in candidates), skipped)
                path = current_path / filename
                try:
                    info = path.lstat()
                    if _is_reparse_or_link(path, info) or not path.is_file():
                        skipped += 1
                        continue
                    resolved = path.resolve(strict=True)
                    if not _is_within(resolved, canonical_root):
                        skipped += 1
                        continue
                    if now - info.st_mtime < older_than_seconds:
                        continue
                    candidates.append(FileCandidate(str(resolved), int(info.st_size), float(info.st_mtime),
                                                    target.category))
                except OSError:
                    skipped += 1

    return ScanResult(tuple(candidates), sum(c.size for c in candidates), skipped)


@dataclass(frozen=True)
class ValidationReport:
    valid: tuple[Path, ...]
    missing: tuple[str, ...]
    violations: tuple[str, ...]


def validate_targets(paths: list[str], roots: list[Path] | None = None) -> ValidationReport:
    """Güvenlik kontrolü: yalnızca izin verilen klasörlerdeki normal dosyalar geçer.

    - Artık var olmayan dosyalar ``missing`` listesine alınır (sorun değildir).
    - İzin verilen klasör dışı, korumalı klasör içi, bağlantı/reparse point
      olan yollar ``violations`` listesine alınır ve işlemi engeller.
    """
    allowed = [r.resolve() for r in (roots if roots is not None else default_scan_roots())]
    valid: list[Path] = []
    missing: list[str] = []
    violations: list[str] = []
    for raw in paths:
        path = Path(raw)
        try:
            info = path.lstat()
        except FileNotFoundError:
            missing.append(raw)
            continue
        except OSError:
            violations.append(raw)
            continue
        try:
            resolved = path.resolve(strict=True)
        except OSError:
            missing.append(raw)
            continue
        if (
            _is_reparse_or_link(path, info)
            or not path.is_file()
            or not any(_is_within(resolved, root) for root in allowed)
            or is_protected(resolved)
        ):
            violations.append(raw)
            continue
        valid.append(resolved)
    return ValidationReport(tuple(valid), tuple(missing), tuple(violations))
