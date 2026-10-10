"""Esquema de telemetría: no admite imágenes, rostros ni IDs de personas."""

from dataclasses import asdict, dataclass
from math import isfinite
from threading import Lock
from time import time

from apc.counting.occupancy import OccupancyCounter


@dataclass(frozen=True)
class TelemetrySample:
    wagon_id: int
    entries: int
    exits: int
    initial_occupancy: int
    occupancy: int
    capacity: int
    level: int  # 0 = verde, 1 = amarillo, 2 = rojo.
    timestamp: float  # Segundos Unix del último frame procesado.
    fps: float
    simulated: int = 0
    # -1/-1 indica un consumidor/productor anterior que no informa umbrales.
    green_below: float = -1.0
    red_above: float = -1.0

    def __post_init__(self):
        integer_values = (self.wagon_id, self.entries, self.exits, self.initial_occupancy,
                          self.occupancy, self.capacity, self.level, self.simulated)
        if any(type(value) is not int or value < 0 for value in integer_values):
            raise ValueError("La telemetría requiere enteros no negativos")
        if self.wagon_id < 1 or self.capacity < 1 or self.level not in (0, 1, 2) or self.simulated not in (0, 1):
            raise ValueError("Vagón, capacidad, nivel o simulación inválidos")
        for value in (self.timestamp, self.fps):
            if type(value) not in (int, float) or not isfinite(value) or value < 0:
                raise ValueError("Timestamp o FPS inválidos")
        thresholds = (self.green_below, self.red_above)
        if any(type(value) not in (int, float) or not isfinite(value) for value in thresholds):
            raise ValueError("Umbrales de telemetría inválidos")
        if thresholds != (-1, -1):
            if not 0 <= self.green_below < self.red_above <= 1:
                raise ValueError("Umbrales de telemetría inválidos")
            ratio = self.occupancy / self.capacity
            expected = 0 if ratio < self.green_below else 2 if ratio > self.red_above else 1
            if self.level != expected:
                raise ValueError("Nivel incompatible con los umbrales del productor")
        if self.occupancy != max(0, self.initial_occupancy + self.entries - self.exits):
            raise ValueError("Saldo de ocupación inconsistente")


def make_sample(wagon_id: int, counter: OccupancyCounter, fps: float,
                *, timestamp: float | None = None, simulated: bool = False) -> TelemetrySample:
    return TelemetrySample(wagon_id, counter.entries, counter.exits, counter.initial,
                           counter.occupancy, counter.config.capacity,
                           {"green": 0, "yellow": 1, "red": 2}[counter.color],
                           time() if timestamp is None else timestamp, fps, int(simulated),
                           counter.config.green_below, counter.config.red_above)


class TelemetryStore:
    """Última muestra por vagón, con copia atómica y sin persistencia."""

    def __init__(self):
        self._samples: dict[int, TelemetrySample] = {}
        self._lock = Lock()

    def publish(self, sample: TelemetrySample) -> None:
        if not isinstance(sample, TelemetrySample):
            raise TypeError("Solo se aceptan muestras numéricas validadas")
        with self._lock:
            previous = self._samples.get(sample.wagon_id)
            if previous is None or sample.timestamp >= previous.timestamp:
                self._samples[sample.wagon_id] = sample

    def snapshot(self) -> dict:
        with self._lock:
            return {"timestamp": time(),
                    "wagons": [asdict(self._samples[key]) for key in sorted(self._samples)]}
