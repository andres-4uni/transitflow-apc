"""Preparación de video/cámara con píxeles y boxes sintéticos, sin pesos ni archivos."""

from dataclasses import replace
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from apc.config import CountingConfig, DetectionConfig, load_config
from apc.counting.factory import create_counter, update_counter
from apc.counting.occupancy import OccupancyCounter
from apc.detection.detector import PersonDetector
from apc.publisher.telemetry import make_sample
from apc.sources.base import FramePacket
from apc.visualization.overlay import draw_overlay


ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / 'configs/next-video.yaml'


class Tensor:
    def __init__(self, values):
        self.values = values

    def int(self): return self
    def cpu(self): return self
    def tolist(self): return self.values


def test_pending_profile_loads_without_opening_video_or_inheriting_defaults(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('Cargar el perfil no debe abrir video ni cámara')
    monkeypatch.setattr(cv2, 'VideoCapture', forbidden)
    config = load_config(PROFILE)
    assert 'PENDIENTE' in config.source.path
    assert config.counting == CountingConfig()
    assert config.detection == DetectionConfig()
    assert not config.visualization.stream and not config.debug.show_video
    assert not config.source.loop and not config.source.realtime


@pytest.mark.parametrize('mode', ['tripwire', 'dual_zone'])
def test_720p_30fps_roi_tracks_counting_occupancy_and_overlay(mode):
    config = load_config(PROFILE)
    # ROI deliberadamente no trivial solo para verificar restitución de coordenadas.
    config = replace(config, detection=replace(config.detection, roi_left=.1, roi_top=.1,
                     roi_right=.9, roi_bottom=.9), counting=replace(config.counting,
                     mode=mode, max_missing_seconds=.9 if mode == 'dual_zone' else 0))
    points = [.2, .3, .5, .7, .8, .8, .7, .5, .3, .2]
    index = 0
    def track(cropped, **kwargs):
        nonlocal index
        assert cropped.shape == (576, 1024, 3)
        assert kwargs['device'] == 'cpu' and kwargs['tracker'] == 'bytetrack.yaml'
        assert all(kwargs[key] is False for key in ('save', 'save_txt', 'save_crop', 'show'))
        y = points[index]
        index += 1
        # Caja en coordenadas del ROI, respuesta de detección/tracking simulada.
        box = [1280*.35-128, 720*(y-.05)-72, 1280*.45-128, 720*(y+.05)-72]
        return [SimpleNamespace(boxes=SimpleNamespace(id=Tensor([7]), xyxy=Tensor([box])))]
    detector = PersonDetector(config.detection, Path('unused'), model=SimpleNamespace(track=track))
    counter, occupancy = create_counter(config.counting), OccupancyCounter(config.occupancy)
    source = SimpleNamespace(metadata={'fps': 30})
    events = []
    peak = 0
    for frame_index, y in enumerate(points):
        frame = np.zeros((720, 1280, 3), np.uint8)
        original = frame.copy()
        packet = FramePacket(frame_index, 1800000000+frame_index/30, frame,
                             media_seconds=frame_index/30)
        tracks = detector.detect(frame)
        assert len(tracks) == 1
        assert tracks[0].centroid == pytest.approx((.4, y))
        assert tracks[0].bbox == pytest.approx((.35, y-.05, .45, y+.05))
        current = update_counter(counter, tracks, packet, source)
        events.extend(current)
        occupancy.apply(current)
        peak = max(peak, occupancy.occupancy)
        sample = make_sample(1, occupancy, 0, timestamp=packet.timestamp)
        assert sample.occupancy == occupancy.occupancy
        overlay = draw_overlay(frame, tracks, config.counting, config.visualization,
                               entries=occupancy.entries, exits=occupancy.exits,
                               occupancy=occupancy.occupancy)
        assert overlay.shape == frame.shape and overlay.any()
        assert np.array_equal(frame, original) and not np.shares_memory(overlay, frame)
    assert [event.direction for event in events] == ['entry', 'exit']
    assert (occupancy.entries, occupancy.exits, occupancy.occupancy, peak) == (1, 1, 0, 1)


def script(name):
    spec = importlib.util.spec_from_file_location(f'next_{name}', ROOT / 'scripts' / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_evaluation_profile_and_explicit_video_disable_loop_and_realtime(tmp_path, monkeypatch):
    cli = script('evaluate_counts')
    config = load_config(PROFILE)
    config = replace(config, source=replace(config.source, loop=True, realtime=True))
    monkeypatch.setattr(cli, 'load_config', lambda path: config)
    monkeypatch.setattr(cli, 'PersonDetector', lambda *args: object())
    seen = []
    def evaluate(config_arg, source, detector, **kwargs):
        seen.append(source)
        assert not source.loop and not source.realtime
        assert kwargs['verified_frames'] is None
        return {'in': {'observed': 1}, 'out': {'observed': 1}, 'processed_frames': 10, 'fps': 0}
    monkeypatch.setattr(cli, 'evaluate', evaluate)
    output = tmp_path / 'new-evaluation.json'
    args = ['--config', str(PROFILE), '--video', '/tmp/authorized-future.mp4',
            '--expected-in', '1', '--expected-out', '1', '--output', str(output)]
    cli.main(args)
    assert seen[0].path == Path('/tmp/authorized-future.mp4')
    original = output.read_bytes()
    with pytest.raises(SystemExit):
        cli.main(args)
    assert output.read_bytes() == original and len(seen) == 1


@pytest.mark.parametrize('explicit_video', [False, True])
def test_benchmark_profile_and_route_without_other_video_or_overwrite(tmp_path, monkeypatch, explicit_video):
    cli = script('benchmark_fps')
    config = load_config(PROFILE)
    config = replace(config, source=replace(config.source, loop=True, realtime=True))
    monkeypatch.setattr(cli, 'load_config', lambda path: config)
    monkeypatch.setattr(cli, 'PersonDetector', lambda *args: object())
    # Solo se simulan metadatos; no se abre ni se crea el video pendiente.
    original_stat = Path.stat
    target = Path('/tmp/authorized-future.mp4') if explicit_video else config.resolve(config.source.path)
    def stat(path, *args, **kwargs):
        if path == target:
            return SimpleNamespace(st_size=123, st_mtime_ns=456)
        return original_stat(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'stat', stat)
    seen = []
    def benchmark(run_config, source, detector, **kwargs):
        seen.append(source)
        assert source.path == target and not source.realtime and not source.loop
        assert run_config.counting == config.counting
        return ({'decoded_frames': 40, 'processed_fps': 0, 'source_fps': 0}, {'instantaneous_fps': [0]})
    monkeypatch.setattr(cli, 'benchmark_once', benchmark)
    output = tmp_path / 'new-benchmark.json'
    args = ['--config', str(PROFILE), '--real-only', '--imgsz', '320', '--vid-stride', '1',
            '--repeats', '1', '--output', str(output)]
    if explicit_video:
        args.extend(['--video', str(target)])
    cli.main(args)
    report = json.loads(output.read_text())
    assert len(seen) == len(report['groups']) == 2  # Overlay/JPEG apagado y encendido.
    assert set(report['sources']) == {'real'}
    assert not report['method']['synthetic_loop_matches_real_frame_count']
    original = output.read_bytes()
    with pytest.raises(SystemExit):
        cli.main(args)
    assert output.read_bytes() == original and len(seen) == 2
