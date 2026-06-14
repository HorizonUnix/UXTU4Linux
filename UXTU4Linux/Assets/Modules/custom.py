from __future__ import annotations

import copy
import json
import sys
from typing import Any

from . import config as cfg
from . import termui
from .ui import _R, _B, _D, _Y, _G, _SEP_W, _wrap

FIELD_DEFS: list[dict[str, Any]] = [
    {
        "key": "tctl_temp", "label": "APU Temp Limit", "arg": "--tctl-temp",
        "unit": "°C", "default": 95, "min": 10, "max": 105, "step": 1,
        "enabled": False, "section": 1,
        "hint": "Controls the temperature limit at which the APU starts soft throttling",
    },
    {
        "key": "apu_skin_temp", "label": "Skin Temp Limit", "arg": "--apu-skin-temp",
        "unit": "°C", "default": 45, "min": 8, "max": 105, "step": 1,
        "enabled": False, "section": 1,
        "hint": "Controls the laptop chassis temperature limit at which the APU starts throttling",
    },
    {
        "key": "stapm_limit", "label": "STAPM Power Limit", "arg": "--stapm-limit",
        "unit": "W", "default": 28, "min": 5, "max": 300, "step": 1,
        "enabled": False, "section": 2,
        "hint": "Controls the APU's Skin Temperature Aware Power Management power limit",
    },
    {
        "key": "fast_limit", "label": "Fast Power Limit", "arg": "--fast-limit",
        "unit": "W", "default": 28, "min": 5, "max": 300, "step": 1,
        "enabled": False, "section": 2,
        "hint": "Controls the APU's fast boost duration power limit. Within SmartShift enabled systems, this options controls the total power shared between the AMD CPU and AMD dGPU",
    },
    {
        "key": "stapm_time", "label": "Fast Boost Duration", "arg": "--stapm-time",
        "unit": "s", "default": 64, "min": 2, "max": 1024, "step": 1,
        "enabled": False, "section": 2,
        "hint": "Controls how long the APU stays within the fast boost power limit",
    },
    {
        "key": "slow_limit", "label": "Slow Power Limit", "arg": "--slow-limit",
        "unit": "W", "default": 28, "min": 5, "max": 300, "step": 1,
        "enabled": False, "section": 2,
        "hint": "Controls the APU's slow boost duration power limit. Within SmartShift enabled systems, this options controls the total power shared between the AMD CPU and AMD dGPU",
    },
    {
        "key": "slow_time", "label": "Slow Boost Duration", "arg": "--slow-time",
        "unit": "s", "default": 128, "min": 2, "max": 1024, "step": 1,
        "enabled": False, "section": 2,
        "hint": "Controls how long the APU stays within the slow boost power limit",
    },
    {
        "key": "vrm_current", "label": "CPU TDC Limit", "arg": "--vrm-current",
        "unit": "A", "default": 64, "min": 8, "max": 300, "step": 1,
        "enabled": False, "section": 3,
        "hint": "Controls the CPU's Thermal Design Current limit",
    },
    {
        "key": "vrmmax_current", "label": "CPU EDC Limit", "arg": "--vrmmax-current",
        "unit": "A", "default": 64, "min": 8, "max": 300, "step": 1,
        "enabled": False, "section": 3,
        "hint": "Controls the CPU's Electrical Design Current limit",
    },
    {
        "key": "vrmsoc_current", "label": "SoC TDC Limit", "arg": "--vrmsoc-current",
        "unit": "A", "default": 64, "min": 8, "max": 300, "step": 1,
        "enabled": False, "section": 3,
        "hint": "Controls the SoC's Thermal Design Current limit",
    },
    {
        "key": "vrmsocmax_current", "label": "SoC EDC Limit", "arg": "--vrmsocmax-current",
        "unit": "A", "default": 64, "min": 8, "max": 300, "step": 1,
        "enabled": False, "section": 3,
        "hint": "Controls the SoC's Electrical Design Current limit",
    },
    {
        "key": "vrmgfx_current", "label": "GFX TDC Limit", "arg": "--vrmgfx-current",
        "unit": "A", "default": 64, "min": 8, "max": 300, "step": 1,
        "enabled": False, "section": 3,
        "hint": "Controls the iGPU's Thermal Design Current limit",
    },
    {
        "key": "vrmgfxmax_current", "label": "GFX EDC Limit", "arg": "--vrmgfxmax-current",
        "unit": "A", "default": 64, "min": 8, "max": 300, "step": 1,
        "enabled": False, "section": 3,
        "hint": "Controls the iGPU's Electrical Design Current limit",
    },
    {
        "key": "max_gfxclk", "label": "Max iGPU Clock", "arg": "--max-gfxclk",
        "unit": "MHz", "default": 1000, "min": 400, "max": 2000, "step": 25,
        "enabled": False, "section": 4,
        "hint": "Controls the maximum soft clock target of the iGPU. This only works when within your APUs specification.",
    },
    {
        "key": "min_gfxclk", "label": "Min iGPU Clock", "arg": "--min-gfxclk",
        "unit": "MHz", "default": 400, "min": 400, "max": 2000, "step": 25,
        "enabled": False, "section": 4,
        "hint": "Controls the minimum soft clock target of the iGPU. This only works when within your APUs specification.",
    },
    {
        "key": "gfx_clk", "label": "iGPU Clock", "arg": "--gfx-clk",
        "unit": "MHz", "default": 1000, "min": 200, "max": 4000, "step": 25,
        "enabled": False, "section": 4,
        "hint": "Controls the static boost clock speed of the iGPU, requires either a system reboot or system sleep to revert back to normal.",
    },
    {
        "key": "boost_profile", "label": "AMD Boost Profile", "arg": "--_boost-profile",
        "check_arg": "max-performance",
        "unit": "", "default": 0, "min": 0, "max": 2, "step": 1,
        "enabled": False, "section": 2,
        "choices": ["Auto", "Power Saving", "Performance"],
        "hint": "Provides the ability to set a manual boost profile which impact on boost delay.",
    },
    {
        "key": "pbo_scalar", "label": "PBO Scalar", "arg": "--pbo-scalar",
        "unit": "", "default": 1, "min": 1, "max": 10, "step": 1, "scale": 100,
        "enabled": False, "section": 5,
        "hint": "Allows control to change the PBO Scalar which adjusts the FIT/FITness/FailuresInTime limit by the set amount",
    },
    {
        "key": "coall", "label": "All Core CO", "arg": "--set-coall",
        "unit": "", "default": 0, "min": -50, "max": 30, "step": 1, "signed_co": True,
        "enabled": False, "section": 5,
        "hint": "Allows control to change the all core Curve Optimiser Frequency/Voltage curve offset",
    },
    {
        "key": "cogfx", "label": "iGPU CO", "arg": "--set-cogfx",
        "unit": "", "default": 0, "min": -50, "max": 30, "step": 1, "signed_co": True,
        "enabled": False, "section": 5,
        "hint": "Allows control to change the iGPU Curve Optimiser Frequency/Voltage curve offset",
    },
    {
        "key": "max_cpuclk", "label": "Max CPU Clock", "arg": "--max-cpuclk",
        "unit": "MHz", "default": 3200, "min": 400, "max": 4200, "step": 25,
        "enabled": False, "section": 7,
        "hint": "Controls the maximum soft clock target of the CPU. This only works when within your APUs specification.",
    },
    {
        "key": "min_cpuclk", "label": "Min CPU Clock", "arg": "--min-cpuclk",
        "unit": "MHz", "default": 400, "min": 400, "max": 2000, "step": 25,
        "enabled": False, "section": 7,
        "hint": "Controls the minimum soft clock target of the CPU. This only works when within your APUs specification.",
    },
    {
        "key": "max_fclk", "label": "Max Fclk", "arg": "--max-fclk-frequency",
        "unit": "MHz", "default": 1600, "min": 400, "max": 2000, "step": 25,
        "enabled": False, "section": 7,
        "hint": "Controls the maximum soft clock target of the Infinity Fabric. This only works when within your APUs specification.",
    },
    {
        "key": "min_fclk", "label": "Min Fclk", "arg": "--min-fclk-frequency",
        "unit": "MHz", "default": 400, "min": 400, "max": 2000, "step": 25,
        "enabled": False, "section": 7,
        "hint": "Controls the minimum soft clock target of the Infinity Fabric. This only works when within your APUs specification.",
    },
    {
        "key": "max_socclk", "label": "Max SoC Clock", "arg": "--max-socclk-frequency",
        "unit": "MHz", "default": 1600, "min": 400, "max": 2000, "step": 25,
        "enabled": False, "section": 7,
        "hint": "Controls the maximum soft clock target of the SoC. This only works when within your APUs specification.",
    },
    {
        "key": "min_socclk", "label": "Min SoC Clock", "arg": "--min-socclk-frequency",
        "unit": "MHz", "default": 400, "min": 400, "max": 2000, "step": 25,
        "enabled": False, "section": 7,
        "hint": "Controls the minimum soft clock target of the SoC. This only works when within your APUs specification.",
    },
    {
        "key": "max_vcn", "label": "Max VCN Clock", "arg": "--max-vcn",
        "unit": "MHz", "default": 1200, "min": 400, "max": 2000, "step": 25,
        "enabled": False, "section": 7,
        "hint": "Controls the maximum soft clock target of the Video Core Next. This only works when within your APUs specification.",
    },
    {
        "key": "min_vcn", "label": "Min VCN Clock", "arg": "--min-vcn",
        "unit": "MHz", "default": 400, "min": 400, "max": 2000, "step": 25,
        "enabled": False, "section": 7,
        "hint": "Controls the minimum soft clock target of the Video Core Next. This only works when within your APUs specification.",
    },
    {
        "key": "max_lclk", "label": "Max Data Clock", "arg": "--max-lclk",
        "unit": "MHz", "default": 1600, "min": 400, "max": 4200, "step": 25,
        "enabled": False, "section": 7,
        "hint": "Controls the maximum soft clock target of the Data Launch Clock. This only works when within your APUs specification.",
    },
    {
        "key": "min_lclk", "label": "Min Data Clock", "arg": "--min-lclk",
        "unit": "MHz", "default": 400, "min": 400, "max": 2000, "step": 25,
        "enabled": False, "section": 7,
        "hint": "Controls the minimum soft clock target of the Data Launch Clock. This only works when within your APUs specification.",
    },
]

