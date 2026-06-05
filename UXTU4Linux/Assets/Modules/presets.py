"""
presets.py
"""
from dataclasses import dataclass, asdict


RYZEN_FAMILY = [
    "Unknown", "SummitRidge", "PinnacleRidge", "RavenRidge", "Dali", "Pollock",
    "Picasso", "FireFlight", "Matisse", "Renoir", "Lucienne", "VanGogh",
    "Mendocino", "Vermeer", "Cezanne_Barcelo", "Rembrandt", "Raphael",
    "DragonRange", "PhoenixPoint", "PhoenixPoint2", "HawkPoint", "HawkPoint2",
    "SonomaValley", "GraniteRidge", "FireRange", "StrixHalo", "StrixPoint",
    "KrackanPoint", "KrackanPoint2",
]


@dataclass
class Preset:
    Eco: str
    Balance: str
    Performance: str
    Extreme: str
    AC: str = "--max-performance"
    DC: str | None = "--power-saving"


def to_dict(preset: Preset) -> dict:
    return {k: v for k, v in asdict(preset).items() if v is not None}


def get_preset_label(cpu_type: str, family: str, cpu_model: str, raw_cpu: str, variant: str = "") -> str:
    if variant and _variant_preset(variant) is not None:
        return variant
    if cpu_type == "Amd_Apu":
        return _apu_label(family, cpu_model)
    if cpu_type == "Amd_Desktop_Cpu":
        return _desktop_label(family, cpu_model)
    return family or "Unknown"


def _apu_label(family: str, cpu_model: str) -> str:
    if family in ("DragonRange", "FireRange"):
        return "AMDAPUDragonFireRange"
    if family == "StrixHalo":
        return "AMDAPUStrixHalo"
    if _before(family, "Matisse"):
        return _pre_matisse_label(cpu_model)
    if family == "Mendocino" and "U" in cpu_model:
        return "AMDAPUMendocino_U"
    return _post_matisse_label(cpu_model)


def _pre_matisse_label(cpu_model: str) -> str:
    if any(s in cpu_model for s in ("U", "e", "Ce")):
        return "AMDAPUPreMatisse_U_e_Ce"
    if "H" in cpu_model:
        return "AMDAPUPreMatisse_H"
    if "GE" in cpu_model:
        return "AMDAPUPreMatisse_GE"
    if "G" in cpu_model:
        return "AMDAPUPreMatisse_G"
    return "AMDAPUPreMatisse"


def _post_matisse_label(cpu_model: str) -> str:
    if "U" in cpu_model or ("AI" in cpu_model and "HX" not in cpu_model):
        return "AMDAPUPostMatisse_U"
    if "HX" in cpu_model:
        return "AMDAPUPostMatisse_HX"
    if "HS" in cpu_model:
        return "AMDAPUPostMatisse_HS"
    if "H" in cpu_model:
        return "AMDAPUPostMatisse_H"
    if "GE" in cpu_model:
        return "AMDAPUPostMatisse_GE"
    if "G" in cpu_model:
        return "AMDAPUPostMatisse_G"
    return "AMDAPUPostMatisse"


def _desktop_label(family: str, cpu_model: str) -> str:
    pre_raphael = _before(family, "Raphael")
    if "X3D" in cpu_model:
        return "AMDCPUPreRaphael_X3D" if pre_raphael else "AMDCPU_X3D"
    return "AMDCPUPreRaphael" if pre_raphael else "AMDCPU"


def _family_idx(name: str) -> int:
    try:
        return RYZEN_FAMILY.index(name)
    except ValueError:
        return -1


def _before(family: str, ref: str) -> bool:
    return _family_idx(family) < _family_idx(ref)


