from __future__ import annotations

import json
from typing import Any

from app.paths import get_resource_path

LOCALES_DIR = get_resource_path("locales")
SUPPORTED_LANGUAGES = ("tr_TR", "en_US")
DEFAULT_LANGUAGE = "tr_TR"


def K(key: str) -> str:
    """Mark a string as a translation key. Returns the key unchanged.

    Used where keys are stored in tables/maps so the locale test can find them.
    """
    return key


class Translator:
    def __init__(self, language: str = DEFAULT_LANGUAGE) -> None:
        self.language = language
        self._strings: dict[str, Any] = {}
        self.set_language(language)

    def set_language(self, language: str) -> None:
        if language not in SUPPORTED_LANGUAGES:
            language = DEFAULT_LANGUAGE
        path = LOCALES_DIR / f"{language}.json"
        try:
            self._strings = json.loads(path.read_text(encoding="utf-8"))
            self.language = language
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Could not load language file: {path}") from exc

    def tr(self, key: str, **kwargs: object) -> str:
        value = self._strings.get(key, key)
        if not isinstance(value, str):
            value = str(value)
        try:
            return value.format(**kwargs)
        except (KeyError, ValueError, IndexError):
            return value