FIELD_DEFS_DT: list[dict[str, Any]] = [
    {
        "key": "tctl_temp", "label": "CPU Temp Limit", "arg": "--tctl-temp",
        "unit": "°C", "default": 85, "min": 10, "max": 95, "step": 1,
        "enabled": False, "section": 1,
        "hint": "Controls the temperature limit at which the CPU starts hard throttling",
    },
    {
        "key": "ppt_limit", "label": "PPT Limit", "arg": "--ppt-limit",
        "unit": "W", "default": 140, "min": 8, "max": 300, "step": 1,
        "enabled": False, "section": 2,
        "hint": "Controls the CPU's Package Power Tracking power limit",
    },
    {
        "key": "tdc_limit", "label": "TDC Limit", "arg": "--tdc-limit",
        "unit": "A", "default": 160, "min": 8, "max": 900, "step": 25,
        "enabled": False, "section": 2,
        "hint": "Controls the CPU's Thermal Design Current limit",
    },
    {
        "key": "edc_limit", "label": "EDC Limit", "arg": "--edc-limit",
        "unit": "A", "default": 160, "min": 8, "max": 900, "step": 25,
        "enabled": False, "section": 2,
        "hint": "Controls the CPU's Electrical Design Current limit",
    },
    {
        "key": "pbo_scalar", "label": "PBO Scalar", "arg": "--pbo-scalar",
        "unit": "", "default": 1, "min": 1, "max": 10, "step": 1, "scale": 100,
        "enabled": False, "section": 3,
        "hint": "Allows control to change the PBO Scalar which adjusts the FIT/FITness/FailuresInTime limit by the set amount",
    },
    {
        "key": "coall", "label": "All Core CO", "arg": "--set-coall",
        "unit": "", "default": 0, "min": -50, "max": 30, "step": 1, "signed_co": True,
        "enabled": False, "section": 3,
        "hint": "Allows control to change the all core Curve Optimiser Frequency/Voltage curve offset",
    },
    {
        "key": "cogfx", "label": "iGPU CO", "arg": "--set-cogfx",
        "unit": "", "default": 0, "min": -50, "max": 30, "step": 1, "signed_co": True,
        "enabled": False, "section": 3,
        "hint": "Allows control to change the iGPU Curve Optimiser Frequency/Voltage curve offset",
    },
]

