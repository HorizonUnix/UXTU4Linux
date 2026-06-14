from __future__ import annotations

import shlex

SOCKET_AM4_V1      = "AM4_V1"
SOCKET_FT5_FP5_AM4 = "FT5_FP5_AM4"
SOCKET_AM4_V2      = "AM4_V2"
SOCKET_FP6_AM4     = "FP6_AM4"
SOCKET_FF3         = "FF3"
SOCKET_FT6_FP7_FP8 = "FT6_FP7_FP8"
SOCKET_AM5_V1      = "AM5_V1"

_FAMILY_SOCKET: dict[str, str] = {
    "SummitRidge":     SOCKET_AM4_V1,
    "PinnacleRidge":   SOCKET_AM4_V1,
    "RavenRidge":      SOCKET_FT5_FP5_AM4,
    "Picasso":         SOCKET_FT5_FP5_AM4,
    "Dali":            SOCKET_FT5_FP5_AM4,
    "Pollock":         SOCKET_FT5_FP5_AM4,
    "FireFlight":      SOCKET_FT5_FP5_AM4,
    "Matisse":         SOCKET_AM4_V2,
    "Renoir":          SOCKET_FP6_AM4,
    "Lucienne":        SOCKET_FP6_AM4,
    "Cezanne_Barcelo": SOCKET_FP6_AM4,
    "VanGogh":         SOCKET_FF3,
    "Mendocino":       SOCKET_FT6_FP7_FP8,
    "Vermeer":         SOCKET_AM4_V2,
    "Rembrandt":       SOCKET_FT6_FP7_FP8,
    "Raphael":         SOCKET_AM5_V1,
    "DragonRange":     SOCKET_AM5_V1,
    "PhoenixPoint":    SOCKET_FT6_FP7_FP8,
    "PhoenixPoint2":   SOCKET_FT6_FP7_FP8,
    "HawkPoint":       SOCKET_FT6_FP7_FP8,
    "HawkPoint2":      SOCKET_FT6_FP7_FP8,
    "SonomaValley":    SOCKET_FT6_FP7_FP8,
    "GraniteRidge":    SOCKET_AM5_V1,
    "FireRange":       SOCKET_AM5_V1,
    "StrixHalo":       SOCKET_FT6_FP7_FP8,
    "StrixPoint":      SOCKET_FT6_FP7_FP8,
    "KrackanPoint":    SOCKET_FT6_FP7_FP8,
    "KrackanPoint2":   SOCKET_FT6_FP7_FP8,
}

_CMD_AM4_V1: list[tuple[str, bool, int]] = [
    ("ppt-limit", False, 0x64),
    ("ppt-limit", True, 0x31),
    ("tdc-limit", False, 0x65),
    ("edc-limit", False, 0x66),
    ("tctl-temp", False, 0x68),
    ("pbo-scalar", False, 0x6a),
    ("oc-clk", False, 0x6c),
    ("oc-clk", True, 0x39),
    ("per-core-oc-clk", False, 0x6d),
    ("oc-volt", False, 0x6e),
    ("oc-volt", True, 0x38),
    ("enable-oc", True, 0x23),
    ("enable-oc", False, 0x6b),
    ("disable-oc", True, 0x24),
    ("get-sustained-power-and-thm-limit", True, 0x36),
    ("setcpu-freqto-ramstate", True, 0x23),
    ("stopcpu-freqto-ramstate", True, 0x24),
    ("stopcpu-freqto-ramstate", True, 0x25),
]

