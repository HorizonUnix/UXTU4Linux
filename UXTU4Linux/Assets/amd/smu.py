from __future__ import annotations

import os
import struct
import threading
import time

DRIVER_PATH   = "/sys/kernel/ryzen_smu_drv"
SMN_PATH      = DRIVER_PATH + "/smn"
VERSION_PATH  = DRIVER_PATH + "/drv_version"

_PCI_CONFIG  = "/sys/bus/pci/devices/0000:00:00.0/config"
_NB_ADDR_OFF = 0xB8
_NB_DATA_OFF = 0xBC

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

_backend = "ryzen_smu"

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


def _smn_read_pci(fd: int, addr: int) -> int:
    os.lseek(fd, _NB_ADDR_OFF, os.SEEK_SET)
    os.write(fd, struct.pack("<I", addr & ~3))
    os.lseek(fd, _NB_DATA_OFF, os.SEEK_SET)
    data = os.read(fd, 4)
    return struct.unpack("<I", data)[0] if len(data) >= 4 else 0


def _smn_write_pci(fd: int, addr: int, value: int) -> None:
    os.lseek(fd, _NB_ADDR_OFF, os.SEEK_SET)
    os.write(fd, struct.pack("<I", addr))
    os.lseek(fd, _NB_DATA_OFF, os.SEEK_SET)
    os.write(fd, struct.pack("<I", value))


def _smn_send_pci(fd: int, msg_addr: int, rsp_addr: int, args_addr: int,
                  op: int, arg0: int) -> int:
    _smn_write_pci(fd, rsp_addr, 0)
    _smn_write_pci(fd, args_addr, arg0)
    for i in range(1, _NARGS):
        _smn_write_pci(fd, args_addr + i * 4, 0)
    _smn_write_pci(fd, msg_addr, op)
    for _ in range(_POLL_FAST):
        rsp = _smn_read_pci(fd, rsp_addr)
        if rsp:
            return rsp
    deadline = time.monotonic() + _POLL_DEADLINE_S
    while time.monotonic() < deadline:
        time.sleep(_POLL_SLEEP_S)
        rsp = _smn_read_pci(fd, rsp_addr)
        if rsp:
            return rsp
    return SMU_FAILED


def init_pci_backend() -> bool:
    global _backend
    if not os.path.exists(_PCI_CONFIG):
        return False
    try:
        fd = os.open(_PCI_CONFIG, os.O_RDWR)
        try:
            os.lseek(fd, _NB_ADDR_OFF, os.SEEK_SET)
            os.write(fd, struct.pack("<I", 0x47))
            os.lseek(fd, _NB_ADDR_OFF, os.SEEK_SET)
            data = os.read(fd, 4)
            if len(data) < 4 or struct.unpack("<I", data)[0] != 0x47:
                return False
        finally:
            os.close(fd)
    except OSError:
        return False
    _backend = "pci"
    return True


def active_backend() -> str:
    return _backend


def is_available() -> bool:
    return os.path.isdir(DRIVER_PATH) or _backend == "pci"


def has_smn() -> bool:
    return os.path.exists(SMN_PATH)


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
    if _backend == "pci":
        return _send_pci(_MP1, _MP1_DEFAULT, family, op, arg0)
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
    if _backend == "pci":
        return _send_pci(_RSMU, _RSMU_DEFAULT, family, op, arg0)
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


def _send_pci(table: dict, default: tuple, family: str, op: int, arg0: int) -> int:
    msg, rsp, args = table.get(family, default)
    try:
        fd = os.open(_PCI_CONFIG, os.O_RDWR)
        try:
            with _lock:
                return _smn_send_pci(fd, msg, rsp, args, op, arg0)
        finally:
            os.close(fd)
    except OSError:
        return SMU_FAILED


def _smn_send_pci_get_args(fd: int, msg_addr: int, rsp_addr: int, args_addr: int,
                            op: int, arg0: int) -> tuple[int, int, int]:
    _smn_write_pci(fd, rsp_addr, 0)
    _smn_write_pci(fd, args_addr, arg0)
    for i in range(1, _NARGS):
        _smn_write_pci(fd, args_addr + i * 4, 0)
    _smn_write_pci(fd, msg_addr, op)
    rsp = 0
    for _ in range(_POLL_FAST):
        rsp = _smn_read_pci(fd, rsp_addr)
        if rsp:
            break
    if not rsp:
        deadline = time.monotonic() + _POLL_DEADLINE_S
        while time.monotonic() < deadline:
            time.sleep(_POLL_SLEEP_S)
            rsp = _smn_read_pci(fd, rsp_addr)
            if rsp:
                break
    if not rsp:
        return SMU_FAILED, 0, 0
    out0 = _smn_read_pci(fd, args_addr)
    out1 = _smn_read_pci(fd, args_addr + 4)
    return rsp, out0, out1


def _send_pci_rsmu_get_args(family: str, op: int, arg0: int = 0) -> tuple[int, int, int]:
    msg, rsp, args = _RSMU.get(family, _RSMU_DEFAULT)
    try:
        fd = os.open(_PCI_CONFIG, os.O_RDWR)
        try:
            with _lock:
                return _smn_send_pci_get_args(fd, msg, rsp, args, op, arg0)
        finally:
            os.close(fd)
    except OSError:
        return SMU_FAILED, 0, 0


