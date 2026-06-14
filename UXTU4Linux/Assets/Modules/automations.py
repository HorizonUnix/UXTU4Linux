from __future__ import annotations
from . import config as cfg
from .ui import clear, pause, menu, MenuItem, _B, _D, _G, _R, _SEP_W, _Y


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


def _preset_picker(title: str, current: str) -> str | None:
    from .power import get_presets
    from .custom import get_custom_preset_names

    builtin_names = list(get_presets().keys())
    custom_names = get_custom_preset_names()

    items: list[MenuItem] = [
        MenuItem("(None) — use Power Management preset", key="__none__"),
        MenuItem("─", kind="separator"),
    ]
    items += [MenuItem(n, hint="← current" if n == current else "", key=n) for n in builtin_names]
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
    return item.key


def _notify_daemon() -> None:
    try:
        from .ipc import get_client
        client = get_client()
        if client.ping():
            client.apply_saved()
    except Exception:
        pass


def _slot_display(name: str) -> str:
    return name.removesuffix("_custom_preset") if name else "(None)"


def _show_info() -> None:
    clear()
    print(f"  {_B}How Automations Work{_R}\n")
    print(f"  {_B}Override{_R}")
    print(f"  {_D}{'─' * _SEP_W}{_R}")
    print("  When Automations is ON the daemon watches AC/battery state and")
    print("  applies the configured preset whenever the power source changes.\n")
    print("  If a slot is set to (None), the Power Management preset is used")
    print("  for that power state instead.\n")
    print("  Works even when Reapply is OFF — the preset is applied once on")
    print("  each power state transition.\n")
    print("  When Reapply is ON, the active preset is also re-applied every")
    print("  N seconds as usual.\n")
    print(f"  {_B}On Resume{_R}")
    print(f"  {_D}{'─' * _SEP_W}{_R}")
    print("  When set, the chosen preset is applied once every time the")
    print("  system wakes from sleep or suspend.")
    print("  This works regardless of whether Override is ON or OFF.\n")
    pause()


def automations_menu() -> None:
    while True:
        cfg.load()
        enabled = automation_enabled()
        ac_name = get_ac_preset()
        bat_name = get_battery_preset()
        resume_name = get_resume_preset()

        items: list[MenuItem] = [
            MenuItem("Override", f"{_R}{_G}● ON{_R}" if enabled else f"{_R}{_Y}○ OFF{_R}", kind="toggle", key="toggle"),
            MenuItem("─", kind="separator"),
            MenuItem("On Battery", _slot_display(bat_name), key="set_bat"),
            MenuItem("On AC Power", _slot_display(ac_name),  key="set_ac"),
            MenuItem("On Resume",   _slot_display(resume_name), key="set_resume"),
            MenuItem("─", kind="separator"),
            MenuItem("How automations work", key="info"),
            MenuItem("Back", key="back"),
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
                    print("  Configure at least one AC/Battery preset slot before enabling Override.")
                    pause()

        elif key == "set_ac":
            clear()
            chosen = _preset_picker("Select AC Preset", ac_name)
            if chosen is not None:
                set_ac_preset(chosen)
                if not chosen and not get_battery_preset():
                    disable_automations()
                if automation_enabled():
                    _notify_daemon()

        elif key == "set_bat":
            clear()
            chosen = _preset_picker("Select Battery Preset", bat_name)
            if chosen is not None:
                set_battery_preset(chosen)
                if not chosen and not get_ac_preset():
                    disable_automations()
                if automation_enabled():
                    _notify_daemon()

        elif key == "set_resume":
            clear()
            chosen = _preset_picker("Select Resume Preset", resume_name)
            if chosen is not None:
                set_resume_preset(chosen)
                try:
                    from .ipc import get_client
                    client = get_client()
                    if client.ping():
                        client.reload_config()
                except Exception:
                    pass

        elif key == "info":
            _show_info()