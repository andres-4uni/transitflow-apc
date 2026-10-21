#!/usr/bin/env python3
"""Comprueba cabeceras MJPEG y StreamSource real, sin guardar ni mostrar imágenes."""
import argparse
import ipaddress
import json
from pathlib import Path
import socket
import sys
from time import perf_counter
from urllib.request import ProxyHandler, build_opener

# Permite ejecutar desde la raíz sin instalación adicional del paquete APC.
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))
from apc.config import SourceConfig
from apc.sources.stream import StreamSource


def local_address(host):
    """Resolver un host explícito; no recorrer ni escanear la red del usuario."""
    try:
        address = ipaddress.IPv4Address(host)
    except ipaddress.AddressValueError:
        if not host.endswith(".local") or any(character in host for character in "/:@ "):
            raise ValueError("Usar una IPv4 privada o nombre .local") from None
        address = ipaddress.IPv4Address(socket.gethostbyname(host))
    networks = ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "169.254.0.0/16", "127.0.0.0/8"]
    if not any(address in ipaddress.IPv4Network(network) for network in networks):
        raise ValueError("Solo se permite una cámara de la red local")
    return str(address)


def check_stream(host, frames=60, port=81):
    if not 1 <= frames <= 10000 or not 1 <= port <= 65535:
        raise ValueError("Cantidad de frames o puerto fuera de rango")
    address = local_address(host)
    url = f"http://{address}:{port}/stream"
    # Sin proxy del sistema, sin redirecciones a otros hosts ni descarga a disco.
    from urllib.request import HTTPRedirectHandler

    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            raise ValueError("La cámara no debe redirigir el endpoint MJPEG")

    with build_opener(ProxyHandler({}), NoRedirect()).open(url, timeout=5) as response:
        content_type = response.headers.get("Content-Type", "").lower()
        if response.status != 200 or not content_type.startswith("multipart/x-mixed-replace") or "boundary=" not in content_type:
            raise RuntimeError("El endpoint no devuelve MJPEG multipart con boundary")
    started = perf_counter()
    source = StreamSource(SourceConfig(type="stream", url=url, open_timeout_ms=5000, read_timeout_ms=3000))
    first_shape = None
    with source:
        for _ in range(frames):
            packet = source.read()
            if packet is None:
                raise RuntimeError("El stream terminó antes de completar la prueba")
            if first_shape is None:
                first_shape = packet.frame.shape
    elapsed = perf_counter() - started
    return {"ip": address, "port": port, "frames": frames, "width": first_shape[1],
            "height": first_shape[0], "seconds": round(elapsed, 3),
            "received_fps": round(frames / elapsed, 2)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("host", help="IP actual o apc-metro.local")
    parser.add_argument("--frames", type=int, default=60)
    parser.add_argument("--port", type=int, default=81)
    args = parser.parse_args()
    try:
        print(json.dumps(check_stream(args.host, args.frames, args.port)))
    except (OSError, ValueError, RuntimeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
