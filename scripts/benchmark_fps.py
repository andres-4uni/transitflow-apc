"""Barrido CPU sin realtime, con tres repeticiones y sin escribir imágenes."""

import argparse
from collections import defaultdict
from dataclasses import asdict, replace
from datetime import datetime, timezone
from itertools import product
from importlib.metadata import version
import json
import os
from pathlib import Path
import platform
import random
import sys
from time import perf_counter

import cv2
import psutil
import torch

from apc.benchmark import benchmark_once, describe
from apc.config import load_config
from apc.detection.detector import PersonDetector
from apc.sources.file import FileSource


def busy_seconds(cpu_times):
    return sum(cpu_times) - cpu_times.idle


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/default.yaml")
    parser.add_argument("--video", help="Archivo local; por defecto source.path del perfil")
    parser.add_argument("--synthetic-video", default="data/demo.avi", help="AVI sintético preexistente; no se genera un archivo")
    parser.add_argument("--real-only", action="store_true", help="Medir solo el video elegido, sin comparación sintética")
    parser.add_argument("--imgsz", type=int, nargs="+", choices=tuple(range(320, 641, 32)), default=[320, 352, 384, 416])
    parser.add_argument("--vid-stride", type=int, nargs="+", choices=(1, 2, 3), default=[1, 2, 3])
    parser.add_argument("--torch-threads", type=int, default=None)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--warmup", type=int, default=30)
    parser.add_argument("--max-frames", type=int, default=0, help="0: archivo real completo; comparación sintética de igual duración en frames")
    parser.add_argument("--output", type=Path, required=True, help="Solo estadísticas JSON; se rechaza sobreescribir un archivo")
    args = parser.parse_args(argv)
    if args.repeats < 1 or args.warmup < 2 or args.max_frames < 0 or (args.torch_threads is not None and args.torch_threads < 0):
        parser.error("Parámetros numéricos inválidos")
    if args.output.exists():
        parser.error("El resultado ya existe; use una ruta nueva")
    config = load_config(args.config)
    thread_count = config.detection.torch_threads if args.torch_threads is None else args.torch_threads
    # PersonDetector configura caches locales antes de importar/cargar el modelo.
    paths = {"real": config.resolve(args.video or config.source.path)}
    if not args.real_only:
        paths["synthetic"] = config.resolve(args.synthetic_video)
    initial_stats = {key: (path.stat().st_size, path.stat().st_mtime_ns) for key, path in paths.items()}
    report = {
        "date_utc": datetime.now(timezone.utc).isoformat(),
        "environment": {"machine": platform.machine(), "os": platform.platform(),
                        "python": platform.python_version(), "torch": torch.__version__,
                        "opencv": cv2.__version__, "ultralytics": version("ultralytics"),
                        "cpu_logical": os.cpu_count(), "memory_bytes": psutil.virtual_memory().total,
                        "torch_threads_requested": thread_count,
                        "torch_interop_threads": torch.get_num_interop_threads()},
        "method": {"warmup_processed_frames": args.warmup, "repeats": args.repeats,
                   "realtime": False, "max_frames": args.max_frames,
                   "configuration_order_seed": 17, "http_transport_measured": False,
                   "synthetic_loop_matches_real_frame_count": not args.real_only},
        "baseline_config": {section: asdict(getattr(config, section)) for section in
                            ("detection", "counting", "visualization")},
        "sources": {key: {"path": str(path.relative_to(config.root)) if path.is_relative_to(config.root) else path.name,
                          "bytes": initial_stats[key][0], "mtime_ns": initial_stats[key][1]} for key, path in paths.items()},
        "groups": [],
    }
    combinations = list(product(args.imgsz, args.vid_stride))
    random.Random(17).shuffle(combinations)
    for imgsz, stride in combinations:
        detection = replace(config.detection, imgsz=imgsz, vid_stride=stride, torch_threads=thread_count)
        detector = PersonDetector(detection, config.resolve(detection.model))
        for source_name in paths:
            for stream in (False, True):
                run_config = replace(config, detection=detection,
                                     visualization=replace(config.visualization, stream=stream))
                runs = []
                pooled = defaultdict(list)
                for repeat in range(args.repeats):
                    source = FileSource(paths[source_name], config.source.queue_size, loop=source_name == "synthetic")
                    limit = args.max_frames if source_name == "real" else real_frames
                    cpu_start, process_start, start = psutil.cpu_times(), psutil.Process().cpu_times(), perf_counter()
                    load_start = os.getloadavg()
                    result, samples = benchmark_once(run_config, source, detector,
                                                     warmup=args.warmup, max_frames=limit)
                    elapsed = perf_counter() - start
                    cpu_end, process_end = psutil.cpu_times(), psutil.Process().cpu_times()
                    total_busy = busy_seconds(cpu_end) - busy_seconds(cpu_start)
                    process_busy = process_end.user + process_end.system - process_start.user - process_start.system
                    scale = elapsed * os.cpu_count()
                    result["background"] = {"load_average_start": load_start,
                                            "system_busy_percent": 100 * total_busy / scale,
                                            "benchmark_busy_percent": 100 * process_busy / scale,
                                            "other_busy_percent_estimate": 100 * max(0, total_busy - process_busy) / scale}
                    result["repeat"] = repeat + 1
                    result["torch_threads_actual"] = torch.get_num_threads()
                    runs.append(result)
                    for key, values in samples.items():
                        pooled[key].extend(values)
                    if source_name == "real":
                        real_frames = result["decoded_frames"]
                    print(json.dumps({"source": source_name, "imgsz": imgsz, "stride": stride,
                                      "stream": stream, "repeat": repeat + 1,
                                      "fps": round(result["processed_fps"], 2)}), file=sys.stderr, flush=True)
                fps = [run["processed_fps"] for run in runs]
                report["groups"].append({"source": source_name, "imgsz": imgsz, "vid_stride": stride,
                                         "stream": stream, "runs": runs, "processed_fps": describe(fps),
                                         "source_fps": describe([run["source_fps"] for run in runs]),
                                         "over_20_all_repeats": min(fps) > 20,
                                         "at_least_25_all_repeats": min(fps) >= 25,
                                         "instantaneous_fps": describe(pooled.pop("instantaneous_fps")),
                                         "stages_ms": {key: describe(values) for key, values in pooled.items()}})
    for key, path in paths.items():
        stat = path.stat()
        if (stat.st_size, stat.st_mtime_ns) != initial_stats[key]:
            raise RuntimeError("Cambió un archivo fuente durante la medición")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, allow_nan=False)
        handle.write("\n")
    print(json.dumps({"output": str(args.output), "groups": len(report["groups"]),
                      "runs": len(report["groups"]) * args.repeats}))


if __name__ == "__main__":
    main()