_CMD_FT5_FP5_AM4: list[tuple[str, bool, int]] = [
    ("enable-feature", True, 0x05),
    ("disable-feature", True, 0x06),
    ("stapm-limit", True, 0x1a),
    ("stapm-limit", False, 0x2e),
    ("stapm-time", True, 0x1e),
    ("stapm-time", False, 0x32),
    ("fast-limit", True, 0x1b),
    ("fast-limit", False, 0x30),
    ("slow-limit", True, 0x1c),
    ("slow-limit", False, 0x2f),
    ("slow-time", True, 0x1d),
    ("slow-time", False, 0x31),
    ("tctl-temp", True, 0x1f),
    ("tctl-temp", False, 0x33),
    ("chtc-temp", False, 0x56),
    ("vrm-current", True, 0x20),
    ("vrm-current", False, 0x34),
    ("vrmmax-current", True, 0x22),
    ("vrmmax-current", False, 0x36),
    ("vrmsoc-current", True, 0x21),
    ("vrmsoc-current", False, 0x35),
    ("vrmsocmax-current", True, 0x23),
    ("vrmsocmax-current", False, 0x37),
    ("psi0-current", True, 0x24),
    ("psi0-current", False, 0x38),
    ("psi0soc-current", True, 0x25),
    ("psi0soc-current", False, 0x39),
    ("prochot-deassertion-ramp", True, 0x26),
    ("prochot-deassertion-ramp", False, 0x3a),
    ("power-saving", True, 0x19),
    ("max-performance", True, 0x18),
    ("enable-oc", True, 0x58),
    ("disable-oc", True, 0x3f),
    ("oc-clk", False, 0x7d),
    ("per-core-oc-clk", False, 0x7e),
    ("oc-clk", True, 0x59),
    ("per-core-oc-clk", True, 0x5a),
    ("oc-clk", True, 0x41),
    ("oc-volt", True, 0x5b),
    ("oc-volt", False, 0x7c),
    ("oc-volt", True, 0x40),
    ("set-gpuclockoverdrive-byvid", True, 0x3d),
    ("set-gpuclockoverdrive-byvid", False, 0x61),
    ("pbo-scalar", True, 0x57),
    ("pbo-scalar", False, 0x63),
    ("get-pbo-scalar", False, 0x62),
    ("max-cpuclk", True, 0x44),
    ("min-cpuclk", True, 0x45),
    ("max-gfxclk", True, 0x46),
    ("max-gfxclk", False, 0x68),
    ("min-gfxclk", True, 0x47),
    ("min-gfxclk", False, 0x69),
    ("max-socclk-frequency", True, 0x48),
    ("max-socclk-frequency", False, 0x66),
    ("min-socclk-frequency", True, 0x49),
    ("min-socclk-frequency", False, 0x67),
    ("max-fclk-frequency", True, 0x4a),
    ("min-fclk-frequency", True, 0x4b),
    ("max-vcn", True, 0x4c),
    ("min-vcn", True, 0x4d),
    ("max-lclk", True, 0x4e),
    ("min-lclk", True, 0x4f),
    ("set-coper", False, 0x58),
    ("set-coall", False, 0x59),
    ("set-cogfx", False, 0x59),
    ("setcpu-freqto-ramstate", True, 0x2f),
    ("stopcpu-freqto-ramstate", True, 0x30),
    ("stopcpu-freqto-ramstate", True, 0x31),
    ("set-ulv-vid", True, 0x35),
    ("set-vddoff-vid", True, 0x3a),
    ("set-vmin-freq", True, 0x3b),
    ("get-sustained-power-and-thm-limit", True, 0x43),
    ("get-sustained-power-and-thm-limit", False, 0x65),
    ("get-pbo-fused-power-limit", False, 0x7F),
    ("get-pbo-fused-slow-limit", False, 0x80),
    ("get-pbo-fused-fast-limit", False, 0x81),
    ("get-pbo-fused-apu-slow-limit", False, 0x82),
    ("get-pbo-fused-vrmtdc-limit", False, 0x83),
    ("get-pbo-fused-vrmsoc-current", False, 0x84),
]

