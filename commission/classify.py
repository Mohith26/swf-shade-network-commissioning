"""ML fault classifier over scan signatures.

Features are aggregates a commissioning technician would read off a scan
report: reply rate distribution, garble clustering, suffix contiguity
along the chain, table diff counts, latency spread. The model is a small
decision tree so the learned splits stay inspectable.
"""

from sklearn.tree import DecisionTreeClassifier

FEATURE_NAMES = [
    "frac_missing",
    "frac_unexpected",
    "frac_group_mismatch",
    "frac_garbled_discovery",
    "mean_reply_rate",
    "min_reply_rate",
    "frac_zero_reply",
    "frac_partial_reply",
    "mean_garble_rate",
    "max_garble_rate",
    "frac_garbly_nodes",
    "suffix_zero_frac",
    "suffix_bad_frac",
    "mean_latency_std",
    "unexpected_healthy_frac",
]

ZERO_REPLY = 0.05
HEALTHY_REPLY = 0.9


def extract_features(expected, diff, health):
    """Turn one episode's scan evidence into a fixed length feature vector."""
    n = max(1, len(expected))
    ordered = sorted(expected.items(), key=lambda kv: kv[1]["segment_pos"])

    reply = []
    garble = []
    lat_std = []
    for addr, _meta in ordered:
        if addr not in health:
            continue
        nh = health[addr]
        reply.append(nh.reply_rate)
        garble.append(nh.garble_rate)
        lat_std.append(nh.latency_std)

    def frac(pred, values):
        return sum(1 for v in values if pred(v)) / n

    suffix_zero = 0
    for addr, _meta in reversed(ordered):
        nh = health.nodes.get(addr) if hasattr(health, "nodes") else None
        if nh is not None and nh.reply_rate <= ZERO_REPLY:
            suffix_zero += 1
        else:
            break
    suffix_bad = 0
    for addr, _meta in reversed(ordered):
        nh = health.nodes.get(addr) if hasattr(health, "nodes") else None
        if nh is not None and nh.reply_rate < HEALTHY_REPLY:
            suffix_bad += 1
        else:
            break

    unexpected_healthy = [
        a
        for a in diff.unexpected
        if a in health and health[a].reply_rate >= HEALTHY_REPLY
    ]

    return [
        len(diff.missing) / n,
        len(diff.unexpected) / n,
        len(diff.group_mismatch) / n,
        len(diff.garbled) / n,
        sum(reply) / len(reply) if reply else 0.0,
        min(reply) if reply else 0.0,
        frac(lambda v: v <= ZERO_REPLY, reply),
        frac(lambda v: ZERO_REPLY < v < HEALTHY_REPLY, reply),
        sum(garble) / len(garble) if garble else 0.0,
        max(garble) if garble else 0.0,
        frac(lambda v: v > 0.1, garble),
        suffix_zero / n,
        suffix_bad / n,
        sum(lat_std) / len(lat_std) if lat_std else 0.0,
        len(unexpected_healthy) / max(1, len(diff.unexpected)) if diff.unexpected else 0.0,
    ]


def train_classifier(X, y, seed=0, max_depth=6):
    """Fit a small decision tree; deterministic under the given seed."""
    model = DecisionTreeClassifier(max_depth=max_depth, random_state=seed)
    model.fit(X, y)
    return model
