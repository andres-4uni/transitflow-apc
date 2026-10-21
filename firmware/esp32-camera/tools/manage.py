#!/usr/bin/env python3
"""Preparación y compilación reproducibles sin abrir Arduino IDE."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
CORE = "3.3.12"
FQBN = "esp32:esp32:XIAO_ESP32S3:PSRAM=opi,FlashSize=8M,CDCOnBoot=default,PartitionScheme=default_8MB,DebugLevel=none"
BUILD = ROOT / ".build"
PRIVATE = ROOT / ".private"


def write_private(path, content):
    """Creación exclusiva: no sustituir por accidente una clave existente."""
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as output:
        output.write(content)


def create_secret():
    PRIVATE.mkdir(mode=0o700, exist_ok=True)
    path = PRIVATE / "setup_password.txt"
    if path.exists():
        print("Se conserva la clave de configuración existente (sin mostrarla).")
    else:
        write_private(path, secrets.token_hex(16) + "\n")
        print("Clave aleatoria creada en .private/setup_password.txt (permisos 600).")


def prepare(destination=None, reference=False):
    manifest = json.loads((ROOT / "vendor/manifest.json").read_text())
    for name, hashes in manifest["files"].items():
        content = (ROOT / "vendor/CameraWebServer" / name).read_bytes()
        if hashlib.sha256(content).hexdigest() != hashes["sha256"]:
            raise RuntimeError(f"Referencia alterada: {name}")
    destination = destination or BUILD / ("reference/CameraWebServer" if reference else "sketch/CameraWebServer")
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True, mode=0o700)
    for name in manifest["files"]:
        shutil.copyfile(ROOT / "vendor/CameraWebServer" / name, destination / name)
    shutil.copyfile(ROOT / "src/board_config.h", destination / "board_config.h")
    if reference:
        # Referencia sin claves reales. No conectar ni subir automáticamente.
        return destination
    for path in (ROOT / "src").iterdir():
        if path.is_file():
            shutil.copyfile(path, destination / path.name)
    subprocess.run(["patch", "--batch", "--fuzz=0", "-s", str(destination / "app_httpd.cpp"),
                    str(ROOT / "patches/app_httpd.patch")], check=True)
    key = (PRIVATE / "setup_password.txt").read_text().strip()
    if len(key) != 32 or any(character not in "0123456789abcdef" for character in key):
        raise RuntimeError("Clave de AP inválida; se requieren 32 dígitos hexadecimales aleatorios")
    write_private(destination / "setup_secret.h", '#pragma once\n#define APC_SETUP_PASSWORD "' + key + '"\n')
    return destination


def cli_command():
    cli = os.environ.get("ARDUINO_CLI") or shutil.which("arduino-cli")
    bundled = Path("/Applications/Arduino IDE.app/Contents/Resources/app/lib/backend/resources/arduino-cli")
    if not cli and bundled.is_file():
        cli = str(bundled)
    if not cli:
        raise RuntimeError("Instalar Arduino CLI o definir ARDUINO_CLI; ver README del firmware")
    BUILD.mkdir(mode=0o700, exist_ok=True)
    # Todos los productos/cachés propios quedan ignorados dentro del firmware.
    config = BUILD / "arduino-cli.yaml"
    data = Path(os.environ.get("ARDUINO_DATA_DIR", str(Path.home() / "Library/Arduino15")))
    settings = {"directories": {"data": str(data), "downloads": str(BUILD / "downloads"),
                                "user": str(BUILD / "user")},
                "build_cache": {"path": str(BUILD / "cache")},
                "board_manager": {"additional_urls": ["https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json"]}}
    # JSON es un subconjunto de YAML; evita añadir PyYAML al entorno de firmware.
    config.write_text(json.dumps(settings))
    if not (data / "packages/esp32/hardware/esp32" / CORE / "platform.txt").is_file():
        raise RuntimeError(f"Falta core esp32:esp32@{CORE}; ver instrucciones de instalación")
    command = [cli, "--config-file", str(config)]
    platforms = json.loads(subprocess.run([*command, "core", "list", "--json"], check=True,
                                         capture_output=True, text=True).stdout)["platforms"]
    selected = next((platform.get("installed_version") for platform in platforms
                     if platform["id"] == "esp32:esp32"), None)
    if selected != CORE:
        raise RuntimeError(f"CLI seleccionó core {selected}; se requiere {CORE}")
    return command


def fingerprint():
    files = [*sorted((ROOT / "src").glob("*")), ROOT / "patches/app_httpd.patch",
             ROOT / "vendor/manifest.json", PRIVATE / "setup_password.txt", Path(__file__)]
    for name in json.loads((ROOT / "vendor/manifest.json").read_text())["files"]:
        files.append(ROOT / "vendor/CameraWebServer" / name)
    digest = hashlib.sha256(FQBN.encode())
    for path in files:
        digest.update(path.read_bytes())
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["secret", "prepare", "build", "reference", "upload", "ports", "monitor"])
    parser.add_argument("--port", help="Puerto USB obtenido con ports; nunca una dirección de red")
    args = parser.parse_args()
    if args.command == "secret":
        create_secret()
        return
    if args.command == "prepare":
        print(prepare())
        return
    cli = cli_command()
    if args.command in {"build", "reference"}:
        reference = args.command == "reference"
        stamp = BUILD / "verified-build.json"
        if not reference:
            stamp.unlink(missing_ok=True)
        sketch = prepare(reference=reference)
        output = BUILD / ("reference-output" if reference else "output")
        subprocess.run([*cli, "compile", "--fqbn", FQBN, "--warnings", "more", "--jobs", "4",
                        "--build-path", str(output), str(sketch)], check=True)
        if not reference:
            binary = output / "CameraWebServer.ino.bin"
            stamp.write_text(json.dumps({"fingerprint": fingerprint(), "core": CORE, "fqbn": FQBN,
                                         "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest()}, indent=2) + "\n")
    elif args.command == "ports":
        subprocess.run([*cli, "board", "list"], check=True)
    else:
        if not args.port or not args.port.startswith(("/dev/cu.", "/dev/tty", "COM")):
            parser.error("Se requiere --port con puerto USB serial explícito")
        if args.command == "monitor":
            subprocess.run([*cli, "monitor", "--port", args.port, "--config", "baudrate=115200"], check=True)
        else:
            stamp = json.loads((BUILD / "verified-build.json").read_text())
            binary = BUILD / "output/CameraWebServer.ino.bin"
            if stamp["fingerprint"] != fingerprint() or stamp["binary_sha256"] != hashlib.sha256(binary.read_bytes()).hexdigest():
                raise RuntimeError("Fuentes/clave/binario cambiaron; compilar nuevamente antes de subir")
            subprocess.run([*cli, "upload", "--fqbn", FQBN, "--port", args.port,
                            "--input-dir", str(BUILD / "output"), str(BUILD / "sketch/CameraWebServer")], check=True)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
