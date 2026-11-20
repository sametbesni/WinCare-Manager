from __future__ import annotations

from dataclasses import dataclass

from app.config_manager import ConfigManager
from app.i18n import Translator
from core.backup import BackupStore
from core.engine import OperationEngine
from database.history import HistoryStore


@dataclass
class AppContext:
    """Sayfaların paylaştığı servisler."""

    config: ConfigManager
    translator: Translator
    history: HistoryStore
    backups: BackupStore
    engine: OperationEngine

    @classmethod
    def create(cls, config: ConfigManager) -> "AppContext":
        history = HistoryStore(config.history_db)
        return cls(
            config=config,
            translator=Translator(str(config.get("language"))),
            history=history,
            backups=BackupStore(config.backups_dir),
            engine=OperationEngine(history),
        )

    def t(self, key: str, **kwargs: object) -> str:
        return self.translator.tr(key, **kwargs)

    @property
    def dry_run(self) -> bool:
        return bool(self.config.get("dry_run", True))
