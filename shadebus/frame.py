"""Frame format and CRC for the invented shade bus protocol.

Wire layout (all single bytes unless noted):

    SYNC | DEST | SRC | CMD | LEN | PAYLOAD (LEN bytes) | CRC_HI | CRC_LO

The CRC is CRC-16/CCITT-FALSE (poly 0x1021, init 0xFFFF, no reflection,
no final xor) computed over DEST..PAYLOAD, transmitted big endian.
The standard check value for this algorithm is crc(b"123456789") == 0x29B1,
as listed in the CRC RevEng catalogue of parametrised CRC algorithms
(https://reveng.sourceforge.io/crc-catalogue/16.htm, entry CRC-16/CCITT-FALSE).
"""

SYNC = 0x7E
MASTER = 0x00
BROADCAST = 0xFF

CMD_PING = 0x01
CMD_GET_STATUS = 0x02
CMD_MOVE_TO = 0x03
CMD_GET_POSITION = 0x04
CMD_SET_ADDRESS = 0x05

# A reply carries the request command with the high bit set.
RESP_FLAG = 0x80

MAX_PAYLOAD = 32
HEADER_LEN = 5  # sync, dest, src, cmd, len
CRC_LEN = 2


class FrameError(ValueError):
    """Raised when a byte string cannot be decoded as a valid frame."""

    def __init__(self, reason, message):
        super().__init__(message)
        self.reason = reason


def crc16_ccitt_bitwise(data, init=0xFFFF):
    """Bit by bit reference implementation, kept for cross checking."""
    crc = init
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


def _build_crc_table():
    table = []
    for byte in range(256):
        crc = byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
        table.append(crc)
    return tuple(table)


_CRC_TABLE = _build_crc_table()


def crc16_ccitt(data, init=0xFFFF):
    """CRC-16/CCITT-FALSE: poly 0x1021, init 0xFFFF, no reflect, xorout 0.

    Table driven for speed; matches crc16_ccitt_bitwise byte for byte.
    """
    crc = init
    for byte in data:
        crc = ((crc << 8) & 0xFFFF) ^ _CRC_TABLE[((crc >> 8) ^ byte) & 0xFF]
    return crc


class Frame:
    """One protocol frame. Immutable enough for our purposes."""

    __slots__ = ("dest", "src", "cmd", "payload")

    def __init__(self, dest, src, cmd, payload=b""):
        if not 0 <= dest <= 0xFF:
            raise ValueError("dest out of range")
        if not 0 <= src <= 0xFF:
            raise ValueError("src out of range")
        if not 0 <= cmd <= 0xFF:
            raise ValueError("cmd out of range")
        if len(payload) > MAX_PAYLOAD:
            raise ValueError("payload too long")
        self.dest = dest
        self.src = src
        self.cmd = cmd
        self.payload = bytes(payload)

    def encode(self):
        body = bytes([self.dest, self.src, self.cmd, len(self.payload)]) + self.payload
        crc = crc16_ccitt(body)
        return bytes([SYNC]) + body + bytes([(crc >> 8) & 0xFF, crc & 0xFF])

    def __len__(self):
        return HEADER_LEN + len(self.payload) + CRC_LEN

    def __eq__(self, other):
        return (
            isinstance(other, Frame)
            and self.dest == other.dest
            and self.src == other.src
            and self.cmd == other.cmd
            and self.payload == other.payload
        )

    def __repr__(self):
        return "Frame(dest=%d, src=%d, cmd=0x%02X, payload=%r)" % (
            self.dest,
            self.src,
            self.cmd,
            self.payload,
        )


def decode(raw):
    """Decode a byte string into a Frame, raising FrameError on any defect."""
    if len(raw) < HEADER_LEN + CRC_LEN:
        raise FrameError("short", "frame shorter than minimum length")
    if raw[0] != SYNC:
        raise FrameError("bad_sync", "missing sync byte")
    length = raw[4]
    expected = HEADER_LEN + length + CRC_LEN
    if len(raw) != expected:
        raise FrameError("length", "length field does not match frame size")
    body = raw[1:-2]
    got_crc = (raw[-2] << 8) | raw[-1]
    want_crc = crc16_ccitt(body)
    if got_crc != want_crc:
        raise FrameError("crc", "CRC mismatch")
    return Frame(raw[1], raw[2], raw[3], raw[5 : 5 + length])