_PM_TABLE_CMDS: dict[str, tuple[int, int, int, bool, bool]] = {
    "RavenRidge":      (0xC, 0xB,  0x3D, False, True),
    "Picasso":         (0xC, 0xB,  0x3D, False, True),
    "Dali":            (0xC, 0xB,  0x3D, False, True),
    "Pollock":         (0xC, 0xB,  0x3D, False, True),
    "Renoir":          (0x6, 0x66, 0x65, False, False),
    "Lucienne":        (0x6, 0x66, 0x65, False, False),
    "Cezanne_Barcelo": (0x6, 0x66, 0x65, False, False),
    "VanGogh":         (0x6, 0x66, 0x65, False, False),
    "Mendocino":       (0x6, 0x66, 0x65, False, False),
    "Rembrandt":       (0x6, 0x66, 0x65, True,  False),
    "PhoenixPoint":    (0x6, 0x66, 0x65, True,  False),
    "PhoenixPoint2":   (0x6, 0x66, 0x65, True,  False),
    "HawkPoint":       (0x6, 0x66, 0x65, True,  False),
    "HawkPoint2":      (0x6, 0x66, 0x65, True,  False),
    "SonomaValley":    (0x6, 0x66, 0x65, True,  False),
    "StrixPoint":      (0x6, 0x66, 0x65, True,  False),
    "KrackanPoint":    (0x6, 0x66, 0x65, True,  False),
    "KrackanPoint2":   (0x6, 0x66, 0x65, True,  False),
    "StrixHalo":       (0x6, 0x66, 0x65, True,  False),
}

_PM_TABLE_SIZES: dict[int, int] = {
    0x1E0001: 0x568, 0x1E0002: 0x580, 0x1E0003: 0x578,
    0x1E0004: 0x608, 0x1E0005: 0x608, 0x1E000A: 0x608, 0x1E0101: 0x608,
    0x370000: 0x794, 0x370001: 0x884, 0x370002: 0x88C,
    0x370003: 0x8AC, 0x370004: 0x8AC, 0x370005: 0x8C8,
    0x3F0000: 0x7AC,
    0x400001: 0x910, 0x400002: 0x928, 0x400003: 0x94C,
    0x400004: 0x944, 0x400005: 0x944,
    0x450004: 0xAA4, 0x450005: 0xAB0,
    0x4C0003: 0xB18, 0x4C0004: 0xB1C, 0x4C0005: 0xAF8,
    0x4C0006: 0xAFC, 0x4C0007: 0xB00, 0x4C0008: 0xAF0, 0x4C0009: 0xB00,
    0x5D0008: 0xD54, 0x5D0009: 0xD54, 0x5D000B: 0xD54,
    0x64020C: 0xE50,
}


def read_pm_table_pci(family: str) -> tuple[bytes, int] | None:
    cmds = _PM_TABLE_CMDS.get(family)
    if cmds is None:
        return None
    ver_cmd, addr_cmd, transfer_cmd, addr_64bit, needs_arg3 = cmds
    extra = 3 if needs_arg3 else 0

    rsp, ver, _ = _send_pci_rsmu_get_args(family, ver_cmd, 0)
    if rsp != SMU_OK or not ver:
        return None

    rsp, addr_lo, addr_hi = _send_pci_rsmu_get_args(family, addr_cmd, extra)
    if rsp != SMU_OK:
        return None
    phys = (addr_hi << 32 | addr_lo) if addr_64bit else addr_lo
    if not phys:
        return None

    rsp, _, _ = _send_pci_rsmu_get_args(family, transfer_cmd, extra)
    if rsp == SMU_REJECTED_PREREQ:
        time.sleep(0.01)
        rsp, _, _ = _send_pci_rsmu_get_args(family, transfer_cmd, extra)
    if rsp != SMU_OK:
        return None

    table_size = _PM_TABLE_SIZES.get(ver, 0x1000)
    try:
        import mmap as _mmap
        page = _mmap.PAGESIZE
        page_off = phys & ~(page - 1)
        inner = phys - page_off
        fd = os.open("/dev/mem", os.O_RDONLY | os.O_SYNC)
        try:
            mm = _mmap.mmap(fd, inner + table_size, _mmap.MAP_SHARED,
                            _mmap.PROT_READ, offset=page_off)
            try:
                mm.seek(inner)
                return mm.read(table_size), ver
            finally:
                mm.close()
        finally:
            os.close(fd)
    except OSError:
        return None


def status_name(code: int) -> str:
    return {
        SMU_OK:              "OK",
        SMU_FAILED:          "FAILED",
        SMU_UNKNOWN_CMD:     "UNKNOWN_CMD",
        SMU_REJECTED_PREREQ: "REJECTED_PREREQ",
        SMU_REJECTED_BUSY:   "REJECTED_BUSY",
    }.get(code, f"0x{code:02X}")
