"""Seeded network builder with labeled fault injection.

build_network() constructs a daisy chain of shade nodes, an expected
address table (the install plan: address, group, chain position), and a
Bus, then injects exactly one labeled fault. Same seed and kind always
produce the same network, which the determinism tests rely on.
"""

import random

from shadebus.bus import Bus
from shadebus.node import ShadeNode

FAULT_KINDS = [
    "no_fault",
    "duplicate_address",
    "offline_node",
    "flaky_node",
    "line_noise",
    "miswired_segment",
    "stale_address_table",
]


class Fault:
    def __init__(self, kind, params=None):
        if kind not in FAULT_KINDS:
            raise ValueError("unknown fault kind: %r" % kind)
        self.kind = kind
        self.params = dict(params or {})

    def __repr__(self):
        return "Fault(%s, %r)" % (self.kind, self.params)


def build_network(n_nodes=32, seed=0, kind="no_fault", group_size=8):
    """Return (bus, expected_table, fault) for one labeled episode.

    expected_table maps address -> {"group": int, "segment_pos": int} and
    reflects the install plan, not necessarily live reality once the
    fault is applied.
    """
    if not 2 <= n_nodes <= 254:
        raise ValueError("n_nodes must be in 2..254")
    # Seed with a string: str seeding is stable across processes, unlike
    # tuple seeding which goes through randomized hash().
    rng = random.Random("%d:%s" % (seed, kind))

    addresses = rng.sample(range(1, 255), n_nodes)
    nodes = []
    expected = {}
    for pos, addr in enumerate(addresses):
        group = pos // group_size
        node = ShadeNode(
            addr,
            group=group,
            latency_s=rng.uniform(0.003, 0.006),
            position=rng.choice([0.0, 50.0, 100.0]),
        )
        node.segment_pos = pos
        nodes.append(node)
        expected[addr] = {"group": group, "segment_pos": pos}

    bus = Bus(nodes, seed=rng.randrange(2**31))
    params = {}

    if kind == "duplicate_address":
        victim_i, offender_i = rng.sample(range(n_nodes), 2)
        victim = nodes[victim_i]
        offender = nodes[offender_i]
        params = {"address": victim.address, "offender_expected": offender.address}
        offender.address = victim.address
    elif kind == "offline_node":
        node = rng.choice(nodes)
        node.online = False
        params = {"address": node.address}
    elif kind == "flaky_node":
        node = rng.choice(nodes)
        node.drop_prob = rng.uniform(0.3, 0.7)
        params = {"address": node.address, "drop_prob": node.drop_prob}
    elif kind == "line_noise":
        start = rng.randint(max(1, n_nodes // 4), n_nodes - 2)
        prob = rng.uniform(0.15, 0.45)
        bus.noise_start = start
        bus.noise_prob = prob
        params = {"start": start, "prob": prob}
    elif kind == "miswired_segment":
        junction = rng.randint(max(1, n_nodes // 4), n_nodes - 2)
        bus.miswire_junction = junction
        params = {"junction": junction}
    elif kind == "stale_address_table":
        moved = rng.sample(nodes, rng.randint(2, min(4, n_nodes)))
        used = set(node.address for node in nodes)
        new_addrs = []
        for node in moved:
            fresh = rng.choice([a for a in range(1, 255) if a not in used])
            used.add(fresh)
            new_addrs.append((node.address, fresh))
            node.address = fresh
        params = {"moved": new_addrs}

    return bus, expected, Fault(kind, params)
