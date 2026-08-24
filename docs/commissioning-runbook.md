# Commissioning runbook

How I run a commissioning pass on a shade bus with this tool, written the
way I would hand it to someone doing it for the first time. The tool never
guesses from the plan alone; every claim below comes from scan evidence.

## Before you start

Have the install plan handy. In this tool that is the expected address
table: for every planned shade, its bus address, its position group (the
zone it moves with), and its position along the daisy chain. The chain
position matters because two of the nastiest faults, miswires and line
noise, are located by where the chain goes bad, not by which address.

## Step 1: discovery

Run a discovery scan. It pings every address from 1 to 254, then pulls
status (group, position, moving) from everything that answers.

You get three outcomes per address and each one is information:

- answered: the node is alive at that address
- timeout: nothing transmitted, or nothing intelligible arrived at the node
- garbled: something transmitted but the frame failed its CRC

A garbled address is the loudest clue on the bus. One address garbled with
everything else clean almost always means two nodes are sitting on it and
colliding.

## Step 2: verify the address table

Diff the plan against discovery. Four buckets come out:

- missing: planned addresses nobody answered from
- unexpected: live addresses the plan does not know about
- group mismatch: right address, wrong zone
- garbled: addresses that answered with garbage

Read missing and unexpected together. A few missing plus the same count of
unexpected, all healthy, usually means the plan is stale: the shades are
fine, they just got re-addressed after the plan was printed. Missing with
nothing unexpected points at dead nodes or dead wire.

## Step 3: health scan

Probe every relevant address several times (I default to 6) and record per
node reply rate, garble rate, and latency spread. One ping is a coin flip;
six probes turn "it seemed fine" into a rate you can compare across the
chain. Scan the union of planned and discovered addresses so both stale
plans and surprise nodes get covered.

## Step 4: read the diagnosis

The tool prints a named fault and where it lives. What each one means on
the ladder:

- duplicate_address: two nodes share the named address. Power down one leg
  or re-address one node, then rescan.
- offline_node: the named address never answers while everything else is
  clean. Check power and the local drop first.
- flaky_node: the named address answers but drops a chunk of replies. Look
  at its connector before you blame the node.
- miswired_segment: everything at or past the named chain position is
  stone silent. Walk to that junction and check polarity and continuity.
- line_noise: nodes past the named position degrade but still answer
  sometimes. Look for a noise source or damaged shielding along that run.
- stale_address_table: the shades moved addresses, the plan did not.
  Update the plan, nothing is broken on the wire.
- no_fault: every planned node answers cleanly and the table matches.

The diagnosis also carries its evidence string. If the evidence does not
match what you see on the wall, trust the wall and rescan; one scan is a
sample, not a verdict.

## After any fix

Rescan from step 1. Fixing a miswire can reveal a second fault that was
hiding behind the dead segment, and a rescan after the fix is the only
way to close out the job with a clean table diff as the record.
