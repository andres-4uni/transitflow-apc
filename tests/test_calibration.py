import importlib.util
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

import pytest
import yaml

from apc.calibration import CalibrationSession, save_calibration
from apc.config import CountingConfig, load_config
from apc.publisher.client import apply_calibration, fetch_calibration, save_calibration as save_remote
from apc.publisher.server import TelemetryPublisher
from apc.publisher.telemetry import TelemetryStore


@pytest.fixture
def profile(tmp_path):
    path = tmp_path / "configs" / "camera.yaml"
    path.parent.mkdir()
    path.write_text("# Cámara de clase\nsource:\n  type: webcam\n  index: 2 # USB\n"
                    "counting:\n  orientation: horizontal # Eje\n  position: 0.5 # Puerta\n"
                    "  enter_direction: positive\n# Privacidad\nvisualization:\n  stream: false\n")
    return path


def test_save_preserves_other_sections_comments_and_explicit_direction(profile):
    initial = profile.read_text()
    counting = CountingConfig(orientation="vertical", enter_direction="left", position=0.6)
    session = CalibrationSession(load_config(profile), profile)
    session.apply({"orientation": "vertical", "enter_direction": "left", "position": 0.6})
    assert profile.read_text() == initial
    result = session.save({"orientation": "vertical", "enter_direction": "left", "position": 0.6})
    saved = profile.read_text()
    assert result["saved_path"] == str(profile)
    assert "type: webcam\n  index: 2 # USB" in saved
    assert "orientation: vertical # Eje" in saved
    assert "position: 0.6 # Puerta" in saved
    assert "# Privacidad\nvisualization:\n  stream: false\n" in saved
    assert load_config(profile).counting == counting
    assert not list(profile.parent.glob("*.tmp"))


def test_save_active_profile_does_not_apply_or_change_source(profile):
    config = load_config(profile)
    session = CalibrationSession(config, profile)
    result = session.save({"position": 0.65})
    saved = load_config(result["saved_path"])
    assert Path(result["saved_path"]) == profile
    assert saved.source == config.source
    assert saved.counting.position == 0.65
    assert session.current() == (0, config.counting)


@pytest.mark.parametrize("source", [
    {"type": "file", "path": "data/another.mp4"},
    {"type": "webcam", "index": 0}, {"type": "webcam", "index": 3},
    {"type": "stream", "url": "http://user:secret@camera/feed"},
    {"type": "stream", "url": "rtsp://user:secret@camera/live"},
])
def test_session_is_source_agnostic_and_hides_stream_credentials(profile, source):
    profile.write_text(yaml.safe_dump({"source": source}))
    config = load_config(profile)
    session = CalibrationSession(config, profile)
    state = session.apply({"orientation": "vertical", "enter_direction": "right", "position": 0.7})
    assert state["source_type"] == source["type"]
    assert state["counting"]["position"] == 0.7
    assert state["revision"] == 1 and state["applied_revision"] == 0
    revision, counting = session.current()
    assert counting.entry_direction == "right"
    session.mark_applied(revision)
    assert session.snapshot()["applied_revision"] == revision
    assert "secret" not in json.dumps(state) and "demo1" not in json.dumps(state)
    assert config.source == load_config(profile).source


def test_invalid_proposals_and_paths_do_not_mutate_session_or_files(profile, tmp_path):
    session = CalibrationSession(load_config(profile), profile)
    initial = profile.read_text()
    for values in ({"orientation": "vertical", "enter_direction": "up"},
                   {"position": 1.1}, {"position": float("nan")}, {"unknown": 1}):
        with pytest.raises(ValueError):
            session.apply(values)
    default = profile.parent / "default.yaml"
    default.write_text(initial)
    alias = profile.parent / "alias.yaml"
    alias.symlink_to(default)
    for path in (default, alias):
        with pytest.raises(ValueError, match="protegido"):
            CalibrationSession(load_config(path), path).save({"position": 0.65})
    assert profile.read_text() == initial and default.read_text() == initial
    assert session.current()[0] == 0


