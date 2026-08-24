"""Scan throughput benchmarks.

Measures discovery scan cost against bus size, probe throughput, and a
full end to end commissioning run (discovery, table verification, health
scan, diagnosis). Reports both simulated bus seconds (what a real wire
at this baud rate would take) and host wall seconds (what the simulator
costs to run). Writes results/bench.json.

Usage:
    .venv/bin/python bench/run_bench.py
"""

import argparse
import json
import os
import platform
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from commission.discovery import discover
from commission.health import health_scan
from commission.localize import diagnose
from commission.table import verify_table
from shadebus.faults import build_network

NODE_COUNTS = [32, 128, 254]
REPEATS = 5


def bench_discovery(n_nodes, seed):
    runs = []
    for rep in range(REPEATS):
        bus, expected, _ = build_network(n_nodes=n_nodes, seed=seed + rep, kind="no_fault")
        disc = discover(bus)
        runs.append(
            {
                "wall_s": disc.wall_time_s,
                "bus_s": disc.bus_time_s,
                "probes": disc.probes,
                "found": len(disc.found),
            }
        )
    walls = [r["wall_s"] for r in runs]
    return {
        "n_nodes": n_nodes,
        "address_space": 254,
        "probes_per_run": runs[0]["probes"],
        "found": runs[0]["found"],
        "bus_time_s_median": round(statistics.median(r["bus_s"] for r in runs), 4),
        "wall_time_s_median": round(statistics.median(walls), 5),
        "probes_per_sec_wall": round(runs[0]["probes"] / statistics.median(walls), 1),
        "repeats": REPEATS,
    }


def bench_end_to_end(n_nodes, seed, probes):
    runs = []
    for rep in range(REPEATS):
        bus, expected, _ = build_network(n_nodes=n_nodes, seed=seed + rep, kind="no_fault")
        t0 = time.perf_counter()
        start_clock = bus.clock
        disc = discover(bus)
        diff = verify_table(expected, disc)
        probe_set = set(expected) | set(disc.found) | set(disc.garbled_addresses)
        health = health_scan(bus, probe_set, probes=probes)
        diag = diagnose(expected, diff, health)
        runs.append(
            {
                "wall_s": time.perf_counter() - t0,
                "bus_s": bus.clock - start_clock,
                "diagnosis": diag.kind,
            }
        )
    assert all(r["diagnosis"] == "no_fault" for r in runs)
    return {
        "n_nodes": n_nodes,
        "health_probes_per_node": probes,
        "bus_time_s_median": round(statistics.median(r["bus_s"] for r in runs), 4),
        "wall_time_s_median": round(statistics.median(r["wall_s"] for r in runs), 5),
        "repeats": REPEATS,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=100)
    parser.add_argument("--probes", type=int, default=6)
    parser.add_argument("--out", default="results")
    args = parser.parse_args()

    result = {
        "machine": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "python": platform.python_version(),
            "note": "single thread, simulated clock for bus time",
        },
        "bus_config": {"baud": 38400, "timeout_s": 0.02},
        "discovery": [bench_discovery(n, args.seed) for n in NODE_COUNTS],
        "end_to_end": [bench_end_to_end(n, args.seed, args.probes) for n in NODE_COUNTS],
    }

    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "bench.json"), "w") as fh:
        json.dump(result, fh, indent=2)

    for row in result["discovery"]:
        print(
            "discovery n=%3d: bus %7.2fs, wall %7.4fs, %8.0f probes/s (wall)"
            % (
                row["n_nodes"],
                row["bus_time_s_median"],
                row["wall_time_s_median"],
                row["probes_per_sec_wall"],
            )
        )
    for row in result["end_to_end"]:
        print(
            "end-to-end n=%3d: bus %7.2fs, wall %7.4fs"
            % (row["n_nodes"], row["bus_time_s_median"], row["wall_time_s_median"])
        )


if __name__ == "__main__":
    main()
