"""
settings.py
"""

from __future__ import annotations

from . import config as cfg
from .ui import menu, clear, ask, pause, confirm, MenuItem


def _tog(section: str, key: str, default: str = "0") -> str:
    return "ON" if cfg.get(section, key, default) == "1" else "OFF"


_TOGGLE_MAP = {
    "Apply preset on daemon start": ("Settings", "ApplyOnStart",   "1"),
    "Software update":              ("Settings", "SoftwareUpdate", "1"),
    "Debug":                        ("Settings", "Debug",          "1"),
}


def _do_toggle(idx: int, items: list) -> None:
    lbl = items[idx].label
    if lbl not in _TOGGLE_MAP:
        return
    section, key, default = _TOGGLE_MAP[lbl]
    was_on = cfg.get(section, key, default) == "1"
    cfg.set(section, key, "0" if was_on else "1")
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
        MenuItem("Apply preset on daemon start", _tog("Settings", "ApplyOnStart",   "1"), "toggle"),
        MenuItem("Software update",              _tog("Settings", "SoftwareUpdate", "1"), "toggle"),
        MenuItem("Debug",                        _tog("Settings", "Debug",          "1"), "toggle"),
        MenuItem("─",                            kind="separator"),
        MenuItem("Reset all"),
        MenuItem("Back"),
    ]
    return items


def settings_menu() -> None:
    from .service import daemon_menu

    last_idx = 0
    while True:
        items  = _settings_items()
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


def preset_cfg() -> None:
    from .power import get_presets
    presets = get_presets()
    names   = list(presets.keys())

    items: list[MenuItem] = (
        [MenuItem("Dynamic mode (recommended)", "auto AC/battery")]
        + [MenuItem(n) for n in names]
        + [MenuItem("Custom", "manual ryzenadj args"), MenuItem("Back")]
    )

    while True:
        choice = menu("Choose a preset", items, subtitle="You can change this later in Power Management")
        if choice == -1 or items[choice].label == "Back":
            return

        lbl = items[choice].label

        if lbl == "Dynamic mode (recommended)":
            cfg.set("User",     "Mode",        "Balance")
            cfg.set("Settings", "DynamicMode", "1")
            cfg.set("Settings", "ReApply",     "1")
            cfg.save()
            return
        elif lbl == "Custom":
            args = ask("ryzenadj arguments")
            if args:
                cfg.set("User",     "Mode",        "Custom")
                cfg.set("User",     "CustomArgs",  args)
                cfg.set("Settings", "DynamicMode", "0")
                cfg.save()
            return
        elif lbl in names:
            cfg.set("User",     "Mode",        lbl)
            cfg.set("Settings", "DynamicMode", "0")
            cfg.save()
            return


def sleep_cfg() -> None:
    from .power import update_reapply_interval
    clear()
    current = cfg.get("Settings", "Time", "3")
    val = ask("Reapply interval in seconds", default=current)
    if not update_reapply_interval(val):
        print("\n  Must be a whole number.")
        pause()


def _reset_all() -> None:
    clear()
    if confirm("Reset all settings? This cannot be undone"):
        from .setup import reset_all
        reset_all()