_CMD_AM4_V2: list[tuple[str, bool, int]] = [
    ("enable-feature", True, 0x03),
    ("disable-feature", True, 0x04),
    ("ppt-limit", True, 0x3D),
    ("ppt-limit", False, 0x53),
    ("tdc-limit", True, 0x3B),
    ("tdc-limit", False, 0x54),
    ("edc-limit", True, 0x3c),
    ("edc-limit", False, 0x55),
    ("tctl-temp", True, 0x3E),
    ("tctl-temp", False, 0x56),
    ("pbo-scalar", False, 0x58),
    ("oc-clk", True, 0x26),
    ("oc-clk", False, 0x5c),
    ("per-core-oc-clk", True, 0x27),
    ("per-core-oc-clk", False, 0x5d),
    ("oc-volt", True, 0x28),
    ("oc-volt", False, 0x61),
    ("set-coall", True, 0x36),
    ("set-coall", False, 0x0b),
    ("set-coper", True, 0x35),
    ("set-coper", False, 0x0a),
    ("enable-oc", True, 0x24),
    ("enable-oc", False, 0x5a),
    ("disable-oc", True, 0x25),
    ("disable-oc", False, 0x5b),
    ("set-boost-limit-frequency", True, 0x2b),
    ("get-pbo-scalar", False, 0x6c),
    ("get-sustained-power-and-thm-limit", True, 0x23),
    ("get-overclocking-support", False, 0x6f),
    ("get-coper-options", False, 0x7c),
]

_CMD_FP6_AM4: list[tuple[str, bool, int]] = [
    ("enable-feature", True, 0x05),
    ("disable-feature", True, 0x07),
    ("stapm-limit", True, 0x14),
    ("stapm-limit", False, 0x31),
    ("ppt-limit", False, 0x33),
    ("stapm-time", True, 0x18),
    ("stapm-time", False, 0x36),
    ("fast-limit", True, 0x15),
    ("fast-limit", False, 0x32),
    ("slow-limit", True, 0x16),
    ("slow-limit", False, 0x33),
    ("slow-time", True, 0x17),
    ("slow-time", False, 0x35),
    ("tctl-temp", True, 0x19),
    ("chtc-temp", False, 0x37),
    ("apu-skin-temp", True, 0x38),
    ("apu-skin-temp", False, 0x91),
    ("dgpu-skin-temp", True, 0x39),
    ("dgpu-skin-temp", False, 0x92),
    ("vrm-current", True, 0x1a),
    ("vrm-current", False, 0x38),
    ("vrmmax-current", True, 0x1c),
    ("vrmmax-current", False, 0x3a),
    ("vrmsoc-current", True, 0x1b),
    ("vrmsoc-current", False, 0x39),
    ("vrmsocmax-current", True, 0x1d),
    ("vrmsocmax-current", False, 0x3b),
    ("psi0-current", True, 0x1e),
    ("psi0-current", False, 0x3c),
    ("psi0soc-current", True, 0x1f),
    ("psi0soc-current", False, 0x3d),
    ("prochot-deassertion-ramp", True, 0x20),
    ("prochot-deassertion-ramp", False, 0x3e),
    ("skin-temp-limit", True, 0x53),
    ("apu-slow-limit", True, 0x21),
    ("apu-slow-limit", False, 0x34),
    ("power-saving", True, 0x12),
    ("max-performance", True, 0x11),
    ("enable-oc", False, 0x17),
    ("enable-oc", True, 0x2f),
    ("disable-oc", False, 0x18),
    ("disable-oc", True, 0x30),
    ("oc-clk", True, 0x31),
    ("oc-clk", False, 0x19),
    ("per-core-oc-clk", True, 0x32),
    ("per-core-oc-clk", False, 0x1a),
    ("oc-volt", True, 0x33),
    ("oc-volt", False, 0x1b),
    ("set-gpuclockoverdrive-byvid", True, 0x34),
    ("gfx-clk", False, 0x89),
    ("gfx-clk", False, 0x1c),
    ("pbo-scalar", True, 0x49),
    ("pbo-scalar", False, 0x3f),
    ("get-pbo-scalar", False, 0x0f),
    ("set-cogfx", False, 0x53),
    ("set-coper", True, 0x54),
    ("set-coper", False, 0x52),
    ("set-coall", True, 0x55),
    ("set-coall", False, 0xB1),
    ("get-coper-options", False, 0xC3),
    ("get-cogfx-options", False, 0xC6),
    ("get-sustained-power-and-thm-limit", True, 0x5b),
    ("get-pbo-fused-power-limit", False, 0x11),
    ("get-pbo-fused-slow-limit", False, 0x12),
    ("get-pbo-fused-fast-limit", False, 0x13),
    ("get-pbo-fused-apu-slow-limit", False, 0x14),
    ("get-pbo-fused-vrmtdc-limit", False, 0x15),
    ("get-pbo-fused-vrmsoc-current", False, 0x16),
]

