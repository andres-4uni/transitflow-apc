from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, replace
import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from apc.config import CountingConfig, OccupancyConfig, load_config
from apc.counting.occupancy import OccupancyCounter
from apc.counting.tripwire import TripwireCounter
from apc.models import Track
from apc.publisher.client import fetch_samples
from apc.publisher.server import TelemetryPublisher
from apc.publisher.simulation import simulation_samples
from apc.publisher.telemetry import TelemetryStore, make_sample


def test_schema_only_numeric_and_consistent():
    sample = make_sample(1, OccupancyCounter(OccupancyConfig(initial=40)), 23.1, timestamp=100)
    assert all(type(value) in (int, float) for value in asdict(sample).values())
    assert sample.level == 1
    with pytest.raises(ValueError):
        replace(sample, occupancy=41)
    with pytest.raises(ValueError):
        replace(sample, fps=float("nan"))
    with pytest.raises(ValueError):
        replace(sample, entries=True)
    with pytest.raises(TypeError):
        TelemetryStore().publish({"frame": b"image"})


def test_store_handles_concurrent_and_old_samples():
    store = TelemetryStore()
    counter = OccupancyCounter(OccupancyConfig())
    def publish(index):
        store.publish(make_sample(1, counter, 20, timestamp=index))
    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(publish, range(100)))
    store.publish(make_sample(1, counter, 20, timestamp=0))
    result = store.snapshot()
    assert result["wagons"][0]["timestamp"] == 99
    result["wagons"][0]["entries"] = 500
    assert store.snapshot()["wagons"][0]["entries"] == 0


def test_tripwire_to_http_and_privacy():
    counter = TripwireCounter(CountingConfig())
    occupancy = OccupancyCounter(OccupancyConfig())
    for y in [0.3, 0.4, 0.7]:
        occupancy.apply(counter.update([Track(123456, (0.5, y))]))
    store = TelemetryStore()
    store.publish(make_sample(1, occupancy, 21, timestamp=100))
    with TelemetryPublisher(store, port=0) as publisher:
        assert publisher._server.server_address[0] == "127.0.0.1"
        samples = fetch_samples(publisher.port)
        assert (samples[0].entries, samples[0].exits, samples[0].occupancy) == (1, 0, 1)
        url = f"http://127.0.0.1:{publisher.port}"
        with urlopen(url + "/telemetry") as response:
            body = response.read().decode()
            assert response.headers["Cache-Control"] == "no-store"
            assert not any(value in body for value in ("123456", "frame", "centroid", "bbox", "face"))
        with urlopen(url + "/health") as response:
            assert json.load(response) == {"ok": 1}
        with pytest.raises(HTTPError) as error:
            urlopen(url + "/unknown")
        assert error.value.code == 404
        with pytest.raises(HTTPError) as error:
            urlopen(Request(url + "/telemetry", method="POST", data=b"{}"))
        assert error.value.code == 501
    assert not publisher._thread.is_alive()


def test_simulation_has_several_wagons_and_all_colors():
    samples = simulation_samples(load_config(), 0, 100)
    assert [sample.wagon_id for sample in samples] == [1, 2, 3, 4]
    assert [sample.level for sample in samples] == [0, 1, 2, 0]
    assert all(sample.simulated == 1 for sample in samples)
    later = simulation_samples(load_config(), 20, 110)
    assert any(a.occupancy != b.occupancy for a, b in zip(samples, later))


@pytest.mark.parametrize('thresholds', [(0.2, 0.5), (0.6, 0.9)])
def test_producer_thresholds_survive_http_and_simulation(thresholds):
    config = load_config()
    config = replace(config, occupancy=replace(config.occupancy,
                                              green_below=thresholds[0], red_above=thresholds[1]))
    samples = simulation_samples(config, 0, 100)
    store = TelemetryStore()
    for sample in samples:
        store.publish(sample)
    with TelemetryPublisher(store, port=0) as publisher:
        assert fetch_samples(publisher.port) == samples
    assert all((s.green_below, s.red_above) == thresholds for s in samples)


def test_legacy_samples_and_threshold_validation():
    from apc.publisher.telemetry import TelemetrySample
    sample = make_sample(1, OccupancyCounter(OccupancyConfig(initial=40)), 23, timestamp=100)
    row = asdict(sample)
    del row['green_below'], row['red_above']
    assert TelemetrySample(**row).green_below == -1
    for changes in ({'green_below': float('nan')}, {'green_below': True},
                    {'red_above': 1.1}, {'green_below': -1}, {'level': 0}):
        with pytest.raises(ValueError):
            replace(sample, **changes)
