# shadebus

I wanted to understand what commissioning actually feels like for a bus of
motorized devices: you show up with an install plan that says which addresses
should exist and which zone each shade belongs to, you plug into an RS-485
style daisy chain, and half the time something is wrong in a way the wire
will not just tell you. A node is silent. Two nodes got flashed with the same
address and stomp on each other. Somebody swapped the A and B lines after a
junction and everything past it is garbage. So I built the whole situation in
software: a simulated serial bus with a framed protocol and real CRCs, six
injectable wiring and configuration faults, and a commissioning tool that has
to figure out what went wrong from scan evidence alone.

The fun constraint I held myself to: the diagnosis side never gets to peek at
the injected fault. It sees exactly what a technician with a bus analyzer
would see, reply rates, garbled frames, timeouts, an address table diff, and
has to name the fault and point at where it lives on the chain.

## The bus

Frames are `SYNC | dest | src | cmd | len | payload | CRC-16`. The CRC is
CRC-16/CCITT-FALSE (poly 0x1021, init 0xFFFF), validated in the tests against
the published check value from the CRC RevEng catalogue: crc("123456789")
must equal 0x29B1. Nodes live at addresses 1 to 254 and answer PING,
GET_STATUS, MOVE_TO, GET_POSITION, and SET_ADDRESS. Motion happens in
simulated time at a fixed percent per second, and every transaction advances
a virtual clock derived from the baud rate (38400, 10 bits per byte), so a
full scan reports realistic on-wire seconds while running in milliseconds of
host time. Everything is seeded: same seed, same network, same scan results,
byte for byte. There is a test that holds me to that.

## The faults

Each episode gets exactly one labeled fault injected at build time:

`duplicate_address` puts two nodes on one address, and if their reply windows
overlap on the wire the master reads a collision as CRC garbage.
`offline_node` is a node that never answers. `flaky_node` drops a seeded
fraction of its replies. `line_noise` corrupts a percentage of frames
traveling to or from everything at or past a chain position, each direction
rolled independently. `miswired_segment` garbles every frame crossing a
junction, which from the master's chair looks like a wall of timeouts
starting at one spot. `stale_address_table` re-addresses a few nodes so the
install plan lies about where things are.

## The tool

Commissioning runs in four passes. Discovery pings the full address space
and builds a live node map. Table verification diffs the plan against
reality: missing addresses, unexpected ones, wrong zone groups, garbled
responders. A health scan hits every relevant address K times and tallies
reply rate, garble rate, and latency spread per node. Then two diagnosers
run on identical evidence:

1. A rule engine that reasons the way I would on a ladder: one garbled
   address with a clean chain elsewhere means a duplicate; a fully silent
   contiguous suffix means a miswire at the first dead position; a degraded
   but not dead suffix means line noise; and so on.
2. A depth-6 decision tree trained on scan signature features (reply rate
   distribution, garble clustering, suffix contiguity, table diff counts,
   latency variance) over seeded labeled episodes.

I score both on the same held out episodes so the comparison stays honest.
On 105 test episodes the tree edges out the rules, 97.1% accuracy against
96.2%, and the confusion is exactly where a human would be confused: a
barely flaky node looks healthy, a very flaky one looks offline. Full
numbers and per-fault precision and recall live in RESULTS.md and
results/eval.json.

## Running it

```
python3 -m venv .venv
.venv/bin/pip install numpy scikit-learn pytest pytest-cov
.venv/bin/python -m pytest tests/ -q          # 71 tests
.venv/bin/python eval/run_eval.py             # classifier vs rules, writes results/
.venv/bin/python bench/run_bench.py           # scan timing, writes results/
```

There is also a short operator style runbook in docs/commissioning-runbook.md
describing the workflow the way I would hand it to someone standing in front
of a real bus.

## Limitations

All of it is synthetic. The protocol is invented for this project and is not
any vendor's real protocol; the bus is a Python object, not copper, so I am
modeling the failure modes I know how to describe, not the ones a real RS-485
transceiver invents at 4pm on a Friday. Collisions are approximated by reply
window overlap rather than bit level arbitration. The classifier is trained
and tested on the same simulator that generates its labels, so its numbers
say "the features separate these fault signatures" and nothing more. Wall
clock throughput numbers are single threaded on my machine (Apple silicon)
and will vary elsewhere. One real ambiguity is preserved rather than papered
over: a flaky node with a high drop rate is genuinely hard to tell from an
offline one with only a handful of probes, and both diagnosers pay for that
in the flaky_node row.
