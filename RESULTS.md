# Results and validation notes

Personal notes on what I measured, with exact commands. Machine: Apple
silicon Mac, single thread, Python 3.9.6, numpy 2.0.2, scikit-learn 1.6.1.
Bus times are simulated on-wire seconds at 38400 baud with a 20 ms reply
timeout; wall times are host seconds and are machine specific.

## CRC validation

CRC-16/CCITT-FALSE checked against the published check value from the CRC
RevEng catalogue (reveng.sourceforge.io/crc-catalogue/16.htm):
crc(b"123456789") == 0x29B1, for both the table driven and the bit by bit
implementation, plus a zero residue property test (data + appended CRC
recomputes to 0x0000) and a 50 case random cross check between the two
implementations.

```
.venv/bin/python -m pytest tests/test_crc.py -q
```

## Fault classification, classifier vs rule baseline

350 labeled episodes, 50 per class across 7 classes (6 faults plus
no_fault), node counts drawn from {24, 32, 40, 48}, 6 health probes per
node, full 254 address discovery per episode. Stratified 70/30 split,
seed 7: 245 train, 105 test. Model is DecisionTreeClassifier(max_depth=6,
random_state=7). The rule baseline needs no training and is scored on the
same 105 test episodes.

```
.venv/bin/python eval/run_eval.py --per-class 50 --seed 7
```

Episode generation took 2.4 s wall for all 350 episodes.

| fault | clf P | clf R | clf F1 | rule P | rule R | rule F1 |
|---|---|---|---|---|---|---|
| no_fault | 0.94 | 1.00 | 0.97 | 0.94 | 1.00 | 0.97 |
| duplicate_address | 1.00 | 0.93 | 0.97 | 1.00 | 0.87 | 0.93 |
| offline_node | 0.88 | 1.00 | 0.94 | 0.94 | 1.00 | 0.97 |
| flaky_node | 1.00 | 0.87 | 0.93 | 0.87 | 0.87 | 0.87 |
| line_noise | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| miswired_segment | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| stale_address_table | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |

Classifier: accuracy 0.9714, macro precision 0.9743, macro recall 0.9714,
macro F1 0.9713. Rule baseline: accuracy 0.9619, macro precision 0.9642,
macro recall 0.9619, macro F1 0.9615. Confusion matrices for both are in
results/confusion_matrix.json (rows are true labels, label order as in
the file). The errors are the honest kind: mild flaky nodes pass as
healthy or read as offline when the drop rate is extreme, and a duplicate
whose two reply windows rarely overlap can look like something else. The
tree beats the rules by about one test episode per hundred, not by magic.

## Scan throughput

Median of 5 runs each, no_fault networks, full 254 address discovery.

```
.venv/bin/python bench/run_bench.py
```

| n nodes | discovery bus s | discovery wall s | probes/s (wall) |
|---|---|---|---|
| 32 | 5.40 | 0.0030 | 95720 |
| 128 | 4.98 | 0.0131 | 29097 |
| 254 | 4.38 | 0.0331 | 15344 |

Discovery probes = 254 pings + one GET_STATUS per responder (286 probes at
n=32, 508 at n=254). Simulated bus time falls as node count rises because
empty addresses each burn the full 20 ms timeout while populated ones
answer in a few ms: a fuller bus is a faster scan in wire time, which
surprised me until I did the arithmetic. Wall time rises with node count
because the simulator does more per-node work; probes/s is wall clock and
machine specific.

End to end commissioning (discovery + table verification + 6 probe health
scan + diagnosis), median of 5:

| n nodes | bus s | wall s |
|---|---|---|
| 32 | 7.07 | 0.0056 |
| 128 | 11.67 | 0.0407 |
| 254 | 17.55 | 0.1302 |

## Tests and coverage

```
.venv/bin/python -m pytest tests/ -q
.venv/bin/python -m pytest tests/ -q --cov=shadebus --cov=commission --cov-report=term
```

71 passed, 97% line coverage over shadebus/ and commission/ (549
statements, 15 missed). Determinism is tested end to end: the same seed
reproduces identical episode features, rule diagnoses, and bus timings,
and the network builder seeds with strings specifically because tuple
seeding goes through Python's randomized hash and silently breaks
cross-process reproducibility. I hit that for real; the test suite now
would catch it.

## Caveats

Everything is simulated and seeded; no hardware was involved anywhere.
The classifier's test set comes from the same generator as its training
set, so these numbers measure signature separability inside the sim, not
field performance. Rule thresholds (reply rate 0.9 healthy, 0.05 dead,
garble 0.5 collision level) were chosen by eyeballing early runs, not
fitted, which keeps the baseline honest but also means it is tunable.
