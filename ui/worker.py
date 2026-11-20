"""Uzun süren işleri arayüzü dondurmadan arka planda çalıştırma."""
from __future__ import annotations

import logging
from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

_active: set["_Relay"] = set()


class _Relay(QObject):
    """Ana iş parçacığında yaşar; sonucu kuyruklu sinyalle ana iş parçacığına taşır."""

    finished = Signal(object, object)

    def __init__(self, on_done: Callable[[Any], None], on_error: Callable[[str], None] | None) -> None:
        super().__init__()
        self._on_done = on_done
        self._on_error = on_error
        self.finished.connect(self._deliver)

    @Slot(object, object)
    def _deliver(self, result: Any, error: object) -> None:
        _active.discard(self)
        try:
            if error is None:
                self._on_done(result)
            elif self._on_error:
                self._on_error(str(error))
        except RuntimeError:
            # Sonuç gelmeden sayfa kapatıldıysa (ör. dil değişikliği) yok say.
            logging.debug("Result receiver no longer exists.")
        finally:
            self.deleteLater()


class _Task(QRunnable):
    def __init__(self, fn: Callable[[], Any], relay: _Relay) -> None:
        super().__init__()
        self._fn = fn
        self._relay = relay

    def run(self) -> None:
        try:
            result = self._fn()
        except Exception as exc:
            logging.exception("Background task failed.")
            self._relay.finished.emit(None, exc)
        else:
            self._relay.finished.emit(result, None)


def run_async(fn: Callable[[], Any], on_done: Callable[[Any], None],
              on_error: Callable[[str], None] | None = None) -> None:
    relay = _Relay(on_done, on_error)
    _active.add(relay)
    QThreadPool.globalInstance().start(_Task(fn, relay))