def get_preset(cpu_type: str, family: str, cpu_model: str, raw_cpu: str, variant: str = "") -> Preset:
    if variant:
        preset = _variant_preset(variant)
        if preset is not None:
            return preset
    if cpu_type == "Amd_Apu":
        return _apu_preset(family, cpu_model)
    if cpu_type == "Amd_Desktop_Cpu":
        return _desktop_preset(family, cpu_model, raw_cpu)
    return _desktop_standard()


def _variant_preset(variant: str) -> Preset | None:
    match variant:
        case "AMDFrameworkLaptop16Ryzen7040_RX7700S":
            return Preset(
                Eco="--tctl-temp=100 --apu-skin-temp=45 --stapm-limit=30000 --fast-limit=35000 --slow-limit=30000 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000 --vrmgfx-current=180000",
                Balance="--tctl-temp=100 --apu-skin-temp=50 --stapm-limit=95000 --fast-limit=95000 --slow-limit=95000 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000 --vrmgfx-current=180000",
                Performance="--tctl-temp=100 --apu-skin-temp=50 --stapm-limit=100000 --fast-limit=100000 --slow-limit=120000 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000 --vrmgfx-current=180000",
                Extreme="--tctl-temp=100 --apu-skin-temp=50 --stapm-limit=120000 --fast-limit=140000 --slow-limit=120000 --vrm-current=200000 --vrmmax-current=200000 --vrmsoc-current=200000 --vrmsocmax-current=200000 --vrmgfx-current=200000",
            )
        case "AMDFrameworkLaptop16Ryzen7040":
            return Preset(
                Eco="--tctl-temp=100 --apu-skin-temp=45 --stapm-limit=6000 --fast-limit=8000 --slow-limit=6000 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000 --vrmgfx-current=180000",
                Balance="--tctl-temp=100 --apu-skin-temp=50 --stapm-limit=35000 --fast-limit=45000 --slow-limit=38000 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000 --vrmgfx-current=180000",
                Performance="--tctl-temp=100 --apu-skin-temp=50 --stapm-limit=45000 --fast-limit=55000 --slow-limit=50000 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000 --vrmgfx-current=180000",
                Extreme="--tctl-temp=100 --apu-skin-temp=50 --stapm-limit=55000 --fast-limit=70000 --slow-limit=65000 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000 --vrmgfx-current=180000",
            )
        case "AMDFrameworkLaptop13Ryzen7040_RyzenAI300":
            return Preset(
                Eco="--tctl-temp=100 --apu-skin-temp=45 --stapm-limit=8000 --fast-limit=10000 --slow-limit=8000 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000 --vrmgfx-current=180000",
                Balance="--tctl-temp=100 --apu-skin-temp=50 --stapm-limit=15000 --fast-limit=18000 --slow-limit=15000 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000 --vrmgfx-current=180000",
                Performance="--tctl-temp=100 --apu-skin-temp=50 --stapm-limit=28000 --fast-limit=42000 --slow-limit=28000 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000 --vrmgfx-current=180000",
                Extreme="--tctl-temp=100 --apu-skin-temp=50 --stapm-limit=35000 --fast-limit=60000 --slow-limit=35000 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000 --vrmgfx-current=180000",
            )
    return None


