"""
automations.py
"""
from __future__ import annotations

import logging

from . import config as cfg
from .ui import clear, pause, menu, MenuItem


def automation_enabled() -> bool:
    return cfg.get("Automations", "Enabled", "0") == "1"


def get_ac_preset() -> str:
    return cfg.get("Automations", "OnAC", "")


def get_battery_preset() -> str:
    return cfg.get("Automations", "OnBattery", "")


def set_ac_preset(name: str) -> None:
    cfg.set_config("Automations", "OnAC", name)
    cfg.save()
    logging.info("Automations: AC preset set to %r", name)


def set_battery_preset(name: str) -> None:
    cfg.set_config("Automations", "OnBattery", name)
    cfg.save()
    logging.info("Automations: Battery preset set to %r", name)


def enable_automations() -> None:
    cfg.set_config("Automations", "Enabled", "1")
    cfg.save()
    logging.info("Automations: enabled")


def disable_automations() -> None:
    cfg.set_config("Automations", "Enabled", "0")
    cfg.save()
    logging.info("Automations: disabled")



def _resolve_args(preset_name: str) -> str | None:
    from .power import get_presets
    from .custom import load_custom_presets, preset_to_args

    presets = get_presets()
    if preset_name in presets:
        return presets[preset_name]

    base = preset_name.removesuffix("_custom_preset")
    for p in load_custom_presets():
        if p["name"] == base:
            return preset_to_args(p)
    return None


def _preset_picker(title: str, current: str) -> str | None:
    from .power import get_presets
    from .custom import get_custom_preset_names

    builtin_names = list(get_presets().keys())
    custom_names  = get_custom_preset_names()

    items: list[MenuItem] = [
        MenuItem("(None) — use Power Management preset", key="__none__"),
        MenuItem("─", kind="separator"),
    ]
    items += [MenuItem(n, hint="← current" if n == current else "") for n in builtin_names]
    if custom_names:
        items.append(MenuItem("─", kind="separator"))
        items += [
            MenuItem(n.removesuffix("_custom_preset"), hint="← current" if n == current else "", key=n)
            for n in custom_names
        ]
    items += [MenuItem("─", kind="separator"), MenuItem("Back", key="back")]

    choice = menu(title, items)
    if choice == -1:
        return None
    item = items[choice]
    if item.key == "back":
        return None
    if item.key == "__none__":
        return ""

    all_names      = builtin_names + custom_names
    selectable_idx = [
        i for i, it in enumerate(items)
        if it.is_selectable and it.key not in ("__none__", "back")
    ]
    if choice in selectable_idx:
        idx = selectable_idx.index(choice)
        if idx < len(all_names):
            return all_names[idx]
    return None


def _notify_daemon() -> None:
    try:
        from .ipc import get_client
        client = get_client()
        if client.ping():
            client.apply_saved()
    except Exception as exc:
        logging.debug("Could not notify daemon after automations change: %s", exc)


def _slot_display(name: str) -> str:
    return name.removesuffix("_custom_preset") if name else "(None)"


def _show_info() -> None:
    clear()
    print(f"  {'─' * 10} How Automations Override Works {'─' * 10}\n")
    print("  When Automations is ON the daemon watches AC/battery state and")
    print("  applies the configured preset whenever the power source changes.\n")
    print("  If a slot is set to (None), the Power Management preset is used")
    print("  for that power state instead.\n")
    print("  Works even when Reapply is OFF — the preset is applied once on")
    print("  each power state transition.\n")
    print("  When Reapply is ON, the active preset is also re-applied every")
    print("  N seconds as usual.\n")
    pause()


def automations_menu() -> None:
    while True:
        cfg.load()
        enabled  = automation_enabled()
        ac_name  = get_ac_preset()
        bat_name = get_battery_preset()

        items: list[MenuItem] = [
            MenuItem("Override",     "ON" if enabled else "OFF", kind="toggle", key="toggle"),
            MenuItem("─",            kind="separator"),
            MenuItem("On Battery",   _slot_display(bat_name), key="set_bat"),
            MenuItem("On AC Power",  _slot_display(ac_name),  key="set_ac"),
            MenuItem("─",            kind="separator"),
            MenuItem("ℹ How overrides work", key="info"),
            MenuItem("Back",                  key="back"),
        ]

        choice = menu("Automations", items)
        if choice == -1 or items[choice].key == "back":
            return

        key = items[choice].key

        if key == "toggle":
            if enabled:
                disable_automations()
                _notify_daemon()
            else:
                if ac_name or bat_name:
                    enable_automations()
                    _notify_daemon()
                else:
                    clear()
                    print("  Configure at least one preset slot before enabling Override.")
                    pause()

        elif key == "set_ac":
            clear()
            chosen = _preset_picker("Select AC Preset", ac_name)
            if chosen is not None:
                set_ac_preset(chosen)
                if not chosen and not get_battery_preset():
                    disable_automations()
                _notify_daemon()

        elif key == "set_bat":
            clear()
            chosen = _preset_picker("Select Battery Preset", bat_name)
            if chosen is not None:
                set_battery_preset(chosen)
                if not chosen and not get_ac_preset():
                    disable_automations()
                _notify_daemon()

        elif key == "info":
            _show_info()