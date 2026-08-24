"""Same seed must mean the same episodes and the same scan results."""

from commission.episode import run_episode
from shadebus.faults import FAULT_KINDS


def strip_wall_time(ep):
    ep = dict(ep)
    ep.pop("wall_time_s")
    return ep


def test_episode_reproducible_end_to_end():
    a = run_episode(n_nodes=24, seed=11, kind="line_noise", probes=6)
    b = run_episode(n_nodes=24, seed=11, kind="line_noise", probes=6)
    assert strip_wall_time(a) == strip_wall_time(b)


def test_episode_set_reproducible():
    def episode_set():
        rows = []
        for kind in FAULT_KINDS:
            for seed in range(3):
                ep = run_episode(n_nodes=16, seed=seed, kind=kind, probes=4)
                rows.append((ep["label"], ep["rule_kind"], tuple(ep["features"])))
        return rows

    assert episode_set() == episode_set()


def test_different_seeds_differ():
    a = run_episode(n_nodes=24, seed=1, kind="offline_node")
    b = run_episode(n_nodes=24, seed=2, kind="offline_node")
    assert a["fault_params"] != b["fault_params"] or a["features"] != b["features"]