_CMD_FF3: list[tuple[str, bool, int]] = [
    ("enable-feature", True, 0x05),
    ("disable-feature", True, 0x07),
    ("stapm-limit", True, 0x14),
    ("stapm-limit", False, 0x31),
    ("stapm-time", True, 0x18),
    ("fast-limit", True, 0x15),
    ("slow-limit", True, 0x16),
    ("slow-time", True, 0x17),
    ("tctl-temp", True, 0x19),
    ("chtc-temp", False, 0x37),
    ("apu-skin-temp", True, 0x33),
    ("vrm-current", True, 0x1a),
    ("vrmmax-current", True, 0x1c),
    ("vrmsoc-current", True, 0x1b),
    ("vrmsocmax-current", True, 0x1d),
    ("vrmgfx-current", True, 0x1e),
    ("vrmgfxmax-current", True, 0x1f),
    ("prochot-deassertion-ramp", True, 0x22),
    ("gfx-clk", False, 0x89),
    ("gfx-clk", False, 0x1c),
    ("power-saving", True, 0x12),
    ("max-performance", True, 0x11),
    ("set-coall", True, 0x4c),
    ("set-coall", False, 0x5d),
    ("set-coper", True, 0x4b),
    ("set-cogfx", False, 0xb7),
    ("get-sustained-power-and-thm-limit", True, 0x54),
    ("skin-temp-limit", True, 0x4a),
    ("apu-slow-limit", True, 0x23),
]

_CMD_FT6_FP7_FP8: list[tuple[str, bool, int]] = [
    ("enable-feature", True, 0x05),
    ("disable-feature", True, 0x07),
    ("stapm-limit", True, 0x14),
    ("stapm-limit", False, 0x31),
    ("stapm-time", True, 0x18),
    ("stapm-time", False, 0x36),
    ("fast-limit", True, 0x15),
    ("fast-limit", False, 0x32),
    ("slow-limit", True, 0x16),
    ("slow-limit", False, 0x33),
    ("slow-time", True, 0x17),
    ("slow-time", False, 0x35),
    ("tctl-temp", True, 0x19),
    ("chtc-temp", True, 0x63),
    ("chtc-temp", False, 0x37),
    ("vrm-current", True, 0x1a),
    ("vrm-current", False, 0x38),
    ("vrmmax-current", True, 0x1c),
    ("vrmmax-current", False, 0x3a),
    ("vrmsoc-current", True, 0x1b),
    ("vrmsoc-current", False, 0x39),
    ("vrmsocmax-current", True, 0x1d),
    ("vrmsocmax-current", False, 0x3b),
    ("psi0-current", True, 0x1e),
    ("psi0-current", False, 0x3c),
    ("psi0soc-current", True, 0x1f),
    ("psi0soc-current", False, 0x3d),
    ("psi3cpu-current", True, 0x20),
    ("psi3gfx-current", True, 0x21),
    ("prochot-deassertion-ramp", True, 0x22),
    ("skin-temp-limit", True, 0x4a),
    ("apu-slow-limit", True, 0x23),
    ("apu-slow-limit", False, 0x34),
    ("apu-skin-temp", True, 0x33),
    ("apu-skin-temp", False, 0x91),
    ("dgpu-skin-temp", True, 0x34),
    ("dgpu-skin-temp", False, 0x92),
    ("max-performance", True, 0x11),
    ("power-saving", True, 0x12),
    ("enable-oc", False, 0x17),
    ("disable-oc", False, 0x18),
    ("oc-clk", False, 0x19),
    ("per-core-oc-clk", False, 0x1a),
    ("oc-volt", False, 0x1b),
    ("gfx-clk", False, 0x89),
    ("gfx-clk", False, 0x1c),
    ("pbo-scalar", False, 0x3e),
    ("get-pbo-scalar", False, 0x0f),
    ("set-cogfx", False, 0xb7),
    ("set-coper", True, 0x4b),
    ("set-coper", False, 0x53),
    ("set-coall", True, 0x4c),
    ("set-coall", False, 0x5d),
    ("get-coper-options", False, 0xE1),
    ("get-sustained-power-and-thm-limit", True, 0x5f),
    ("get-pbo-fused-power-limit", False, 0x11),
    ("get-pbo-fused-slow-limit", False, 0x12),
    ("get-pbo-fused-fast-limit", False, 0x13),
    ("get-pbo-fused-apu-slow-limit", False, 0x14),
    ("get-pbo-fused-vrmtdc-limit", False, 0x15),
    ("get-pbo-fused-vrmsoc-current", False, 0x16),
    ("get-pbo-fused-tctl-temp", False, 0xE5),
]

