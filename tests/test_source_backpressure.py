"""Productores sintéticos coordinados por eventos; ninguna cota de FPS/latencia."""

from queue import Queue
from threading import Event, Thread

import numpy as np
import pytest

from apc.sources.base import FramePacket, ThreadedSource


class BurstCapture:
    def __init__(self, count=100, error=False):
        self.count = count
        self.error = error
        self.index = 0
        self.drained = Event()
        self.released = Event()

    def get(self, prop):
        return 30

    def read(self):
        if self.index == self.count:
            self.drained.set()
            if self.error:
                raise OSError('backend sintético')
            return False, None
        frame = np.full((2, 2, 3), self.index, np.uint8)
        self.index += 1
        return True, frame

    def release(self):
        self.released.set()


class BurstSource(ThreadedSource):
    def __init__(self, capture, live):
        super().__init__(queue_size=2, live=live)
        self.capture = capture

    def _open_capture(self):
        return self.capture


class NonblockingFrameQueue(Queue):
    def put(self, item, block=True, timeout=None):
        if isinstance(item, FramePacket):
            assert not block, 'Un frame live no debe esperar timeout antes del reemplazo'
        return super().put(item, block=block, timeout=timeout)


def test_live_burst_completes_before_consumer_and_keeps_latest_frames():
    capture = BurstCapture()
    source = BurstSource(capture, live=True)
    source._queue = NonblockingFrameQueue(maxsize=2)
    with source:
        # Consumidor deliberadamente detenido hasta que terminó toda la ráfaga.
        assert capture.drained.wait(5)
        assert source._queue.qsize() == 2
        packets = [source.read(), source.read()]
        assert [packet.index for packet in packets] == [98, 99]
        assert [int(packet.frame[0, 0, 0]) for packet in packets] == [98, 99]
        with pytest.raises(RuntimeError, match='desconectó'):
            source.read()
        assert source.read() is None
    assert capture.released.is_set() and not source._thread.is_alive()


def test_file_backpressure_keeps_full_order_for_slow_consumer():
    capture = BurstCapture()
    source = BurstSource(capture, live=False)
    with source:
        packets = []
        for _ in range(100):
            packets.append(source.read())
            # El productor puede adelantar solo la cola acotada y un read en curso.
            assert capture.index <= len(packets) + 3
            assert source._queue.qsize() <= 2
        assert source.read() is None
    assert [packet.index for packet in packets] == list(range(100))
    assert capture.released.is_set() and not source._thread.is_alive()


@pytest.mark.parametrize('live', [False, True])
def test_read_error_and_end_are_delivered_even_when_queue_is_full(live):
    capture = BurstCapture(error=True)
    source = BurstSource(capture, live=live)
    with source:
        if live:
            assert capture.drained.wait(5)
        for _ in range(2 if live else 100):
            assert source.read() is not None
        with pytest.raises(RuntimeError, match='Falló la lectura'):
            source.read()
        assert source.read() is None
    assert capture.released.is_set() and not source._thread.is_alive()


@pytest.mark.parametrize('control', [None, RuntimeError('señal de prueba')])
def test_frame_never_replaces_a_queued_control(control):
    source = BurstSource(BurstCapture(), live=True)
    source._queue = Queue(maxsize=1)
    source._put(control)
    started, done = Event(), Event()
    def put_frame():
        started.set()
        source._put(FramePacket(1, 0, np.zeros((2, 2, 3), np.uint8)))
        done.set()
    producer = Thread(target=put_frame)
    producer.start()
    try:
        assert started.wait(5)
        assert source._queue.get(timeout=5) is control
        assert done.wait(5)
        assert source._queue.get(timeout=5).index == 1
    finally:
        source.close()
        producer.join(timeout=5)
    assert not producer.is_alive()


@pytest.mark.parametrize('live', [False, True])
def test_close_releases_capture_and_producer_waiting_on_full_queue(live):
    capture = BurstCapture()
    source = BurstSource(capture, live=live)
    source.open()
    if live:
        assert capture.drained.wait(5)
    source.close()
    assert capture.released.is_set() and not source._thread.is_alive()
    assert source._queue.empty()
    assert source.read() is None
