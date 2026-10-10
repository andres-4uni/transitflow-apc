"""API local: telemetría de lectura y calibración explícita de la fuente activa."""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from time import monotonic

from apc.calibration import CalibrationSession
from apc.publisher.telemetry import TelemetryStore
from apc.publisher.video import LatestFrame


class TelemetryPublisher:
    def __init__(self, store: TelemetryStore, port: int = 8765, *, video: LatestFrame | None = None,
                 calibration: CalibrationSession | None = None):
        self.store = store
        self.port = port
        self.video = video
        self.calibration = calibration
        self._server = None
        self._thread = None

    def __enter__(self):
        store = self.store
        video = self.video
        calibration = self.calibration

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                path = self.path.split("?", 1)[0]
                if path == "/video":
                    self.serve_video()
                    return
                if path == "/video/status":
                    status, payload = 200, video.status() if video else {"enabled": 0, "ready": 0}
                elif path == "/telemetry":
                    status, payload = 200, store.snapshot()
                elif path == "/health":
                    status, payload = 200, {"ok": 1}
                elif path == "/calibration" and calibration is not None:
                    status, payload = 200, calibration.snapshot()
                else:
                    status, payload = 404, {"error": 404}
                self.send_json(status, payload)

            def do_POST(self):
                path = self.path.split("?", 1)[0]
                if path not in {"/calibration/apply", "/calibration/save"}:
                    self.send_error(501)
                    return
                if calibration is None:
                    self.send_json(404, {"error": "Calibración no disponible en este publicador"})
                    return
                # El dashboard usa el cliente Python local. No aceptar solicitudes de webs.
                if self.headers.get("Origin") is not None:
                    self.send_json(403, {"error": "La calibración solo acepta el cliente local"})
                    return
                if self.headers.get_content_type() != "application/json":
                    self.send_json(415, {"error": "Se requiere application/json"})
                    return
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if not 0 < length <= 8192:
                        self.send_json(413, {"error": "Solicitud vacía o demasiado grande"})
                        return
                    self.connection.settimeout(2)
                    payload = json.loads(self.rfile.read(length))
                    if not isinstance(payload, dict) or set(payload) - {"counting", "expected"}:
                        raise ValueError("Solicitud de calibración inválida")
                    values = payload.get("counting")
                    if path.endswith("/apply"):
                        result = calibration.apply(values, expected=payload.get("expected"))
                    else:
                        result = calibration.save(values, expected=payload.get("expected"))
                except (ValueError, TypeError, UnicodeError) as error:
                    self.send_json(400, {"error": str(error)})
                    return
                except OSError as error:
                    self.send_json(400, {"error": f"No se pudo completar la calibración: {error}"})
                    return
                self.send_json(200, result)

            def send_json(self, status, payload):
                body = json.dumps(payload, allow_nan=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                try:
                    self.wfile.write(body)
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def serve_video(self):
                state = video.status() if video else {"enabled": 0, "ready": 0}
                if not state["enabled"]:
                    self.send_json(404, {"error": 404, **state})
                    return
                if not state["ready"]:
                    self.send_json(503, {"error": 503, **state})
                    return
                self.connection.settimeout(2)
                self.send_response(200)
                self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
                self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
                self.send_header("Pragma", "no-cache")
                self.send_header("Connection", "close")
                self.end_headers()
                version, last_sent = -1, float("-inf")
                try:
                    while not video.closed.is_set():
                        delay = max(0, 1 / video.config.max_fps - (monotonic() - last_sent))
                        if video.closed.wait(delay):
                            break
                        latest = video.next_frame(version)
                        if latest is None:
                            if not video.status()["ready"]:
                                break
                            continue
                        version, jpeg = latest
                        header = (f"--frame\r\nContent-Type: image/jpeg\r\n"
                                  f"Content-Length: {len(jpeg)}\r\n\r\n").encode("ascii")
                        self.wfile.write(header)
                        self.wfile.write(jpeg)
                        self.wfile.write(b"\r\n")
                        self.wfile.flush()
                        last_sent = monotonic()
                    self.wfile.write(b"--frame--\r\n")
                except OSError:
                    # Desconexión o cliente lento: no retener frames ni bloquear el productor.
                    pass
                finally:
                    self.close_connection = True

            def log_message(self, *_):
                # No mantener un registro de telemetría ni de clientes.
                pass

        self._server = ThreadingHTTPServer(("127.0.0.1", self.port), Handler)
        self.port = self._server.server_port
        self._thread = Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *_):
        if self.video:
            self.video.close()
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=2)
