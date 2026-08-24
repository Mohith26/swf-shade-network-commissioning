"""Bus timing, delivery, determinism, and collision behaviour."""

import pytest

from shadebus import frame as fr
from shadebus.bus import Bus, BITS_PER_BYTE
from shadebus.node import ShadeNode


def test_transaction_ok_and_clock_advances():
    node = ShadeNode(5, latency_s=0.004)
    bus = Bus([node], seed=1)
    result = bus.transaction(fr.Frame(5, fr.MASTER, fr.CMD_PING))
    assert result.status == "ok"
    assert result.frame.src == 5
    assert result.elapsed > 0
    assert bus.clock == pytest.approx(result.elapsed)


def test_timeout_on_empty_address():
    bus = Bus([ShadeNode(5)], seed=1, timeout_s=0.02)
    result = bus.transaction(fr.Frame(9, fr.MASTER, fr.CMD_PING))
    assert result.status == "timeout"
    assert result.elapsed >= 0.02
    assert bus.timeouts_seen == 1


def test_byte_time_matches_baud():
    bus = Bus([], seed=0, baud=38400)
    assert bus.byte_time(1) == pytest.approx(BITS_PER_BYTE / 38400.0)


def test_same_seed_same_transcript():
    def run():
        nodes = [ShadeNode(a, latency_s=0.004) for a in (3, 7, 9)]
        nodes[1].drop_prob = 0.5
        bus = Bus(nodes, seed=42)
        transcript = []
        for _ in range(30):
            for addr in (3, 7, 9, 11):
                r = bus.transaction(fr.Frame(addr, fr.MASTER, fr.CMD_PING))
                transcript.append((addr, r.status, round(r.elapsed, 9)))
        return transcript

    assert run() == run()


def test_duplicate_address_collides():
    # Same base latency: jitter windows always overlap the reply airtime,
    # so two responders at one address must produce garbage at the master.
    a = ShadeNode(20, latency_s=0.004)
    b = ShadeNode(20, latency_s=0.004)
    bus = Bus([a, b], seed=3)
    outcomes = [bus.transaction(fr.Frame(20, fr.MASTER, fr.CMD_PING)) for _ in range(10)]
    assert all(o.status == "garbled" for o in outcomes)
    assert all(o.cause == "collision" for o in outcomes)


def test_corrupt_flips_at_least_one_byte():
    bus = Bus([], seed=9)
    raw = fr.Frame(5, fr.MASTER, fr.CMD_PING).encode()
    corrupted = bus._corrupt(raw)
    assert corrupted != raw
    assert len(corrupted) == len(raw)
    with pytest.raises(fr.FrameError):
        fr.decode(corrupted)


def test_broadcast_returns_without_reply():
    nodes = [ShadeNode(a) for a in (1, 2, 3)]
    bus = Bus(nodes, seed=0)
    result = bus.transaction(fr.Frame(fr.BROADCAST, fr.MASTER, fr.CMD_MOVE_TO, bytes([70])))
    assert result.status == "ok"
    assert result.frame is None
    assert all(n.target == 70.0 for n in nodes)
