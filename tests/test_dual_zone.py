"""Trayectorias sintéticas; no videos ni imágenes reales en la regresión."""

from dataclasses import replace
from types import SimpleNamespace

import pytest

from apc.config import CountingConfig, counting_from_dict
from apc.counting.dual_zone import DualZoneCounter
from apc.counting.factory import create_counter, update_counter
from apc.counting.tripwire import TripwireCounter
from apc.models import Track


def config(**changes):
    return replace(CountingConfig(mode='dual_zone', max_missing_seconds=.9,
                                  enter_direction='down', stitching=True), **changes)


def track(key, y, x=.5):
    return Track(key, (x, y))


def feed(counter, rows, start=0, step=.1):
    return [event for index, tracks in enumerate(rows)
            for event in counter.update(tracks, timestamp=start + index * step)]


def test_full_down_up_crossings_and_no_duplicate_after_edge_disappearance():
    counter = DualZoneCounter(config())
    rows = [[track(7, y)] for y in [.2, .3, .5, .7, .8, .9, .9]]
    events = feed(counter, rows + [[], [], [track(7, .9)]])
    assert [e.direction for e in events] == ['entry']
    events = feed(counter, [[track(7, y)] for y in [.7, .5, .3, .2]], start=1.1)
    assert [e.direction for e in events] == ['exit']
    assert events[0].logical_id == 1


@pytest.mark.parametrize('gap,expected', [(.8, ['entry']), (.9, ['entry']), (1.0, [])])
def test_seconds_ttl_for_same_id(gap, expected):
    counter = DualZoneCounter(config())
    feed(counter, [[track(7, .2)], [track(7, .3)], [track(7, .5)]])
    assert [e.direction for e in feed(counter, [[track(7, .7)], [track(7, .8)]],
                                      start=.2 + gap)] == expected


def test_neutral_return_and_jitter_never_cross():
    counter = DualZoneCounter(config())
    rows = [[track(7, y)] for y in [.2, .3, .4, .401, .399, .5, .649, .651, .64, .3, .2]]
    assert feed(counter, rows) == []


def test_stitch_retains_zone_history_and_reports_physical_and_logical_ids():
    rows = []
    counter = DualZoneCounter(config(), diagnostic=rows.append)
    assert feed(counter, [[track(7, .2)], [track(7, .3)], [track(7, .5)], [], []]) == []
    events = feed(counter, [[track(12, .7)], [track(12, .8)]], start=.5)
    assert len(events) == 1
    assert (events[0].track_id, events[0].logical_id, events[0].direction) == (12, 1, 'entry')
    stitched = [r for r in rows if 'stitch' in r]
    assert len(stitched) == 1
    assert stitched[0]['stitch']['from_track_id'] == 7
    assert feed(counter, [[track(12, .9)], [track(7, .9)], [track(7, .9), track(12, .9)]], start=.7) == []


@pytest.mark.parametrize('new_id,points,start,changes', [
    (12, [.7, .8], 1.2, {}),  # TTL agotado
    (12, [.7, .6], .5, {}),   # dirección opuesta
    (12, [.7, .8], .5, {'stitch_max_distance': .1}),
    (12, [.7, .8], .5, {'stitching': False}),
])
def test_unjustified_stitch_is_rejected(new_id, points, start, changes):
    counter = DualZoneCounter(config(**changes))
    feed(counter, [[track(7, .2)], [track(7, .3)], [track(7, .5)]])
    assert feed(counter, [[track(new_id, y)] for y in points], start=start) == []


def test_opposite_out_stitch_and_vertical_profile():
    for orientation, direction in [('horizontal', 'down'), ('vertical', 'right')]:
        counter = DualZoneCounter(config(orientation=orientation, enter_direction=direction))
        def item(key, p):
            return Track(key, (.5, p) if orientation == 'horizontal' else (p, .5))
        events = feed(counter, [[item(7, .9)], [item(7, .8)], [item(7, .55)], [],
                                [item(12, .35)], [item(12, .25)]])
        assert [e.direction for e in events] == ['exit']


def test_independent_ids_and_ambiguous_candidates_are_not_merged():
    counter = DualZoneCounter(config())
    events = feed(counter, [[track(7, .2, .3), track(8, .8, .7)],
                            [track(7, .3, .3), track(8, .7, .7)],
                            [track(7, .7, .3), track(8, .3, .7)],
                            [track(7, .8, .3), track(8, .2, .7)]])
    assert sorted(e.direction for e in events) == ['entry', 'exit']
    counter.reset()
    feed(counter, [[track(7, .2, .49), track(8, .2, .51)],
                   [track(7, .3, .49), track(8, .3, .51)],
                   [track(7, .5, .49), track(8, .5, .51)]])
    assert feed(counter, [[track(12, .7)], [track(12, .8)]], start=.5) == []


