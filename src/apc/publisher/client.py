"""Cliente local y validación de datos para el dashboard."""

import json
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

from apc.config import counting_from_dict
from apc.publisher.telemetry import TelemetrySample


def _calibration_request(port: int, endpoint: str, payload: dict | None = None,
                         timeout: float = 2) -> dict:
    opener = build_opener(ProxyHandler({}))
    request = Request(f"http://127.0.0.1:{port}{endpoint}")
    if payload is not None:
        request = Request(request.full_url, data=json.dumps(payload, allow_nan=False).encode("utf-8"),
                          headers={"Content-Type": "application/json"}, method="POST")
    try:
        with opener.open(request, timeout=timeout) as response:
            result = json.load(response)
    except HTTPError as error:
        if error.code == 404:
            raise ValueError("El publicador activo no ofrece calibración; inicie run_demo.py") from error
        try:
            message = json.load(error).get("error", "Solicitud de calibración rechazada")
        except (ValueError, AttributeError):
            message = "Solicitud de calibración rechazada"
        raise ValueError(message) from error
    if not isinstance(result, dict):
        raise ValueError("Respuesta de calibración inválida")
    counting_from_dict(result.get("counting"))
    return result


def fetch_calibration(port: int, timeout: float = 1) -> dict:
    result = _calibration_request(port, "/calibration", timeout=timeout)
    if (result.get("source_type") not in {"file", "webcam", "stream"}
            or not isinstance(result.get("config_path"), str)
            or any(type(result.get(key)) is not int or result[key] < 0
                   for key in ("revision", "applied_revision"))):
        raise ValueError("Estado de calibración inválido")
    if "session_id" in result and (not isinstance(result["session_id"], str) or not result["session_id"]):
        raise ValueError("Sesión de calibración inválida")
    if result["applied_revision"] > result["revision"]:
        raise ValueError("Revisión aplicada inválida")
    return result


def apply_calibration(port: int, values: dict, *, expected: dict | None = None) -> dict:
    payload = {"counting": values}
    if expected is not None:
        payload["expected"] = expected
    return _calibration_request(port, "/calibration/apply", payload)


def save_calibration(port: int, values: dict, *, expected: dict | None = None) -> dict:
    payload = {"counting": values}
    if expected is not None:
        payload["expected"] = expected
    return _calibration_request(port, "/calibration/save", payload)


def fetch_video_status(port: int, timeout: float = 1) -> dict[str, int]:
    opener = build_opener(ProxyHandler({}))
    with opener.open(f"http://127.0.0.1:{port}/video/status", timeout=timeout) as response:
        payload = json.load(response)
    if not isinstance(payload, dict) or any(
        type(payload.get(key)) is not int or payload[key] not in (0, 1)
        for key in ("enabled", "ready")
    ):
        raise ValueError("Estado de video inválido")
    return payload


def fetch_samples(port: int, timeout: float = 1) -> list[TelemetrySample]:
    # Evitar que variables de proxy envíen solicitudes locales fuera del equipo.
    opener = build_opener(ProxyHandler({}))
    with opener.open(f"http://127.0.0.1:{port}/telemetry", timeout=timeout) as response:
        payload = json.load(response)
    if not isinstance(payload, dict) or not isinstance(payload.get("wagons"), list):
        raise ValueError("Respuesta de telemetría inválida")
    samples = [TelemetrySample(**row) for row in payload["wagons"]]
    if len({sample.wagon_id for sample in samples}) != len(samples):
        raise ValueError("Vagones duplicados")
    return sorted(samples, key=lambda sample: sample.wagon_id)