APU_PER_CORE_CO = [
    {"ccd": 0, "core": i, "key": f"co_ccd1_core{i + 1}", "label": f"CCD1 Core {i + 1}", "section": 6}
    for i in range(12)
] + [
    {"ccd": 1, "core": i, "key": f"co_ccd2_core{i + 1}", "label": f"CCD2 Core {i + 1}", "section": 6}
    for i in range(12)
]

DT_PER_CORE_CO = [
    {"ccd": 0, "core": i, "key": f"co_ccd1_core{i + 1}", "label": f"CCD1 Core {i + 1}", "section": 4}
    for i in range(8)
] + [
    {"ccd": 1, "core": i, "key": f"co_ccd2_core{i + 1}", "label": f"CCD2 Core {i + 1}", "section": 4}
    for i in range(8)
]

for _e in APU_PER_CORE_CO:
    FIELD_DEFS.append({
        "key": _e["key"], "label": _e["label"], "arg": "--set-coper",
        "unit": "", "default": 0, "min": -50, "max": 30, "step": 1,
        "enabled": False, "section": _e["section"],
        "hint": f"Allows control to change the Curve Optimiser Frequency/Voltage curve offset for core {_e['core'] + 1}",
        "ccd": _e["ccd"], "core": _e["core"],
    })

for _e in DT_PER_CORE_CO:
    FIELD_DEFS_DT.append({
        "key": _e["key"], "label": _e["label"], "arg": "--set-coper",
        "unit": "", "default": 0, "min": -50, "max": 30, "step": 1,
        "enabled": False, "section": _e["section"],
        "hint": f"Allows control to change the Curve Optimiser Frequency/Voltage curve offset for core {_e['core'] + 1}",
        "ccd": _e["ccd"], "core": _e["core"],
    })

OC_SECTION = 9
NV_SECTION = 10
SYS_SECTION = 11

_OC_FIELDS: list[dict[str, Any]] = [
    {
        "key": "oc_clk", "label": "CPU Clocks (MHz)", "arg": "--oc-clk",
        "unit": "MHz", "default": 3200, "min": 400, "max": 8000, "step": 25,
        "enabled": False, "section": OC_SECTION,
        "hint": "Provides the ability to set a static CPU clock",
    },
    {
        "key": "oc_volt", "label": "CPU VID (mV)", "arg": "--oc-volt",
        "unit": "", "default": 1200, "min": 512, "max": 1450, "step": 25,
        "enabled": False, "section": OC_SECTION,
        "hint": "Controls the set voltage for the CPU",
    },
]

_NV_FIELDS: list[dict[str, Any]] = [
    {
        "key": "nv_max_clk", "label": "Max GPU Clock", "arg": "--_nv",
        "unit": "MHz", "default": 4000, "min": 400, "max": 4000, "step": 5,
        "enabled": False, "section": NV_SECTION, "nvidia_only": True,
        "hint": "Controls the maximum voltage your GPU will run within the Frequency/Voltage curve based on clock speed. You can undervolt your NVIDIA GPU by lowering this clock speed below stock and increasing the core clock offset. Start at your GPU's rated boost clock and work down. To reset it, set it to the maximum possible clock the slider allows.",
    },
    {
        "key": "nv_core_offset", "label": "GPU Core Offset", "arg": "--_nv",
        "unit": "MHz", "default": 0, "min": -500, "max": 2000, "step": 5,
        "enabled": False, "section": NV_SECTION, "nvidia_only": True,
        "hint": "Controls the clock offset for your NVIDIA GPU's core clock",
    },
    {
        "key": "nv_mem_offset", "label": "GPU Mem Offset", "arg": "--_nv",
        "unit": "MHz", "default": 0, "min": -900, "max": 2000, "step": 5,
        "enabled": False, "section": NV_SECTION, "nvidia_only": True,
        "hint": "Controls the clock offset for your NVIDIA GPU's VRAM clock",
    },
]

