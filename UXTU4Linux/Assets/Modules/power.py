from __future__ import annotations

from dataclasses import dataclass

from . import config as cfg
from .ui import menu, clear, ask, pause, MenuItem, _B, _D, _G, _R, _Y, _SEP_W


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
        parts.append(f"On AC: {ac_name}")
    if bat_name:
        parts.append(f"On Battery: {bat_name}")
    return "\n".join(parts)


def build_menu_items(state: PowerState) -> list[MenuItem]:
    auto_hint = _automation_hint(state)
    select_hint = f"{_R}{_G}● Override{_R}\n{auto_hint}" if auto_hint else state.mode

    items: list[MenuItem] = [
        MenuItem("Select preset", select_hint, key="select_preset"),
        MenuItem("─", kind="separator"),
        MenuItem("Reapply", f"{_R}{_G}● ON{_R}" if state.loop else f"{_R}{_Y}○ OFF{_R}", key="toggle_reapply"),
    ]

    if state.loop:
        items.append(MenuItem("Reapply interval", f"{state.interval}s", key="reapply_interval"))

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
    "Eco": "This preset is designed to prioritize energy efficiency over performance. It sets power limits to conservative levels to reduce power consumption and heat generation, making it ideal for prolonged use in situations where maximizing battery life or minimizing energy usage is critical.",
    "Balance": "This preset aims to find a balance between performance and power consumption, providing a stable and efficient experience. This preset sets the power limits to a level that balances performance and power usage, without sacrificing too much of either.",
    "Performance": "This preset is optimized for maximum performance by increasing the power limits of the APU/CPU, which allows it to run at higher clock speeds for longer periods of time. This can result in improved system responsiveness and faster load times in applications that require high levels of processing power.",
    "Extreme": "This preset aims to push the power limits of the system to their maximum, allowing for the highest possible performance. This preset is designed for users who demand the most from their hardware and are willing to tolerate higher power consumption and potentially increased noise levels.",
}


def _select_preset_menu(presets: dict, builtin_names: list[str], custom_names: list[str], current: str) -> None:
    actual_current = cfg.get("User", "Mode")
    items: list[MenuItem] = [
        MenuItem(
            n,
            hint="← current" if n == actual_current else "",
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
                hint="← current" if n == actual_current else "",
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
    import sys
    from . import termui

    def _build() -> tuple[list[str], float | None]:
        lines: list[str] = [f"  {_B}Daemon Status{_R}", ""]
        if not client.ping():
            lines += [
                f"  Daemon        : {_Y}○ Not running{_R}",
                "",
                "  Start it with:",
                f"  {_B}sudo systemctl enable --now uxtu4linux.service{_R}",
            ]
            return lines, None

        s = client.status()
        auto = s.get("automation", False)
        loop = s.get("running_loop")
        on_ac = s.get("on_ac")
        mode = _dn(s.get("mode", ""))

        lines.append(f"  Daemon        : {_G}● Running{_R}")
        lines.append(f"  Power source  : {'AC' if on_ac else 'Battery'}")
        lines.append(f"  Active preset : {mode if mode != 'none' else _D + 'none applied yet' + _R}")

        if loop:
            lines.append(f"  Auto reapply  : {_G}● ON{_R} {_D}(every {s.get('interval', '?')}s){_R}")
        else:
            lines.append(f"  Auto reapply  : {_Y}○ OFF{_R}")

        if auto:
            _pm_preset = _dn(cfg.get("User", "Mode", "Balance"))
            _fallback = f"{_D}Power Management preset ({_pm_preset}){_R}"
            ac_val = _dn(cfg.get("Automations", "OnAC", ""))
            bat_val = _dn(cfg.get("Automations", "OnBattery", ""))
            lines.append(f"  Automations   : {_G}● ON{_R}")
            lines.append(f"    On AC       : {ac_val or _fallback}")
            lines.append(f"    On Battery  : {bat_val or _fallback}")
        else:
            lines.append(f"  Automations   : {_Y}○ OFF{_R}")

        last = s.get("last_output", "")
        if last:
            if s.get("last_rejected"):
                lines.append(f"  Last apply    : {_Y}[!] some commands were rejected{_R}")
            else:
                lines.append(f"  Last apply    : {_G}✓ OK{_R}")
            lines.append(f"\n  {_D}{'─' * _SEP_W}{_R}\n")
            lines += [f"  {line}" for line in last.splitlines()]

        refresh = float(cfg.parse_interval(s.get("interval", 3))) if loop else None
        return lines, refresh

    if not sys.stdin.isatty():
        lines, _ = _build()
        clear()
        print("\n".join(lines) + "\n")
        pause()
        return

    sys.stdout.write(termui.HIDE_CURSOR)
    sys.stdout.flush()
    try:
        while True:
            lines, refresh = _build()
            content = lines + ["", f"  {_D}Press Esc to go back{_R}"]
            clear()
            sys.stdout.write("\n".join(content) + "\n")
            sys.stdout.flush()
            if termui.get_key(timeout=refresh) == termui.ESC:
                break
    finally:
        sys.stdout.write(termui.SHOW_CURSOR)
        sys.stdout.flush()


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
    print(f"  {_B}Reapply Interval{_R}\n")
    current = cfg.get("Settings", "Time", str(state.interval))
    val = ask("Reapply interval in seconds", default=current)
    if not update_reapply_interval(val):
        print("\n  Must be a whole number.")
        pause()
        return state
    saved = cfg.parse_interval(cfg.get("Settings", "Time", val), default=3)
    return PowerState(mode=state.mode, automation=state.automation, loop=state.loop, interval=saved)


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
        "reapply_interval": lambda s: _reapply_interval_menu(s, client),
        "toggle_reapply": lambda s: _stop_loop_screen(s, client) if s.loop else _start_loop_screen(s, client),
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