def test_append_counting_and_reject_unpreservable_yaml(profile):
    profile.write_text("source:\n  type: webcam\n# Comentario final")
    save_calibration(profile, CountingConfig(enter_direction="up"))
    assert "# Comentario final\ncounting:" in profile.read_text()
    assert load_config(profile).counting.entry_direction == "up"
    profile.write_text("counting: {position: 0.5}\n")
    with pytest.raises(ValueError, match="mapa en bloque"):
        save_calibration(profile, CountingConfig())
    assert profile.read_text() == "counting: {position: 0.5}\n"


def test_malformed_active_profile_reports_error_without_mutation(profile):
    session = CalibrationSession(load_config(profile), profile)
    malformed = "source: [\n"
    profile.write_text(malformed)
    with pytest.raises(ValueError, match="YAML de destino no es válido"):
        session.save({"position": 0.65})
    assert profile.read_text() == malformed
    assert session.current()[0] == 0
    assert not list(profile.parent.glob("*.tmp"))


def test_local_api_apply_save_validation_and_origin_protection(profile):
    session = CalibrationSession(load_config(profile), profile)
    opener = build_opener(ProxyHandler({}))
    original = profile.read_text()
    with TelemetryPublisher(TelemetryStore(), port=0, calibration=session) as publisher:
        assert fetch_calibration(publisher.port)["counting"]["enter_direction"] == "down"
        state = apply_calibration(publisher.port, {"orientation": "vertical", "enter_direction": "left"})
        assert state["revision"] == 1 and state["applied_revision"] == 0
        assert profile.read_text() == original
        result = save_remote(publisher.port, {"position": 0.65})
        assert result["counting"]["position"] == 0.65
        assert session.current()[1].position == 0.5
        with pytest.raises(ValueError, match="Banda"):
            apply_calibration(publisher.port, {"position": 0})
        url = f"http://127.0.0.1:{publisher.port}/calibration/apply"
        for headers, payload, expected in [
            ({"Content-Type": "application/json", "Origin": "https://example.com"}, b"{}", 403),
            ({"Content-Type": "text/plain"}, b"{}", 415),
            ({"Content-Type": "application/json"}, b"x" * 8193, 413),
            ({"Content-Type": "application/json"}, b'{"counting":null}', 400),
            ({"Content-Type": "application/json"}, b'{"counting":{},"target":"other.yaml"}', 400),
        ]:
            request = Request(url, data=payload, headers=headers, method="POST")
            with pytest.raises(HTTPError) as error:
                opener.open(request, timeout=2)
            assert error.value.code == expected
        assert session.current()[0] == 1


