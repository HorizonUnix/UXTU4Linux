"""
settings.py
"""
from __future__ import annotations

from . import config as cfg
from .ui import menu, clear, confirm, MenuItem


def _tog(section: str, key: str, default: str = "0") -> str:
    return "ON" if cfg.get(section, key, default) == "1" else "OFF"


_TOGGLE_MAP = {
    "Apply preset on daemon start": ("Settings", "ApplyOnStart", "1"),
    "Software update": ("Settings", "SoftwareUpdate", "1"),
    "Debug": ("Settings", "Debug", "1"),
}


def ensure_config_files() -> None:
    cfg.CUSTOM_PRESETS_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not cfg.CUSTOM_PRESETS_PATH.exists():
        cfg.CUSTOM_PRESETS_PATH.write_text("[]")


def _do_toggle(idx: int, items: list) -> None:
    lbl = items[idx].label
    if lbl not in _TOGGLE_MAP:
        return
    section, key, default = _TOGGLE_MAP[lbl]
    was_on = cfg.get(section, key, default) == "1"
    cfg.set_config(section, key, "0" if was_on else "1")
    cfg.save()
    items[idx] = MenuItem(lbl, "OFF" if was_on else "ON", "toggle")

    if lbl == "Debug":
        try:
            from .ipc import get_client
            get_client().reload_config()
        except Exception:
            pass


def _settings_items() -> list[MenuItem]:
    from .service import service_running, _has_systemctl
    items: list[MenuItem] = []
    if _has_systemctl():
        running = service_running()
        items.append(MenuItem("Daemon service", "Running" if running else "Stopped"))
        items.append(MenuItem("─", kind="separator"))
    items += [
        MenuItem("Apply preset on daemon start", _tog("Settings", "ApplyOnStart", "1"), "toggle"),
        MenuItem("Software update", _tog("Settings", "SoftwareUpdate", "1"), "toggle"),
        MenuItem("Debug", _tog("Settings", "Debug", "1"), "toggle"),
        MenuItem("─", kind="separator"),
        MenuItem("Reset all"),
        MenuItem("Back"),
    ]
    return items


def settings_menu() -> None:
    from .service import daemon_menu

    last_idx = 0
    while True:
        items = _settings_items()
        choice = menu("Settings", items, selected=last_idx, on_toggle=_do_toggle)
        if choice == -1:
            return

        last_idx = choice
        lbl = items[choice].label

        if lbl == "Back":
            return
        elif lbl == "Daemon service":
            daemon_menu()
        elif lbl in _TOGGLE_MAP:
            _do_toggle(choice, items)
        elif lbl == "Reset all":
            _reset_all()


def _reset_all() -> None:
    clear()
    if confirm("Reset all settings? This cannot be undone"):
        from .setup import reset_all
        reset_all()