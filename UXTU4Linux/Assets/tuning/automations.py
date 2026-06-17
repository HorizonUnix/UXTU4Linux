from __future__ import annotations
from Assets.core import config as cfg


def automation_enabled() -> bool:
    return cfg.get("Automations", "Enabled", "0") == "1"


def get_ac_preset() -> str:
    return cfg.get("Automations", "OnAC", "")


def get_battery_preset() -> str:
    return cfg.get("Automations", "OnBattery", "")


def get_resume_preset() -> str:
    return cfg.get("Automations", "OnResume", "")


def set_ac_preset(name: str) -> None:
    cfg.set_config("Automations", "OnAC", name)
    cfg.save()


def set_battery_preset(name: str) -> None:
    cfg.set_config("Automations", "OnBattery", name)
    cfg.save()


def set_resume_preset(name: str) -> None:
    cfg.set_config("Automations", "OnResume", name)
    cfg.save()


def enable_automations() -> None:
    cfg.set_config("Automations", "Enabled", "1")
    cfg.save()


def disable_automations() -> None:
    cfg.set_config("Automations", "Enabled", "0")
    cfg.save()


def _notify_daemon() -> None:
    try:
        from Assets.core.ipc import get_client
        client = get_client()
        if client.ping():
            client.apply_saved()
    except Exception:
        pass