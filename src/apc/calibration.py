"""Calibración normalizada compartida por consola, dashboard y fuente activa."""

from dataclasses import asdict
from pathlib import Path
import re
from tempfile import NamedTemporaryFile
from threading import RLock
from uuid import uuid4

import yaml

from apc.config import Config, CountingConfig, counting_from_dict, validate_counting


def counting_values(config: CountingConfig) -> dict:
    """Serializar el sentido con palabras físicas, sin convenciones de signos."""
    values = asdict(config)
    values["enter_direction"] = config.entry_direction
    return values


def calibration_path(config_path: str | Path) -> Path:
    """Guardar exclusivamente en el perfil activo; default.yaml es solo lectura."""
    active = Path(config_path).expanduser().resolve()
    default = Path(__file__).resolve().parents[2] / "configs" / "default.yaml"
    if (active.name.lower() == "default.yaml" or active == default.resolve()
            or (active.exists() and default.exists() and active.samefile(default))):
        raise ValueError("default.yaml está protegido. Inicie el contador con otro perfil, "
                         "por ejemplo configs/video-demo.yaml o configs/live-demo.yaml.")
    if active.suffix.lower() not in {".yaml", ".yml"}:
        raise ValueError("El perfil activo debe ser un archivo YAML")
    return active


def _replace_counting(text: str, values: dict) -> str:
    """Editar escalares en el bloque conocido conservando comentarios y otros bloques."""
    try:
        original = yaml.safe_load(text)
    except yaml.YAMLError as error:
        raise ValueError("El YAML de destino no es válido; no se guardaron cambios") from error
    if not isinstance(original, dict):
        raise ValueError("La configuración debe ser un mapa YAML")
    lines = text.splitlines(keepends=True)
    starts = [index for index, line in enumerate(lines) if re.match(r"^counting\s*:", line)]
    if "counting" not in original:
        if text and not text.endswith("\n"):
            text += "\n"
        result = text + "counting:\n" + "".join(f"  {key}: {value}\n" for key, value in values.items())
    else:
        if len(starts) != 1 or not re.match(r"^counting\s*:\s*(?:#.*)?(?:\n)?$", lines[starts[0]]):
            raise ValueError("Para preservar el YAML, counting debe usar un mapa en bloque, sin alias")
        start = starts[0]
        end = next((index for index in range(start + 1, len(lines))
                    if re.match(r"^[^\s#]", lines[index])), len(lines))
        block = lines[start + 1:end]
        written = set()
        for index, line in enumerate(block):
            match = re.match(r"^(\s+)([a-z_]+)(\s*:\s*)([^#\r\n]*)(.*)$", line.rstrip("\r\n"))
            if not match or match[2] not in values:
                continue
            key = match[2]
            suffix = match[5]
            spacing = " " if suffix else ""
            block[index] = f"{match[1]}{key}{match[3]}{values[key]}{spacing}{suffix}\n"
            written.add(key)
        missing = [f"  {key}: {value}\n" for key, value in values.items() if key not in written]
        # Insertar antes de comentarios finales que suelen describir la próxima sección.
        insert = len(block)
        while insert and (not block[insert - 1].strip() or block[insert - 1].lstrip().startswith("#")):
            insert -= 1
        block[insert:insert] = missing
        result = "".join(lines[:start + 1] + block + lines[end:])
    try:
        parsed = yaml.safe_load(result)
    except yaml.YAMLError as error:
        raise ValueError("No se pudo conservar la estructura del YAML; no se guardaron cambios") from error
    expected = {**original, "counting": values}
    if parsed != expected:
        raise ValueError("No se pudo conservar la estructura del YAML; no se guardaron cambios")
    return result


def save_calibration(config_path: str | Path, counting: CountingConfig) -> Path:
    """Guardar solo mediante una llamada explícita; nunca escribir imágenes."""
    validate_counting(counting)
    destination = calibration_path(config_path)
    updated = _replace_counting(destination.read_text(encoding="utf-8"), counting_values(counting))
    temporary = None
    try:
        with NamedTemporaryFile(mode="w", encoding="utf-8", dir=destination.parent,
                                prefix=f".{destination.name}.", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(updated)
        temporary.replace(destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return destination


class CalibrationSession:
    """Pedido de calibración en RAM; el productor lo aplica entre dos frames."""

    def __init__(self, config: Config, config_path: str | Path):
        self.config_path = Path(config_path).expanduser().resolve()
        self.source_type = config.source.type
        self._counting = config.counting
        self.session_id = uuid4().hex  # Identifica el productor, nunca a una persona.
        self._revision = 0
        self._applied_revision = 0
        self._lock = RLock()

    def snapshot(self) -> dict:
        with self._lock:
            return {"session_id": self.session_id,
                    "counting": counting_values(self._counting), "revision": self._revision,
                    "applied_revision": self._applied_revision, "source_type": self.source_type,
                    "config_path": str(self.config_path)}

    def current(self) -> tuple[int, CountingConfig]:
        with self._lock:
            return self._revision, self._counting

    def mark_applied(self, revision: int) -> None:
        with self._lock:
            if not self._applied_revision <= revision <= self._revision:
                raise ValueError("Revisión de calibración inválida")
            self._applied_revision = revision

    def _proposal(self, values: dict) -> CountingConfig:
        if not isinstance(values, dict):
            raise ValueError("counting debe ser un mapa")
        return counting_from_dict({**counting_values(self._counting), **values})

    def _check_expected(self, expected: dict | None) -> None:
        if expected is not None and expected != {"session_id": self.session_id, "revision": self._revision}:
            raise ValueError("El productor cambió; revise la calibración antes de enviar de nuevo")

    def apply(self, values: dict, *, expected: dict | None = None) -> dict:
        with self._lock:
            self._check_expected(expected)
            proposed = self._proposal(values)
            if proposed != self._counting:
                self._counting = proposed
                self._revision += 1
            return self.snapshot()

    def save(self, values: dict, *, expected: dict | None = None) -> dict:
        with self._lock:
            self._check_expected(expected)
            proposed = self._proposal(values)
            destination = save_calibration(self.config_path, proposed)
            return {"saved_path": str(destination), "counting": counting_values(proposed)}
