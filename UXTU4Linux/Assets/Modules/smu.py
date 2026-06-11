from __future__ import annotations

import os
import struct
import threading
import time

DRIVER_PATH   = "/sys/kernel/ryzen_smu_drv"
SMN_PATH      = DRIVER_PATH + "/smn"
CODENAME_PATH = DRIVER_PATH + "/codename"
VERSION_PATH  = DRIVER_PATH + "/drv_version"
PM_TABLE_PATH = DRIVER_PATH + "/pm_table"
RSMU_CMD      = DRIVER_PATH + "/rsmu_cmd"
MP1_CMD       = DRIVER_PATH + "/mp1_smu_cmd"
SMU_ARGS      = DRIVER_PATH + "/smu_args"

MIN_VERSION = (0, 1, 7)

SMU_OK              = 0x01
SMU_FAILED          = 0xFF
SMU_UNKNOWN_CMD     = 0xFE
SMU_REJECTED_PREREQ = 0xFD
SMU_REJECTED_BUSY   = 0xFC

_NARGS = 6
_POLL_FAST = 100
_POLL_SLEEP_S = 0.0001
_POLL_DEADLINE_S = 1.0
_lock = threading.Lock()

_MP1: dict[str, tuple[int, int, int]] = {
    "SummitRidge":  (0x3B10528, 0x3B10564, 0x3B10598),
    "PinnacleRidge":(0x3B10528, 0x3B10564, 0x3B10598),
    "Matisse":      (0x3B10530, 0x3B1057C, 0x3B109C4),
    "Vermeer":      (0x3B10530, 0x3B1057C, 0x3B109C4),
    "VanGogh":      (0x3B10528, 0x3B10578, 0x3B10998),
    "Mendocino":    (0x3B10528, 0x3B10578, 0x3B10998),
    "Rembrandt":    (0x3B10528, 0x3B10578, 0x3B10998),
    "PhoenixPoint": (0x3B10528, 0x3B10578, 0x3B10998),
    "PhoenixPoint2":(0x3B10528, 0x3B10578, 0x3B10998),
    "HawkPoint":    (0x3B10528, 0x3B10578, 0x3B10998),
    "HawkPoint2":   (0x3B10528, 0x3B10578, 0x3B10998),
    "SonomaValley": (0x3B10528, 0x3B10578, 0x3B10998),
    "Raphael":      (0x3B10530, 0x3B1057C, 0x3B109C4),
    "DragonRange":  (0x3B10530, 0x3B1057C, 0x3B109C4),
    "GraniteRidge": (0x3B10530, 0x3B1057C, 0x3B109C4),
    "FireRange":    (0x3B10530, 0x3B1057C, 0x3B109C4),
    "StrixPoint":   (0x3B10928, 0x3B10978, 0x3B10998),
    "KrackanPoint": (0x3B10928, 0x3B10978, 0x3B10998),
    "KrackanPoint2":(0x3B10928, 0x3B10978, 0x3B10998),
    "StrixHalo":    (0x3B10928, 0x3B10978, 0x3B10998),
}
_MP1_DEFAULT = (0x3B10528, 0x3B10564, 0x3B10998)

_RSMU: dict[str, tuple[int, int, int]] = {
    "SummitRidge":  (0x3B1051C, 0x3B10568, 0x3B10590),
    "PinnacleRidge":(0x3B1051C, 0x3B10568, 0x3B10590),
    "Matisse":      (0x3B10524, 0x3B10570, 0x3B10A40),
    "Vermeer":      (0x3B10524, 0x3B10570, 0x3B10A40),
    "Raphael":      (0x3B10524, 0x3B10570, 0x3B10A40),
    "DragonRange":  (0x3B10524, 0x3B10570, 0x3B10A40),
    "GraniteRidge": (0x3B10524, 0x3B10570, 0x3B10A40),
    "FireRange":    (0x3B10524, 0x3B10570, 0x3B10A40),
}
_RSMU_DEFAULT = (0x3B10A20, 0x3B10A80, 0x3B10A88)


def _smn_read(fd: int, addr: int) -> int:
    os.lseek(fd, 0, os.SEEK_SET)
    os.write(fd, struct.pack("<I", addr))
    os.lseek(fd, 0, os.SEEK_SET)
    data = os.read(fd, 4)
    return struct.unpack("<I", data)[0] if len(data) >= 4 else 0


def _smn_write(fd: int, addr: int, value: int) -> None:
    os.lseek(fd, 0, os.SEEK_SET)
    os.write(fd, struct.pack("<II", addr, value))


def _smn_send(fd: int, msg_addr: int, rsp_addr: int, args_addr: int,
              op: int, arg0: int) -> int:
    _smn_write(fd, rsp_addr, 0)
    _smn_write(fd, args_addr, arg0)
    for i in range(1, _NARGS):
        _smn_write(fd, args_addr + i * 4, 0)
    _smn_write(fd, msg_addr, op)
    for _ in range(_POLL_FAST):
        rsp = _smn_read(fd, rsp_addr)
        if rsp:
            return rsp
    deadline = time.monotonic() + _POLL_DEADLINE_S
    while time.monotonic() < deadline:
        time.sleep(_POLL_SLEEP_S)
        rsp = _smn_read(fd, rsp_addr)
        if rsp:
            return rsp
    return SMU_FAILED



def is_available() -> bool:
    return os.path.isdir(DRIVER_PATH)


def has_smn() -> bool:
    return os.path.exists(SMN_PATH)



def get_codename() -> int | None:
    try:
        with open(CODENAME_PATH) as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return None


def get_version() -> str:
    try:
        with open(VERSION_PATH) as f:
            return f.read().strip()
    except OSError:
        return "unknown"


def parse_version(s: str) -> tuple[int, ...]:
    s = s.strip().lstrip("v")
    try:
        return tuple(int(x) for x in s.split("."))
    except ValueError:
        return (0,)


def version_str(v: tuple[int, ...]) -> str:
    return ".".join(str(x) for x in v)


def version_ok() -> bool:
    return parse_version(get_version()) >= MIN_VERSION


def send_mp1(family: str, op: int, arg0: int = 0) -> int:
    if not has_smn():
        return SMU_FAILED
    msg, rsp, args = _MP1.get(family, _MP1_DEFAULT)
    try:
        fd = os.open(SMN_PATH, os.O_RDWR)
        try:
            with _lock:
                return _smn_send(fd, msg, rsp, args, op, arg0)
        finally:
            os.close(fd)
    except OSError:
        return SMU_FAILED


def send_rsmu(family: str, op: int, arg0: int = 0) -> int:
    if not has_smn():
        return SMU_FAILED
    msg, rsp, args = _RSMU.get(family, _RSMU_DEFAULT)
    try:
        fd = os.open(SMN_PATH, os.O_RDWR)
        try:
            with _lock:
                return _smn_send(fd, msg, rsp, args, op, arg0)
        finally:
            os.close(fd)
    except OSError:
        return SMU_FAILED



def has_pm_table() -> bool:
    return os.path.exists(PM_TABLE_PATH)


def read_pm_table() -> bytes:
    try:
        with open(PM_TABLE_PATH, "rb") as f:
            return f.read()
    except OSError:
        return b""


def status_name(code: int) -> str:
    return {
        SMU_OK:              "OK",
        SMU_FAILED:          "FAILED",
        SMU_UNKNOWN_CMD:     "UNKNOWN_CMD",
        SMU_REJECTED_PREREQ: "REJECTED_PREREQ",
        SMU_REJECTED_BUSY:   "REJECTED_BUSY",
    }.get(code, f"0x{code:02X}")
