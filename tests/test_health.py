"""Health scan tallies and latency statistics."""

import pytest

from shadebus.bus import Bus
from shadebus.node import ShadeNode
from commission.health import health_scan


def test_healthy_node_full_reply_rate():
    bus = Bus([ShadeNode(7, latency_s=0.004)], seed=2)
    report = health_scan(bus, [7], probes=10)
    nh = report[7]
    assert nh.reply_rate == 1.0
    assert nh.garble_rate == 0.0
    assert nh.timeout_rate == 0.0
    assert len(nh.latencies) == 10


def test_missing_node_full_timeout_rate():
    bus = Bus([ShadeNode(7)], seed=2)
    report = health_scan(bus, [9], probes=5)
    nh = report[9]
    assert nh.reply_rate == 0.0
    assert nh.timeout_rate == 1.0


def test_latency_stats_reflect_jitter():
    bus = Bus([ShadeNode(7, latency_s=0.005)], seed=2)
    report = health_scan(bus, [7], probes=20)
    nh = report[7]
    assert nh.latency_mean > 0.005  # latency plus airtime
    assert nh.latency_std > 0.0


def test_flaky_node_partial_rates():
    node = ShadeNode(7, latency_s=0.004)
    node.drop_prob = 0.5
    bus = Bus([node], seed=2)
    report = health_scan(bus, [7], probes=60)
    nh = report[7]
    assert nh.reply_rate == pytest.approx(0.5, abs=0.2)
    assert nh.ok + nh.timeout + nh.garbled == 60
