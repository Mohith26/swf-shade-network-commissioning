"""Rule based localization: right fault name and right place, per fault."""

from shadebus.faults import build_network
from commission.discovery import discover
from commission.table import verify_table
from commission.health import health_scan
from commission.localize import diagnose


def run(kind, seed=1, n_nodes=32, probes=8):
    bus, expected, fault = build_network(n_nodes=n_nodes, seed=seed, kind=kind)
    disc = discover(bus)
    diff = verify_table(expected, disc)
    probe_set = set(expected) | set(disc.found) | set(disc.garbled_addresses)
    health = health_scan(bus, probe_set, probes=probes)
    return diagnose(expected, diff, health), fault, expected


def test_no_fault_diagnosed_clean():
    diag, fault, _ = run("no_fault")
    assert diag.kind == "no_fault"


def test_duplicate_address_named_and_located():
    diag, fault, _ = run("duplicate_address")
    assert diag.kind == "duplicate_address"
    assert diag.detail["address"] == fault.params["address"]


def test_offline_node_named_and_located():
    diag, fault, _ = run("offline_node")
    assert diag.kind == "offline_node"
    assert diag.detail["address"] == fault.params["address"]


def test_flaky_node_named_and_located():
    diag, fault, _ = run("flaky_node", probes=20)
    assert diag.kind == "flaky_node"
    assert diag.detail["address"] == fault.params["address"]


def test_line_noise_localized_to_chain_position():
    diag, fault, _ = run("line_noise", probes=12)
    assert diag.kind == "line_noise"
    assert diag.detail["start"] >= fault.params["start"]


def test_miswired_segment_localized_to_junction():
    diag, fault, _ = run("miswired_segment")
    assert diag.kind == "miswired_segment"
    assert diag.detail["junction"] == fault.params["junction"]


def test_stale_table_lists_moved_addresses():
    diag, fault, _ = run("stale_address_table")
    assert diag.kind == "stale_address_table"
    moved_old = sorted(old for old, _new in fault.params["moved"])
    assert diag.detail["missing"] == moved_old
