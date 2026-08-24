"""Rule based fault localization from scan evidence.

The rules only look at what the tool can actually observe: the expected
table (address, group, chain position from the install plan), the
discovery outcome, the table diff, and the health scan. They never peek
at the injected fault object.
"""

ZERO_REPLY = 0.05
HEALTHY_REPLY = 0.9
GARBLE_DOMINANT = 0.5


class Diagnosis:
    def __init__(self, kind, detail=None, evidence=""):
        self.kind = kind
        self.detail = dict(detail or {})
        self.evidence = evidence

    def __repr__(self):
        return "Diagnosis(%s, %r)" % (self.kind, self.detail)


def _expected_by_position(expected):
    return sorted(expected.items(), key=lambda kv: kv[1]["segment_pos"])


def diagnose(expected, diff, health):
    """Return a Diagnosis naming the most likely fault and where it is."""
    ordered = _expected_by_position(expected)
    rates = {}
    for addr, meta in ordered:
        if addr in health:
            rates[addr] = health[addr]

    bad = [a for a, nh in rates.items() if nh.reply_rate < HEALTHY_REPLY]
    garbly = [a for a, nh in rates.items() if nh.garble_rate >= GARBLE_DOMINANT]

    # Stale table: planned addresses moved somewhere else. Nodes are healthy
    # at their new addresses, nothing is garbled.
    unexpected_healthy = [
        a
        for a in diff.unexpected
        if a in health and health[a].reply_rate >= HEALTHY_REPLY
    ]
    if (
        diff.missing
        and diff.unexpected
        and len(unexpected_healthy) == len(diff.unexpected)
        and not garbly
        and len(diff.missing) <= len(diff.unexpected) + 1
    ):
        return Diagnosis(
            "stale_address_table",
            {"missing": diff.missing, "found_instead": diff.unexpected},
            "planned addresses silent while unplanned addresses answer cleanly",
        )

    # Duplicate address: exactly one address answers with collision garbage
    # while the rest of the chain is clean, except possibly the one planned
    # address the offending node abandoned.
    if garbly:
        others_partial = [
            a for a in bad if a not in garbly and rates[a].reply_rate > ZERO_REPLY
        ]
        zero_others = [
            a for a in bad if a not in garbly and rates[a].reply_rate <= ZERO_REPLY
        ]
        if len(garbly) == 1 and not others_partial and len(zero_others) <= 1:
            addr = garbly[0]
            return Diagnosis(
                "duplicate_address",
                {"address": addr, "also_missing": diff.missing},
                "replies at address %d are garbled at a collision level" % addr,
            )
        # Garbling spread across several addresses points at the wire, not
        # at one duplicated address.
        degraded = sorted(bad + [a for a in garbly if a not in bad])
        start = min(expected[a]["segment_pos"] for a in degraded if a in expected)
        return Diagnosis(
            "line_noise",
            {"start": start, "degraded": degraded},
            "garbled and dropped frames spread across the chain from position %d"
            % start,
        )

    # Suffix analysis over chain positions.
    positions = [(meta["segment_pos"], addr) for addr, meta in ordered]
    suffix_zero = []
    for pos, addr in reversed(positions):
        nh = rates.get(addr)
        if nh is not None and nh.reply_rate <= ZERO_REPLY:
            suffix_zero.append((pos, addr))
        else:
            break
    suffix_bad = []
    for pos, addr in reversed(positions):
        nh = rates.get(addr)
        if nh is not None and nh.reply_rate < HEALTHY_REPLY:
            suffix_bad.append((pos, addr))
        else:
            break

    if len(suffix_zero) >= 2 and len(suffix_zero) == len(bad):
        junction = min(pos for pos, _ in suffix_zero)
        return Diagnosis(
            "miswired_segment",
            {"junction": junction, "dead_addresses": sorted(a for _, a in suffix_zero)},
            "every node at or past chain position %d is completely silent" % junction,
        )

    if len(suffix_bad) >= 2:
        start = min(pos for pos, _ in suffix_bad)
        return Diagnosis(
            "line_noise",
            {"start": start, "degraded": sorted(a for _, a in suffix_bad)},
            "nodes at or past chain position %d degrade but still answer sometimes"
            % start,
        )

    if len(bad) == 1:
        addr = bad[0]
        nh = rates[addr]
        if nh.reply_rate <= ZERO_REPLY:
            return Diagnosis(
                "offline_node",
                {"address": addr},
                "address %d never answers while the rest of the bus is clean" % addr,
            )
        return Diagnosis(
            "flaky_node",
            {"address": addr, "reply_rate": nh.reply_rate},
            "address %d drops %.0f%% of replies" % (addr, 100 * (1 - nh.reply_rate)),
        )

    if not bad and diff.clean:
        return Diagnosis("no_fault", {}, "all planned nodes answer cleanly")

    # Weak evidence fallback: report the closest match rather than invent one.
    if bad:
        addr = bad[0]
        return Diagnosis(
            "flaky_node",
            {"address": addr},
            "unclassified degradation, closest match is a flaky node",
        )
    return Diagnosis("no_fault", {}, "no actionable evidence found")
