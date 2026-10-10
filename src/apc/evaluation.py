"""Evaluación numérica de conteos y transiciones; nunca recibe imágenes en el informe."""

from time import perf_counter

from apc.counting.occupancy import OccupancyCounter
from apc.counting.factory import create_counter, update_counter, configure_detector_clock
from apc.counting.debug import CountingDebug
from apc.sources.validation import validate_frame_count


class EvaluationDiagnostics:
    """Resumen por ID y transiciones, sin mensajes por frame ni cajas persistentes."""

    def __init__(self, counting):
        self.counting = counting
        self.events = []
        self.expirations = []
        self.transitions = []
        self.ids = {}
        self.raw_ids = set()
        self.stitches = []
        self.ambiguities = []
        self.alias_rejections = []
        self.frame = 0
        self.seconds = 0.0
        self.border_ids = set()
        self.detections = self.detection_frames = self.track_observations = self.track_frames = 0
        self.area_rejections = self.low_confidence_detections = 0
        self.timestamp_fallback_frames = 0

    def observe(self, packet, tracks, detector, fps):
        self.frame = packet.index
        self.seconds = getattr(packet, "media_seconds", None)
        if self.seconds is None:
            self.timestamp_fallback_frames += 1
            self.seconds = packet.index / fps if fps > 0 else None
        stats = getattr(detector, "last_diagnostics", {})
        count = stats.get("person_detections", 0)
        self.detections += count
        self.detection_frames += bool(count)
        self.low_confidence_detections += stats.get("low_confidence_detections", 0)
        self.area_rejections += stats.get("area_rejections", 0)
        self.track_observations += len(tracks)
        self.raw_ids.update(t.track_id for t in tracks)
        self.track_frames += bool(tracks)
        self.border_ids = {t.track_id for t in tracks if t.bbox and
                           (min(t.bbox[:2]) <= 0.01 or max(t.bbox[2:]) >= 0.99)}

    def __call__(self, row):
        if row["position"] == "retired":
            # Es ciclo de vida diagnóstico, no otra observación/expiración del pasajero.
            return
        key = row.get("logical_id", row["track_id"])
        summary = self.ids.setdefault(key, {"track_id": row["track_id"], "first_frame": self.frame,
            "last_frame": self.frame, "observations": 0, "max_gap_frames": 0,
            "border_observations": 0, "events": 0, "expirations": 0,
            "min_anchor": list(row["point"]), "max_anchor": list(row["point"])})
        detail = {"frame": self.frame, "processed_frame": row["frame"],
                  "video_seconds": self.seconds, "track_id": row["track_id"], "anchor": row["point"],
                  "age_observations": row["age"], "from_side": row["previous"],
                  "to_side": row["current"], "zone": row["position"],
                  "missing_frames": row["missing"], "reason": row["reason"]}
        if "logical_id" in row:
            detail.update(logical_id=key, gap_seconds=row["gap_seconds"])
            summary["logical_id"] = key
            summary.setdefault("track_ids", [])
            if row["track_id"] not in summary["track_ids"]:
                summary["track_ids"].append(row["track_id"])
        if "stitch" in row:
            self.stitches.append({**detail, **row["stitch"]})
            # El estado provisional ya aportó observaciones: consolidar su resumen
            # numérico evita inflar el número de pasajeros lógicos en el informe.
            provisional = self.ids.pop(row["stitch"]["provisional_logical_id"], None)
            if provisional:
                for field in ("observations", "border_observations", "events", "expirations"):
                    summary[field] += provisional[field]
                summary["track_ids"] = sorted(set(summary["track_ids"] + provisional.get("track_ids", [])))
                summary["min_anchor"] = [min(a,b) for a,b in zip(summary["min_anchor"], provisional["min_anchor"])]
                summary["max_anchor"] = [max(a,b) for a,b in zip(summary["max_anchor"], provisional["max_anchor"])]
                summary["max_gap_frames"] = max(summary["max_gap_frames"], provisional["max_gap_frames"],
                                               provisional['first_frame'] - summary['last_frame'] - 1)
                summary["last_frame"] = provisional['last_frame']
        if 'alias_rejection' in row:
            self.alias_rejections.append({**detail, **row['alias_rejection']})
        if row["position"] == "ambiguous":
            self.ambiguities.append(detail)
            return
        if row["position"] == "expired":
            summary["expirations"] += 1
            self.expirations.append({**detail, "last_observed_frame": summary["last_frame"],
                                     "last_observed_at_border": summary.get("last_at_border", False)})
            return
        if row["position"] == "missing":
            return
        gap = self.frame - summary["last_frame"] - 1 if summary["observations"] else 0
        summary["max_gap_frames"] = max(summary["max_gap_frames"], gap)
        detail["recent_gap_source_frames"] = gap
        summary["observations"] += 1
        summary["last_frame"] = self.frame
        summary["last_at_border"] = row["track_id"] in self.border_ids
        summary["border_observations"] += row["track_id"] in self.border_ids
        summary["min_anchor"] = [min(a, b) for a, b in zip(summary["min_anchor"], row["point"])]
        summary["max_anchor"] = [max(a, b) for a, b in zip(summary["max_anchor"], row["point"])]
        signature = (row["position"], row["current"], row["reason"])
        if signature != summary.get("signature"):
            self.transitions.append(detail)
        summary["signature"] = signature
        if row["event"] != "none":
            summary["events"] += 1
            self.events.append({**detail, "direction": "in" if row["event"] == "entry" else "out"})

    def report(self):
        ids = [{k: v for k, v in row.items() if k != "signature"} for row in self.ids.values()]
        axis = 1 if self.counting.orientation == "horizontal" else 0
        low = self.counting.position - self.counting.band_half_width
        high = self.counting.position + self.counting.band_half_width
        if self.counting.mode == "dual_zone":
            low, high = self.counting.zone_a_max, self.counting.zone_b_min
        possible = [r for r in ids if not r["events"] and r["expirations"] and
                    (r["min_anchor"][axis] < low and r["max_anchor"][axis] > high)]
        return {"person_detections": self.detections, "person_detection_frames": self.detection_frames,
                "low_confidence_detections": self.low_confidence_detections,
                "track_observations": self.track_observations, "track_frames": self.track_frames,
                "area_rejections": self.area_rejections, "unique_ids": len(self.raw_ids),
                "logical_passengers": len(ids), "stitches": self.stitches, "ambiguous_aliases": self.ambiguities,
                "alias_rejections": self.alias_rejections,
                "events": self.events, "expirations": self.expirations, "transitions": self.transitions,
                "ids": ids, "possible_missed_crossings": possible,
                "unconfirmed_tracks": [r for r in ids if not r['events']],
                "candidate_basis": "Same ID observed on both external sides, no event, expired; visual audit required",
                "timestamp_basis": "OpenCV media time; source frame / FPS fallback when unavailable",
                "timestamp_fallback_frames": self.timestamp_fallback_frames,
                "id_switches": "Candidates require local visual matching; different IDs alone do not prove a switch"}


