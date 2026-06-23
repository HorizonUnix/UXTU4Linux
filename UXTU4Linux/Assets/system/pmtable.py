import struct

PM_TABLE_PATH = "/sys/kernel/ryzen_smu_drv/pm_table"
PM_TABLE_VERSION_PATH = "/sys/kernel/ryzen_smu_drv/pm_table_version"

_FIXED = {
    "stapm_limit": 0x00,
    "stapm_value": 0x04,
    "fast_limit": 0x08,
    "fast_value": 0x0C,
    "slow_limit": 0x10,
    "slow_value": 0x14,
}


def _group(offset, *versions):
    return {version: offset for version in versions}


_TCTL = {}
_TCTL.update(_group(0x5C, 0x1E0001, 0x1E0002, 0x1E0003, 0x1E0004, 0x1E0005,
                          0x1E000A, 0x1E0101, 0x64020C))
_TCTL.update(_group(0x44, 0x370000, 0x370001, 0x370002, 0x370003, 0x370004,
                          0x370005, 0x3F0000, 0x400001, 0x400002, 0x400003,
                          0x400004, 0x400005, 0x450004, 0x450005, 0x4C0006,
                          0x4C0007, 0x4C0008, 0x4C0009, 0x5D0008, 0x5D0009,
                          0x5D000B, 0x650005))

_CCLK_BUSY = {}
_CCLK_BUSY.update(_group(0x9C, 0x1E0001, 0x1E0002, 0x1E0003, 0x1E0004, 0x1E0005,
                               0x1E000A, 0x1E0101))
_CCLK_BUSY.update(_group(0x100, 0x370000, 0x370001, 0x370002, 0x370003, 0x370004,
                                0x370005))
_CCLK_BUSY.update(_group(0x104, 0x400001, 0x400002, 0x400003, 0x400004, 0x400005))
_CCLK_BUSY.update(_group(0xCC, 0x5D0008, 0x5D0009, 0x5D000B))

_SOCKET_POWER = {}
_SOCKET_POWER.update(_group(0x98, 0x370000, 0x370001, 0x370002, 0x370003, 0x370004,
                                  0x370005, 0x400001, 0x400002, 0x400003, 0x400004,
                                  0x400005))
_SOCKET_POWER.update(_group(0xA8, 0x3F0000))
_SOCKET_POWER.update(_group(0xD0, 0x5D0008, 0x5D0009, 0x5D000B))

_GFX_CLK = {}
_GFX_CLK.update(_group(0x5B4, 0x370000, 0x370001, 0x370002, 0x370003, 0x370004))
_GFX_CLK.update(_group(0x5D0, 0x370005))
_GFX_CLK.update(_group(0x60C, 0x400001))
_GFX_CLK.update(_group(0x624, 0x400002))
_GFX_CLK.update(_group(0x644, 0x400003))
_GFX_CLK.update(_group(0x648, 0x400004, 0x400005))
_GFX_CLK.update(_group(0x388, 0x3F0000))
_GFX_CLK.update(_group(0x4C0, 0x5D0008, 0x5D0009, 0x5D000B))
_GFX_CLK.update(_group(0x558, 0x64020C))

_GFX_TEMP = {}
_GFX_TEMP.update(_group(0x5AC, 0x370000, 0x370001, 0x370002, 0x370003, 0x370004))
_GFX_TEMP.update(_group(0x5C8, 0x370005))
_GFX_TEMP.update(_group(0x604, 0x400001))
_GFX_TEMP.update(_group(0x61C, 0x400002))
_GFX_TEMP.update(_group(0x63C, 0x400003))
_GFX_TEMP.update(_group(0x640, 0x400004, 0x400005))
_GFX_TEMP.update(_group(0x380, 0x3F0000))
_GFX_TEMP.update(_group(0x4C8, 0x5D0008, 0x5D0009, 0x5D000B))
_GFX_TEMP.update(_group(0x550, 0x64020C))

_MEM_CLK = {}
_MEM_CLK.update(_group(0x5D4, 0x370000, 0x370001, 0x370002, 0x370003, 0x370004))
_MEM_CLK.update(_group(0x5F0, 0x370005))
_MEM_CLK.update(_group(0x3C4, 0x3F0000))
_MEM_CLK.update(_group(0x66C, 0x400004, 0x400005))
_MEM_CLK.update(_group(0x4EC, 0x5D0008, 0x5D0009, 0x5D000B))

_VERSION_MAPS = {
    "tctl_temp": _TCTL,
    "cclk_busy": _CCLK_BUSY,
    "socket_power": _SOCKET_POWER,
    "gfx_clk": _GFX_CLK,
    "gfx_temp": _GFX_TEMP,
    "mem_clk": _MEM_CLK,
}

_FIELDS = list(_FIXED) + list(_VERSION_MAPS)


class PmSample:
    __slots__ = ("version",) + tuple(_FIELDS)

    def __init__(self, version):
        self.version = version
        for name in _FIELDS:
            setattr(self, name, None)


def _read_version(path):
    try:
        with open(path, "rb") as f:
            raw = f.read(4)
    except OSError:
        return None
    if len(raw) < 4:
        return None
    return struct.unpack("<I", raw)[0]


def _read_bytes(path):
    try:
        with open(path, "rb") as f:
            return f.read()
    except OSError:
        return None


def _value(data, offset):
    if offset is None or offset + 4 > len(data):
        return None
    result = struct.unpack_from("<f", data, offset)[0]
    if result != result:
        return None
    return result


def read(table_path=PM_TABLE_PATH, version_path=PM_TABLE_VERSION_PATH):
    version = _read_version(version_path)
    if version is None:
        return None
    data = _read_bytes(table_path)
    if data is None:
        return None
    sample = PmSample(version)
    for name, offset in _FIXED.items():
        setattr(sample, name, _value(data, offset))
    for name, version_map in _VERSION_MAPS.items():
        setattr(sample, name, _value(data, version_map.get(version)))
    return sample
