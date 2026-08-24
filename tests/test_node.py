"""Shade node command handling and motion model."""

import pytest

from shadebus import frame as fr
from shadebus.node import ShadeNode, MOTOR_SPEED_PCT_PER_S


def make_node(addr=10, **kwargs):
    return ShadeNode(addr, **kwargs)


def test_ping_reply():
    node = make_node()
    reply = node.handle(fr.Frame(10, fr.MASTER, fr.CMD_PING))
    assert reply.cmd == fr.CMD_PING | fr.RESP_FLAG
    assert reply.src == 10
    assert reply.dest == fr.MASTER
    assert reply.payload == bytes([0x01])


def test_get_status_payload():
    node = make_node(group=3, position=40.0)
    reply = node.handle(fr.Frame(10, fr.MASTER, fr.CMD_GET_STATUS))
    group, position, moving = reply.payload
    assert group == 3
    assert position == 40
    assert moving == 0


def test_move_to_sets_target_and_acks():
    node = make_node(position=0.0)
    reply = node.handle(fr.Frame(10, fr.MASTER, fr.CMD_MOVE_TO, bytes([80])))
    assert reply.payload == bytes([0x01])
    assert node.target == 80.0
    assert node.moving


def test_motion_advances_with_tick():
    node = make_node(position=0.0)
    node.handle(fr.Frame(10, fr.MASTER, fr.CMD_MOVE_TO, bytes([100])))
    node.tick(1.0)
    assert node.position == pytest.approx(MOTOR_SPEED_PCT_PER_S)
    node.tick(100.0)
    assert node.position == 100.0
    assert not node.moving


def test_move_to_invalid_target_naks():
    node = make_node()
    reply = node.handle(fr.Frame(10, fr.MASTER, fr.CMD_MOVE_TO, bytes([101])))
    assert reply.payload == bytes([0x00])


def test_get_position_payload():
    node = make_node(position=25.0)
    reply = node.handle(fr.Frame(10, fr.MASTER, fr.CMD_GET_POSITION))
    assert reply.payload[0] == 25
    assert reply.payload[1] == 0


def test_set_address_acks_from_old_address():
    node = make_node(addr=10)
    reply = node.handle(fr.Frame(10, fr.MASTER, fr.CMD_SET_ADDRESS, bytes([42])))
    assert node.address == 42
    assert reply.src == 10
    assert reply.payload == bytes([42])


def test_set_address_invalid_naks():
    node = make_node(addr=10)
    reply = node.handle(fr.Frame(10, fr.MASTER, fr.CMD_SET_ADDRESS, bytes([0])))
    assert reply.payload == bytes([0x00])
    assert node.address == 10


def test_ignores_other_addresses():
    node = make_node(addr=10)
    assert node.handle(fr.Frame(11, fr.MASTER, fr.CMD_PING)) is None


def test_broadcast_executes_but_stays_silent():
    node = make_node(position=0.0)
    reply = node.handle(fr.Frame(fr.BROADCAST, fr.MASTER, fr.CMD_MOVE_TO, bytes([60])))
    assert reply is None
    assert node.target == 60.0


def test_offline_node_is_silent():
    node = make_node()
    node.online = False
    assert node.handle(fr.Frame(10, fr.MASTER, fr.CMD_PING)) is None


def test_unknown_command_naks():
    node = make_node()
    reply = node.handle(fr.Frame(10, fr.MASTER, 0x7F))
    assert reply.payload == bytes([0x00])


def test_address_range_enforced():
    with pytest.raises(ValueError):
        ShadeNode(0)
    with pytest.raises(ValueError):
        ShadeNode(255)
