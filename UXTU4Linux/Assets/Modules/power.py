"""
power.py
"""
from __future__ import annotations

from dataclasses import dataclass

from . import config as cfg
from .ui import menu, clear, ask, pause, MenuItem, _B, _R


def _strip_cpu_name(raw: str) -> str:
    for word in ("AMD", "with", "Mobile", "Ryzen", "Radeon", "Graphics", "Vega", "Gfx"):
        raw = raw.replace(word, "")
    return raw


def get_presets() -> dict:
    from .presets import get_preset, get_preset_label, to_dict

    raw_cpu = cfg.get("Info", "CPU")
    family = cfg.get("Info", "Family")
    cpu_type = cfg.get("Info", "Type")
    variant = cfg.get("Info", "Variant")
    cpu_model = _strip_cpu_name(raw_cpu)

    preset = get_preset(cpu_type, family, cpu_model, raw_cpu, variant)
    cfg.set_loaded_preset(get_preset_label(cpu_type, family, cpu_model, raw_cpu, variant))
    return to_dict(preset)


def get_all_presets() -> dict:
    from .custom import load_custom_presets, preset_to_args
    presets = dict(get_presets())
    for p in load_custom_presets():
        name = p["name"] + "_custom_preset"
        presets[name] = preset_to_args(p)
    return presets


def apply_smu(args: str, user_mode: str, *, save_to_config: bool = True) -> None:
    from .ipc import get_client

    if cfg.get("Info", "Type") == "Intel":
        clear()
        print("  Intel chipsets are not supported.")
        pause()
        return

    if save_to_config and user_mode != "Custom":
        cfg.set_config("User", "Mode", user_mode)
        cfg.save()
    elif save_to_config and user_mode == "Custom":
        cfg.set_config("User", "Mode", "Custom")
        cfg.set_config("User", "CustomArgs", args)
        cfg.save()

    client = get_client()
    if not client.ping():
        clear()
        print("  Daemon is not running.")
        print(f"  {_B}sudo systemctl enable --now uxtu4linux.service{_R}")
        pause()
        return

    interval = cfg.parse_interval(cfg.get("Settings", "Time", "3"), default=3)
    automation = cfg.get("Automations", "Enabled", "0") == "1"
    reapply = cfg.get("Settings", "ReApply", "0") == "1"

    if reapply:
        client.apply_loop(args=args, mode=user_mode, interval=interval, automation=automation)
    elif automation:
        client.apply_saved()
    else:
        client.apply(args=args, mode=user_mode)


def update_reapply_interval(val: str) -> bool:
    if not val.isdigit():
        return False
    clamped = str(cfg.parse_interval(val, default=3))
    cfg.set_config("Settings", "Time", clamped)
    cfg.save()
    from .ipc import get_client
    client = get_client()
    if client.ping():
        client.apply_saved()
    return True


@dataclass
class PowerState:
    mode: str
    automation: bool
    loop: bool
    interval: int


def _dn(name: str) -> str:
    return name.removesuffix("_custom_preset")


def load_power_state() -> PowerState:
    automation = cfg.get("Automations", "Enabled", "0") == "1"
    interval = cfg.parse_interval(cfg.get("Settings", "Time", "3"), default=3)
    try:
        from .ipc import get_client
        s = get_client().status()
        mode = "Automations" if automation else _dn(s.get("mode") or cfg.get("User", "Mode"))
        loop = s.get("running_loop", False)
    except Exception:
        mode = "Automations" if automation else _dn(cfg.get("User", "Mode"))
        loop = cfg.get("Settings", "ReApply", "0") == "1"
    return PowerState(mode=mode, automation=automation, loop=loop, interval=interval)


def _refresh_state_from_daemon(state: PowerState, client) -> PowerState:
    cfg.load()
    try:
        s = client.status()
        automation = cfg.get("Automations", "Enabled", "0") == "1"
        return PowerState(
            mode="Automations" if automation else _dn(s.get("mode") or state.mode),
            automation=automation,
            loop=s.get("running_loop", state.loop),
            interval=state.interval,
        )
    except Exception:
        automation = cfg.get("Automations", "Enabled", "0") == "1"
        return PowerState(
            mode="Automations" if automation else state.mode,
            automation=automation,
            loop=state.loop,
            interval=state.interval,
        )


def _automation_hint(state: PowerState) -> str:
    if not state.automation:
        return ""
    ac_name = _dn(cfg.get("Automations", "OnAC", ""))
    bat_name = _dn(cfg.get("Automations", "OnBattery", ""))
    parts = []
    if ac_name:
        parts.append(f"AC:{ac_name}")
    if bat_name:
        parts.append(f"Bat:{bat_name}")
    return " / ".join(parts)


def build_menu_items(state: PowerState) -> list[MenuItem]:
    auto_hint = _automation_hint(state)
    select_hint = f"[OVERRIDE] {auto_hint}" if auto_hint else state.mode

    items: list[MenuItem] = [
        MenuItem("Select preset", select_hint, key="select_preset"),
        MenuItem("Custom arguments", key="custom_args"),
        MenuItem("─", kind="separator"),
    ]

    if state.loop:
        items.append(MenuItem("Stop reapply", "", key="stop_reapply"))
        items.append(MenuItem("Reapply interval", f"{state.interval}s", key="reapply_interval"))
    else:
        items.append(MenuItem("Start reapply", key="start_reapply"))

    items += [
        MenuItem("Daemon status", key="daemon_status"),
        MenuItem("Back", key="back"),
    ]
    return items


