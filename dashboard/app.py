"""Panel de ocupación con video local optativo y telemetría numérica separada."""

import os
from pathlib import Path
from time import time

import streamlit as st

from apc.config import counting_from_dict, load_config
from apc.publisher.client import (apply_calibration, fetch_calibration, fetch_samples,
                                  fetch_video_status, save_calibration)


st.set_page_config(page_title="APC Metro · Ocupación", page_icon="🚇", layout="wide")
config = load_config(os.environ.get("APC_CONFIG", str(Path(__file__).resolve().parents[1] / "configs/default.yaml")))
st.markdown("""
<style>
.block-container {max-width: 1400px; padding-top: 2.5rem;}
.train {display:flex; gap:18px; flex-wrap:wrap; margin:24px 0 36px;}
.wagon {flex:1 1 220px; border:2px solid var(--accent); border-radius:24px;
  padding:24px; background:var(--bg); color:#142334; position:relative;}
.wagon:after {content:''; display:block; height:8px; background:#344257;
  border-radius:8px; margin-top:24px;}
.wagon-name {font-size:16px; font-weight:700; letter-spacing:1px;}
.occupancy {font-size:52px; font-weight:800; line-height:1.2; margin:18px 0 4px;}
.capacity {font-size:14px; color:#46566b;}
.status {font-size:17px; font-weight:750; margin:20px 0 12px;}
.bar {height:10px; border-radius:6px; background:#ffffffaa; overflow:hidden;}
.fill {height:100%; background:var(--accent);}
.flow {font-size:14px; margin-top:18px; color:#344257;}
</style>
""", unsafe_allow_html=True)
st.caption("APC METRO / PROTOTIPO DE AULA")
st.title("Ocupación por vagón")
st.write("Un vistazo al tren para distribuir mejor a los pasajeros.")


@st.fragment(run_every=config.telemetry.interval_seconds)
def render_video():
    st.subheader("Vista en vivo")
    st.caption("VIDEO LOCAL: no se guarda ni se transmite fuera de este equipo")
    try:
        status = fetch_video_status(config.telemetry.port)
    except (OSError, ValueError, TypeError):
        st.info("Video no disponible: no hay conexión con el publicador local.")
        return
    if not status["enabled"]:
        st.info("Video desactivado. Active visualization.stream en el YAML y ejecute "
                "run_demo.py; --fake-tracks permite probarlo sin hardware.")
        return
    if not status["ready"]:
        st.info("Stream activo, sin frames recientes. Esperando señal de video…")
        return
    # El navegador abre MJPEG directamente en loopback; Streamlit no almacena imágenes.
    st.markdown(f'<img src="http://127.0.0.1:{config.telemetry.port}/video" '
                'alt="Video local anotado en vivo" '
                'style="width:100%;max-height:65vh;object-fit:contain;border-radius:12px;background:#1e232a" />', unsafe_allow_html=True)


