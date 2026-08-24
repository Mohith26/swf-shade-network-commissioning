"""Discovery scan: enumerate the address space and build a live node map."""

import time

from shadebus import frame as fr


class DiscoveryResult:
    def __init__(self):
        self.found = {}  # addr -> {"group": int, "position": int, "moving": bool}
        self.outcome = {}  # addr -> 'ok' | 'timeout' | 'garbled'
        self.probes = 0
        self.bus_time_s = 0.0  # simulated seconds on the wire
        self.wall_time_s = 0.0  # host seconds to run the scan

    @property
    def garbled_addresses(self):
        return sorted(a for a, s in self.outcome.items() if s == "garbled")

    def __repr__(self):
        return "DiscoveryResult(%d found, %d garbled, bus %.2fs)" % (
            len(self.found),
            len(self.garbled_addresses),
            self.bus_time_s,
        )


def discover(bus, addresses=None, fetch_status=True):
    """Ping every address, then pull status from responders.

    Returns a DiscoveryResult with per address outcomes plus simulated
    bus time and host wall time.
    """
    if addresses is None:
        addresses = range(1, 255)
    result = DiscoveryResult()
    start_clock = bus.clock
    start_wall = time.perf_counter()

    for addr in addresses:
        ping = fr.Frame(addr, fr.MASTER, fr.CMD_PING)
        outcome = bus.transaction(ping)
        result.probes += 1
        result.outcome[addr] = outcome.status
        if outcome.status != "ok":
            continue
        entry = {"group": None, "position": None, "moving": None}
        if fetch_status:
            status = bus.transaction(fr.Frame(addr, fr.MASTER, fr.CMD_GET_STATUS))
            result.probes += 1
            if status.status == "ok" and len(status.frame.payload) == 3:
                entry = {
                    "group": status.frame.payload[0],
                    "position": status.frame.payload[1],
                    "moving": bool(status.frame.payload[2]),
                }
        result.found[addr] = entry

    result.bus_time_s = bus.clock - start_clock
    result.wall_time_s = time.perf_counter() - start_wall
    return result