_SYS_FIELDS: list[dict[str, Any]] = [
    {
        "key": "power_profile", "label": "Power Profile", "arg": "--sys-power-profile",
        "unit": "", "default": 1, "min": 0, "max": 2, "step": 1,
        "enabled": False, "section": SYS_SECTION, "system_check": "power_profile",
        "choices": ["Power Saver", "Balanced", "Performance"],
        "hint": "Controls the system power profile to prioritise either power efficiency or performance, the Linux equivalent of the Windows power mode",
    },
    {
        "key": "asus_mode", "label": "ASUS Performance Mode", "arg": "--sys-asus-mode",
        "unit": "", "default": 1, "min": 0, "max": 2, "step": 1,
        "enabled": False, "section": SYS_SECTION, "system_check": "asus",
        "choices": ["Silent", "Balanced", "Turbo"],
        "hint": "Controls the ASUS performance mode, like the Silent, Balanced and Turbo modes within Armoury Crate",
    },
    {
        "key": "asus_gpu_eco", "label": "ASUS GPU Eco", "arg": "--sys-asus-eco",
        "unit": "", "default": 0, "min": 0, "max": 1, "step": 1,
        "enabled": False, "section": SYS_SECTION, "system_check": "asus_eco",
        "choices": ["dGPU On", "dGPU Off (Eco)"],
        "hint": "Controls the power state of the dGPU, like the Eco mode within Armoury Crate, requires the dGPU to be idle and the MUX set to Optimus",
    },
    {
        "key": "asus_gpu_mux", "label": "ASUS GPU MUX", "arg": "--sys-asus-mux",
        "unit": "", "default": 1, "min": 0, "max": 1, "step": 1,
        "enabled": False, "section": SYS_SECTION, "system_check": "asus_mux",
        "choices": ["dGPU (Ultimate)", "Optimus (Hybrid)"],
        "hint": "Controls the GPU MUX switch between dGPU (Ultimate) and Optimus (Hybrid) mode, requires a system reboot to take effect",
    },
    {
        "key": "ccd_affinity", "label": "CCD Affinity", "arg": "--sys-ccd-affinity",
        "unit": "", "default": 0, "min": 0, "max": 2, "step": 1,
        "enabled": False, "section": SYS_SECTION, "system_check": "ccd",
        "choices": ["All Cores", "CCD1 Only", "CCD2 Only"],
        "hint": "Allows control to pin applications to a single CCD, useful to keep games on the V-Cache die of X3D CPUs",
    },
]

for _oc in _OC_FIELDS:
    FIELD_DEFS.append(dict(_oc))
    FIELD_DEFS_DT.append(dict(_oc))

for _nv in _NV_FIELDS:
    FIELD_DEFS.append(dict(_nv))
    FIELD_DEFS_DT.append(dict(_nv))

for _sf in _SYS_FIELDS:
    FIELD_DEFS.append(dict(_sf))
    FIELD_DEFS_DT.append(dict(_sf))

APU_SECTION_NAMES = {1: "Temp", 2: "Power", 3: "VRM", 4: "iGPU", 5: "CO", 6: "CO Per-Core", 7: "Clocks", OC_SECTION: "CPU Tuning", NV_SECTION: "NV GPU", SYS_SECTION: "System"}
APU_SECTION_TITLES = {
    1: "APU Temperature",
    2: "APU Power Limits",
    3: "APU VRM Limits",
    4: "iGPU Clock Limits",
    5: "Curve Optimiser",
    6: "Curve Optimiser Per-Core",
    7: "Soft Clock Limits",
    OC_SECTION: "CPU Tuning",
    NV_SECTION: "NVIDIA GPU",
    SYS_SECTION: "System",
}

DT_SECTION_NAMES = {1: "Thermal", 2: "Power", 3: "PBO/CO", 4: "CO Per-Core", OC_SECTION: "OC", NV_SECTION: "NV GPU", SYS_SECTION: "System"}
DT_SECTION_TITLES = {
    1: "CPU Thermal",
    2: "CPU Power Limits",
    3: "PBO & Curve Optimiser",
    4: "Curve Optimiser Per-Core",
    OC_SECTION: "CPU Tuning",
    NV_SECTION: "NVIDIA GPU",
    SYS_SECTION: "System",
}

APU_PER_CORE_SECTION = 6
DT_PER_CORE_SECTION = 4

_CLK_PAIRS = [
    ("min_gfxclk", "max_gfxclk"),
    ("min_cpuclk", "max_cpuclk"),
    ("min_fclk", "max_fclk"),
    ("min_socclk", "max_socclk"),
    ("min_vcn", "max_vcn"),
    ("min_lclk", "max_lclk"),
]


def _display_name(internal_name: str) -> str:
    return internal_name.removesuffix("_custom_preset")


def _supports_ccd2_apu() -> bool:
    family = cfg.get("Info", "Family")
    cpu = cfg.get("Info", "CPU")
    return family in {"DragonRange", "FireRange", "StrixHalo", "KrackanPoint"} and (
        "Ryzen 9" in cpu or "395" in cpu or "390" in cpu
    )


def _supports_ccd2_dt() -> bool:
    cpu = cfg.get("Info", "CPU")
    return "Ryzen 9" in cpu or "Ryzen Threadripper" in cpu


def _special_coper_family() -> bool:
    return cfg.get("Info", "Family") in {"DragonRange", "FireRange", "StrixHalo"}


def clamp_field(value: int, fdef: dict) -> int:
    return max(fdef["min"], min(fdef["max"], value))


_nvidia_available: bool | None = None


def has_nvidia() -> bool:
    global _nvidia_available
    if _nvidia_available is None:
        import shutil
        _nvidia_available = shutil.which("nvidia-smi") is not None
    return _nvidia_available


_sys_support: dict[str, bool] = {}


def _system_supported(kind: str) -> bool:
    if kind not in _sys_support:
        try:
            from . import platformctl
            checks = {
                "power_profile": platformctl.power_profile_available,
                "asus": platformctl.asus_available,
                "asus_eco": platformctl.asus_eco_available,
                "asus_mux": platformctl.asus_mux_available,
                "ccd": platformctl.ccd_affinity_available,
            }
            fn = checks.get(kind)
            _sys_support[kind] = fn() if fn else False
        except Exception:
            _sys_support[kind] = False
    return _sys_support[kind]


def _supported_field_keys(family: str, fields: list[dict]) -> set[str]:
    from . import runner
    nv = has_nvidia()
    supported = set()
    for f in fields:
        if f.get("nvidia_only"):
            if nv:
                supported.add(f["key"])
            continue
        if f.get("system_check"):
            if _system_supported(f["system_check"]):
                supported.add(f["key"])
            continue
        check = f.get("check_arg") or f.get("arg", "").lstrip("-")
        if check and runner.lookup(family, check):
            supported.add(f["key"])
    return supported


