"""Demo APC: cámara/archivo o --fake-tracks; vista local opcional por YAML."""

import argparse
import json
import sys
from dataclasses import replace
from time import perf_counter

import cv2

from apc.config import load_config
from apc.calibration import CalibrationSession
from apc.counting.occupancy import OccupancyCounter
from apc.counting.factory import create_counter, update_counter, configure_detector_clock
from apc.counting.debug import CountingDebug
from apc.detection.detector import PersonDetector
from apc.performance import LiveMetrics
from apc.publisher.server import TelemetryPublisher
from apc.publisher.telemetry import TelemetryStore, make_sample
from apc.publisher.video import LatestFrame
from apc.sources import create_source
from apc.sources.fake import FakeTracksSource
from apc.visualization.overlay import TrackTrails, draw_overlay


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/default.yaml")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--counting-debug", action="store_true", help="Diagnóstico textual; no activa video")
    parser.add_argument("--fake-tracks", action="store_true", help="Cruces artificiales sin YOLO, cámara ni videos")
    parser.add_argument("--max-frames", type=int, default=0, help="0: hasta finalizar")
    parser.add_argument("--realtime", action="store_true", help="Limitar archivos a su FPS original")
    parser.add_argument("--loop", action="store_true", help="Repetir archivo; reinicia conteos en cada vuelta")
    parser.add_argument("--metrics", action="store_true", help="FPS de recepción e inferencia por separado; solo stream/webcam")
    args = parser.parse_args(argv)
    if args.max_frames < 0:
        parser.error("--max-frames no puede ser negativo")
    config = load_config(args.config)
    if args.metrics and (args.fake_tracks or config.source.type not in {"stream", "webcam"}):
        parser.error("--metrics requiere una fuente stream/webcam real; no --fake-tracks")
    metrics = LiveMetrics() if args.metrics else None
    if (args.realtime or args.loop) and (args.fake_tracks or config.source.type != "file"):
        parser.error("--realtime y --loop requieren una fuente file")
    config = replace(config, source=replace(config.source,
                     realtime=args.realtime or config.source.realtime,
                     loop=args.loop or config.source.loop))
    if args.fake_tracks:
        source = FakeTracksSource(config)
        detector = None
    else:
        detector = PersonDetector(config.detection, config.resolve(config.detection.model))
        source = create_source(config)
    diagnostic = CountingDebug() if args.counting_debug or config.debug.counting else None
    counter = create_counter(config.counting, diagnostic=diagnostic)
    occupancy = OccupancyCounter(config.occupancy)
    store = TelemetryStore()
    video = LatestFrame(config.visualization, config.telemetry.stale_after_seconds)
    history = TrackTrails(config.visualization.trail_length) if config.visualization.show_trails else None
    show = args.debug or config.debug.show_video
    processed = 0
    start = perf_counter()
    last_publish = 0.0
    cycle = 0
    calibration = CalibrationSession(config, args.config)
    revision = 0
    try:
        with TelemetryPublisher(store, config.telemetry.port, video=video, calibration=calibration), source:
            configure_detector_clock(detector, source)
            for packet in source:
                if metrics:
                    metrics.received(packet, perf_counter())
                # La misma ruta se usa para archivo, USB/webcam y HTTP/RTSP.
                requested_revision, counting = calibration.current()
                if requested_revision != revision:
                    config = replace(config, counting=counting)
                    if args.fake_tracks:
                        source.config = config
                    diagnostic = CountingDebug() if diagnostic else None
                    counter = create_counter(counting, diagnostic=diagnostic)
                    occupancy = OccupancyCounter(config.occupancy)
                    history = TrackTrails(config.visualization.trail_length) if history else None
                    last_publish = 0.0
                    revision = requested_revision
                    calibration.mark_applied(revision)
                if packet.cycle != cycle:
                    cycle = packet.cycle
                    detector.reset()
                    counter = create_counter(config.counting, diagnostic=diagnostic)
                    occupancy = OccupancyCounter(config.occupancy)
                    history = TrackTrails(config.visualization.trail_length) if history else None
                    last_publish = 0.0
                if not args.fake_tracks and packet.index % config.detection.vid_stride:
                    continue
                tracks = source.tracks(packet.index) if args.fake_tracks else detector.detect(packet.frame)
                occupancy.apply(update_counter(counter, tracks, packet, source))
                trails = history.update(tracks) if history else None
                processed += 1
                if metrics:
                    metrics.inferred(detector.last_timings, perf_counter())
                fps = processed / max(perf_counter() - start, 1e-9)
                if perf_counter() - last_publish >= config.telemetry.interval_seconds:
                    store.publish(make_sample(config.telemetry.wagon_id, occupancy, fps,
                                              timestamp=packet.timestamp, simulated=args.fake_tracks))
                    last_publish = perf_counter()
                    if metrics:
                        print(json.dumps({"performance": metrics.snapshot()}), file=sys.stderr, flush=True)
                if show or video.can_publish():
                    annotated = draw_overlay(packet.frame, tracks, config.counting, config.visualization,
                                             entries=occupancy.entries, exits=occupancy.exits,
                                             occupancy=occupancy.occupancy, fps=fps,
                                             trails=trails, simulated=args.fake_tracks)
                    video.publish(annotated)
                    if show:
                        cv2.imshow("APC - vista local (Q para salir)", annotated)
                if show:
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        break
                if args.max_frames and processed >= args.max_frames:
                    break
    except KeyboardInterrupt:
        pass
    finally:
        if show:
            cv2.destroyAllWindows()
    summary = {"frames": processed,
                      "fps": round(processed / max(perf_counter() - start, 1e-9), 2),
                      "entries": occupancy.entries, "exits": occupancy.exits,
                      "occupancy": occupancy.occupancy}
    if metrics:
        summary["performance"] = metrics.snapshot()
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
