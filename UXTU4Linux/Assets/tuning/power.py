from __future__ import annotations

from Assets.core import config as cfg


_PRESET_HINTS: dict[str, str] = {
    "Eco": "This preset is designed to prioritize energy efficiency over performance. It sets power limits to conservative levels to reduce power consumption and heat generation, making it ideal for prolonged use in situations where maximizing battery life or minimizing energy usage is critical.",
    "Balance": "This preset aims to find a balance between performance and power consumption, providing a stable and efficient experience. This preset sets the power limits to a level that balances performance and power usage, without sacrificing too much of either.",
    "Performance": "This preset is optimized for maximum performance by increasing the power limits of the APU/CPU, which allows it to run at higher clock speeds for longer periods of time. This can result in improved system responsiveness and faster load times in applications that require high levels of processing power.",
    "Extreme": "This preset aims to push the power limits of the system to their maximum, allowing for the highest possible performance. This preset is designed for users who demand the most from their hardware and are willing to tolerate higher power consumption and potentially increased noise levels.",
}


def _strip_cpu_name(raw: str) -> str:
    for word in ("AMD", "with", "Mobile", "Ryzen", "Radeon", "Graphics", "Vega", "Gfx"):
        raw = raw.replace(word, "")
    return raw


def get_presets() -> dict:
    from Assets.engine.presets import get_preset, get_preset_label, to_dict

    raw_cpu = cfg.get("Info", "CPU")
    family = cfg.get("Info", "Family")
    cpu_type = cfg.get("Info", "Type")
    variant = cfg.get("Info", "Variant")
    cpu_model = _strip_cpu_name(raw_cpu)

    preset = get_preset(cpu_type, family, cpu_model, variant)
    cfg.set_loaded_preset(get_preset_label(cpu_type, family, cpu_model, variant))
    return to_dict(preset)


def get_all_presets() -> dict:
    from Assets.tuning.custom import load_custom_presets, preset_to_args
    presets = dict(get_presets())
    for p in load_custom_presets():
        name = p["name"] + "_custom_preset"
        presets[name] = preset_to_args(p)
    return presets


def apply_preset(args: str, mode: str) -> dict:
    from Assets.core.ipc import get_client

    if cfg.get("Info", "Type") == "Intel":
        return {"ok": False, "error": "Intel chipsets are not supported."}

    cfg.set_config("User", "Mode", mode)
    cfg.save()

    client = get_client()
    if not client.ping():
        return {"ok": False, "error": "Daemon is not running."}

    interval = cfg.parse_interval(cfg.get("Settings", "Time", "3"), default=3)
    automation = cfg.get("Automations", "Enabled", "0") == "1"
    reapply = cfg.get("Settings", "ReApply", "0") == "1"

    if reapply:
        return client.apply_loop(args=args, mode=mode, interval=interval, automation=automation)
    if automation:
        return client.apply_saved()
    return client.apply(args=args, mode=mode)


def update_reapply_interval(val: str) -> bool:
    if not val.isdigit():
        return False
    clamped = str(cfg.parse_interval(val, default=3))
    cfg.set_config("Settings", "Time", clamped)
    cfg.save()
    from Assets.core.ipc import get_client
    client = get_client()
    if client.ping():
        client.apply_saved()
    return True