def _active_sections(
    all_sections: dict[int, str],
    fields: list[dict],
    supported: set[str],
) -> dict[int, str]:
    return {
        s: name for s, name in all_sections.items()
        if any(f["section"] == s and f["key"] in supported for f in fields)
    }


def _section_indices(fields: list[dict], section: int, supported: set[str] | None = None) -> list[int]:
    return [
        i for i, f in enumerate(fields)
        if f["section"] == section and (supported is None or f["key"] in supported)
    ]


def _enforce_clk_clamp(fields: list[dict], changed_key: str) -> None:
    by_key = {f["key"]: f for f in fields}
    for min_key, max_key in _CLK_PAIRS:
        if changed_key not in (min_key, max_key):
            continue
        mn = by_key.get(min_key)
        mx = by_key.get(max_key)
        if mn is None or mx is None:
            continue
        if changed_key == min_key and mn["value"] > mx["value"]:
            mx["value"] = mn["value"]
        elif changed_key == max_key and mx["value"] < mn["value"]:
            mn["value"] = mx["value"]
        break


def _smu_value(f: dict) -> int:
    val = f["value"]
    if "scale" in f:
        return int(val * f["scale"])
    if f.get("unit") in ("W", "A"):
        return val * 1000
    if f.get("signed_co") and val < 0:
        return 0x100000 + val
    return val


def _coper_value(f: dict) -> int:
    offset = max(-50, min(30, int(f["value"])))
    magnitude = min(abs(offset), 0xFFFFF)
    encoded = (0x100000 - magnitude) & 0xFFFFF if offset < 0 else magnitude & 0xFFFFF
    prefix = (((int(f.get("ccd", 0)) << 4) | 0) << 4 | (int(f.get("core", 0)) % 8 & 15)) << 20
    return prefix | encoded


_OC_NEWER_FAMILIES = {
    "Rembrandt", "PhoenixPoint", "PhoenixPoint2", "HawkPoint", "HawkPoint2",
    "SonomaValley", "StrixPoint", "StrixHalo", "KrackanPoint", "KrackanPoint2",
    "Raphael", "DragonRange", "GraniteRidge", "FireRange",
}


def _encode_oc_volt(vid: int, family: str) -> int:
    if family in _OC_NEWER_FAMILIES:
        return int((vid - 1125) / 5 + 1200)
    return round((1.55 - vid / 1000) / 0.00625)


def build_args(fields: list[dict], cpu_type: str = "") -> str:
    if not cpu_type:
        cpu_type = cfg.get("Info", "Type")
    is_apu = cpu_type == "Amd_Apu"
    is_dt = cpu_type == "Amd_Desktop_Cpu"
    use_coper_encode = is_dt or _special_coper_family()
    parts = []
    oc_emitted = False
    nv_enabled = False
    nv_vals: dict[str, int] = {}
    for f in fields:
        if f.get("nvidia_only"):
            nv_vals[f["key"]] = f.get("value", f["default"])
            if f["enabled"]:
                nv_enabled = True
            continue
        if not f["enabled"]:
            continue
        if f["key"] == "boost_profile":
            if f["value"] == 1:
                parts.append("--power-saving")
            elif f["value"] == 2:
                parts.append("--max-performance")
        elif f["key"] == "oc_clk":
            v = f["value"]
            parts.append(f"--oc-clk={v} --oc-clk={v}")
            oc_emitted = True
        elif f["key"] == "oc_volt":
            family = cfg.get("Info", "Family")
            vid = _encode_oc_volt(f["value"], family)
            parts.append(f"--oc-volt={vid} --oc-volt={vid}")
            oc_emitted = True
        elif f["arg"] == "--set-coper":
            if use_coper_encode:
                parts.append(f"--set-coper={_coper_value(f)}")
            else:
                core = int(f.get("core", 0))
                encoded = ((core if core < 8 else 7) << 20) | (int(f["value"]) & 0xFFFF)
                parts.append(f"--set-coper={encoded}")
        elif f["key"] == "tctl_temp" and is_apu:
            val = f["value"]
            parts.append(f"--tctl-temp={val}")
            parts.append(f"--chtc-temp={val}")
        else:
            parts.append(f"{f['arg']}={_smu_value(f)}")
    if oc_emitted:
        parts.append("--enable-oc --enable-oc")
    if nv_enabled:
        max_clk = nv_vals.get("nv_max_clk", 4000)
        core = nv_vals.get("nv_core_offset", 0)
        mem = nv_vals.get("nv_mem_offset", 0)
        parts.append(f"--nvidia-clocks={max_clk},{core},{mem}")
    return " ".join(parts)


def default_fields(include_ccd2: bool = True) -> list[dict]:
    fields = []
    for f in FIELD_DEFS:
        if not include_ccd2 and f.get("section") == APU_PER_CORE_SECTION and int(f.get("ccd", 0)) == 1:
            continue
        d = dict(f)
        d["value"] = f["default"]
        fields.append(d)
    return fields


def default_dt_fields(include_ccd2: bool = True) -> list[dict]:
    fields = []
    for f in FIELD_DEFS_DT:
        if not include_ccd2 and f.get("section") == DT_PER_CORE_SECTION and int(f.get("ccd", 0)) == 1:
            continue
        d = dict(f)
        d["value"] = f["default"]
        fields.append(d)
    return fields


def _default_fields_for_current_cpu() -> list[dict]:
    cpu_type = cfg.get("Info", "Type")
    if cpu_type == "Amd_Desktop_Cpu":
        return default_dt_fields(include_ccd2=_supports_ccd2_dt())
    return default_fields(include_ccd2=_supports_ccd2_apu())


