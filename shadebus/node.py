"""Motorized shade node model.

Each node sits on the bus at an address in 1..254, belongs to a position
group (a zone of shades that move together), and answers a small command
set. Motion is modelled in simulated time: MOVE_TO sets a target and the
shade travels at a fixed percent per second until it arrives.
"""

from shadebus import frame as fr

MOTOR_SPEED_PCT_PER_S = 12.5  # full travel in 8 simulated seconds

STATUS_STOPPED = 0
STATUS_MOVING = 1


class ShadeNode:
    def __init__(self, address, group=0, latency_s=0.004, position=0.0):
        if not 1 <= address <= 254:
            raise ValueError("node address must be in 1..254")
        self.address = address
        self.group = group
        self.latency_s = latency_s
        self.position = float(position)  # 0 = open, 100 = closed
        self.target = float(position)
        # Fault knobs, all off by default.
        self.online = True
        self.drop_prob = 0.0
        # Segment position along the daisy chain, set by the network builder.
        self.segment_pos = 0

    @property
    def moving(self):
        return abs(self.position - self.target) > 1e-9

    def tick(self, dt):
        """Advance the motor by dt simulated seconds."""
        if not self.moving:
            return
        step = MOTOR_SPEED_PCT_PER_S * dt
        if self.position < self.target:
            self.position = min(self.target, self.position + step)
        else:
            self.position = max(self.target, self.position - step)

    def handle(self, request):
        """Return a reply Frame, or None if this node stays silent.

        Nodes never reply to broadcast frames. That mirrors how shared
        buses avoid guaranteed collisions on group commands.
        """
        if not self.online:
            return None
        if request.dest == fr.BROADCAST:
            self._execute(request)
            return None
        if request.dest != self.address:
            return None
        return self._execute(request)

    def _execute(self, request):
        cmd = request.cmd
        reply_cmd = cmd | fr.RESP_FLAG
        src = self.address
        if cmd == fr.CMD_PING:
            return fr.Frame(request.src, src, reply_cmd, bytes([0x01]))
        if cmd == fr.CMD_GET_STATUS:
            payload = bytes(
                [
                    self.group & 0xFF,
                    int(round(self.position)) & 0xFF,
                    STATUS_MOVING if self.moving else STATUS_STOPPED,
                ]
            )
            return fr.Frame(request.src, src, reply_cmd, payload)
        if cmd == fr.CMD_MOVE_TO:
            if len(request.payload) != 1 or request.payload[0] > 100:
                return self._nak(request)
            self.target = float(request.payload[0])
            if request.dest == fr.BROADCAST:
                return None
            return fr.Frame(request.src, src, reply_cmd, bytes([0x01]))
        if cmd == fr.CMD_GET_POSITION:
            payload = bytes(
                [
                    int(round(self.position)) & 0xFF,
                    STATUS_MOVING if self.moving else STATUS_STOPPED,
                ]
            )
            return fr.Frame(request.src, src, reply_cmd, payload)
        if cmd == fr.CMD_SET_ADDRESS:
            if len(request.payload) != 1 or not 1 <= request.payload[0] <= 254:
                return self._nak(request)
            old = self.address
            self.address = request.payload[0]
            if request.dest == fr.BROADCAST:
                return None
            # Ack from the old address so the master can confirm the change.
            return fr.Frame(request.src, old, reply_cmd, bytes([self.address]))
        return self._nak(request)

    def _nak(self, request):
        if request.dest == fr.BROADCAST:
            return None
        return fr.Frame(request.src, self.address, request.cmd | fr.RESP_FLAG, bytes([0x00]))
