"""Verificación local del firmware sin ESP32 ni credenciales de una red real."""
import importlib.util
import json
import re
from pathlib import Path
import shutil
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from time import sleep
from urllib.parse import parse_qs

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


@pytest.fixture
def controller_binary(manager, tmp_path):
    compiler = shutil.which("c++") or shutil.which("clang++") or shutil.which("g++")
    assert compiler, "Se requiere compilador C++"
    sketch = manager.prepare(tmp_path / "CameraWebServer")
    output = tmp_path / "network-test"
    subprocess.run([compiler, "-std=c++17", "-Wall", "-Wextra", "-Werror", "-pedantic",
                    "-I", str(ROOT / "tests/fakes"), "-I", str(sketch),
                    str(ROOT / "tests/network_test.cpp"), str(sketch / "network_setup.cpp"),
                    "-o", str(output)], check=True)
    return output


def test_network_controller_with_fake_hardware(controller_binary):
    subprocess.run([str(controller_binary)], check=True)


@pytest.mark.parametrize("legacy_policy", [True, False], ids=["reproduce-no-referrer", "portal-current-policy"])
def test_browser_form_origin_and_encoding(controller_binary, tmp_path, legacy_policy):
    # Chrome real, sin perfil personal, usa el formulario/cabeceras del controlador.
    # No ejecuta WebServer/driver de radio: esa parte sigue requiriendo la placa.
    browser = shutil.which("chromium") or shutil.which("google-chrome")
    mac_browser = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    browser = browser or (str(mac_browser) if mac_browser.is_file() else None)
    if not browser:
        pytest.skip("Prueba adicional requiere Chrome/Chromium instalado")
    rendered = subprocess.run([str(controller_binary), "--render-portal"], check=True, capture_output=True).stdout.decode()
    headers_text, page = rendered.split("\r\n\r\n", 1)
    headers = dict(line.split(": ", 1) for line in headers_text.split("\r\n"))
    tokens = re.findall(r'name="token" value="([0-9a-f]{32})"', page)
    assert len(tokens) == 2 and tokens[0] == tokens[1]
    policy = "no-referrer" if legacy_policy else headers["Referrer-Policy"]
    page = page.replace("</html>", """<script>
const form=document.querySelector('form[action="/save"]');
form.elements.ssid.value='Red sintética + & = % ñ';
form.elements.password.value='prueba+&=%123';
form.requestSubmit();
</script></html>""")
    observed = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            self.send_response(200)
            if self.path == "/scan":
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b"[]")
                return
            for name, value in headers.items():
                self.send_header(name, policy if name == "Referrer-Policy" else value)
            self.end_headers()
            self.wfile.write(page.encode())

        def do_POST(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode()
            observed.append((self.path, self.headers.get("Origin"), self.headers.get("Content-Type"),
                             parse_qs(body, keep_blank_values=True)))
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<p>Formulario recibido</p>")

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f"http://127.0.0.1:{server.server_port}"
    try:
        result = subprocess.run([browser, "--headless", "--no-first-run", "--no-default-browser-check",
                                 "--disable-background-networking", "--disable-component-update", "--disable-sync",
                                 "--disable-extensions", f"--user-data-dir={tmp_path / 'chrome-profile'}",
                                 "--dump-dom", "--virtual-time-budget=1500", origin + "/"],
                                capture_output=True, timeout=30)
        assert result.returncode == 0, "Chrome terminó con error; no mostrar DOM/tokens en logs"
        assert len(observed) == 1
        path, submitted_origin, media_type, fields = observed[0]
        assert path == "/save"
        assert submitted_origin == ("null" if legacy_policy else origin)
        assert media_type == "application/x-www-form-urlencoded"
        assert len(fields["token"][0]) == 32
        token_matches = fields["token"] == [tokens[0]]
        assert token_matches, "El formulario debe conservar el token completo"
        assert fields["ssid"] == ["Red sintética + & = % ñ"]
        assert fields["password"] == ["prueba+&=%123"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


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
