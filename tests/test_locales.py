"""Koddaki her çeviri anahtarının iki dil dosyasında da bulunduğunu doğrular."""
from __future__ import annotations

import re
import string
from pathlib import Path

from app.i18n import Translator

ROOT = Path(__file__).resolve().parent.parent
KEY_PATTERN = re.compile(r"""(?:\bt|\.tr|\bK)\(\s*["']([a-z0-9_]+)["']""")


def _keys_used_in_code() -> set[str]:
    keys: set[str] = set()
    for folder in ("app", "core", "ui", "database"):
        for path in (ROOT / folder).rglob("*.py"):
            keys.update(KEY_PATTERN.findall(path.read_text(encoding="utf-8")))
    keys.update(KEY_PATTERN.findall((ROOT / "main.py").read_text(encoding="utf-8")))
    return keys


def test_every_key_used_in_code_exists_in_both_locales() -> None:
    used = _keys_used_in_code()
    assert len(used) > 100
    for language in ("tr_TR", "en_US"):
        missing = used - set(Translator(language)._strings)
        assert not missing, f"{language} missing: {sorted(missing)}"


def test_no_unused_locale_keys() -> None:
    unused = set(Translator("tr_TR")._strings) - _keys_used_in_code()
    assert not unused, f"unused keys: {sorted(unused)}"


def test_placeholders_match_between_languages() -> None:
    tr = Translator("tr_TR")._strings
    en = Translator("en_US")._strings

    def fields(text: str) -> set[str]:
        return {name for _, name, _, _ in string.Formatter().parse(text) if name}

    for key in tr:
        assert fields(tr[key]) == fields(en[key]), key
