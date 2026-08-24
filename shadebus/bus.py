"""Shared bus model with a virtual clock, timing, and fault hooks.

The bus is a broadcast medium: a master (the commissioning tool) sends a
frame and any node whose address matches replies after its response
latency. Time is simulated, not slept: byte times come from the baud
rate and the clock advances per transaction, so runs are fast and fully
deterministic under a seed.

Fault hooks handled here:
  line_noise      : traffic to or from nodes at or past a chain position is
                    corrupted with some probability, each direction rolled
                    independently
  miswired_segment: traffic to or from nodes at or past the junction is
                    always garbled
  collisions      : if two nodes reply and their reply windows overlap on
                    the wire, the master sees one garbled frame

Node level faults (offline, flaky) live on the node objects.
"""

import random

from shadebus import frame as fr

BITS_PER_BYTE = 10  # 8N1 framing: start bit, 8 data bits, stop bit


class TransactionResult:
    __slots__ = ("status", "frame", "elapsed", "cause")

    def __init__(self, status, frame=None, elapsed=0.0, cause=None):
        self.status = status  # 'ok' | 'timeout' | 'garbled'
        self.frame = frame
        self.elapsed = elapsed
        self.cause = cause  # debug only, the tool must not rely on it

    def __repr__(self):
        return "TransactionResult(%s, cause=%s, %.4fs)" % (
            self.status,
            self.cause,
            self.elapsed,
        )


class Bus:
    def __init__(self, nodes, seed=0, baud=38400, timeout_s=0.02):
        self.nodes = list(nodes)
        self.rng = random.Random(seed)
        self.baud = baud
        self.timeout_s = timeout_s
        self.clock = 0.0
        # Fault hooks.
        self.noise_start = None  # chain position where noise begins
        self.noise_prob = 0.0
        self.miswire_junction = None
        # Counters.
        self.frames_sent = 0
        self.garbled_seen = 0
        self.timeouts_seen = 0

    def byte_time(self, n_bytes):
        return n_bytes * BITS_PER_BYTE / float(self.baud)

    def _advance(self, dt):
        self.clock += dt
        for node in self.nodes:
            node.tick(dt)

    def _wire_garbles(self, segment_pos, prob_roll=True):
        """Does the wire between master and this chain position garble a frame?"""
        if self.miswire_junction is not None and segment_pos >= self.miswire_junction:
            return True, "miswire"
        if (
            self.noise_start is not None
            and segment_pos >= self.noise_start
            and prob_roll
            and self.rng.random() < self.noise_prob
        ):
            return True, "noise"
        return False, None

    def _corrupt(self, raw):
        """Flip one random byte so the CRC check fails downstream."""
        idx = self.rng.randrange(len(raw))
        flipped = raw[idx] ^ (1 + self.rng.randrange(255))
        return raw[:idx] + bytes([flipped]) + raw[idx + 1 :]

    def transaction(self, request):
        """Send one frame from the master and wait for a reply or timeout."""
        raw = request.encode()
        self.frames_sent += 1
        tx_time = self.byte_time(len(raw))
        self._advance(tx_time)

        # Deliver to every node whose configured address matches. On a real
        # bus every node parses every frame; only matching nodes act, so we
        # shortcut delivery to the matching set for speed.
        replies = []  # (latency, raw_reply, cause)
        cause = None
        for node in self.nodes:
            if request.dest != fr.BROADCAST and node.address != request.dest:
                continue
            garbled_out, out_cause = self._wire_garbles(node.segment_pos)
            if garbled_out:
                # Node receives an undecodable frame and stays silent.
                cause = cause or out_cause
                continue
            try:
                seen = fr.decode(raw)
            except fr.FrameError:
                continue
            reply = node.handle(seen)
            if reply is None:
                if not node.online:
                    cause = cause or "offline"
                continue
            if node.drop_prob and self.rng.random() < node.drop_prob:
                cause = cause or "drop"
                continue
            latency = node.latency_s * self.rng.uniform(0.8, 1.2)
            raw_reply = reply.encode()
            garbled_back, back_cause = self._wire_garbles(node.segment_pos)
            if garbled_back:
                raw_reply = self._corrupt(raw_reply)
                cause = back_cause
            replies.append((latency, raw_reply))

        if request.dest == fr.BROADCAST:
            # Nodes stay silent on broadcast; just settle the bus.
            self._advance(self.timeout_s)
            return TransactionResult("ok", None, tx_time + self.timeout_s, "broadcast")

        if not replies:
            self._advance(self.timeout_s)
            self.timeouts_seen += 1
            return TransactionResult(
                "timeout", None, tx_time + self.timeout_s, cause or "no_node"
            )

        replies.sort(key=lambda item: item[0])
        first_latency, first_raw = replies[0]
        reply_time = self.byte_time(len(first_raw))

        if len(replies) > 1:
            # Two transmitters. If the second starts before the first frame
            # ends, the wire carries a collision and the master sees garbage.
            second_latency = replies[1][0]
            if second_latency < first_latency + reply_time:
                self._advance(first_latency + reply_time)
                self.garbled_seen += 1
                return TransactionResult(
                    "garbled", None, tx_time + first_latency + reply_time, "collision"
                )

        self._advance(first_latency + reply_time)
        elapsed = tx_time + first_latency + reply_time
        try:
            decoded = fr.decode(first_raw)
        except fr.FrameError:
            self.garbled_seen += 1
            return TransactionResult("garbled", None, elapsed, cause or "corrupt")
        return TransactionResult("ok", decoded, elapsed, None)
