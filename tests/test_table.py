"""Address table diff cases."""

from commission.discovery import DiscoveryResult
from commission.table import verify_table


def make_discovery(found, outcomes=None):
    disc = DiscoveryResult()
    for addr, group in found.items():
        disc.found[addr] = {"group": group, "position": 0, "moving": False}
        disc.outcome[addr] = "ok"
    for addr, status in (outcomes or {}).items():
        disc.outcome[addr] = status
    return disc


EXPECTED = {
    10: {"group": 0, "segment_pos": 0},
    20: {"group": 0, "segment_pos": 1},
    30: {"group": 1, "segment_pos": 2},
}


def test_clean_diff():
    disc = make_discovery({10: 0, 20: 0, 30: 1})
    diff = verify_table(EXPECTED, disc)
    assert diff.clean
    assert diff.missing == []
    assert diff.unexpected == []
    assert diff.group_mismatch == []


def test_missing_address_reported():
    disc = make_discovery({10: 0, 30: 1})
    diff = verify_table(EXPECTED, disc)
    assert diff.missing == [20]
    assert not diff.clean


def test_unexpected_address_reported():
    disc = make_discovery({10: 0, 20: 0, 30: 1, 99: 2})
    diff = verify_table(EXPECTED, disc)
    assert diff.unexpected == [99]


def test_group_mismatch_reported():
    disc = make_discovery({10: 0, 20: 1, 30: 1})
    diff = verify_table(EXPECTED, disc)
    assert diff.group_mismatch == [20]


def test_garbled_addresses_carried_through():
    disc = make_discovery({10: 0, 30: 1}, outcomes={20: "garbled"})
    diff = verify_table(EXPECTED, disc)
    assert diff.garbled == [20]
    assert diff.missing == [20]


def test_unknown_group_not_counted_as_mismatch():
    disc = make_discovery({10: 0, 20: 0, 30: 1})
    disc.found[30]["group"] = None
    diff = verify_table(EXPECTED, disc)
    assert diff.group_mismatch == []
