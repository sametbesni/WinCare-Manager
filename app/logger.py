from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def configure_logging(data_dir: Path) -> Path:
    log_dir = data_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "wincare.log"

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    # Günlük ayarlanmadan önce yazılan bir hata, logging'in kendi stderr işleyicisini ekleyebilir;
    # bu yüzden "işleyici var mı" yerine dosya işleyicimizin olup olmadığına bakılır.
    target = os.path.abspath(log_file)  # RotatingFileHandler.baseFilename ile aynı biçim
    has_file_handler = any(isinstance(h, RotatingFileHandler) and h.baseFilename == target for h in root.handlers)
    if not has_file_handler:
        handler = RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s"))
        root.addHandler(handler)

    def _hook(exc_type, exc, tb) -> None:
        logging.critical("Unhandled exception", exc_info=(exc_type, exc, tb))
        sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = _hook
    return log_file
