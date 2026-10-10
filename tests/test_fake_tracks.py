import importlib.util
import json
from dataclasses import replace
from pathlib import Path

import cv2
import pytest

from apc.config import load_config
from apc.counting.occupancy import OccupancyCounter
from apc.counting.tripwire import TripwireCounter
from apc.sources.fake import FakeTracksSource


@pytest.mark.parametrize("orientation", ["horizontal", "vertical"])
@pytest.mark.parametrize("direction", ["positive", "negative"])
def test_fake_people_feed_real_counter_with_expected_crossings(orientation, direction):
    config = load_config()
    config = replace(config, counting=replace(config.counting, orientation=orientation, enter_direction=direction))
    source = FakeTracksSource(config, realtime=False)
    counter, occupancy = TripwireCounter(config.counting), OccupancyCounter(config.occupancy)
    peak = 0
    with source:
        for _ in range(source.cycle_frames * 3):
            packet = source.read()
            tracks = source.tracks(packet.index)
            occupancy.apply(counter.update(tracks))
            peak = max(peak, occupancy.occupancy)
            assert packet.frame.shape == (480, 640, 3)
            assert all(track.bbox is not None for track in tracks)
    assert (occupancy.entries, occupancy.exits, occupancy.occupancy) == (3, 3, 0)
    assert peak == 1
    assert source.read() is None


@pytest.mark.parametrize("stream", [False, True])
def test_fake_cli_uses_no_detector_capture_or_image_files(tmp_path, monkeypatch, capsys, stream):
    path = Path(__file__).resolve().parents[1] / "scripts" / "run_demo.py"
    spec = importlib.util.spec_from_file_location("apc_demo_test", path)
    demo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(demo)
    config = load_config()
    config = replace(config, telemetry=replace(config.telemetry, port=0),
                     visualization=replace(config.visualization, stream=stream))
    monkeypatch.setattr(demo, "load_config", lambda path: config)
    monkeypatch.setattr(demo, "FakeTracksSource", lambda c: FakeTracksSource(c, realtime=False))
    def forbidden(*args, **kwargs):
        pytest.fail("El modo fake intentó usar detector/captura o guardar imágenes")
    monkeypatch.setattr(demo, "PersonDetector", forbidden)
    monkeypatch.setattr(demo, "create_source", forbidden)
    monkeypatch.setattr(cv2, "VideoCapture", forbidden)
    monkeypatch.setattr(cv2, "VideoWriter", forbidden)
    monkeypatch.setattr(cv2, "imwrite", forbidden)
    if not stream:
        monkeypatch.setattr(demo, "draw_overlay", forbidden)
        monkeypatch.setattr(cv2, "imencode", forbidden)
    monkeypatch.chdir(tmp_path)
    count = 2 * FakeTracksSource(config).cycle_frames
    demo.main(["--fake-tracks", "--max-frames", str(count)])
    summary = json.loads(capsys.readouterr().out)
    assert (summary["entries"], summary["exits"], summary["occupancy"]) == (2, 2, 0)
    assert summary["frames"] == count
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('orientation', ['horizontal', 'vertical'])
@pytest.mark.parametrize('direction', ['positive', 'negative'])
@pytest.mark.parametrize('zones', [(.1, .9), (.0001, .9999), (.01, .02), (.98, .99)])
@pytest.mark.parametrize('min_zone_frames', [2, 8])
def test_fake_dual_zone_holds_extremes_and_counts_each_cycle(orientation, direction, zones, min_zone_frames):
    from apc.counting.factory import create_counter
    config = load_config()
    config = replace(config, counting=replace(config.counting, mode='dual_zone', max_missing_seconds=.9,
                     orientation=orientation, enter_direction=direction, zone_a_max=zones[0],
                     zone_b_min=zones[1], min_zone_frames=min_zone_frames),
                     simulation=replace(config.simulation, fake_cycle_seconds=1, fake_fps=30))
    source = FakeTracksSource(config, realtime=False)
    counter = create_counter(config.counting)
    occupancy = OccupancyCounter(config.occupancy)
    events = []
    peak = 0
    for index in range(source.cycle_frames * 4):
        current = counter.update(source.tracks(index), timestamp=index / 30)
        occupancy.apply(current)
        events.extend(current)
        peak = max(peak, occupancy.occupancy)
    assert [e.direction for e in events] == ['entry', 'exit'] * 4
    assert [e.track_id for e in events] == list(range(1, 9))
    assert (occupancy.entries, occupancy.exits, occupancy.occupancy, peak) == (4, 4, 0, 1)