_CMD_AM5_V1: list[tuple[str, bool, int]] = [
    ("enable-feature", True, 0x03),
    ("disable-feature", True, 0x04),
    ("stapm-limit", True, 0x4f),
    ("stapm-time", True, 0x53),
    ("fast-limit", True, 0x3e),
    ("slow-limit", True, 0x5f),
    ("slow-time", True, 0x60),
    ("vrm-current", True, 0x3c),
    ("vrm-current", False, 0x57),
    ("ppt-limit", True, 0x3e),
    ("ppt-limit", False, 0x56),
    ("tdc-limit", True, 0x3c),
    ("tdc-limit", False, 0x57),
    ("edc-limit", True, 0x3d),
    ("edc-limit", False, 0x58),
    ("tctl-temp", True, 0x3f),
    ("tctl-temp", False, 0x59),
    ("pbo-scalar", False, 0x5b),
    ("oc-clk", False, 0x5f),
    ("per-core-oc-clk", False, 0x60),
    ("oc-volt", False, 0x61),
    ("set-coall", False, 0x07),
    ("set-coper", False, 0x06),
    ("enable-oc", False, 0x5d),
    ("disable-oc", False, 0x5e),
    ("slow-limit", False, 0xcb),
    ("skin-temp-limit", True, 0x5e),
    ("apu-slow-limit", True, 0x60),
    ("vrmmax-current", True, 0x3d),
    ("vrmmax-current", False, 0x58),
    ("chtc-temp", False, 0x59),
    ("get-pbo-scalar", False, 0x6d),
    ("set-cogfx", False, 0xA7),
    ("set-coall", True, 0x36),
    ("set-coper", True, 0x35),
    ("set-boost-limit-frequency", True, 0x2b),
    ("set-vddoff-vid", True, 0x4b),
    ("set-fll-btc-enable", True, 0x37),
    ("get-sustained-power-and-thm-limit", True, 0x23),
    ("get-overclocking-support", False, 0x6f),
    ("get-max-cpu-clk", False, 0x6e),
    ("get-min-gfx-clk", False, 0xCe),
    ("get-max-gfx-clk", False, 0xCf),
    ("get-curr-gfx-clk", False, 0xD8),
    ("disable-prochot", False, 0x5d),
    ("get-coper-options", False, 0xD5),
    ("get-cogfx-options", False, 0xD7),
    ("get-pbo-fused-vrmsoc-current", False, 0xD9),
    ("get-pbo-fused-vrmtdc-limit", False, 0xDb),
    ("get-pbo-fused-slow-limit", False, 0xDc),
    ("get-pbo-fused-apu-slow-limit", False, 0xDa),
    ("get-pbo-fused-tctl-temp", False, 0xDe),
]

_SOCKET_COMMANDS: dict[str, list[tuple[str, bool, int]]] = {
    SOCKET_AM4_V1:      _CMD_AM4_V1,
    SOCKET_FT5_FP5_AM4: _CMD_FT5_FP5_AM4,
    SOCKET_AM4_V2:      _CMD_AM4_V2,
    SOCKET_FP6_AM4:     _CMD_FP6_AM4,
    SOCKET_FF3:         _CMD_FF3,
    SOCKET_FT6_FP7_FP8: _CMD_FT6_FP7_FP8,
    SOCKET_AM5_V1:      _CMD_AM5_V1,
}


