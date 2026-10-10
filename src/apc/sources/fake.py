"""Escena artificial en RAM, sin cámara, archivo de video ni modelo detector."""

from threading import Event
from time import perf_counter, time

import numpy as np

from apc.config import Config
from apc.models import Track
from apc.sources.base import FramePacket, VideoSource


class FakeTracksSource(VideoSource):
    def __init__(self, config: Config, *, realtime: bool = True):
        self.config = config
        self.realtime = realtime
        self.cycle_frames = round(config.simulation.fake_cycle_seconds * config.simulation.fake_fps)
        if config.counting.mode == "dual_zone":
            # Reservar observaciones en ambos extremos incluso con zonas estrechas.
            self._hold = max(config.counting.min_zone_frames, config.counting.min_track_frames)
            self.cycle_frames = max(self.cycle_frames, 4 * self._hold + 2)
        self._stop = Event()
        self._opened = False
        self._index = 0

    def open(self) -> None:
        if self._opened or self._stop.is_set():
            raise RuntimeError("Cree una nueva fuente para otra sesión simulada")
        self._opened = True
        self._start = perf_counter()

    def read(self) -> FramePacket | None:
        if not self._opened:
            raise RuntimeError("Abra la fuente antes de leer")
        if self.realtime:
            delay = self._start + self._index / self.config.simulation.fake_fps - perf_counter()
            self._stop.wait(max(0, delay))
        if self._stop.is_set():
            return None
        frame = np.full((self.config.source.height, self.config.source.width, 3),
                        (30, 35, 42), dtype=np.uint8)
        packet = FramePacket(self._index, time(), frame)
        self._index += 1
        return packet

    def tracks(self, index: int) -> list[Track]:
        """Dos IDs nuevos por ciclo: primero entrada, después salida."""
        cycle, offset = divmod(index, self.cycle_frames)
        phase = offset / (self.cycle_frames - 1)
        counting = self.config.counting
        low = (counting.position - counting.band_half_width) / 2
        high = (1 + counting.position + counting.band_half_width) / 2
        if counting.mode == "dual_zone":
            low, high = counting.zone_a_max / 2, (1 + counting.zone_b_min) / 2
        outside, inside = (low, high) if counting.entry_positive else (high, low)
        tracks = []
        progressions = (min(1, phase / 0.6), max(0, min(1, (phase - 0.2) / 0.6)))
        if counting.mode == "dual_zone":
            travel = (self.cycle_frames - 4 * self._hold) // 2
            progressions = tuple(max(0, min(1, (offset - start) / travel))
                                 for start in (self._hold, 2 * self._hold + travel))
        for person, progress in enumerate(progressions):
            start, end = (outside, inside) if person == 0 else (inside, outside)
            position = start + progress * (end - start)
            lane = 0.32 if person == 0 else 0.68
            x, y = (lane, position) if counting.orientation == "horizontal" else (position, lane)
            tracks.append(Track(cycle * 2 + person + 1, (x, y),
                                (max(0, x - 0.06), max(0, y - 0.09),
                                 min(1, x + 0.06), min(1, y + 0.09))))
        return tracks

    def close(self) -> None:
        self._stop.set()
