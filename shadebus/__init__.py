"""shadebus: a small simulated RS-485 style bus of motorized shade nodes.

Everything here is synthetic and seeded. The protocol is invented for this
project and does not correspond to any real product protocol.
"""

from shadebus.frame import (
    SYNC,
    MASTER,
    BROADCAST,
    CMD_PING,
    CMD_GET_STATUS,
    CMD_MOVE_TO,
    CMD_GET_POSITION,
    CMD_SET_ADDRESS,
    RESP_FLAG,
    Frame,
    FrameError,
    crc16_ccitt,
)
from shadebus.node import ShadeNode
from shadebus.bus import Bus, TransactionResult
from shadebus.faults import Fault, FAULT_KINDS, build_network

__all__ = [
    "SYNC",
    "MASTER",
    "BROADCAST",
    "CMD_PING",
    "CMD_GET_STATUS",
    "CMD_MOVE_TO",
    "CMD_GET_POSITION",
    "CMD_SET_ADDRESS",
    "RESP_FLAG",
    "Frame",
    "FrameError",
    "crc16_ccitt",
    "ShadeNode",
    "Bus",
    "TransactionResult",
    "Fault",
    "FAULT_KINDS",
    "build_network",
]
