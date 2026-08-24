"""Each injected fault must leave its expected observable signature."""

from shadebus.faults import build_network, FAULT_KINDS, Fault
from commission.discovery import discover
from commission.health import health_scan

import pytest


def scan(bus, expected, probes=8):
    disc = discover(bus)
    probe_set = set(expected) | set(disc.found) | set(disc.garbled_addresses)
    health = health_scan(bus, probe_set, probes=probes)
    return disc, health


def test_no_fault_finds_every_planned_node():
    bus, expected, fault = build_network(n_nodes=24, seed=5, kind="no_fault")
    disc, health = scan(bus, expected)
    assert set(disc.found) == set(expected)
    assert disc.garbled_addresses == []
    assert all(health[a].reply_rate == 1.0 for a in expected)


def test_duplicate_address_garbles_the_shared_address():
    bus, expected, fault = build_network(n_nodes=24, seed=5, kind="duplicate_address")
    disc, health = scan(bus, expected)
    shared = fault.params["address"]
    abandoned = fault.params["offender_expected"]
    assert health[shared].garble_rate > 0.5
    assert health[abandoned].reply_rate == 0.0
    clean = [a for a in expected if a not in (shared, abandoned)]
    assert all(health[a].reply_rate == 1.0 for a in clean)


def test_offline_node_times_out_only_there():
    bus, expected, fault = build_network(n_nodes=24, seed=5, kind="offline_node")
    disc, health = scan(bus, expected)
    dead = fault.params["address"]
    assert dead not in disc.found
    assert health[dead].reply_rate == 0.0
    assert health[dead].timeout == health[dead].probes
    others = [a for a in expected if a != dead]
    assert all(health[a].reply_rate == 1.0 for a in others)


def test_flaky_node_drops_a_fraction_of_replies():
    bus, expected, fault = build_network(n_nodes=24, seed=5, kind="flaky_node")
    disc, health = scan(bus, expected, probes=40)
    flaky = fault.params["address"]
    rate = health[flaky].reply_rate
    assert 0.0 < rate < 1.0
    assert rate == pytest.approx(1.0 - fault.params["drop_prob"], abs=0.25)


def test_line_noise_degrades_the_tail_but_not_completely():
    bus, expected, fault = build_network(n_nodes=24, seed=5, kind="line_noise")
    disc, health = scan(bus, expected, probes=30)
    start = fault.params["start"]
    ahead = [a for a, m in expected.items() if m["segment_pos"] < start]
    behind = [a for a, m in expected.items() if m["segment_pos"] >= start]
    assert all(health[a].reply_rate == 1.0 for a in ahead)
    behind_rates = [health[a].reply_rate for a in behind]
    assert all(r < 1.0 for r in behind_rates)
    assert any(r > 0.0 for r in behind_rates)


def test_miswired_segment_silences_everything_past_the_junction():
    bus, expected, fault = build_network(n_nodes=24, seed=5, kind="miswired_segment")
    disc, health = scan(bus, expected)
    junction = fault.params["junction"]
    ahead = [a for a, m in expected.items() if m["segment_pos"] < junction]
    behind = [a for a, m in expected.items() if m["segment_pos"] >= junction]
    assert all(health[a].reply_rate == 1.0 for a in ahead)
    assert all(health[a].reply_rate == 0.0 for a in behind)


def test_stale_table_moves_nodes_to_new_addresses():
    bus, expected, fault = build_network(n_nodes=24, seed=5, kind="stale_address_table")
    disc, health = scan(bus, expected)
    for old, new in fault.params["moved"]:
        assert old in expected
        assert old not in disc.found
        assert new not in expected
        assert new in disc.found
        assert health[new].reply_rate == 1.0


def test_build_network_is_deterministic():
    for kind in FAULT_KINDS:
        bus1, exp1, f1 = build_network(n_nodes=20, seed=77, kind=kind)
        bus2, exp2, f2 = build_network(n_nodes=20, seed=77, kind=kind)
        assert exp1 == exp2
        assert f1.params == f2.params
        assert [n.address for n in bus1.nodes] == [n.address for n in bus2.nodes]


def test_unknown_fault_kind_rejected():
    with pytest.raises(ValueError):
        Fault("gremlins")
    with pytest.raises(ValueError):
        build_network(n_nodes=1, seed=0, kind="no_fault")
