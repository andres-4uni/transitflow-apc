"""Compuerta pura A/neutro/B con identidad lógica y unión geométrica conservadora."""

from collections import deque
from dataclasses import dataclass, field
from math import hypot, isfinite

from apc.config import CountingConfig, validate_counting
from apc.counting.tripwire import CrossingEvent
from apc.models import Track


@dataclass
class _Passenger:
    logical_id: int
    track_id: int
    last_seen: float
    last_frame: int
    observations: int = 0
    stable: int = 0
    pending: int = 0
    hits: int = 0
    events: int = 0
    ids: set = field(default_factory=set)
    # Solo coordenadas y tiempos; la ventana limita la memoria por pasajero.
    history: deque = field(default_factory=lambda: deque(maxlen=6))

    @property
    def point(self):
        return self.history[-1][1]

    @property
    def motion(self):
        first, last = self.history[0][1], self.history[-1][1]
        return last[0] - first[0], last[1] - first[1]


class DualZoneCounter:
    """Confirma dos presencias exteriores; no interpola observaciones perdidas.

    timestamp es tiempo de captura/contenido, independiente del cómputo. Las
    identidades físicas se conservan como alias hasta que vence su propio TTL.
    min_zone_frames cuenta observaciones de zona: una ausencia tolerada conserva
    las presencias pendientes; no exige frames consecutivos del video.
    """

    def __init__(self, config: CountingConfig, *, diagnostic=None):
        validate_counting(config)
        if config.mode != "dual_zone":
            raise ValueError("DualZoneCounter requiere mode=dual_zone")
        self.config, self.diagnostic = config, diagnostic
        self.axis = int(config.orientation == "horizontal")
        self.reset()

    def reset(self):
        for state in getattr(self, "_states", {}).values():
            self._report(state, state.stable, "retired", "reinicio del contador",
                         retired_track_ids=sorted(state.ids | {state.track_id}))
        self._states = {}
        self._aliases = {}
        self._alias_seen = {}
        self._next_id = 1
        self._frame_index = -1
        self._seconds = None

    def _zone(self, point):
        position = point[self.axis]
        return -1 if position < self.config.zone_a_max else 1 if position > self.config.zone_b_min else 0

    def _consume(self, state, point):
        state.observations += 1
        zone = self._zone(point)
        if zone == 0 or zone == state.stable:
            state.pending = state.hits = 0
            return "none"
        state.hits = state.hits + 1 if state.pending == zone else 1
        state.pending = zone
        margin = self.config.zone_single_observation_margin
        # Una observación profunda evita exigir un segundo frame tras salir por
        # el borde; cerca de los límites se mantienen las presencias repetidas.
        deep = margin > 0 and (point[self.axis] < round(self.config.zone_a_max-margin, 10)
                              if zone == -1 else point[self.axis] > round(self.config.zone_b_min+margin, 10))
        required = 1 if deep else self.config.min_zone_frames
        if state.hits < required:
            return "none"
        if state.stable == 0:
            state.stable = zone
        elif state.observations >= self.config.min_track_frames:
            entering = (zone > state.stable) == self.config.entry_positive
            state.stable = zone
            state.events += 1
            state.pending = state.hits = 0
            return "entry" if entering else "exit"
        return "none"

    @staticmethod
    def _cosine(a, b):
        length = hypot(*a) * hypot(*b)
        return (a[0] * b[0] + a[1] * b[1]) / length if length else -1.0

    def _candidate(self, old, new):
        config = self.config
        # El fragmento nuevo necesita dirección medida; nunca se une a ciegas.
        if not old.stable or new.events or len(new.history) < 2 or new.observations > len(new.history):
            return None
        first_seconds, first_point = new.history[0]
        gap = first_seconds - old.last_seen
        if not 0 < gap <= config.max_missing_seconds + 1e-9:
            return None
        low = config.zone_a_max - config.stitch_boundary_margin
        high = config.zone_b_min + config.stitch_boundary_margin
        if not (low <= old.point[self.axis] <= high and low <= first_point[self.axis] <= high):
            return None
        old_motion, new_motion = old.motion, new.motion
        displacement = tuple(b - a for a, b in zip(old.point, first_point))
        distance = hypot(*displacement)
        # Avance hacia la otra zona y continuidad angular de ambos fragmentos.
        sign = -old.stable
        if (old_motion[self.axis] * sign < config.stitch_min_motion or
                new_motion[self.axis] * sign < config.stitch_min_motion or
                displacement[self.axis] * sign <= 0 or distance > config.stitch_max_distance):
            return None
        cosine = min(self._cosine(old_motion, new_motion), self._cosine(old_motion, displacement))
        if cosine < config.stitch_min_cosine:
            return None
        return dict(distance=distance, gap_seconds=gap, direction_cosine=cosine,
                    from_track_id=old.track_id, to_track_id=new.track_id,
                    from_logical_id=old.logical_id, provisional_logical_id=new.logical_id)

    def update(self, tracks: list[Track], *, timestamp: float | None = None) -> list[CrossingEvent]:
        if timestamp is None or not isfinite(timestamp) or (self._seconds is not None and timestamp < self._seconds):
            raise ValueError("Compuerta requiere timestamps finitos y crecientes")
        seen = set()
        for track in tracks:
            if track.track_id in seen:
                raise ValueError("ID duplicado en una misma observación")
            if not all(isfinite(v) and 0 <= v <= 1 for v in track.centroid):
                raise ValueError("Centroide debe estar normalizado y ser finito")
            seen.add(track.track_id)
        self._seconds = timestamp
        self._frame_index += 1
        for key, state in list(self._states.items()):
            if timestamp - state.last_seen > self.config.max_missing_seconds + 1e-9:
                self._report(state, state.stable, "expired", "caducó TTL",
                             gap_seconds=timestamp-state.last_seen,
                             missing=self._frame_index-state.last_frame,
                             retired_track_ids=sorted(state.ids | {state.track_id}))
                del self._states[key]
                for alias in state.ids:
                    self._aliases.pop(alias, None)
                    self._alias_seen.pop(alias, None)
        # Un pasajero activo no retiene indefinidamente IDs físicos antiguos.
        for alias, last_seen in list(self._alias_seen.items()):
            if timestamp-last_seen > self.config.max_missing_seconds + 1e-9:
                key = self._aliases.pop(alias)
                state = self._states[key]
                self._report(state, state.stable, "retired", "caducó alias físico",
                             retired_track_ids=[alias])
                state.ids.discard(alias)
                del self._alias_seen[alias]

        events, observed = [], {}
        # Si reaparecen simultáneamente dos alias, usar solo el ID activo.
        for track in sorted(tracks, key=lambda t: t.track_id):
            key = self._aliases.get(track.track_id)
            state = self._states.get(key)
            rejection = None
            if state is not None and state.track_id != track.track_id and state.track_id in seen:
                self._alias_seen[track.track_id] = timestamp
                self._report(state, state.stable, "ambiguous", "alias simultáneos; sin actualización", alias=track.track_id)
                continue
            if state is not None and state.track_id != track.track_id:
                distance = hypot(*(b-a for a,b in zip(state.point, track.centroid)))
                if distance > self.config.stitch_max_distance:
                    # ByteTrack puede asignar un alias anterior a otra persona.
                    # No heredar historia por ID si contradice la unión geométrica.
                    rejection = dict(previous_logical_id=key, distance=distance,
                                     previous_track_id=state.track_id, reappearing_track_id=track.track_id)
                    state.ids.discard(track.track_id)
                    del self._aliases[track.track_id]
                    self._alias_seen.pop(track.track_id, None)
                    state = None
            if state is None:
                key = self._next_id
                self._next_id += 1
                state = _Passenger(key, track.track_id, timestamp, self._frame_index, ids={track.track_id})
                self._states[key] = state
                self._aliases[track.track_id] = key
            self._alias_seen[track.track_id] = timestamp
            if key in observed:
                continue
            previous = state.stable
            gap = timestamp - state.last_seen
            missing = max(0, self._frame_index - state.last_frame - 1)
            state.track_id = track.track_id
            event = self._consume(state, track.centroid)
            state.history.append((timestamp, track.centroid))
            state.last_seen, state.last_frame = timestamp, self._frame_index
            observed[key] = dict(state=state, previous=previous, event=event,
                                 gap_seconds=gap, missing=missing)
            if rejection is not None:
                observed[key]['alias_rejection'] = rejection

        if self.config.stitching:
            lost = [s for key, s in self._states.items() if key not in observed and not s.ids & seen]
            candidates = []
            for key, observation in observed.items():
                new = observation["state"]
                for old in lost:
                    detail = self._candidate(old, new)
                    if detail is not None:
                        candidates.append((detail["distance"], old.logical_id, key, detail))
            # Asignación mutua y margen frente al segundo candidato en ambos lados.
            # Orden de detecciones e IDs no decide asociaciones ambiguas.
            matches = []
            for item in candidates:
                distance, old_key, new_key, detail = item
                competitors = [c[0] for c in candidates if c is not item and (c[1] == old_key or c[2] == new_key)]
                if competitors and min(competitors) <= distance + self.config.stitch_ambiguity_margin:
                    continue
                matches.append(item)
            for _, old_key, new_key, detail in matches:
                old, new = self._states[old_key], self._states[new_key]
                previous = old.stable
                event = "none"
                # Reproducir solo el fragmento breve aún sin eventos; conserva A/B
                # del pasajero original y la presencia medida en el fragmento nuevo.
                for seconds, point in new.history:
                    current = self._consume(old, point)
                    if current != "none":
                        event = current
                    old.history.append((seconds, point))
                old.ids.update(new.ids)
                for alias in new.ids:
                    self._aliases[alias] = old_key
                old.track_id, old.last_seen, old.last_frame = new.track_id, timestamp, self._frame_index
                del self._states[new_key]
                del observed[new_key]
                observed[old_key] = dict(state=old, previous=previous, event=event,
                                        gap_seconds=detail["gap_seconds"], missing=0, stitch=detail,
                                        retired_track_ids=[detail["from_track_id"]])

        for observation in observed.values():
            state = observation.pop("state")
            event = observation["event"]
            if event != "none":
                events.append(CrossingEvent(state.track_id, event, self._frame_index, state.logical_id))
            reason = "cruce de zonas confirmado" if event != "none" else "presencia de zona; falta transición"
            self._report(state, observation.pop("previous"), self._zone(state.point), reason, **observation)
        return events

    def _report(self, state, previous, position, reason, *, event="none", missing=0,
                gap_seconds=0.0, **details):
        if self.diagnostic is not None:
            motion = state.motion
            delta = motion[self.axis]
            movement = (("down" if self.axis else "right") if delta > 0 else
                        ("up" if self.axis else "left") if delta < 0 else "still")
            self.diagnostic(dict(frame=self._frame_index, track_id=state.track_id,
                logical_id=state.logical_id, age=state.observations, point=state.point,
                position=position, previous=previous, current=state.stable,
                movement=movement, event=event, reason=reason, missing=missing,
                gap_seconds=gap_seconds, orientation=self.config.orientation, **details))
