"""Pipeline con MJPEG HTTP real sintético, sin cámara ni imágenes persistidas."""
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
from pathlib import Path
from threading import Event, Thread
from types import SimpleNamespace
from urllib.request import ProxyHandler, build_opener

import cv2
import numpy as np
import pytest
from streamlit.testing.v1 import AppTest

from apc.config import CountingConfig, DetectionConfig, load_config
from apc.detection.detector import PersonDetector
from apc.publisher.client import fetch_calibration, fetch_samples, fetch_video_status
from apc.publisher.server import TelemetryPublisher
from apc.sources import create_source
from apc.sources.stream import StreamSource

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "configs/esp32-demo.yaml"


def demo_script():
    spec = importlib.util.spec_from_file_location("esp32_demo_test", ROOT / "scripts/run_demo.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def mjpeg_url():
    # Misma cabecera/boundary de Espressif, imagen negra enteramente sintética.
    ok, jpeg = cv2.imencode(".jpg", np.zeros((240, 320, 3), np.uint8))
    assert ok
    data = jpeg.tobytes()
    stopped = Event()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            if self.path != "/stream":
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace;boundary=123456789000000000000987654321")
            self.end_headers()
            try:
                while not stopped.is_set():
                    self.wfile.write(b"\r\n--123456789000000000000987654321\r\nContent-Type: image/jpeg\r\nContent-Length: "
                                     + str(len(data)).encode() + b"\r\nX-Timestamp: 1.000000\r\n\r\n" + data)
                    self.wfile.flush()
                    stopped.wait(.03)
            except (BrokenPipeError, ConnectionResetError):
                pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/stream"
    finally:
        stopped.set()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_esp32_profile_keeps_calibration_and_selects_existing_stream_without_opening(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("El perfil no debe abrir una cámara al cargar")
    monkeypatch.setattr(cv2, "VideoCapture", forbidden)
    config = load_config(PROFILE)
    assert config.source.url == "http://apc-metro.local:81/stream"
    assert isinstance(create_source(config), StreamSource)
    assert config.counting == CountingConfig()
    assert config.detection == DetectionConfig()
    assert config.visualization.stream and config.visualization.show_boxes
    assert config.visualization.show_ids and config.visualization.show_trails
    assert not config.visualization.show_line and not config.visualization.show_band
    assert not config.debug.show_video
    assert not config.source.loop and not config.source.realtime


class Tensor:
    def __init__(self, values): self.values = values
    def int(self): return self
    def cpu(self): return self
    def tolist(self): return self.values


def test_http_to_detector_counting_overlay_api_and_dashboard(mjpeg_url, tmp_path, monkeypatch, capsys):
    demo = demo_script()
    config = load_config(PROFILE)
    config = replace(config, source=replace(config.source, url=mjpeg_url),
                     telemetry=replace(config.telemetry, port=0, interval_seconds=.001),
                     visualization=replace(config.visualization, max_fps=60))
    monkeypatch.setattr(demo, "load_config", lambda path: config)
    points = iter([.2, .3, .5, .7, .8, .8, .7, .5, .3, .2])
    calls = []

    def track(frame, **options):
        calls.append(options)
        assert frame.shape == (240, 320, 3)
        y = next(points)
        return [SimpleNamespace(boxes=SimpleNamespace(id=Tensor([7]),
                xyxy=Tensor([[100, (y-.06)*240, 150, (y+.06)*240]])), speed={"inference": 4.0})]

    detector = PersonDetector(config.detection, Path("unused"), model=SimpleNamespace(track=track))
    monkeypatch.setattr(demo, "PersonDetector", lambda *args: detector)
    seen_trails = []
    original_overlay = demo.draw_overlay

    def overlay(*args, **kwargs):
        seen_trails.append(kwargs["trails"])
        return original_overlay(*args, **kwargs)

    monkeypatch.setattr(demo, "draw_overlay", overlay)
    local_profile = tmp_path / "configs/esp32-demo.yaml"
    local_profile.parent.mkdir()
    verified = []

    class CheckedPublisher(TelemetryPublisher):
        def __exit__(self, *args):
            try:
                assert self._server.server_address[0] == "127.0.0.1"
                samples = fetch_samples(self.port)
                assert len(samples) == 1
                assert (samples[0].entries, samples[0].exits, samples[0].occupancy) == (1, 1, 0)
                assert fetch_video_status(self.port) == {"enabled": 1, "ready": 1}
                current = fetch_calibration(self.port)
                assert current["source_type"] == "stream" and current["revision"] == 0
                opener = build_opener(ProxyHandler({}))
                with opener.open(f"http://127.0.0.1:{self.port}/video", timeout=3) as response:
                    assert response.readline() == b"--frame\r\n"
                    assert response.readline() == b"Content-Type: image/jpeg\r\n"
                    length = int(response.readline().split(b":", 1)[1])
                    assert response.readline() == b"\r\n"
                    frame = cv2.imdecode(np.frombuffer(response.read(length), np.uint8), cv2.IMREAD_COLOR)
                    assert frame.shape == (240, 320, 3) and frame.any()
                local_profile.write_text(PROFILE.read_text() + f"\ntelemetry:\n  port: {self.port}\n")
                original = local_profile.read_bytes()
                monkeypatch.setenv("APC_CONFIG", str(local_profile))
                app = AppTest.from_file(ROOT / "dashboard/app.py").run(timeout=20)
                assert not app.exception and not app.error
                assert app.slider(key="cal_position").value == .5
                assert app.slider(key="cal_band").value == .04
                assert app.button(key="cal_save") is not None
                assert app.metric[0].value == "0" and app.metric[3].value == "1 / 1"
                assert any("HTTP / RTSP" in item.value for item in app.caption)
                assert any("/video" in item.value for item in app.markdown)
                app.run(timeout=20)
                assert fetch_calibration(self.port)["revision"] == 0
                assert local_profile.read_bytes() == original
                verified.append(True)
            finally:
                super().__exit__(*args)

    monkeypatch.setattr(demo, "TelemetryPublisher", CheckedPublisher)
    demo.main(["--config", str(local_profile), "--metrics", "--max-frames", "10"])
    result = json.loads(capsys.readouterr().out)
    assert result["frames"] == result["performance"]["inference_frames"] == 10
    assert result["performance"]["capture_fps"] > 0
    assert result["performance"]["yolo_inference_ms_mean"] == 4
    assert calls and all(call["classes"] == [0] and call["device"] == "cpu" for call in calls)
    assert all(call["tracker"] == "bytetrack.yaml" and call["persist"] for call in calls)
    assert all(not call[key] for call in calls for key in ("save", "save_txt", "save_crop", "show"))
    assert any(len(path) > 1 for trails in seen_trails for path in trails.values())
    assert verified == [True]


@pytest.mark.skipif(not (ROOT / "models/yolov8n.pt").is_file(), reason="Pesos locales no disponibles; no descargar")
def test_real_yolo_and_bytetrack_on_synthetic_http(mjpeg_url):
    config = load_config(PROFILE)
    detector = PersonDetector(config.detection, config.resolve(config.detection.model))
    source_config = replace(config, source=replace(config.source, url=mjpeg_url))
    with create_source(source_config) as source:
        for _ in range(3):
            packet = source.read()
            assert packet.frame.shape == (240, 320, 3)
            assert isinstance(detector.detect(packet.frame), list)
    assert detector.model.predictor.device.type == "cpu"
    assert type(detector.model.predictor.trackers[0]).__name__ == "BYTETracker"
    assert detector.last_timings["inference"] > 0


@pytest.mark.parametrize("options", [[], ["--fake-tracks"]])
def test_metrics_cannot_be_mislabelled_as_live_for_file_or_fake(options):
    with pytest.raises(SystemExit) as result:
        demo_script().main(["--metrics", *options])
    assert result.value.code == 2
