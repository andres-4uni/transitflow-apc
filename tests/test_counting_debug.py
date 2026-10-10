"""Diagnóstico numérico optativo; estos tests no crean ni reciben imágenes."""

from io import StringIO

from apc.config import CountingConfig
from apc.counting.debug import CountingDebug
from apc.counting.tripwire import TripwireCounter
from apc.models import Track


def test_diagnostic_reports_real_states_reasons_and_event():
    rows = []
    counter = TripwireCounter(
        CountingConfig(orientation="vertical", enter_direction="left", min_track_frames=4),
        diagnostic=rows.append,
    )
    for x in [0.8, 0.2, 0.5, 0.2, 0.2]:
        counter.update([Track(7, (x, 0.4))])
    assert [row["reason"] for row in rows] == [
        "primer lado estable; falta cruce", "track demasiado joven",
        "sigue dentro de banda", "cruce completo", "no cambió de lado",
    ]
    assert [row["event"] for row in rows] == ["none", "none", "none", "entry", "none"]
    assert rows[3] == dict(frame=3, track_id=7, age=4, point=(0.2, 0.4),
                           position=-1, previous=1, current=-1,
                           movement="left", event="entry", reason="cruce completo", missing=0,
                           orientation="vertical")
    # Dentro de la banda se conserva el último lado estable, no se rearma el track.
    assert rows[2]["position"] == 0
    assert rows[2]["previous"] == rows[2]["current"] == 1


def test_diagnostic_explains_missing_and_expired_id_without_inventing_crossing():
    rows = []
    counter = TripwireCounter(CountingConfig(max_missing_frames=2), diagnostic=rows.append)
    counter.update([Track(9, (0.3, 0.2))])
    counter.update([])
    counter.update([])
    counter.update([])
    assert counter.update([Track(9, (0.3, 0.8))]) == []
    expired = next(row for row in rows if row["position"] == "expired")
    assert expired["frame"] == 3
    assert expired["reason"] == "perdió el track"
    assert expired["missing"] == 3
    assert expired["event"] == "none"
    assert expired["point"] == (0.3, 0.2)
    assert rows[-1]["age"] == 1
    assert rows[-1]["reason"] == "primer lado estable; falta cruce"
    assert [row["missing"] for row in rows if row["reason"] == "ausencia tolerada"] == [1, 2]


def test_counter_is_silent_by_default(capsys):
    counter = TripwireCounter(CountingConfig())
    events = []
    for y in [0.2, 0.2, 0.8, 0.8]:
        events.extend(counter.update([Track(1, (0.5, y))]))
    assert [event.direction for event in events] == ["entry"]
    assert capsys.readouterr() == ("", "")


def test_debug_throttles_unchanged_tracks_with_periodic_reminder():
    output = StringIO()
    counter = TripwireCounter(CountingConfig(), diagnostic=CountingDebug(output))
    for _ in range(65):
        counter.update([Track(1, (0.5, 0.2))])
    lines = output.getvalue().splitlines()
    assert len(lines) == 4
    assert "edad=1 " in lines[0]
    assert "edad=2 " in lines[1]
    assert "edad=30 " in lines[2]
    assert "edad=60 " in lines[3]
    assert all("p=(0.5000,0.2000)" in line for line in lines)


def test_debug_emits_each_event_and_tracks_ids_independently():
    output = StringIO()
    counter = TripwireCounter(
        CountingConfig(orientation="horizontal", enter_direction="up", min_track_frames=2),
        diagnostic=CountingDebug(output),
    )
    counter.update([Track(1, (0.3, 0.8)), Track(2, (0.7, 0.2))])
    counter.update([Track(1, (0.3, 0.2)), Track(2, (0.7, 0.8))])
    text = output.getvalue()
    assert "id=1 edad=2 p=(0.3000,0.2000) zona=arriba estado=1->-1 mov=up evento=IN" in text
    assert "id=2 edad=2 p=(0.7000,0.8000) zona=abajo estado=-1->1 mov=down evento=OUT" in text
    assert len(text.splitlines()) == 4


def test_debug_releases_expired_ids():
    debug = CountingDebug(StringIO())
    counter = TripwireCounter(CountingConfig(max_missing_frames=0), diagnostic=debug)
    counter.update([Track(8, (0.2, 0.2))])
    counter.update([])
    counter.update([])
    assert debug._last == {}


def test_dual_zone_successive_stitches_retire_debug_ids_without_changing_events():
    from apc.counting.dual_zone import DualZoneCounter
    config = CountingConfig(mode='dual_zone', max_missing_seconds=.9, stitching=True)
    output = StringIO()
    debug = CountingDebug(output)
    observed = DualZoneCounter(config, diagnostic=debug)
    plain = DualZoneCounter(config)
    # Dos uniones, una en cada sentido; las pausas permanecen dentro del TTL.
    samples = [(0, 7, .2), (.1, 7, .3), (.2, 7, .5), (.5, 12, .7), (.6, 12, .8),
               (.7, 12, .85), (.8, 12, .8), (.9, 12, .75), (1.0, 12, .65),
               (1.1, 12, .55), (1.4, 19, .35), (1.5, 19, .25)]
    events = []
    for seconds, key, y in samples:
        tracks = [Track(key, (.5, y))]
        actual = observed.update(tracks, timestamp=seconds)
        assert actual == plain.update(tracks, timestamp=seconds)
        events.extend(actual)
    assert [e.direction for e in events] == ['entry', 'exit']
    assert debug._last.keys() == {19}
    # Caducan aliases mientras la identidad lógica continúa activa.
    assert observed.update([Track(19, (.5, .25))], timestamp=2.2) == plain.update([Track(19, (.5, .25))], timestamp=2.2)
    assert observed._states[1].ids == {19} and debug._last.keys() == {19}
    assert observed.update([], timestamp=3.2) == plain.update([], timestamp=3.2) == []
    assert observed._states == observed._aliases == debug._last == {}
    assert 'evento=IN' in output.getvalue() and 'evento=OUT' in output.getvalue()
    assert 'caducó alias físico' in output.getvalue()


def test_retirement_of_reappearing_alias_and_reset_clear_debug():
    from apc.counting.dual_zone import DualZoneCounter
    counter = DualZoneCounter(CountingConfig(mode='dual_zone', max_missing_seconds=.9, stitching=True),
                              diagnostic=(debug := CountingDebug(StringIO())))
    for seconds, key, y in [(0, 7, .2), (.1, 7, .3), (.2, 7, .5), (.5, 12, .7), (.6, 12, .8),
                             (.7, 7, .8), (.8, 12, .8)]:
        counter.update([Track(key, (.5, y))], timestamp=seconds)
    assert 7 in debug._last
    counter.update([Track(12, (.5, .8))], timestamp=1.7)
    assert 7 not in debug._last and counter._states
    counter.reset()
    assert counter._states == debug._last == {}
