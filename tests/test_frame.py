"""Frame encode and decode behaviour, including every defect path."""

import pytest

from shadebus import frame as fr


def test_round_trip_empty_payload():
    f = fr.Frame(12, fr.MASTER, fr.CMD_PING)
    assert fr.decode(f.encode()) == f


def test_round_trip_with_payload():
    f = fr.Frame(200, 7, fr.CMD_MOVE_TO, bytes([55]))
    decoded = fr.decode(f.encode())
    assert decoded.dest == 200
    assert decoded.src == 7
    assert decoded.cmd == fr.CMD_MOVE_TO
    assert decoded.payload == bytes([55])


def test_round_trip_max_payload():
    f = fr.Frame(1, 2, fr.CMD_GET_STATUS, bytes(range(fr.MAX_PAYLOAD)))
    assert fr.decode(f.encode()) == f


def test_bad_sync_rejected():
    raw = bytearray(fr.Frame(5, 0, fr.CMD_PING).encode())
    raw[0] = 0x55
    with pytest.raises(fr.FrameError) as err:
        fr.decode(bytes(raw))
    assert err.value.reason == "bad_sync"


def test_truncated_frame_rejected():
    raw = fr.Frame(5, 0, fr.CMD_PING).encode()
    with pytest.raises(fr.FrameError) as err:
        fr.decode(raw[:4])
    assert err.value.reason == "short"


def test_length_field_mismatch_rejected():
    raw = bytearray(fr.Frame(5, 0, fr.CMD_GET_STATUS, b"ab").encode())
    raw[4] = 5  # lie about payload length
    with pytest.raises(fr.FrameError) as err:
        fr.decode(bytes(raw))
    assert err.value.reason == "length"


def test_corrupted_payload_rejected_by_crc():
    raw = bytearray(fr.Frame(5, 0, fr.CMD_GET_STATUS, b"ab").encode())
    raw[5] ^= 0xFF
    with pytest.raises(fr.FrameError) as err:
        fr.decode(bytes(raw))
    assert err.value.reason == "crc"


def test_corrupted_crc_byte_rejected():
    raw = bytearray(fr.Frame(9, 0, fr.CMD_PING).encode())
    raw[-1] ^= 0x01
    with pytest.raises(fr.FrameError) as err:
        fr.decode(bytes(raw))
    assert err.value.reason == "crc"


def test_payload_too_long_rejected_at_build():
    with pytest.raises(ValueError):
        fr.Frame(1, 0, fr.CMD_PING, bytes(fr.MAX_PAYLOAD + 1))


def test_address_range_validated():
    with pytest.raises(ValueError):
        fr.Frame(300, 0, fr.CMD_PING)
    with pytest.raises(ValueError):
        fr.Frame(1, -1, fr.CMD_PING)


def test_frame_wire_length():
    f = fr.Frame(1, 0, fr.CMD_PING, b"xyz")
    assert len(f.encode()) == fr.HEADER_LEN + 3 + fr.CRC_LEN