@st.fragment(run_every=config.telemetry.interval_seconds)
def render_calibration():
    st.subheader("Calibración de Conteo")
    try:
        active = fetch_calibration(config.telemetry.port)
    except (OSError, ValueError, TypeError):
        st.caption("Calibración no disponible. Inicie run_demo.py con el perfil de la fuente que desea calibrar.")
        return
    # Comparar contra el último estado aceptado, no contra la ruta del YAML.
    control_fields = {"cal_orientation": "orientation", "cal_position": "position",
                      "cal_band": "band_half_width", "cal_direction": "enter_direction",
                      "cal_zone_a": "zone_a_max", "cal_zone_b": "zone_b_min"}
    baseline = st.session_state.get("calibration_baseline")
    dirty = baseline is not None and any(
        key in st.session_state and st.session_state[key] != baseline["counting"][field]
        for key, field in control_fields.items())
    remote_changed = baseline is not None and any(
        baseline.get(key) != active.get(key)
        for key in ("session_id", "config_path", "source_type", "revision", "counting"))
    conflict = remote_changed and dirty
    if conflict:
        restart = baseline.get("session_id") != active.get("session_id")
        st.warning(("Nueva sesión del productor" if restart else "Cambio externo de calibración")
                   + "; hay una edición local pendiente. Elija qué configuración usar.")
        if st.button("Usar configuración del productor", key="cal_use_producer"):
            conflict = False
            dirty = False
    if baseline is None or (remote_changed and not dirty):
        for key, field in control_fields.items():
            st.session_state[key] = active["counting"][field]
        st.session_state.pop("calibration_saved", None)
        st.session_state["calibration_baseline"] = baseline = active
    values = baseline["counting"]
    labels = {"file": "archivo de video", "webcam": "webcam / cámara USB", "stream": "HTTP / RTSP"}
    st.caption(f"Fuente activa: {labels[active['source_type']]} · Perfil: {active['config_path']}")
    dual = values.get("mode", "tripwire") == "dual_zone"
    if dual:
        st.caption("Compuerta de dos zonas: A antes del primer límite, B después del segundo; "
                   "centro neutro. Colores semitransparentes y flechas IN/OUT en el video.")
    else:
        st.caption("Coordenadas normalizadas: 0 = izquierda/arriba; 1 = derecha/abajo. "
                   "La banda va desde posición − semiancho hasta posición + semiancho.")
        st.caption("En el video: línea sólida = LÍNEA DE CONTEO; límites discontinuos = banda. "
                   "Las flechas IN/OUT muestran el sentido de cada evento.")
    orientation = st.selectbox("Orientación", ["vertical", "horizontal"],
                               index=["vertical", "horizontal"].index(values["orientation"]),
                               format_func=lambda value: value.capitalize(), key="cal_orientation")
    if dual:
        zone_a = st.slider("Límite de Zona A (0–1)", 0.0, 1.0, float(values["zone_a_max"]),
                           .0001, format="%.6f", key="cal_zone_a")
        zone_b = st.slider("Límite de Zona B (0–1)", 0.0, 1.0, float(values["zone_b_min"]),
                           .0001, format="%.6f", key="cal_zone_b")
        geometry = {"zone_a_max": zone_a, "zone_b_min": zone_b}
    else:
        position = st.slider("Posición de la línea (0–1)", 0.0, 1.0,
                             float(values["position"]), 0.0001, format="%.6f", key="cal_position")
        half_width = st.slider("Semiancho de banda / tolerancia (0–1)", 0.0, 1.0,
                               float(values["band_half_width"]), 0.0001, format="%.6f", key="cal_band")
        geometry = {"position": position, "band_half_width": half_width}
    directions = ["left", "right"] if orientation == "vertical" else ["up", "down"]
    direction_labels = {"left": "Izquierda (←)", "right": "Derecha (→)", "up": "Arriba (↑)", "down": "Abajo (↓)"}
    previous_direction = st.session_state.get("cal_direction", values["enter_direction"])
    if previous_direction not in directions:
        st.session_state["cal_direction"] = directions[0]
    direction = st.selectbox("Sentido de ENTRADA", directions,
                             index=directions.index(values["enter_direction"]) if values["enter_direction"] in directions else 0,
                             format_func=direction_labels.get, key="cal_direction")
    proposed = {**values, "orientation": orientation, **geometry, "enter_direction": direction}
    valid = True
    try:
        counting_from_dict(proposed)
    except ValueError as error:
        st.error(f"Calibración inválida: {error}")
        valid = False
    if dual:
        st.caption(f"Propuesta: A < {zone_a:.6g}; neutro [{zone_a:.6g}, {zone_b:.6g}]; "
                   f"B > {zone_b:.6g}; IN hacia {direction_labels[direction].lower()}.")
    else:
        st.caption(f"Propuesta: línea {'x' if orientation == 'vertical' else 'y'}={position:.6g}; "
                   f"banda [{position-half_width:.6g}, {position+half_width:.6g}]; "
                   f"IN hacia {direction_labels[direction].lower()}.")
    st.caption("Mover los controles actualiza la vista previa y reinicia los conteos de la sesión. "
               "Solo Guardar calibración escribe el perfil para la próxima ejecución.")
    expected = ({"session_id": active["session_id"], "revision": active["revision"]}
                if "session_id" in active else None)
    resolve_local = conflict and st.button("Aplicar edición local", disabled=not valid, key="cal_use_local")
    previous_draft = st.session_state.get("calibration_draft")
    st.session_state["calibration_draft"] = proposed
    local_changed = proposed != previous_draft
    retry = (not conflict and proposed != values and not local_changed
             and st.button("Reintentar vista previa", disabled=not valid, key="cal_retry"))
    if valid and ((not conflict and proposed != values and (local_changed or retry)) or resolve_local):
        try:
            active = apply_calibration(config.telemetry.port, proposed, expected=expected)
            st.session_state["calibration_baseline"] = active
            conflict = False
        except (OSError, ValueError, TypeError) as error:
            st.error(f"No se pudo actualizar la vista previa: {error}")
            valid = False
    if active["revision"] != active["applied_revision"]:
        st.info("Calibración enviada; esperando el próximo frame de la fuente para aplicarla.")
    active_path = Path(active["config_path"])
    protected = active_path.name.lower() == "default.yaml"
    if protected:
        st.warning("default.yaml está protegido: puede previsualizar, pero no guardar. "
                   "Inicie el contador con configs/video-demo.yaml o configs/live-demo.yaml.")
    else:
        st.caption(f"Guardar actualizará únicamente el perfil activo: {active_path}")
    if st.button("Guardar calibración", disabled=not valid or protected or conflict or proposed != active["counting"], key="cal_save"):
        st.session_state.pop("calibration_saved", None)
        try:
            expected = ({"session_id": active["session_id"], "revision": active["revision"]}
                        if "session_id" in active else None)
            result = save_calibration(config.telemetry.port, proposed, expected=expected)
            st.session_state["calibration_saved"] = (proposed, result["saved_path"])
        except (OSError, ValueError, TypeError) as error:
            st.error(f"No se pudo guardar: {error}")
    saved = st.session_state.get("calibration_saved")
    if saved is not None and saved[0] == proposed:
        st.success(f"Calibración guardada en {saved[1]}")