def test_co_visible_ids_never_stitch():
    counter = DualZoneCounter(config())
    feed(counter, [[track(7, .2)], [track(7, .3)], [track(7, .5)]])
    assert feed(counter, [[track(7, .5), track(12, .7)],
                          [track(7, .5), track(12, .8)]], start=.3) == []


def test_deep_destination_confirms_before_edge_loss_but_shallow_jitter_does_not():
    counter = DualZoneCounter(config(zone_single_observation_margin=.1))
    feed(counter, [[track(7, .8)], [track(7, .7)], [track(7, .55)]])
    events = feed(counter, [[track(7, .25)], [], []], start=.4)
    assert [e.direction for e in events] == ['exit']
    assert feed(counter, [[track(7, .2)]], start=.8) == []
    counter.reset()
    rows = [[track(7, y)] for y in [.2, .3, .4, .5, .649, .651, .64, .3, .2]]
    assert feed(counter, rows) == []


def test_deep_presence_still_requires_track_age_and_full_zone_transition():
    counter = DualZoneCounter(config(zone_single_observation_margin=.1))
    assert feed(counter, [[track(7, .2)], [track(7, .8)]]) == []
    assert len(feed(counter, [[track(7, .9)]], start=.2)) == 1
    counter.reset()
    assert feed(counter, [[track(7, .5)], [track(7, .8)], [track(7, .9)]]) == []


def test_old_alias_memory_is_bounded_while_passenger_remains_present():
    counter = DualZoneCounter(config())
    feed(counter, [[track(7, .2)], [track(7, .3)], [track(7, .5)]])
    feed(counter, [[track(12, .7)], [track(12, .8)]], start=.5)
    feed(counter, [[track(12, .8)], [track(12, .8)]], start=.9, step=.4)
    assert 7 not in counter._aliases
    assert counter._states[1].ids == {12}


def test_reused_old_id_at_incompatible_position_does_not_inherit_passenger():
    rows = []
    counter = DualZoneCounter(config(), diagnostic=rows.append)
    feed(counter, [[track(7, .2)], [track(7, .3)], [track(7, .5)]])
    assert len(feed(counter, [[track(12, .7)], [track(12, .8)]], start=.5)) == 1
    assert feed(counter, [[track(7, .7, .95)], [track(7, .8, .95)]], start=.7) == []
    assert counter._aliases[7] != counter._aliases[12]
    rejected, = [r['alias_rejection'] for r in rows if 'alias_rejection' in r]
    assert rejected['previous_logical_id'] == 1


def test_factory_and_file_clock_ignore_processing_speed():
    assert isinstance(create_counter(CountingConfig()), TripwireCounter)
    counter = create_counter(config(min_zone_frames=1))
    source = SimpleNamespace(metadata={'fps': 30})
    events = []
    for index, y in [(0, .2), (1, .3), (20, .8)]:
        packet = SimpleNamespace(index=index, timestamp=1000+index, media_seconds=None)
        events += update_counter(counter, [track(7, y)], packet, source)
    assert [e.direction for e in events] == ['entry']


def test_tripwire_seconds_is_optional_and_compatible():
    counter = TripwireCounter(CountingConfig(max_missing_seconds=.8))
    counter.update([track(7, .2)], timestamp=0)
    counter.update([track(7, .3)], timestamp=.1)
    assert len(counter.update([track(7, .8)], timestamp=.85)) == 1
    counter.reset()
    counter.update([track(7, .2)], timestamp=0)
    counter.update([track(7, .3)], timestamp=.1)
    assert not counter.update([track(7, .8)], timestamp=1.0)


@pytest.mark.parametrize('changes', [dict(mode='unknown'), dict(max_missing_seconds=0),
    dict(zone_a_max=.7), dict(zone_b_min=.2), dict(min_zone_frames=0),
    dict(stitch_min_cosine=1.1), dict(stitch_max_distance=0), dict(stitch_min_motion=0)])
def test_invalid_gate_config(changes):
    from dataclasses import asdict
    with pytest.raises(ValueError):
        counting_from_dict(asdict(config(**changes)))


def test_invalid_observations_do_not_advance_state():
    counter = DualZoneCounter(config())
    with pytest.raises(ValueError):
        counter.update([track(1, .2), track(1, .3)], timestamp=0)
    with pytest.raises(ValueError):
        counter.update([track(1, 1.1)], timestamp=0)
    feed(counter, [[track(1, .2)], [track(1, .3)]])
    with pytest.raises(ValueError):
        counter.update([], timestamp=.05)
    with pytest.raises(ValueError):
        counter.update([], timestamp=float('nan'))


def test_zone_observations_survive_tolerated_absence():
    counter = DualZoneCounter(config(stitching=False))
    events = feed(counter, [[track(7, .2)], [], [track(7, .3)], [track(7, .7)], [], [track(7, .8)]])
    assert [e.direction for e in events] == ['entry']
