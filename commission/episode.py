"""One labeled commissioning episode: build, scan, diff, diagnose, featurize."""

import time

from shadebus.faults import build_network
from commission.discovery import discover
from commission.table import verify_table
from commission.health import health_scan
from commission.localize import diagnose
from commission.classify import extract_features


def run_episode(n_nodes=32, seed=0, kind="no_fault", probes=6, address_space=None):
    """Run the full commissioning workflow on one injected fault episode.

    Returns a dict with the label, the rule diagnosis, the feature vector
    for the classifier, and timing numbers. The label is never shown to
    the tool itself, only used afterwards for scoring.
    """
    bus, expected, fault = build_network(n_nodes=n_nodes, seed=seed, kind=kind)
    wall_start = time.perf_counter()

    disc = discover(bus, addresses=address_space)
    diff = verify_table(expected, disc)
    probe_set = set(expected) | set(disc.found) | set(disc.garbled_addresses)
    health = health_scan(bus, probe_set, probes=probes)
    rule = diagnose(expected, diff, health)
    features = extract_features(expected, diff, health)

    wall = time.perf_counter() - wall_start
    return {
        "label": fault.kind,
        "fault_params": fault.params,
        "n_nodes": n_nodes,
        "seed": seed,
        "features": features,
        "rule_kind": rule.kind,
        "rule_detail": rule.detail,
        "discovery_found": len(disc.found),
        "discovery_bus_time_s": disc.bus_time_s,
        "bus_time_s": bus.clock,
        "wall_time_s": wall,
    }