def _apu_preset(family: str, cpu_model: str) -> Preset:
    if family in ("DragonRange", "FireRange"):
        return Preset(
            Eco="--tctl-temp=95 --stapm-limit=35000 --fast-limit=45000 --stapm-time=64 --slow-limit=35000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000 --vrmgfx-current=180000",
            Balance="--tctl-temp=95 --stapm-limit=65000 --fast-limit=75000 --stapm-time=64 --slow-limit=65000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000 --vrmgfx-current=180000",
            Performance="--tctl-temp=95 --stapm-limit=100000 --fast-limit=120000 --stapm-time=64 --slow-limit=100000 --slow-time=128 --vrm-current=240000 --vrmmax-current=240000 --vrmsoc-current=240000 --vrmsocmax-current=240000 --vrmgfx-current=240000",
            Extreme="--tctl-temp=95 --stapm-limit=125000 --fast-limit=145000 --stapm-time=64 --slow-limit=125000 --slow-time=128 --vrm-current=240000 --vrmmax-current=240000 --vrmsoc-current=240000 --vrmsocmax-current=240000 --vrmgfx-current=240000",
        )

    if family == "StrixHalo":
        return Preset(
            Eco="--tctl-temp=95 --stapm-limit=18000 --fast-limit=25000 --stapm-time=64 --slow-limit=18000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000 --vrmgfx-current=180000",
            Balance="--tctl-temp=95 --stapm-limit=55000 --fast-limit=65000 --stapm-time=64 --slow-limit=55000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000 --vrmgfx-current=180000",
            Performance="--tctl-temp=95 --stapm-limit=100000 --fast-limit=120000 --stapm-time=64 --slow-limit=100000 --slow-time=128 --vrm-current=240000 --vrmmax-current=240000 --vrmsoc-current=240000 --vrmsocmax-current=240000 --vrmgfx-current=240000",
            Extreme="--tctl-temp=95 --stapm-limit=145000 --fast-limit=165000 --stapm-time=64 --slow-limit=145000 --slow-time=128 --vrm-current=240000 --vrmmax-current=240000 --vrmsoc-current=240000 --vrmsocmax-current=240000 --vrmgfx-current=240000",
        )

    if _before(family, "Matisse"):
        return _pre_matisse_apu(cpu_model)

    if family == "Mendocino" and "U" in cpu_model:
        return _u_e_ce()

    return _post_matisse_apu(cpu_model)


def _u_e_ce() -> Preset:
    return Preset(
        Eco="--tctl-temp=95 --apu-skin-temp=45 --stapm-limit=6000 --fast-limit=8000 --stapm-time=64 --slow-limit=6000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000 --vrmgfx-current=180000",
        Balance="--tctl-temp=95 --apu-skin-temp=45 --stapm-limit=15000 --fast-limit=18000 --stapm-time=64 --slow-limit=16000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000 --vrmgfx-current=180000",
        Performance="--tctl-temp=95 --apu-skin-temp=95 --stapm-limit=18000 --fast-limit=20000 --stapm-time=64 --slow-limit=19000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000 --vrmgfx-current=180000",
        Extreme="--tctl-temp=95 --apu-skin-temp=95 --stapm-limit=28000 --fast-limit=28000 --stapm-time=64 --slow-limit=28000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000 --vrmgfx-current=180000",
    )


