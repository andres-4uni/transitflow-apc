from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from apc.calibration import CalibrationSession
from apc.config import load_config
from apc.publisher import client


APP_PATH = Path(__file__).resolve().parents[1] / "dashboard/app.py"


@pytest.fixture
def calibration_app(tmp_path, monkeypatch):
    profile = tmp_path / "configs" / "usb-camera.yaml"
    profile.parent.mkdir()
    profile.write_text("source:\n  type: webcam\n  index: 2\n")
    session = CalibrationSession(load_config(profile), profile)
    monkeypatch.setattr(client, "fetch_samples", lambda port: [])
    monkeypatch.setattr(client, "fetch_video_status", lambda port: {"enabled": 0, "ready": 0})
    monkeypatch.setattr(client, "fetch_calibration", lambda port: session.snapshot())
    applied, saved = [], []
    def apply(port, values, **kwargs):
        applied.append(values)
        return session.apply(values, **kwargs)
    def save(port, values, **kwargs):
        saved.append(values)
        return session.save(values, **kwargs)
    monkeypatch.setattr(client, "apply_calibration", apply)
    monkeypatch.setattr(client, "save_calibration", save)
    return AppTest.from_file(APP_PATH), session, profile, applied, saved


def test_dashboard_uses_active_source_and_separates_apply_from_save(calibration_app):
    app, session, profile, applied, saved = calibration_app
    original = profile.read_text()
    app.run(timeout=20)
    assert not app.exception
    assert "webcam / cámara USB" in " ".join(item.value for item in app.caption)
    assert str(profile) in " ".join(item.value for item in app.caption)
    app.selectbox(key="cal_orientation").set_value("vertical").run()
    app.selectbox(key="cal_direction").set_value("left").run()
    app.slider(key="cal_position").set_value(0.6).run()
    assert not app.exception and applied and not saved
    assert profile.read_text() == original
    assert applied[-1]["enter_direction"] == "left"
    assert session.current()[1].position == 0.6
    assert profile.read_text() == original and not saved
    app.button(key="cal_save").click().run()
    assert not app.exception and len(saved) == 1
    assert load_config(profile).counting.entry_direction == "left"
    app.run()
    assert len(saved) == 1 and len(app.success) == 1
    app.slider(key="cal_position").set_value(0.61).run()
    assert not app.success and load_config(profile).counting.position == 0.6


def test_dashboard_updates_directions_and_rejects_invalid_band(calibration_app):
    app, session, _, applied, saved = calibration_app
    app.run(timeout=20)
    assert app.selectbox(key="cal_direction").options == ["Arriba (↑)", "Abajo (↓)"]
    app.selectbox(key="cal_orientation").set_value("vertical").run()
    assert app.selectbox(key="cal_direction").options == ["Izquierda (←)", "Derecha (→)"]
    app.slider(key="cal_position").set_value(0.01).run()
    assert not app.exception
    assert app.button(key="cal_save").disabled
    assert not saved
    assert session.current()[1].position == 0.5


def test_dashboard_reports_save_error_without_crashing(calibration_app, monkeypatch):
    app, _, _, _, _ = calibration_app
    def reject(*args, **kwargs):
        raise ValueError("default.yaml está protegido")
    monkeypatch.setattr(client, "save_calibration", reject)
    app.run(timeout=20)
    app.button(key="cal_save").click().run()
    assert not app.exception
    assert any("default.yaml está protegido" in item.value for item in app.error)


def test_dashboard_preserves_valid_calibration_near_image_edge(calibration_app):
    app, session, _, applied, _ = calibration_app
    session.apply({"position": 0.0005, "band_half_width": 0.0001})
    app.run(timeout=20)
    assert not app.exception
    assert app.slider(key="cal_position").value == 0.0005
    assert app.slider(key="cal_band").value == 0.0001
    assert not app.button(key="cal_save").disabled
    captions = " ".join(item.value for item in app.caption)
    assert "y=0.0005" in captions and "[0.0004, 0.0006]" in captions
    assert not applied  # El backend ya tenía estos valores; no reiniciar sin cambios.
    assert session.current()[0] == 1


def test_default_profile_can_preview_but_cannot_save(calibration_app):
    app, session, profile, applied, saved = calibration_app
    session.config_path = profile.with_name("default.yaml")
    session.config_path.write_text(profile.read_text())
    original = session.config_path.read_text()
    app.run(timeout=20)
    app.slider(key="cal_position").set_value(0.6).run()
    assert not app.exception and applied
    assert app.button(key="cal_save").disabled
    assert any("default.yaml está protegido" in item.value for item in app.warning)
    assert not saved and session.config_path.read_text() == original


def test_preview_failure_disables_save_and_keeps_yaml(calibration_app, monkeypatch):
    app, _, profile, _, saved = calibration_app
    def unavailable(*args, **kwargs):
        raise OSError("sin conexión")
    monkeypatch.setattr(client, "apply_calibration", unavailable)
    original = profile.read_text()
    app.run(timeout=20)
    app.slider(key="cal_position").set_value(0.6).run()
    assert not app.exception
    assert app.button(key="cal_save").disabled
    assert any("vista previa" in item.value for item in app.error)
    assert not saved and profile.read_text() == original


