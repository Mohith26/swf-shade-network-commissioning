"""Address table verification: expected install plan vs discovered reality."""


class TableDiff:
    def __init__(self, missing, unexpected, group_mismatch, garbled):
        self.missing = sorted(missing)  # planned addresses that did not answer
        self.unexpected = sorted(unexpected)  # answering addresses not in the plan
        self.group_mismatch = sorted(group_mismatch)  # answered with wrong group
        self.garbled = sorted(garbled)  # addresses that answered with garbage

    @property
    def clean(self):
        return not (self.missing or self.unexpected or self.group_mismatch or self.garbled)

    def __repr__(self):
        return "TableDiff(missing=%r, unexpected=%r, group_mismatch=%r, garbled=%r)" % (
            self.missing,
            self.unexpected,
            self.group_mismatch,
            self.garbled,
        )


def verify_table(expected, discovery):
    """Diff the expected address table against a DiscoveryResult."""
    found = discovery.found
    missing = [a for a in expected if a not in found]
    unexpected = [a for a in found if a not in expected]
    group_mismatch = []
    for addr, entry in found.items():
        if addr in expected and entry.get("group") is not None:
            if entry["group"] != expected[addr]["group"]:
                group_mismatch.append(addr)
    garbled = discovery.garbled_addresses
    return TableDiff(missing, unexpected, group_mismatch, garbled)