def test_cli_only_saves_with_explicit_flag(profile, capsys):
    path = Path(__file__).resolve().parents[1] / "scripts/calibrate_counting.py"
    spec = importlib.util.spec_from_file_location("calibrate_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    original = profile.read_text()
    args = ["--config", str(profile), "--orientation", "vertical", "--enter-direction", "left", "--position", "0.6"]
    module.main(args)
    assert json.loads(capsys.readouterr().out)["saved"] is False
    assert profile.read_text() == original
    module.main([*args, "--save"])
    result = json.loads(capsys.readouterr().out)
    assert result["saved"] is True
    assert load_config(result["saved_path"]).counting.entry_direction == "left"
    assert result["saved_path"] == str(profile)


def test_api_protects_active_default_even_after_preview(profile):
    default = profile.with_name("default.yaml")
    original = profile.read_text()
    default.write_text(original)
    session = CalibrationSession(load_config(default), default)
    with TelemetryPublisher(TelemetryStore(), port=0, calibration=session) as publisher:
        apply_calibration(publisher.port, {"position": 0.6})
        with pytest.raises(ValueError, match="default.yaml está protegido"):
            save_remote(publisher.port, {"position": 0.6})
    assert default.read_text() == original


@pytest.mark.parametrize("source_values", [
    {"type": "file", "path": "data/another.mp4"},
    {"type": "webcam", "index": 2},
    {"type": "stream", "url": "http://camera/feed"},
    {"type": "stream", "url": "rtsp://camera/live"},
])
def test_demo_applies_preview_in_common_pipeline(profile, source_values, monkeypatch, capsys):
    """La captura simulada entra por create_source, igual que cada cámara soportada."""
    import numpy as np
    from dataclasses import replace
    from time import time
    from apc.models import Track
    from apc.sources.base import FramePacket
    path = Path(__file__).resolve().parents[1] / "scripts/run_demo.py"
    spec = importlib.util.spec_from_file_location("calibration_demo_test", path)
    demo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(demo)
    profile.write_text(yaml.safe_dump({"source": source_values, "visualization": {"stream": True}}))
    original = profile.read_text()
    config = load_config(profile)
    config = replace(config, telemetry=replace(config.telemetry, port=0))
    session = CalibrationSession(config, profile)
    monkeypatch.setattr(demo, "load_config", lambda _: config)
    monkeypatch.setattr(demo, "CalibrationSession", lambda *args: session)

    class Source:
        def __enter__(self):
            return self
        def __exit__(self, *_):
            pass
        def __iter__(self):
            for index in range(4):
                if index == 1:
                    session.apply({"orientation": "vertical", "enter_direction": "left",
                                   "position": 0.55, "band_half_width": 0.03})
                yield FramePacket(index, time(), np.zeros((240, 320, 3), np.uint8))

    class Detector:
        index = 0
        def detect(self, frame):
            x = [0.8, 0.8, 0.7, 0.2][self.index]
            self.index += 1
            return [Track(1, (x, 0.3))]
        def reset(self):
            pytest.fail("Previsualizar no debe reiniciar ByteTrack ni la captura")

    monkeypatch.setattr(demo, "create_source", lambda c: Source())
    monkeypatch.setattr(demo, "PersonDetector", lambda *args: Detector())
    overlays = []
    original_draw = demo.draw_overlay
    def draw(frame, tracks, counting, *args, **kwargs):
        overlays.append(counting)
        return original_draw(frame, tracks, counting, *args, **kwargs)
    monkeypatch.setattr(demo, "draw_overlay", draw)
    # El overlay se valida en cada frame; JPEG y transporte se prueban por separado.
    monkeypatch.setattr(demo.LatestFrame, "can_publish", lambda _: True)
    demo.main(["--config", str(profile)])
    result = json.loads(capsys.readouterr().out)
    assert (result["entries"], result["exits"]) == (1, 0)
    assert overlays[0].orientation == "horizontal"
    assert all(c.orientation == "vertical" and c.position == 0.55 and
               c.band_half_width == 0.03 and c.entry_direction == "left" for c in overlays[1:])
    assert session.snapshot()["applied_revision"] == 1
    assert profile.read_text() == original


def test_session_identity_and_conditional_requests(profile):
    session = CalibrationSession(load_config(profile), profile)
    another = CalibrationSession(load_config(profile), profile)
    assert session.snapshot()['session_id'] != another.snapshot()['session_id']
    expected = dict(session_id=session.session_id, revision=0)
    original = profile.read_text()
    with TelemetryPublisher(TelemetryStore(), port=0, calibration=session) as publisher:
        apply_calibration(publisher.port, {'position': .6}, expected=expected)
        for operation in (apply_calibration, save_remote):
            with pytest.raises(ValueError, match='productor cambió'):
                operation(publisher.port, {'position': .7}, expected=expected)
            with pytest.raises(ValueError, match='productor cambió'):
                operation(publisher.port, {'position': .7},
                          expected=dict(session_id=another.session_id, revision=1))
    assert session.current()[0] == 1 and profile.read_text() == original