def load_custom_presets() -> list[dict]:
    try:
        data = json.loads(cfg.CUSTOM_PRESETS_PATH.read_text())
        return data if isinstance(data, list) else []
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return []


def _save_custom_presets(presets: list[dict]) -> None:
    try:
        cfg.CUSTOM_PRESETS_PATH.parent.mkdir(parents=True, exist_ok=True)
        cfg.atomic_write(str(cfg.CUSTOM_PRESETS_PATH), json.dumps(presets, indent=2))
    except OSError as e:
        from .ui import clear, pause
        clear()
        print(f"  Failed to save presets: {e}")
        pause()


def fields_to_record(base_name: str, fields: list[dict]) -> dict:
    record: dict = {"name": base_name}
    for f in fields:
        record[f["key"]] = {"enabled": f["enabled"], "value": f["value"]}
    return record


def record_to_fields(record: dict, cpu_type: str = "") -> list[dict]:
    if not cpu_type:
        cpu_type = cfg.get("Info", "Type")
    if cpu_type == "Amd_Desktop_Cpu":
        fields = default_dt_fields(include_ccd2=_supports_ccd2_dt())
    else:
        fields = default_fields(include_ccd2=_supports_ccd2_apu())
    known = {f["key"] for f in fields}
    for key, entry in record.items():
        if key == "name" or key not in known or not isinstance(entry, dict):
            continue
        for f in fields:
            if f["key"] == key:
                f["enabled"] = bool(entry.get("enabled", f["enabled"]))
                try:
                    f["value"] = clamp_field(int(entry.get("value", f["default"])), f)
                except (TypeError, ValueError):
                    f["value"] = f["default"]
                break
    return fields


def preset_to_args(record: dict, cpu_type: str = "") -> str:
    if not cpu_type:
        cpu_type = cfg.get("Info", "Type")
    return build_args(record_to_fields(record, cpu_type), cpu_type)


def get_custom_preset_names() -> list[str]:
    return [p["name"] + "_custom_preset" for p in load_custom_presets()]


def save_preset(base_name: str, fields: list[dict]) -> str:
    presets = load_custom_presets()
    presets = [p for p in presets if p["name"] != base_name]
    presets.append(fields_to_record(base_name, fields))
    _save_custom_presets(presets)

    internal_name = base_name + "_custom_preset"
    active_mode = cfg.get("User", "Mode")
    ac_slot = cfg.get("Automations", "OnAC", "")
    bat_slot = cfg.get("Automations", "OnBattery", "")
    in_use = (
        active_mode in (base_name, internal_name)
        or ac_slot in (base_name, internal_name)
        or bat_slot in (base_name, internal_name)
    )
    if in_use:
        try:
            from .ipc import get_client
            client = get_client()
            if client.ping():
                client.apply_saved()
        except Exception:
            pass

    return internal_name


def delete_preset(display_name: str) -> None:
    base = display_name.removesuffix("_custom_preset")
    internal_name = base + "_custom_preset"
    presets = [p for p in load_custom_presets() if p["name"] != base]
    _save_custom_presets(presets)

    changed = False

    if cfg.get("User", "Mode") in (internal_name, base):
        cfg.set_config("User", "Mode", "Balance")
        changed = True

    ac_slot = cfg.get("Automations", "OnAC", "")
    bat_slot = cfg.get("Automations", "OnBattery", "")

    if ac_slot in (internal_name, base):
        cfg.set_config("Automations", "OnAC", "")
        ac_slot = ""
        changed = True

    if bat_slot in (internal_name, base):
        cfg.set_config("Automations", "OnBattery", "")
        bat_slot = ""
        changed = True

    if not ac_slot and not bat_slot:
        cfg.set_config("Automations", "Enabled", "0")
        changed = True

    if changed:
        cfg.save()
        try:
            from .ipc import get_client
            client = get_client()
            if client.ping():
                client.apply_saved()
        except Exception:
            pass


def load_preset_fields(display_name: str, cpu_type: str = "") -> list[dict] | None:
    base = display_name.removesuffix("_custom_preset")
    presets = load_custom_presets()
    for p in presets:
        if p.get("name") == base:
            return record_to_fields(p, cpu_type)
    return None


def _render_editor(
    fields: list[dict],
    sections: dict[int, str],
    section_titles: dict[int, str],
    section: int,
    row: int,
    dirty: bool,
    preset_name: str,
    supported_keys: set[str] | None = None,
) -> list[str]:
    name_display = preset_name or "(unnamed)"
    dirty_mark = f"  {_Y}[*]{_R}" if dirty else ""
    lines: list[str] = [
        f"  {_B}Custom Preset Editor{_R}",
        f"  Name: {_B}{name_display}{_R}{dirty_mark}",
        "",
    ]

    sec_list = sorted(sections.keys())
    n = len(sec_list)
    mid = (n + 1) // 2
    chunks = [sec_list[:mid], sec_list[mid:]] if n > 4 else [sec_list]
    for chunk in chunks:
        if not chunk:
            continue
        base = sec_list.index(chunk[0])
        tab_line = "  "
        for idx, s in enumerate(chunk, base + 1):
            if s == section:
                tab_line += f"{_B}[{idx}] {sections[s]}{_R}  "
            else:
                tab_line += f"{_D}[{idx}] {sections[s]}{_R}  "
        lines.append(tab_line.rstrip())

    lines.append(f"  {_D}{'─' * _SEP_W}{_R}")
    lines.append(f"  {_B}{section_titles.get(section, '')}{_R}")
    lines.append("")

    sec_rows = _section_indices(fields, section, supported_keys)
    active_hint = ""
    for r, gi in enumerate(sec_rows):
        f = fields[gi]
        tog = f"{_G}[✓]{_R}" if f["enabled"] else f"{_D}[ ]{_R}"
        lbl = f"{f['label']:<22}"
        if "choices" in f:
            vstr = f"{f['choices'][f['value']]:^10}"
            rng = ""
        else:
            vstr = f"{f['value']:>5} {f['unit']:<4}"
            rng = f"[{f['min']} – {f['max']}]"
        if r == row:
            active_hint = f.get("hint", "")
            lines.append(f"  {_B}▶{_R} {tog} {_B}{lbl}{_R}  {_B}{vstr}{_R}  {_D}{rng}{_R}")
        else:
            if f["enabled"]:
                lines.append(f"    {tog} {lbl}  {_D}{vstr}  {rng}{_R}")
            else:
                lines.append(f"    {tog} {_D}{lbl}  {vstr}  {rng}{_R}")

    lines.append("")
    if active_hint:
        for hl in _wrap(active_hint, _SEP_W - 2):
            lines.append(f"  {_D}{hl}{_R}")
    lines += [
        f"  {_D}{'─' * _SEP_W}{_R}",
        f"  {_D}[S] Save  [L] Load  [D] Delete  [R] Rename{_R}",
        f"  {_D}Space to toggle, ←/→ to step, Enter to type value{_R}",
        f"  {_D}Backspace to reset, Tab to switch section, Esc to go back{_R}",
    ]
    return lines