_SOCKET_SHORT: dict[str, str] = {
    SOCKET_AM4_V1:      "AM4",
    SOCKET_FT5_FP5_AM4: "FP5",
    SOCKET_AM4_V2:      "AM4",
    SOCKET_FP6_AM4:     "FP6",
    SOCKET_FF3:         "FF3",
    SOCKET_FT6_FP7_FP8: "FP7",
    SOCKET_AM5_V1:      "AM5",
}


def get_socket(family: str) -> str | None:
    return _FAMILY_SOCKET.get(family)


def get_socket_short(family: str) -> str:
    return _SOCKET_SHORT.get(get_socket(family) or "", "")


def has_smu_support(family: str) -> bool:
    socket = get_socket(family)
    if socket is None:
        return False
    return bool(_SOCKET_COMMANDS.get(socket))


def get_commands(family: str) -> list[tuple[str, bool, int]]:
    socket = _FAMILY_SOCKET.get(family)
    if socket is None:
        return []
    return _SOCKET_COMMANDS.get(socket, [])


def lookup(family: str, arg_name: str) -> list[tuple[bool, int]]:
    norm = arg_name.lstrip("-").replace("_", "-").lower()
    return [
        (is_mp1, op)
        for name, is_mp1, op in get_commands(family)
        if name.lower() == norm
    ]


def _skin_scale(arg_name: str, value: int) -> int:
    return value * 256 if "skin" in arg_name else value


def _nvml_set_offsets(core_offset: int, mem_offset: int, lines: list[str]) -> None:
    import ctypes

    try:
        lib = ctypes.CDLL("libnvidia-ml.so.1")
    except OSError:
        lines.append("nvidia offsets -> libnvidia-ml.so.1 not found")
        return

    NVML_ERROR_NOT_SUPPORTED = 3
    NVML_CLOCK_GRAPHICS = 0
    NVML_CLOCK_MEM = 2
    NVML_PSTATE_0 = 0

    class _ClockOffset(ctypes.Structure):
        _fields_ = [
            ("version",          ctypes.c_uint),
            ("type",             ctypes.c_uint),
            ("pstate",           ctypes.c_uint),
            ("clockOffsetMHz",   ctypes.c_int),
            ("minClockOffsetMHz",ctypes.c_int),
            ("maxClockOffsetMHz",ctypes.c_int),
        ]

    OFFSET_V1 = ctypes.sizeof(_ClockOffset) | (1 << 24)

    nvmlInit     = lib.nvmlInit_v2
    nvmlGetDev   = lib.nvmlDeviceGetHandleByIndex_v2
    nvmlShutdown = lib.nvmlShutdown
    nvmlInit.restype     = ctypes.c_int
    nvmlGetDev.restype   = ctypes.c_int
    nvmlShutdown.restype = ctypes.c_int
    nvmlGetDev.argtypes  = [ctypes.c_uint, ctypes.POINTER(ctypes.c_void_p)]

    init_rc = nvmlInit()
    if init_rc != 0:
        lines.append(f"nvidia offsets -> nvmlInit failed (rc={init_rc})")
        return

    dev = ctypes.c_void_p()
    if nvmlGetDev(0, ctypes.byref(dev)) != 0:
        lines.append("nvidia offsets -> nvmlDeviceGetHandleByIndex failed")
        nvmlShutdown()
        return

    pairs = [(NVML_CLOCK_GRAPHICS, core_offset, "core"), (NVML_CLOCK_MEM, mem_offset, "mem")]
    used_modern = False

    setModern = getattr(lib, "nvmlDeviceSetClockOffsets", None)
    if setModern:
        setModern.restype = ctypes.c_int
        setModern.argtypes = [ctypes.c_void_p, ctypes.POINTER(_ClockOffset)]
        for clock_type, offset, name in pairs:
            info = _ClockOffset()
            info.version = OFFSET_V1
            info.type = clock_type
            info.pstate = NVML_PSTATE_0
            info.clockOffsetMHz = offset
            rc = setModern(dev, ctypes.byref(info))
            if rc == NVML_ERROR_NOT_SUPPORTED:
                break
            used_modern = True
            lines.append(f"nvidia {name}-offset -> {offset} MHz (rc={rc})")

    if not used_modern:
        setGpc = getattr(lib, "nvmlDeviceSetGpcClkVfOffset", None)
        setMem = getattr(lib, "nvmlDeviceSetMemClkVfOffset", None)
        if setGpc:
            setGpc.restype = ctypes.c_int
            setGpc.argtypes = [ctypes.c_void_p, ctypes.c_int]
        if setMem:
            setMem.restype = ctypes.c_int
            setMem.argtypes = [ctypes.c_void_p, ctypes.c_int]
        for fn, offset, name in [(setGpc, core_offset, "core"), (setMem, mem_offset, "mem")]:
            if fn:
                rc = fn(dev, offset)
                lines.append(f"nvidia {name}-offset -> {offset} MHz (legacy, rc={rc})")

    nvmlShutdown()