def _pre_matisse_apu(cpu_model: str) -> Preset:
    if any(s in cpu_model for s in ("U", "e", "Ce")):
        return _u_e_ce()

    if "H" in cpu_model:
        return Preset(
            Eco="--tctl-temp=95 --apu-skin-temp=45 --stapm-limit=6000 --fast-limit=8000 --stapm-time=64 --slow-limit=6000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000 --vrmgfx-current=180000",
            Balance="--tctl-temp=95 --apu-skin-temp=45 --stapm-limit=30000 --fast-limit=35000 --stapm-time=64 --slow-limit=33000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000 --vrmgfx-current=180000",
            Performance="--tctl-temp=95 --apu-skin-temp=95 --stapm-limit=35000 --fast-limit=42000 --stapm-time=64 --slow-limit=40000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000 --vrmgfx-current=180000",
            Extreme="--tctl-temp=95 --apu-skin-temp=95 --stapm-limit=56000 --fast-limit=56000 --stapm-time=64 --slow-limit=56000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000 --vrmgfx-current=180000",
        )

    if "GE" in cpu_model:
        return Preset(
            Eco="--tctl-temp=95 --apu-skin-temp=45 --stapm-limit=15000 --fast-limit=15000 --stapm-time=64 --slow-limit=18000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000 --vrmgfx-current=180000",
            Balance="--tctl-temp=95 --apu-skin-temp=45 --stapm-limit=45000 --fast-limit=55000 --stapm-time=64 --slow-limit=48000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000 --vrmgfx-current=180000",
            Performance="--tctl-temp=95 --apu-skin-temp=95 --stapm-limit=55000 --fast-limit=65000 --stapm-time=64 --slow-limit=60000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000 --vrmgfx-current=180000",
            Extreme="--tctl-temp=95 --apu-skin-temp=95 --stapm-limit=65000 --fast-limit=80000 --stapm-time=64 --slow-limit=75000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000 --vrmgfx-current=180000",
        )

    if "G" in cpu_model:
        return Preset(
            Eco="--tctl-temp=95 --apu-skin-temp=45 --stapm-limit=15000 --fast-limit=18000 --stapm-time=64 --slow-limit=18000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000 --vrmgfx-current=180000",
            Balance="--tctl-temp=95 --apu-skin-temp=45 --stapm-limit=65000 --fast-limit=75000 --stapm-time=64 --slow-limit=65000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000 --vrmgfx-current=180000",
            Performance="--tctl-temp=95 --apu-skin-temp=95 --stapm-limit=80000 --fast-limit=75000 --stapm-time=64 --slow-limit=75000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000 --vrmgfx-current=180000",
            Extreme="--tctl-temp=95 --apu-skin-temp=95 --stapm-limit=85000 --fast-limit=95000 --stapm-time=64 --slow-limit=90000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000 --vrmgfx-current=180000",
        )

    return _desktop_standard()


