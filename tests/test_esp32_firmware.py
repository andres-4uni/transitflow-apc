"""Verificación local del firmware sin ESP32 ni credenciales de una red real."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from time import sleep

import pytest

ROOT = Path(__file__).resolve().parents[1] / "firmware/esp32-camera"


def load_manager():
    spec = importlib.util.spec_from_file_location("camera_manager", ROOT / "tools/manage.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def manager(tmp_path, monkeypatch):
    module = load_manager()
    monkeypatch.setattr(module, "PRIVATE", tmp_path / "private")
    module.create_secret()
    return module


def test_native_policy(tmp_path):
    compiler = shutil.which("c++") or shutil.which("clang++") or shutil.which("g++")
    if not compiler:
        pytest.fail("Instalar compilador C++ para verificar la política del firmware")
    output = tmp_path / "policy-test"
    subprocess.run([compiler, "-std=c++17", "-Wall", "-Wextra", "-Werror", "-pedantic",
                    "-I", str(ROOT / "src"), str(ROOT / "tests/policy_test.cpp"), "-o", str(output)], check=True)
    subprocess.run([str(output)], check=True)


def test_network_controller_with_fake_hardware(manager, tmp_path):
    compiler = shutil.which("c++") or shutil.which("clang++") or shutil.which("g++")
    assert compiler, "Se requiere compilador C++"
    sketch = manager.prepare(tmp_path / "CameraWebServer")
    output = tmp_path / "network-test"
    subprocess.run([compiler, "-std=c++17", "-Wall", "-Wextra", "-Werror", "-pedantic",
                    "-I", str(ROOT / "tests/fakes"), "-I", str(sketch),
                    str(ROOT / "tests/network_test.cpp"), str(sketch / "network_setup.cpp"),
                    "-o", str(output)], check=True)
    subprocess.run([str(output)], check=True)


def test_secret_is_private_and_not_replaced(manager, capsys):
    path = manager.PRIVATE / "setup_password.txt"
    key = path.read_text().strip()
    assert len(key) == 32 and all(character in "0123456789abcdef" for character in key)
    assert path.stat().st_mode & 0o777 == 0o600
    manager.create_secret()
    assert path.read_text().strip() == key
    assert key not in capsys.readouterr().out


def test_build_preserves_stream_and_isolates_reference(manager, tmp_path):
    sketch = manager.prepare(tmp_path / "CameraWebServer")
    source = (sketch / "app_httpd.cpp").read_text()
    assert '.uri = "/stream"' in source
    assert "config.server_port = 80;" in source
    assert "config.server_port += 1;" in source
    assert "multipart/x-mixed-replace" in source
    assert "while (stream_enabled.load())" in source
    assert "bool startCameraServer()" in source
    assert "void stopCameraServer()" in source
    assert "Access-Control-Allow-Origin" not in source
    assert "CAMERA_MODEL_XIAO_ESP32S3" in (sketch / "board_config.h").read_text()
    assert (sketch / "setup_secret.h").stat().st_mode & 0o777 == 0o600
    # El original preservado conserva sus hashes, no recibe el parche ni secretos.
    reference = manager.prepare(tmp_path / "reference/CameraWebServer", reference=True)
    assert "void startCameraServer()" in (reference / "app_httpd.cpp").read_text()
    assert not (reference / "setup_secret.h").exists()
    assert 'const char *ssid = "";' in (reference / "CameraWebServer.ino").read_text()
    assert 'const char *password = "";' in (reference / "CameraWebServer.ino").read_text()


def test_altered_vendor_fails_closed(manager, tmp_path, monkeypatch):
    isolated = tmp_path / "altered"
    shutil.copytree(ROOT / "vendor", isolated / "vendor")
    (isolated / "vendor/CameraWebServer/camera_pins.h").write_text("alterado")
    monkeypatch.setattr(manager, "ROOT", isolated)
    with pytest.raises(RuntimeError, match="Referencia alterada"):
        manager.prepare(tmp_path / "CameraWebServer")


def test_invalid_secret_cannot_produce_firmware(manager, tmp_path):
    (manager.PRIVATE / "setup_password.txt").write_text("clave-corta")
    with pytest.raises(RuntimeError, match="Clave de AP inválida"):
        manager.prepare(tmp_path / "CameraWebServer")


def test_hardware_build_options_are_explicit():
    manager = load_manager()
    assert manager.CORE == json.loads((ROOT / "vendor/manifest.json").read_text())["core"]
    for option in ["XIAO_ESP32S3", "PSRAM=opi", "FlashSize=8M", "CDCOnBoot=default", "PartitionScheme=default_8MB", "DebugLevel=none"]:
        assert option in manager.FQBN


def load_stream_checker():
    spec = importlib.util.spec_from_file_location("camera_stream_check", ROOT / "tools/check_stream.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("host", ["8.8.8.8", "example.com", "http://apc-metro.local", "user@apc-metro.local"])
def test_stream_check_only_accepts_local_hosts(host):
    with pytest.raises(ValueError):
        load_stream_checker().local_address(host)


def test_stream_checker_uses_real_apc_source_without_saving_images():
    import cv2
    import numpy as np
    checker = load_stream_checker()
    success, jpeg = cv2.imencode(".jpg", np.full((64, 96, 3), 90, dtype=np.uint8))
    assert success
    payload = jpeg.tobytes()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            assert self.path == "/stream"
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace;boundary=123456789000000000000987654321")
            self.end_headers()
            try:
                for _ in range(300):
                    self.wfile.write(b"\r\n--123456789000000000000987654321\r\nContent-Type: image/jpeg\r\nContent-Length: "
                                     + str(len(payload)).encode() + b"\r\nX-Timestamp: 1.000000\r\n\r\n" + payload)
                    self.wfile.flush()
                    sleep(.01)
            except (BrokenPipeError, ConnectionResetError):
                pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = checker.check_stream("127.0.0.1", frames=4, port=server.server_port)
        assert result["frames"] == 4 and result["width"] == 96 and result["height"] == 64
        assert result["received_fps"] > 0
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