_MAX_NAME = _SEP_W - 8


def _prompt_name(current: str) -> str | None:
    from .ui import ask, clear
    clear()
    print(f"  {_B}Preset Name{_R}\n")
    print(f"  {_D}Max {_MAX_NAME} characters{_R}\n")
    name = ask("Preset name", default=current)
    return name.strip()[:_MAX_NAME] or None


def _confirm_overwrite(name: str) -> bool:
    from .ui import menu, MenuItem
    items = [
        MenuItem("Yes, overwrite", key="yes"),
        MenuItem("No, cancel",     key="no"),
    ]
    choice = menu(f"Overwrite '{name}'?", items)
    return choice != -1 and items[choice].key == "yes"


def _prompt_value(f: dict) -> int | None:
    from .ui import clear, ask
    clear()
    unit_str = f" {f['unit']}" if f.get("unit") else ""
    print(f"  {_B}{f['label']}{_R}\n")
    print(f"  {_D}Range: {f['min']} – {f['max']}{unit_str}{_R}\n")
    raw = ask("Value", default=str(f["value"]))
    try:
        return clamp_field(int(raw.strip()), f)
    except (ValueError, TypeError):
        return None


def _do_save(fields: list[dict], preset_name: str) -> tuple[str, bool]:
    if not any(f["enabled"] for f in fields):
        from .ui import clear, pause
        clear()
        print("  Cannot save — no parameters are enabled.")
        print("  Enable at least one parameter with Space before saving.")
        pause()
        return preset_name, False

    name = preset_name or ""
    if not name:
        name = _prompt_name("") or ""
        if not name:
            return preset_name, False

    existing = [p["name"] for p in load_custom_presets()]
    if name in existing and not _confirm_overwrite(name):
        return name, False

    save_preset(name, fields)
    return name, True


def _do_load(fields: list[dict], dirty: bool, cpu_type: str) -> tuple[list[dict], str, bool] | None:
    names = get_custom_preset_names()
    if not names:
        from .ui import clear, pause
        clear()
        print("  No saved custom presets.")
        pause()
        return None

    if dirty:
        from .ui import confirm
        if not confirm("Discard unsaved changes and load another preset?"):
            return None

    choice = _arrow_pick("Load Preset", names)
    if choice is None:
        return None

    loaded = load_preset_fields(choice, cpu_type)
    if loaded is None:
        return None

    base_name = choice.removesuffix("_custom_preset")
    return loaded, base_name, False


def _do_delete() -> str | None:
    names = get_custom_preset_names()
    if not names:
        from .ui import clear, pause
        clear()
        print("  No saved custom presets.")
        pause()
        return None

    choice = _arrow_pick("Delete Preset", names)
    if choice is not None:
        from .ui import confirm
        if confirm(f"Delete '{_display_name(choice)}'? This cannot be undone"):
            delete_preset(choice)
            return choice
    return None


def _arrow_pick(title: str, names: list[str]) -> str | None:
    from .ui import menu, MenuItem
    items = [MenuItem(_display_name(n), key=n) for n in names]
    items += [MenuItem("─", kind="separator"), MenuItem("Back", key="back")]
    choice = menu(title, items)
    if choice == -1 or items[choice].key == "back":
        return None
    return items[choice].key


