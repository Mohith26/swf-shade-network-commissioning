"""CRC-16/CCITT-FALSE validation.

The published check value comes from the CRC RevEng catalogue of
parametrised CRC algorithms (reveng.sourceforge.io/crc-catalogue/16.htm):
CRC-16/CCITT-FALSE has check("123456789") == 0x29B1 with poly 0x1021,
init 0xFFFF, no reflection, xorout 0x0000.
"""

import random

from shadebus.frame import crc16_ccitt, crc16_ccitt_bitwise


def test_published_check_value():
    assert crc16_ccitt(b"123456789") == 0x29B1


def test_published_check_value_bitwise_reference():
    assert crc16_ccitt_bitwise(b"123456789") == 0x29B1


def test_empty_input_returns_init():
    assert crc16_ccitt(b"") == 0xFFFF


def test_table_matches_bitwise_on_random_data():
    rng = random.Random(1234)
    for _ in range(50):
        data = bytes(rng.randrange(256) for _ in range(rng.randrange(1, 40)))
        assert crc16_ccitt(data) == crc16_ccitt_bitwise(data)


def test_appending_crc_yields_zero_residue():
    data = b"shadebus frame body"
    crc = crc16_ccitt(data)
    extended = data + bytes([(crc >> 8) & 0xFF, crc & 0xFF])
    assert crc16_ccitt(extended) == 0x0000


def test_single_bit_flip_changes_crc():
    data = b"commissioning"
    baseline = crc16_ccitt(data)
    flipped = bytes([data[0] ^ 0x01]) + data[1:]
    assert crc16_ccitt(flipped) != baseline


def test_incremental_init_chaining():
    data = b"segment by segment"
    partial = crc16_ccitt(data[:7])
    assert crc16_ccitt(data[7:], init=partial) == crc16_ccitt(data)