@st.fragment(run_every=config.telemetry.interval_seconds)
def render_live():
    try:
        samples = fetch_samples(config.telemetry.port)
    except (OSError, ValueError, TypeError):
        st.error("Sin conexión con el contador. Inicie la demo o el simulador de telemetría.")
        return
    if not samples:
        st.info("Esperando el primer dato del contador…")
        return
    simulated = any(sample.simulated for sample in samples)
    if simulated:
        st.warning("SIMULACIÓN · Datos de prueba; no representan pasajeros reales.")
    else:
        st.caption("DATOS DE CÁMARA · Procesamiento local")
    now = time()
    fresh = [sample for sample in samples
             if 0 <= now - sample.timestamp <= config.telemetry.stale_after_seconds]
    columns = st.columns(4)
    columns[0].metric("Ocupación con señal", sum(s.occupancy for s in fresh) if fresh else "—")
    columns[1].metric("Entradas con señal", sum(s.entries for s in fresh) if fresh else "—")
    columns[2].metric("Salidas con señal", sum(s.exits for s in fresh) if fresh else "—")
    columns[3].metric("Vagones con señal", f"{len(fresh)} / {len(samples)}")
    if len(fresh) != len(samples):
        st.error("Hay datos desactualizados. Los vagones sin señal se muestran en gris.")
    palette = [('#13864b', '#e7f6ed', '● Disponible'),
               ('#b67800', '#fff3cd', '● Ocupación media'),
               ('#ca3544', '#fde9ec', '● Ocupación alta')]
    cards = []
    for sample in samples:
        stale = not 0 <= now - sample.timestamp <= config.telemetry.stale_after_seconds
        accent, background, label = ('#7b8796', '#eef0f3', '○ Sin señal') if stale else palette[sample.level]
        percent = sample.occupancy / sample.capacity * 100
        note = "Último valor" if stale else f"{percent:.0f}% de capacidad"
        cards.append(f"""<div class="wagon" style="--accent:{accent};--bg:{background}">
          <div class="wagon-name">VAGÓN {sample.wagon_id:02d}</div>
          <div class="occupancy">{sample.occupancy}</div>
          <div class="capacity">personas / capacidad {sample.capacity}</div>
          <div class="status">{label}</div>
          <div class="bar"><div class="fill" style="width:{min(percent, 100):.1f}%"></div></div>
          <div class="flow">{note}<br>↑ {sample.entries} entradas &nbsp; ↓ {sample.exits} salidas</div>
        </div>""")
    st.markdown('<div class="train">' + ''.join(cards) + '</div>', unsafe_allow_html=True)
    thresholds = {(sample.green_below, sample.red_above) for sample in samples}
    for green_ratio, red_ratio in sorted(thresholds):
        prefix = ""
        if len(thresholds) > 1:
            wagons = ", ".join(str(s.wagon_id) for s in samples
                               if (s.green_below, s.red_above) == (green_ratio, red_ratio))
            prefix = f"Vagón(es) {wagons}: "
        if green_ratio < 0:
            st.caption(prefix + "Umbrales no informados por el productor antiguo; color recibido del productor.")
        else:
            green, red = green_ratio * 100, red_ratio * 100
            st.caption(prefix + f"Verde <{green:g}% · Amarillo {green:g}–{red:g}% · Rojo >{red:g}%")
    if not simulated and fresh:
        st.caption(f"Procesamiento: {sum(s.fps for s in fresh) / len(fresh):.1f} FPS · "
                   "No se almacenan imágenes ni rostros.")
    else:
        st.caption("Actualización automática · Telemetría numérica separada del video opcional")


with st.sidebar:
    render_calibration()

video_panel, train_panel = st.columns([1.15, 1])
with video_panel:
    render_video()
with train_panel:
    render_live()