def set_current_preset(name: str, args: str) -> None:
    cfg.set_config("User", "Mode", name)
    cfg.save()
    apply_smu(args, name, save_to_config=False)


_PRESET_HINTS: dict[str, str] = {
    "Eco": "Prioritizes battery life — conservative power limits, minimal heat",
    "Balance": "Balanced performance and efficiency for everyday use",
    "Performance": "Higher power limits for sustained workloads and faster response",
    "Extreme": "Maximum power limits — highest performance, more heat and power draw",
    "AC": "Hidden options to improve performance (when AC plugged in)",
    "DC": "Hidden options to improve power efficiency (when AC unplugged)",
}


def _select_preset_menu(presets: dict, builtin_names: list[str], custom_names: list[str], current: str) -> None:
    items: list[MenuItem] = [
        MenuItem(
            n,
            hint="← current" if n == current else "",
            desc=_PRESET_HINTS.get(n, ""),
            key=n,
        )
        for n in builtin_names
    ]
    if custom_names:
        items.append(MenuItem("─", kind="separator"))
        items += [
            MenuItem(
                n.removesuffix("_custom_preset"),
                hint="← current" if n == current else "",
                key=n,
            )
            for n in custom_names
        ]
    items += [MenuItem("─", kind="separator"), MenuItem("Back", key="back")]

    choice = menu("Select Preset", items)
    if choice == -1:
        return

    selected_key = items[choice].key
    if selected_key and selected_key != "back" and selected_key in presets:
        set_current_preset(selected_key, presets[selected_key])


def _daemon_status_screen(client) -> None:
    clear()
    if not client.ping():
        print("  Daemon is not running.")
        print(f"  {_B}sudo systemctl enable --now uxtu4linux.service{_R}")
    else:
        s = client.status()
        auto = s.get("automation", False)
        print(f"  Auto reapply : {'ON' if s.get('running_loop') else 'OFF'}")
        if auto:
            print(f"  Mode         : Automations (AC/Battery)")
            print(f"  AC preset    : {_dn(cfg.get('Automations', 'OnAC', '(not set)')) or '(not set)'}")
            print(f"  Bat preset   : {_dn(cfg.get('Automations', 'OnBattery', '(not set)')) or '(not set)'}")
        else:
            print(f"  Preset       : {_dn(s.get('mode', 'N/A'))}")
        print(f"  Interval     : {s.get('interval', '?')}s")
        print(f"  Power        : {'AC' if s.get('on_ac') else 'Battery'}")
        last = s.get("last_output", "")
        if last:
            print(f"\n  {'─'*30}\n")
            for line in last.splitlines():
                print(f"  {line}")
            print()
    pause()


def _stop_loop_screen(state: PowerState, client) -> PowerState:
    if client.ping():
        client.stop_loop()
    cfg.set_config("Settings", "ReApply", "0")
    cfg.save()
    return PowerState(mode=state.mode, automation=state.automation, loop=False, interval=state.interval)


def _start_loop_screen(state: PowerState, client) -> PowerState:
    cfg.set_config("Settings", "ReApply", "1")
    cfg.save()
    if client.ping():
        client.apply_saved()
    return PowerState(mode=state.mode, automation=state.automation, loop=True, interval=state.interval)


def _reapply_interval_menu(state: PowerState, client) -> PowerState:
    clear()
    current = cfg.get("Settings", "Time", str(state.interval))
    val = ask("Reapply interval in seconds", default=current)
    if not update_reapply_interval(val):
        print("\n  Must be a whole number.")
        pause()
        return state
    saved = cfg.parse_interval(cfg.get("Settings", "Time", val), default=3)
    return PowerState(mode=state.mode, automation=state.automation, loop=state.loop, interval=saved)


def _custom_args_menu(state: PowerState, client) -> PowerState:
    clear()
    args = ask("ryzenadj arguments")
    if args:
        apply_smu(args, "Custom", save_to_config=True)
    return PowerState(
        mode="Custom" if args else state.mode,
        automation=False if args else state.automation,
        loop=state.loop,
        interval=state.interval,
    )


def preset_menu() -> None:
    from .ipc import get_client
    from .custom import get_custom_preset_names

    client = get_client()
    state = load_power_state()
    last_idx = 0

    def _do_select_preset(s: PowerState) -> PowerState:
        builtin_presets = get_presets()
        custom_names = get_custom_preset_names()
        all_presets = get_all_presets()
        _select_preset_menu(all_presets, list(builtin_presets.keys()), custom_names, s.mode)
        return s

    def _do_daemon_status(s: PowerState) -> PowerState:
        _daemon_status_screen(client)
        return s

    handlers = {
        "select_preset": _do_select_preset,
        "custom_args": lambda s: _custom_args_menu(s, client),
        "reapply_interval": lambda s: _reapply_interval_menu(s, client),
        "stop_reapply": lambda s: _stop_loop_screen(s, client),
        "start_reapply": lambda s: _start_loop_screen(s, client),
        "daemon_status": _do_daemon_status,
    }

    while True:
        items = build_menu_items(state)
        choice = menu(
            "Power Management", items,
            selected=min(last_idx, len(items) - 1),
        )
        if choice == -1:
            return

        last_idx = choice
        item = items[choice]

        if item.key == "back":
            return

        handler = handlers.get(item.key)
        if handler is None or item.is_disabled:
            continue

        state = handler(state)
        state = _refresh_state_from_daemon(state, client)