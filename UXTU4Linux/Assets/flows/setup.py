from __future__ import annotations

import os

from Assets.core import config as cfg


def _apply_defaults() -> None:
    cfg.ensure_sections("User", "Settings", "Info", "Automations")
    defaults = {
        ("User", "Mode"): "",
        ("Settings", "Time"): "3",
        ("Settings", "SoftwareUpdate"): "1",
        ("Settings", "ReApply"): "0",
        ("Settings", "ApplyOnStart"): "0",
        ("Settings", "Debug"): "0",
        ("Settings", "DefaultTab"): "home",
        ("Automations", "OnAC"): "",
        ("Automations", "OnBattery"): "",
        ("Automations", "OnResume"): "",
    }
    for (section, key), value in defaults.items():
        if not cfg.get(section, key):
            cfg.set_config(section, key, value)


def ensure_custom_presets_file() -> None:
    cfg.CUSTOM_PRESETS_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not cfg.CUSTOM_PRESETS_PATH.exists():
        cfg.CUSTOM_PRESETS_PATH.write_text("[]")


def init_config() -> None:
    cfg.ensure_sections("User", "Settings", "Info", "Automations")
    _apply_defaults()
    ensure_custom_presets_file()
    cfg.save()


def needs_setup() -> bool:
    if not os.path.isfile(cfg.CONFIG_PATH) or os.stat(cfg.CONFIG_PATH).st_size == 0:
        return True
    cfg.load()
    if not cfg.instance().has_section("Info"):
        return True
    return not cfg.get("Info", "Type")


_CFG_DEFAULTS: dict[str, dict[str, str]] = {
    "User": {"mode": ""},
    "Settings": {"time": "3", "reapply": "0", "applyonstart": "0",
                 "autostartadaptive": "0", "softwareupdate": "1", "debug": "0",
                 "defaulttab": "home"},
    "Automations": {"onac": "", "onbattery": "", "onresume": ""},
    "Adaptive": {"preset": "", "interval": "2"},
}


def check_integrity() -> None:
    cfg.load()

    repaired = False
    for s, keys in cfg.REQUIRED.items():
        if s == "Info":
            continue
        if not cfg.instance().has_section(s):
            cfg.instance().add_section(s)
            repaired = True
        for k in keys:
            if k not in cfg.instance()[s]:
                cfg.instance().set(s, k, _CFG_DEFAULTS.get(s, {}).get(k, ""))
                repaired = True
    if repaired:
        cfg.save()


def reset_all() -> None:
    if os.path.isfile(cfg.CONFIG_PATH):
        os.remove(cfg.CONFIG_PATH)
    if cfg.CUSTOM_PRESETS_PATH.exists():
        cfg.CUSTOM_PRESETS_PATH.unlink(missing_ok=True)
    if os.path.isfile(cfg.ADAPTIVE_PRESETS_PATH):
        os.remove(cfg.ADAPTIVE_PRESETS_PATH)
    cfg.instance().clear()
