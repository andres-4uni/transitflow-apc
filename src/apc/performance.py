"""Métricas optativas de fuentes vivas; conserva solo acumuladores numéricos."""

from math import isfinite


class LiveMetrics:
    def __init__(self):
        self.first_index = self.last_index = None
        self.first_timestamp = self.last_timestamp = None
        self.started = self.ended = None
        self.delivered = self.inferences = 0
        self.capture_valid = True
        self._sums = {"inference": 0.0, "tracking": 0.0}
        self._counts = {key: 0 for key in self._sums}

    def received(self, packet, now: float) -> None:
        # index cuenta todos los frames decodificados, incluso los reemplazados
        # en la cola live. Los timestamps se asignan en el hilo de captura.
        if self.first_index is None:
            self.first_index = packet.index
            self.first_timestamp = packet.timestamp
            self.started = now
        elif packet.index <= self.last_index or packet.timestamp <= self.last_timestamp:
            self.capture_valid = False
        if not isfinite(packet.timestamp):
            self.capture_valid = False
        self.last_index, self.last_timestamp = packet.index, packet.timestamp
        self.delivered += 1

    def inferred(self, timings: dict, now: float) -> None:
        self.inferences += 1
        self.ended = now
        for key in self._sums:
            value = timings.get(key)
            if isinstance(value, (int, float)) and isfinite(value) and value >= 0:
                self._sums[key] += value
                self._counts[key] += 1

    def snapshot(self) -> dict:
        span = 0 if self.first_index is None else self.last_index - self.first_index + 1
        capture_fps = None
        if self.capture_valid and span > 1:
            seconds = self.last_timestamp - self.first_timestamp
            if seconds > 0:
                capture_fps = (span - 1) / seconds
        seconds = 0 if self.ended is None or self.started is None else self.ended - self.started
        means = {key: round(self._sums[key] / self._counts[key], 3) if self._counts[key] else None
                 for key in self._sums}
        return {"capture_fps": round(capture_fps, 2) if capture_fps is not None else None,
                "inference_fps": round(self.inferences / seconds, 2) if seconds > 0 else 0.0,
                "yolo_inference_ms_mean": means["inference"],
                "bytetrack_ms_mean": means["tracking"],
                "received_frame_span": max(0, span), "delivered_frames": self.delivered,
                "inference_frames": self.inferences,
                "queue_replacements": max(0, span - self.delivered),
                "stride_skipped_frames": self.delivered - self.inferences}