def count_error(observed: int, expected: int) -> dict:
    if min(observed, expected) < 0:
        raise ValueError("Los conteos no pueden ser negativos")
    absolute = abs(observed - expected)
    return {"expected": expected, "observed": observed, "absolute_error": absolute,
            "error_percent": 100 * absolute / expected if expected else (0.0 if not absolute else None)}


def evaluate(config, source, detector, *, expected_in: int, expected_out: int,
             diagnostics: bool = False, verified_frames: int | None = None) -> dict:
    """Una pasada completa, sin calentamiento descartado ni reproducción en bucle."""
    if min(expected_in, expected_out) < 0:
        raise ValueError("La referencia manual no puede ser negativa")
    if getattr(source, "loop", False):
        raise ValueError("La evaluación debe usar una sola pasada")
    if verified_frames is not None and verified_frames <= 0:
        raise ValueError("La referencia de frames verificada debe ser positiva")
    report = EvaluationDiagnostics(config.counting) if diagnostics else None
    debug = CountingDebug() if config.debug.counting else None
    def observe(row):
        if report is not None:
            report(row)
        if debug is not None:
            debug(row)
    counter = create_counter(config.counting, diagnostic=observe if diagnostics or debug else None)
    occupancy = OccupancyCounter(config.occupancy)
    processed = decoded = 0
    start = perf_counter()
    detector.reset()
    with source:
        configure_detector_clock(detector, source)
        for packet in source:
            decoded += 1
            if packet.index % config.detection.vid_stride:
                continue
            tracks = detector.detect(packet.frame)
            if report is not None:
                report.observe(packet, tracks, detector, getattr(source, "metadata", {}).get("fps", 0))
            occupancy.apply(update_counter(counter, tracks, packet, source))
            processed += 1
    if not processed:
        raise RuntimeError("El video no entregó frames para evaluar")
    elapsed = perf_counter() - start
    declared = getattr(source, "metadata", {}).get("frames", 0)
    frame_validation = validate_frame_count(verified_frames if verified_frames is not None else declared, decoded)
    if verified_frames is not None:
        frame_validation.update(container_declared=declared, container_difference=decoded - declared,
                                reference="independently verified reproducible frames")
    entries = count_error(occupancy.entries, expected_in)
    exits = count_error(occupancy.exits, expected_out)
    denominator = expected_in + expected_out
    absolute = entries["absolute_error"] + exits["absolute_error"]
    result = {"decoded_frames": decoded, "processed_frames": processed,
            "source_metadata": dict(getattr(source, "metadata", {})),
            "frame_validation": frame_validation,
            "elapsed_seconds": elapsed, "fps": processed / elapsed,
            "in": entries, "out": exits, "absolute_error_sum": absolute,
            "error_percent_combined": 100 * absolute / denominator if denominator else
            (0.0 if not absolute else None), "occupancy": occupancy.occupancy}
    if report is not None:
        result["diagnostics"] = report.report()
    return result