def _post_matisse_apu(cpu_model: str) -> Preset:
    if "U" in cpu_model or ("AI" in cpu_model and "HX" not in cpu_model):
        return Preset(
            Eco="--tctl-temp=95 --apu-skin-temp=45 --stapm-limit=6000 --fast-limit=8000 --stapm-time=64 --slow-limit=6000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000 --vrmgfx-current=180000",
            Balance="--tctl-temp=95 --apu-skin-temp=45 --stapm-limit=22000 --fast-limit=24000 --stapm-time=64 --slow-limit=22000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000 --vrmgfx-current=180000",
            Performance="--tctl-temp=95 --apu-skin-temp=95 --stapm-limit=28000 --fast-limit=28000 --stapm-time=64 --slow-limit=28000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000 --vrmgfx-current=180000",
            Extreme="--tctl-temp=95 --apu-skin-temp=95 --stapm-limit=30000 --fast-limit=34000 --stapm-time=64 --slow-limit=32000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000 --vrmgfx-current=180000",
        )

    if "HX" in cpu_model:
        return Preset(
            Eco="--tctl-temp=95 --apu-skin-temp=45 --stapm-limit=6000 --fast-limit=8000 --stapm-time=64 --slow-limit=6000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000 --vrmgfx-current=180000",
            Balance="--tctl-temp=95 --apu-skin-temp=45 --stapm-limit=55000 --fast-limit=65000 --stapm-time=64 --slow-limit=55000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000 --vrmgfx-current=180000",
            Performance="--tctl-temp=95 --apu-skin-temp=95 --stapm-limit=78000 --fast-limit=70000 --stapm-time=64 --slow-limit=70000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000 --vrmgfx-current=180000",
            Extreme="--tctl-temp=95 --apu-skin-temp=95 --stapm-limit=85000 --fast-limit=95000 --stapm-time=64 --slow-limit=90000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000 --vrmgfx-current=180000",
        )

    if "HS" in cpu_model:
        return Preset(
            Eco="--tctl-temp=95 --apu-skin-temp=45 --stapm-limit=6000 --fast-limit=8000 --stapm-time=64 --slow-limit=6000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000 --vrmgfx-current=180000",
            Balance="--tctl-temp=95 --apu-skin-temp=45 --stapm-limit=35000 --fast-limit=45000 --stapm-time=64 --slow-limit=38000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000 --vrmgfx-current=180000",
            Performance="--tctl-temp=95 --apu-skin-temp=95 --stapm-limit=45000 --fast-limit=55000 --stapm-time=64 --slow-limit=50000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000 --vrmgfx-current=180000",
            Extreme="--tctl-temp=95 --apu-skin-temp=95 --stapm-limit=55000 --fast-limit=70000 --stapm-time=64 --slow-limit=65000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000 --vrmgfx-current=180000",
        )

    if "H" in cpu_model:
        return Preset(
            Eco="--tctl-temp=95 --apu-skin-temp=45 --stapm-limit=6000 --fast-limit=8000 --stapm-time=64 --slow-limit=6000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000 --vrmgfx-current=180000",
            Balance="--tctl-temp=95 --apu-skin-temp=45 --stapm-limit=45000 --fast-limit=55000 --stapm-time=64 --slow-limit=48000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000 --vrmgfx-current=180000",
            Performance="--tctl-temp=95 --apu-skin-temp=95 --stapm-limit=55000 --fast-limit=65000 --stapm-time=64 --slow-limit=60000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000 --vrmgfx-current=180000",
            Extreme="--tctl-temp=95 --apu-skin-temp=95 --stapm-limit=65000 --fast-limit=80000 --stapm-time=64 --slow-limit=75000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000 --vrmgfx-current=180000",
        )

    if "GE" in cpu_model:
        return Preset(
            Eco="--tctl-temp=95 --apu-skin-temp=45 --stapm-limit=15000 --fast-limit=15000 --stapm-time=64 --slow-limit=18000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000 --vrmgfx-current=180000",
            Balance="--tctl-temp=95 --apu-skin-temp=45 --stapm-limit=45000 --fast-limit=55000 --stapm-time=64 --slow-limit=48000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000 --vrmgfx-current=180000",
            Performance="--tctl-temp=95 --apu-skin-temp=95 --stapm-limit=55000 --fast-limit=65000 --stapm-time=64 --slow-limit=60000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000 --vrmgfx-current=180000",
            Extreme="--tctl-temp=95 --apu-skin-temp=95 --stapm-limit=65000 --fast-limit=80000 --stapm-time=64 --slow-limit=75000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000 --vrmgfx-current=180000",
        )

    if "G" in cpu_model:
        return Preset(
            Eco="--tctl-temp=95 --apu-skin-temp=45 --stapm-limit=15000 --fast-limit=18000 --stapm-time=64 --slow-limit=18000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000 --vrmgfx-current=180000",
            Balance="--tctl-temp=95 --apu-skin-temp=45 --stapm-limit=65000 --fast-limit=75000 --stapm-time=64 --slow-limit=65000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000 --vrmgfx-current=180000",
            Performance="--tctl-temp=95 --apu-skin-temp=95 --stapm-limit=80000 --fast-limit=75000 --stapm-time=64 --slow-limit=75000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000 --vrmgfx-current=180000",
            Extreme="--tctl-temp=95 --apu-skin-temp=95 --stapm-limit=85000 --fast-limit=95000 --stapm-time=64 --slow-limit=90000 --slow-time=128 --vrm-current=180000 --vrmmax-current=180000 --vrmsoc-current=180000 --vrmsocmax-current=180000 --vrmgfx-current=180000",
        )

    return _desktop_standard()


def _desktop_preset(family: str, cpu_model: str, raw_cpu: str) -> Preset:
    if "X3D" in cpu_model:
        return _desktop_x3d()
    return _desktop_standard()


def _desktop_standard() -> Preset:
    return Preset(
        Eco="--tctl-temp=95",
        Balance="--tctl-temp=95",
        Performance="--tctl-temp=95",
        Extreme="--tctl-temp=95",
    )


def _desktop_x3d() -> Preset:
    return Preset(
        Eco="--tctl-temp=85",
        Balance="--tctl-temp=85",
        Performance="--tctl-temp=85",
        Extreme="--tctl-temp=85",
    )