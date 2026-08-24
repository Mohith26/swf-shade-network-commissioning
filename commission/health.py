"""Per node health scan: reply rate, garble rate, latency stats over K probes."""

import math

from shadebus import frame as fr


class NodeHealth:
    __slots__ = ("address", "probes", "ok", "garbled", "timeout", "latencies")

    def __init__(self, address, probes):
        self.address = address
        self.probes = probes
        self.ok = 0
        self.garbled = 0
        self.timeout = 0
        self.latencies = []

    @property
    def reply_rate(self):
        return self.ok / self.probes if self.probes else 0.0

    @property
    def garble_rate(self):
        return self.garbled / self.probes if self.probes else 0.0

    @property
    def timeout_rate(self):
        return self.timeout / self.probes if self.probes else 0.0

    @property
    def latency_mean(self):
        return sum(self.latencies) / len(self.latencies) if self.latencies else 0.0

    @property
    def latency_std(self):
        if len(self.latencies) < 2:
            return 0.0
        mean = self.latency_mean
        var = sum((x - mean) ** 2 for x in self.latencies) / (len(self.latencies) - 1)
        return math.sqrt(var)


class HealthReport:
    def __init__(self, probes_per_node):
        self.probes_per_node = probes_per_node
        self.nodes = {}  # addr -> NodeHealth

    def __getitem__(self, addr):
        return self.nodes[addr]

    def __contains__(self, addr):
        return addr in self.nodes


def health_scan(bus, addresses, probes=6):
    """Probe each address `probes` times with GET_POSITION and tally outcomes."""
    report = HealthReport(probes)
    for addr in sorted(addresses):
        nh = NodeHealth(addr, probes)
        for _ in range(probes):
            outcome = bus.transaction(fr.Frame(addr, fr.MASTER, fr.CMD_GET_POSITION))
            if outcome.status == "ok":
                nh.ok += 1
                nh.latencies.append(outcome.elapsed)
            elif outcome.status == "garbled":
                nh.garbled += 1
            else:
                nh.timeout += 1
        report.nodes[addr] = nh
    return report