def run_editor(
    initial_fields: list[dict] | None = None,
    initial_name: str = "",
    cpu_type: str = "",
) -> None:
    if not cpu_type:
        cpu_type = cfg.get("Info", "Type")

    if cpu_type == "Amd_Desktop_Cpu":
        all_sections = DT_SECTION_NAMES
        section_titles = DT_SECTION_TITLES
        default_fn = lambda: default_dt_fields(include_ccd2=_supports_ccd2_dt())
    else:
        all_sections = APU_SECTION_NAMES
        section_titles = APU_SECTION_TITLES
        default_fn = lambda: default_fields(include_ccd2=_supports_ccd2_apu())

    family = cfg.get("Info", "Family")
    fields = copy.deepcopy(initial_fields) if initial_fields else default_fn()

    def _recompute_support() -> tuple[set[str], dict[int, str]]:
        sk = _supported_field_keys(family, fields)
        act = _active_sections(all_sections, fields, sk)
        return sk, act

    supported_keys, sections = _recompute_support()
    preset_name = initial_name
    section = min(sections.keys()) if sections else min(all_sections.keys())
    row = 0
    dirty = False

    def clamp_row() -> None:
        nonlocal row
        n = len(_section_indices(fields, section, supported_keys))
        row = max(0, min(row, n - 1)) if n else 0

    try:
        while True:
            clamp_row()
            from .ui import clear as ui_clear
            ui_clear()
            lines = _render_editor(
                fields, sections, section_titles, section, row, dirty,
                preset_name, supported_keys,
            )
            sys.stdout.write(termui.HIDE_CURSOR + "\n".join(lines) + "\n")
            sys.stdout.flush()
            key = termui.get_key()

            if len(key) == 1 and 0x31 <= key[0] <= 0x39:
                idx = key[0] - 0x31
                sec_list = sorted(sections.keys())
                if idx < len(sec_list):
                    new_sec = sec_list[idx]
                    if new_sec != section:
                        section = new_sec
                        row = 0
                continue

            sec_rows = _section_indices(fields, section, supported_keys)

            if key == termui.UP:
                if row > 0:
                    row -= 1
                continue

            if key == termui.DOWN:
                if row < len(sec_rows) - 1:
                    row += 1
                continue

            if key == b"\t":
                sec_list = sorted(sections.keys())
                if sec_list:
                    idx = sec_list.index(section) if section in sec_list else 0
                    section = sec_list[(idx + 1) % len(sec_list)]
                    row = 0
                continue

            if key == b" " and sec_rows:
                f = fields[sec_rows[row]]
                f["enabled"] = not f["enabled"]
                dirty = True
                continue

            if key == termui.ENTER and sec_rows:
                f = fields[sec_rows[row]]
                if "choices" in f:
                    n = len(f["choices"])
                    f["value"] = (f["value"] + f["step"]) % n
                    dirty = True
                else:
                    sys.stdout.write(termui.SHOW_CURSOR)
                    sys.stdout.flush()
                    new_val = _prompt_value(f)
                    if new_val is not None:
                        f["value"] = new_val
                        _enforce_clk_clamp(fields, f["key"])
                        dirty = True
                continue

            if key == termui.LEFT and sec_rows:
                f = fields[sec_rows[row]]
                if "choices" in f:
                    n = len(f["choices"])
                    f["value"] = (f["value"] - f["step"]) % n
                else:
                    f["value"] = clamp_field(f["value"] - f["step"], f)
                    _enforce_clk_clamp(fields, f["key"])
                dirty = True
                continue

            if key == termui.RIGHT and sec_rows:
                f = fields[sec_rows[row]]
                if "choices" in f:
                    n = len(f["choices"])
                    f["value"] = (f["value"] + f["step"]) % n
                else:
                    f["value"] = clamp_field(f["value"] + f["step"], f)
                    _enforce_clk_clamp(fields, f["key"])
                dirty = True
                continue

            if key in (b"\x7f", b"\x08") and sec_rows:
                f = fields[sec_rows[row]]
                f["value"] = f["default"]
                f["enabled"] = False
                _enforce_clk_clamp(fields, f["key"])
                dirty = True
                continue

            if key in (b"s", b"S"):
                sys.stdout.write(termui.SHOW_CURSOR)
                sys.stdout.flush()
                preset_name, saved = _do_save(fields, preset_name)
                if saved:
                    dirty = False
                continue

            if key in (b"l", b"L"):
                sys.stdout.write(termui.SHOW_CURSOR)
                sys.stdout.flush()
                result = _do_load(fields, dirty, cpu_type)
                if result is not None:
                    fields, preset_name, dirty = result
                    supported_keys, sections = _recompute_support()
                    if section not in sections:
                        section = min(sections.keys()) if sections else min(all_sections.keys())
                        row = 0
                continue

            if key in (b"d", b"D"):
                sys.stdout.write(termui.SHOW_CURSOR)
                sys.stdout.flush()
                deleted = _do_delete()
                if deleted and deleted.removesuffix("_custom_preset") == preset_name:
                    preset_name = ""
                    fields = default_fn()
                    supported_keys, sections = _recompute_support()
                    section = min(sections.keys()) if sections else min(all_sections.keys())
                    row = 0
                    dirty = False
                continue

            if key in (b"r", b"R"):
                sys.stdout.write(termui.SHOW_CURSOR)
                sys.stdout.flush()
                new_name = _prompt_name(preset_name or "")
                if new_name and new_name != preset_name:
                    preset_name = new_name
                    dirty = True
                continue

            if key == termui.ESC:
                if dirty:
                    sys.stdout.write(termui.SHOW_CURSOR)
                    sys.stdout.flush()
                    from .ui import confirm
                    ok = confirm("Discard unsaved changes?")
                    if not ok:
                        continue
                break

            if key in (b"\x03", b"\x04"):
                break

    finally:
        sys.stdout.write(termui.SHOW_CURSOR + "\n")
        sys.stdout.flush()


def custom_preset_menu() -> None:
    from .ui import clear, pause, menu, MenuItem

    cpu_type = cfg.get("Info", "Type")
    if cpu_type not in ("Amd_Apu", "Amd_Desktop_Cpu"):
        clear()
        print("  Custom Preset editor is only supported on AMD APUs and Desktop CPUs.")
        pause()
        return

    saved = load_custom_presets()
    if saved:
        names = get_custom_preset_names()
        items = [MenuItem(_display_name(n), key=n) for n in names]
        items += [
            MenuItem("─", kind="separator"),
            MenuItem("Create new preset", key="new"),
            MenuItem("Back", key="back"),
        ]
        choice = menu("Custom Preset", items)
        if choice == -1 or items[choice].key == "back":
            return
        if items[choice].key == "new":
            fields = _default_fields_for_current_cpu()
            name = ""
        else:
            selected = items[choice].key
            fields = load_preset_fields(selected, cpu_type) or _default_fields_for_current_cpu()
            name = selected.removesuffix("_custom_preset")
    else:
        fields = _default_fields_for_current_cpu()
        name = ""

    clear()
    run_editor(initial_fields=fields, initial_name=name, cpu_type=cpu_type)