def test_dual_zone_controls_edit_actual_geometry_and_preserve_mode(calibration_app):
    app, session, profile, applied, saved = calibration_app
    original = profile.read_bytes()
    session.apply({'mode': 'dual_zone', 'max_missing_seconds': .9, 'enter_direction': 'down'})
    app.run(timeout=20)
    assert not app.exception
    assert {item.key for item in app.slider} == {'cal_zone_a', 'cal_zone_b'}
    app.slider(key='cal_zone_a').set_value(.42).run()
    assert not app.exception and applied[-1]['mode'] == 'dual_zone'
    assert session.current()[1].zone_a_max == .42
    assert profile.read_bytes() == original
    app.button(key='cal_save').click().run()
    assert not app.exception and saved
    assert load_config(profile).counting.zone_a_max == .42
    app.slider(key='cal_zone_b').set_value(.3).run()
    assert app.button(key='cal_save').disabled
    assert session.current()[1].zone_b_min == .65


def test_restart_same_path_adopts_producer_without_post(calibration_app, monkeypatch):
    app, session, profile, applied, saved = calibration_app
    session.apply({'position': .61})
    app.run(timeout=20)
    new_session = CalibrationSession(load_config(profile), profile)
    new_session.apply({'position': .70})
    monkeypatch.setattr(client, 'fetch_calibration', lambda port: new_session.snapshot())
    app.run()
    assert not app.exception
    assert app.slider(key='cal_position').value == .70
    assert not applied and not saved
    assert new_session.current()[0] == 1


def test_external_update_and_unchanged_controls_never_post(calibration_app):
    app, session, _, applied, saved = calibration_app
    app.run(timeout=20)
    for _ in range(3):
        app.run()
    assert session.current()[0] == 0 and not applied
    session.apply({'position': .7, 'orientation': 'vertical', 'enter_direction': 'right'})
    app.run()
    assert not app.exception
    assert app.slider(key='cal_position').value == .7
    assert app.selectbox(key='cal_orientation').value == 'vertical'
    assert app.selectbox(key='cal_direction').value == 'right'
    assert not applied and not saved
    assert any('esperando el próximo frame' in item.value for item in app.info)
    session.mark_applied(1)
    app.run()
    assert not applied
    assert not any('esperando el próximo frame' in item.value for item in app.info)


@pytest.mark.parametrize('restart', [False, True])
def test_pending_edit_survives_remote_change_until_explicit_resolution(calibration_app, monkeypatch, restart):
    app, session, profile, applied, saved = calibration_app
    app.run(timeout=20)
    # Una propuesta inválida sigue siendo una edición pendiente del usuario.
    app.slider(key='cal_band').set_value(.6).run()
    remote = CalibrationSession(load_config(profile), profile) if restart else session
    remote.apply({'position': .7})
    monkeypatch.setattr(client, 'fetch_calibration', lambda port: remote.snapshot())
    monkeypatch.setattr(client, 'apply_calibration', lambda port, values, **kwargs: remote.apply(values, **kwargs))
    app.run()
    assert not app.exception
    assert app.slider(key='cal_position').value == .5
    assert app.slider(key='cal_band').value == .6
    assert any('edición local pendiente' in item.value for item in app.warning)
    assert app.button(key='cal_save').disabled
    assert not applied and not saved and remote.current()[0] == 1
    # Corregir el borrador no resuelve el conflicto implícitamente.
    app.slider(key='cal_band').set_value(.05).run()
    assert remote.current()[1].position == .7
    app.button(key='cal_use_local').click().run()
    assert not app.exception
    assert remote.current()[1].position == .5 and remote.current()[1].band_half_width == .05
    assert remote.current()[0] == 2 and not saved
    app.run()
    assert not any('edición local pendiente' in item.value for item in app.warning)


def test_conflict_can_discard_local_edit_by_button(calibration_app):
    app, session, _, applied, _ = calibration_app
    app.run(timeout=20)
    app.slider(key='cal_band').set_value(.6).run()
    session.apply({'position': .7})
    app.run()
    app.button(key='cal_use_producer').click().run()
    assert not app.exception
    assert app.slider(key='cal_position').value == .7
    assert app.slider(key='cal_band').value == .04
    assert not applied and session.current()[0] == 1


def test_failed_preview_is_not_retried_by_automatic_queries(calibration_app, monkeypatch):
    app, session, _, _, _ = calibration_app
    calls = []
    def unavailable(port, values, **kwargs):
        calls.append(values)
        raise OSError('sin conexión')
    monkeypatch.setattr(client, 'apply_calibration', unavailable)
    app.run(timeout=20)
    app.slider(key='cal_position').set_value(.61).run()
    for _ in range(3):
        app.run()
    assert len(calls) == 1 and session.current()[0] == 0
    assert app.slider(key='cal_position').value == .61
    assert app.button(key='cal_save').disabled
    app.button(key='cal_retry').click().run()
    assert len(calls) == 2
