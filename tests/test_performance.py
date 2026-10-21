from types import SimpleNamespace

import pytest

from apc.performance import LiveMetrics


def test_live_rates_include_replaced_frames_without_inflating_inferences():
    metrics = LiveMetrics()
    for index, milliseconds in zip((0, 10, 30), (10, 20, 30)):
        metrics.received(SimpleNamespace(index=index, timestamp=1000 + index / 30), index / 30)
        metrics.inferred({"inference": milliseconds, "tracking": milliseconds / 10},
                         1.5 if index == 30 else index / 30 + .1)
    result = metrics.snapshot()
    assert result["capture_fps"] == 30
    assert result["inference_fps"] == 2
    assert result["yolo_inference_ms_mean"] == 20
    assert result["bytetrack_ms_mean"] == 2
    assert result["queue_replacements"] == 28
    assert result["delivered_frames"] == result["inference_frames"] == 3


def test_stride_does_not_count_skipped_frames_as_inferences_or_queue_replacements():
    metrics = LiveMetrics()
    for index in range(11):
        metrics.received(SimpleNamespace(index=index, timestamp=1000 + index / 10), index / 10)
        if index % 2 == 0:
            metrics.inferred({"inference": 12}, index / 10 + .2)
    result = metrics.snapshot()
    assert result["capture_fps"] == 10
    assert result["inference_fps"] == 5
    assert result["stride_skipped_frames"] == 5
    assert result["queue_replacements"] == 0
    assert result["bytetrack_ms_mean"] is None


@pytest.mark.parametrize("timestamp,index", [(999, 1), (1000, 1), (float("nan"), 1), (1001, 0)])
def test_invalid_capture_clock_or_sequence_does_not_report_a_false_rate(timestamp, index):
    metrics = LiveMetrics()
    metrics.received(SimpleNamespace(index=0, timestamp=1000), 0)
    metrics.inferred({}, .1)
    metrics.received(SimpleNamespace(index=index, timestamp=timestamp), 1)
    metrics.inferred({"inference": float("nan"), "tracking": -1}, 2)
    assert metrics.snapshot()["capture_fps"] is None
    assert metrics.snapshot()["inference_fps"] == 1
    assert metrics.snapshot()["yolo_inference_ms_mean"] is None


def test_no_frames_or_single_frame_has_no_capture_rate():
    metrics = LiveMetrics()
    assert metrics.snapshot()["capture_fps"] is None
    assert metrics.snapshot()["inference_frames"] == 0
    metrics.received(SimpleNamespace(index=10, timestamp=1000), 1)
    metrics.inferred({}, 1)
    assert metrics.snapshot()["capture_fps"] is None
    assert metrics.snapshot()["inference_fps"] == 0
