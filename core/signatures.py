"""Dosyaların dijital imza (Authenticode) bilgisi — salt okunur.

Windows'un kendi imza doğrulaması (``Get-AuthenticodeSignature``) kullanılır;
böylece dosyanın içine gömülü imzalar ile Windows sistem dosyalarının
kullandığı katalog imzaları birlikte doğrulanır. Ücretli bir servis veya ek
program veya çevrimiçi servis gerekmez.

Her dosya yalnızca bir kez denetlenir; sonuç dosyanın yolu, boyutu ve
değiştirilme zamanına göre önbellekte tutulur. Dosya değişirse yeniden denetlenir.
"""
from __future__ import annotations

import logging
import os
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path

from core.winproc import run_powershell_json

# Get-AuthenticodeSignature durumları -> uygulama durumları
_STATUS_MAP = {
    "valid": "valid",
    "notsigned": "unsigned",
    "hashmismatch": "invalid",
    "nottrusted": "untrusted",
}
STATUSES = ("valid", "unsigned", "invalid", "untrusted", "unknown")
# Kullanıcının dikkat etmesi gereken durumlar
ATTENTION = frozenset({"unsigned", "invalid", "untrusted"})

_SCRIPT = (
    "$paths = Get-Content -LiteralPath '{list}' -Encoding UTF8;"
    "$paths | Where-Object {{ $_ }} | ForEach-Object {{"
    "  $p = [string]$_;"  # Get-Content satırları ek özellik taşır; düz metne çevir
    "  try {{"
    "    $s = Get-AuthenticodeSignature -LiteralPath $p -ErrorAction Stop;"
    "    $signer = '';"
    "    if ($s.SignerCertificate) {{"
    "      $signer = $s.SignerCertificate.GetNameInfo("
    "        [System.Security.Cryptography.X509Certificates.X509NameType]::SimpleName, $false) }};"
    "    [pscustomobject]@{{ Path = $p; Status = [string]$s.Status; Signer = $signer }}"
    "  }} catch {{ [pscustomobject]@{{ Path = $p; Status = 'Error'; Signer = '' }} }}"
    "}} | ConvertTo-Json -Compress"
)


@dataclass(frozen=True)
class SignatureInfo:
    status: str   # valid, unsigned, invalid, untrusted, unknown
    signer: str = ""

    @property
    def needs_attention(self) -> bool:
        return self.status in ATTENTION


UNKNOWN = SignatureInfo("unknown")


def map_status(raw: str) -> str:
    return _STATUS_MAP.get(str(raw or "").strip().lower(), "unknown")


def parse_rows(rows: list[dict]) -> dict[str, SignatureInfo]:
    result: dict[str, SignatureInfo] = {}
    for row in rows:
        path = str(row.get("Path") or "")
        if not path:
            continue
        status = map_status(row.get("Status"))
        signer = str(row.get("Signer") or "") if status != "unsigned" else ""
        result[_key(path)] = SignatureInfo(status, signer)
    return result


def _key(path: str) -> str:
    return os.path.normcase(os.path.normpath(path))


def check_signatures(paths: list[str], timeout: int = 180) -> dict[str, SignatureInfo]:
    """Verilen dosyaların imzasını tek bir PowerShell çağrısıyla denetler."""
    paths = [p for p in dict.fromkeys(paths) if p]
    if not paths or os.name != "nt":
        return {}
    handle, name = tempfile.mkstemp(suffix=".txt", prefix="wincare_sig_")
    os.close(handle)
    list_file = Path(name)
    try:
        list_file.write_text("\n".join(paths), encoding="utf-8")
        script = _SCRIPT.format(list=str(list_file).replace("'", "''"))
        rows = run_powershell_json(script, timeout=timeout)
    finally:
        list_file.unlink(missing_ok=True)
    found = parse_rows(rows)
    # Sonuç dönmeyen yollar "bilinmiyor" olarak işaretlenir; tekrar tekrar denenmez.
    return {_key(p): found.get(_key(p), UNKNOWN) for p in paths}


def _fingerprint(path: str) -> tuple[int, int] | None:
    try:
        stat = os.stat(path)
    except OSError:
        return None
    return stat.st_size, int(stat.st_mtime)


class SignatureCache:
    """İş parçacığı güvenli imza önbelleği."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._items: dict[str, tuple[tuple[int, int] | None, SignatureInfo]] = {}

    def get(self, path: str) -> SignatureInfo | None:
        if not path:
            return None
        with self._lock:
            item = self._items.get(_key(path))
        if item is None:
            return None
        fingerprint, info = item
        if fingerprint != _fingerprint(path):
            return None  # dosya değişmiş: yeniden denetlenmeli
        return info

    def missing(self, paths: list[str]) -> list[str]:
        """Önbellekte olmayan dosyalar, küçükten büyüğe.

        İmza denetimi dosyanın tamamını okur; yüzlerce MB'lık dosyalar ilk okumada
        saniyeler sürebilir. Küçük dosyalar önce denetlenir ki liste hızla dolsun.
        "Registry", "MemCompression" gibi dosya olmayan süreç adları denetlenmez.
        """
        todo = [p for p in dict.fromkeys(paths) if p and os.path.isabs(p) and self.get(p) is None]
        return sorted(todo, key=lambda p: (_fingerprint(p) or (0, 0))[0])

    def update(self, results: dict[str, SignatureInfo], paths: list[str]) -> None:
        with self._lock:
            for path in paths:
                info = results.get(_key(path))
                if info is not None:
                    self._items[_key(path)] = (_fingerprint(path), info)

    def check_missing(self, paths: list[str], batch_size: int = 200) -> int:
        """Önbellekte olmayan dosyaları denetler; denetlenen dosya sayısını döner."""
        todo = self.missing(paths)
        for start in range(0, len(todo), batch_size):
            chunk = todo[start:start + batch_size]
            try:
                self.update(check_signatures(chunk), chunk)
            except Exception:
                logging.exception("Signature check failed.")
                self.update({_key(p): UNKNOWN for p in chunk}, chunk)
        return len(todo)


# Uygulama boyunca paylaşılan önbellek (dil değişikliğinde sayfalar yeniden kurulsa da korunur).
CACHE = SignatureCache()
