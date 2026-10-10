"""Contrato de captura y lectura ordenada en un hilo separado."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from queue import Empty, Full, Queue
from threading import Event, Thread
from time import time
from typing import Iterator

import numpy as np


@dataclass(frozen=True)
class FramePacket:
    index: int
    timestamp: float
    frame: np.ndarray
    cycle: int = 0
    capture_ms: float = 0.0
    # Tiempo del contenido para evaluar archivos; timestamp sigue siendo Unix.
    media_seconds: float | None = None


class VideoSource(ABC):
    @abstractmethod
    def open(self) -> None: ...

    @abstractmethod
    def read(self) -> FramePacket | None: ...

    @abstractmethod
    def close(self) -> None: ...

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *_):
        self.close()

    def __iter__(self) -> Iterator[FramePacket]:
        while (packet := self.read()) is not None:
            yield packet


class ThreadedSource(VideoSource):
    """Cola acotada: no acumula un video completo en memoria."""

    def __init__(self, queue_size: int = 2, *, live: bool = False, close_timeout: float = 5):
        if queue_size < 1:
            raise ValueError("queue_size debe ser positivo")
        self._queue: Queue = Queue(maxsize=queue_size)
        self._stop = Event()
        self._thread: Thread | None = None
        self._ended = False
        self._live = live
        self._close_timeout = close_timeout
        self.metadata = {}

    @abstractmethod
    def _open_capture(self): ...

    def open(self) -> None:
        if self._thread is not None or self._stop.is_set():
            raise RuntimeError("La fuente ya fue abierta; cree otra instancia")
        capture = self._open_capture()
        if self._live:
            import cv2
            self.metadata["fps"] = capture.get(cv2.CAP_PROP_FPS)
        self._thread = Thread(target=self._capture, args=(capture,), daemon=True)
        self._thread.start()

    def _put(self, value) -> None:
        recent_frame = self._live and isinstance(value, FramePacket)
        while not self._stop.is_set():
            try:
                if recent_frame:
                    self._queue.put_nowait(value)
                else:
                    # Archivo y señales de control mantienen orden y backpressure.
                    self._queue.put(value, timeout=0.1)
                return
            except Full:
                if recent_frame:
                    # Inspección/retiro atómicos: el consumidor puede vaciar la
                    # cola entre put_nowait y este lock. Nunca retirar error/fin.
                    with self._queue.not_full:
                        if self._queue.queue:
                            if isinstance(self._queue.queue[0], FramePacket):
                                self._queue._get()
                                self._queue.unfinished_tasks -= 1
                                self._queue.not_full.notify()
                            else:
                                self._queue.not_full.wait(timeout=0.1)
                continue

    def _capture(self, capture) -> None:
        try:
            index = 0
            while not self._stop.is_set():
                ok, frame = capture.read()
                if not ok:
                    if self._live and not self._stop.is_set():
                        self._put(RuntimeError("La fuente en vivo se desconectó o agotó su tiempo de lectura"))
                    break
                self._put(FramePacket(index, time(), frame))
                index += 1
        except Exception:
            # Evitar mensajes del backend que podrían contener credenciales de una URL.
            self._put(RuntimeError("Falló la lectura de la fuente de video"))
        finally:
            capture.release()
            self._put(None)

    def read(self) -> FramePacket | None:
        if self._thread is None:
            raise RuntimeError("Abra la fuente antes de leer")
        if self._ended or self._stop.is_set():
            return None
        while not self._stop.is_set():
            try:
                value = self._queue.get(timeout=0.1)
                if isinstance(value, Exception):
                    raise value
                if value is None:
                    self._ended = True
                return value
            except Empty:
                continue
        return None

    def close(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=self._close_timeout)
            if self._thread.is_alive():
                raise RuntimeError("El backend de captura no respondió al cierre")
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except Empty:
                break