def _apply_nvidia(packed: str, lines: list[str]) -> None:
    import shutil
    import subprocess

    parts = packed.split(",")
    if len(parts) != 3:
        lines.append("nvidia-clocks -> invalid format")
        return
    try:
        max_clk = int(parts[0])
        core_offset = int(parts[1])
        mem_offset = int(parts[2])
    except ValueError:
        lines.append("nvidia-clocks -> invalid values")
        return

    smi = shutil.which("nvidia-smi")
    if not smi:
        lines.append("nvidia-clocks -> nvidia-smi not found")
        return

    if max_clk >= 4000:
        proc = subprocess.run([smi, "-rgc"], capture_output=True, text=True)
        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "unknown error").strip()
            lines.append(f"nvidia max-clock -> reset failed: {err}")
        else:
            lines.append("nvidia max-clock -> reset")
    else:
        proc = subprocess.run([smi, "-lgc", f"0,{max_clk}"], capture_output=True, text=True)
        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "unknown error").strip()
            lines.append(f"nvidia max-clock -> failed to set {max_clk} MHz: {err}")
        else:
            lines.append(f"nvidia max-clock -> {max_clk} MHz")

    _nvml_set_offsets(core_offset, mem_offset, lines)


def _apply_system(name: str, raw: int, lines: list[str]) -> None:
    from . import platformctl

    if name == "sys-power-profile":
        lines.append(platformctl.set_power_profile(raw))
    elif name == "sys-asus-mode":
        lines.append(platformctl.set_asus_mode(raw))
    elif name == "sys-asus-eco":
        lines.append(platformctl.set_asus_eco(raw))
    elif name == "sys-asus-mux":
        lines.append(platformctl.set_asus_mux(raw))
    elif name == "sys-ccd-affinity":
        lines.append(platformctl.set_ccd_affinity(raw))
    else:
        lines.append(f"{name} -> unknown system setting")


def apply_args(args_str: str, family: str) -> tuple[str, bool]:
    from . import smu

    tokens = shlex.split(args_str)
    lines: list[str] = []
    any_rejected = False

    for token in tokens:
        token = token.lstrip("-")
        if not token:
            continue
        if "=" in token:
            name, _, val_str = token.partition("=")
            if name == "nvidia-clocks":
                _apply_nvidia(val_str, lines)
                continue
            try:
                raw = int(val_str, 0)
            except ValueError:
                lines.append(f"{name} -> invalid value '{val_str}'")
                continue
        else:
            name, raw = token, 0

        if name.startswith("sys-"):
            _apply_system(name, raw, lines)
            continue

        matches = lookup(family, name)
        if not matches:
            lines.append(f"{name} -> not supported on {family}")
            continue

        smu_val = _skin_scale(name, raw)
        smu_val = max(0, min(0xFFFFFFFF, smu_val))

        for is_mp1, op in matches:
            if is_mp1:
                status = smu.send_mp1(family, op, smu_val)
            else:
                status = smu.send_rsmu(family, op, smu_val)
            mb = "MP1" if is_mp1 else "RSMU"
            status_str = smu.status_name(status)
            if status != smu.SMU_OK:
                any_rejected = True
                lines.append(f"{name} [{mb} 0x{op:02X}] = {smu_val} -> {status_str} [!]")
            else:
                lines.append(f"{name} [{mb} 0x{op:02X}] = {smu_val} -> {status_str}")

    return "\n".join(lines) if lines else "(no matching commands for this family)", any_rejected