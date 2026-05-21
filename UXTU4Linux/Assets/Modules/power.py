"""
power.py
"""

from __future__ import annotations
import importlib
from dataclasses import dataclass
from . import config as cfg
from .hardware import RYZEN_FAMILY
from .ui import menu, clear, ask, pause, MenuItem


def _strip_cpu_name(raw: str) -> str:
    for word in ("AMD", "with", "Mobile", "Ryzen", "Radeon", "Graphics", "Vega", "Gfx"):
        raw = raw.replace(word, "")
    return raw


def _family_idx(name: str) -> int:
    try:
        return RYZEN_FAMILY.index(name)
    except ValueError:
        return -1


def _preset_module_name(cpu_type: str, family: str, cpu_model: str, raw_cpu: str) -> str:
    is_ryzen9 = "Ryzen 9" in raw_cpu

    if cpu_type == "Amd_Apu":
        if _family_idx(family) < _family_idx("Matisse"):
            if any(s in cpu_model for s in ("U", "e", "Ce")):
                return "AMDAPUPreMatisse_U_e_Ce"
            if "H" in cpu_model:   return "AMDAPUPreMatisse_H"
            if "GE" in cpu_model:  return "AMDAPUPreMatisse_GE"
            if "G" in cpu_model:   return "AMDAPUPreMatisse_G"
            return "AMDCPU"
        else:
            if family in ("DragonRange", "FireRange"): return "AMDAPUDragonFireRange"
            if family == "StrixHalo":                  return "AMDAPUStrixHalo"
            if family == "Mendocino" and "U" in cpu_model: return "AMDAPUPreMatisse_U_e_Ce"
            if "U" in cpu_model or ("AI" in cpu_model and "HX" not in cpu_model):
                return "AMDAPUPostMatisse_U"
            if "HX" in cpu_model:  return "AMDAPUPostMatisse_HX"
            if "HS" in cpu_model:  return "AMDAPUPostMatisse_HS"
            if "H" in cpu_model:   return "AMDAPUPostMatisse_H"
            if "GE" in cpu_model:  return "AMDAPUPostMatisse_GE"
            if "G" in cpu_model:   return "AMDAPUPostMatisse_G"
            return "AMDCPU"

    if cpu_type == "Amd_Desktop_Cpu":
        if _family_idx(family) < _family_idx("Raphael"):
            if "E"   in cpu_model: return "AMDCPUPreRaphael_E"
            if "X3D" in cpu_model: return "AMDCPUPreRaphael_X3D"
            if "X"   in cpu_model and is_ryzen9: return "AMDCPUPreRaphael_X9"
            if "X"   in cpu_model: return "AMDCPUPreRaphael_X"
            return "AMDCPUPreRaphael"
        else:
            if "E"   in cpu_model: return "AMDCPU_E"
            if "X3D" in cpu_model: return "AMDCPU_X3D"
            if "X"   in cpu_model and is_ryzen9: return "AMDCPU_X9"
            return "AMDCPU"

    return "AMDCPU"


def get_presets() -> dict:
    raw_cpu   = cfg.get("Info", "CPU")
    family    = cfg.get("Info", "Family")
    cpu_type  = cfg.get("Info", "Type")
    cpu_model = _strip_cpu_name(raw_cpu)
    mod_name  = _preset_module_name(cpu_type, family, cpu_model, raw_cpu)
    full_mod  = f"Assets.Presets.{mod_name}"
    module    = importlib.import_module(full_mod)
    cfg.set_loaded_preset(full_mod)
    return module.PRESETS


def apply_smu(args: str, user_mode: str, *, save_to_config: bool = True) -> None:
    from .ipc import get_client

    if cfg.get("Info", "Type") == "Intel":
        clear()
        print("  Intel chipsets are not supported.")
        pause()
        return

    if save_to_config and user_mode != "Custom":
        cfg.set("User", "Mode", user_mode)
        cfg.save()
    elif save_to_config and user_mode == "Custom":
        cfg.set("User", "Mode", "Custom")
        cfg.set("User", "CustomArgs", args)
        cfg.save()

    client = get_client()
    if not client.ping():
        clear()
        print("  Daemon is not running.")
        print("  sudo systemctl enable --now uxtu4linux.service")
        pause()
        return

    interval = cfg.parse_interval(cfg.get("Settings", "Time", "3"), default=3)
    dynamic  = cfg.get("Settings", "DynamicMode", "0") == "1"
    reapply  = cfg.get("Settings", "ReApply", "0") == "1" or dynamic

    if reapply:
        client.apply_loop(args=args, mode=user_mode, interval=interval, dynamic=dynamic)
    else:
        client.apply(args=args, mode=user_mode)


def update_reapply_interval(val: str) -> bool:
    if not val.isdigit():
        return False
    clamped = str(cfg.parse_interval(val, default=3))
    cfg.set("Settings", "Time", clamped)
    cfg.save()
    from .ipc import get_client
    client = get_client()
    if client.ping():
        client.apply_saved()
    return True


@dataclass
class PowerState:
    mode:     str
    dynamic:  bool
    loop:     bool
    interval: int


def load_power_state() -> PowerState:
    dynamic  = cfg.get("Settings", "DynamicMode", "0") == "1"
    interval = cfg.parse_interval(cfg.get("Settings", "Time", "3"), default=3)
    try:
        from .ipc import get_client
        s    = get_client().status()
        mode = "Dynamic" if dynamic else (s.get("mode") or cfg.get("User", "Mode"))
        loop = s.get("running_loop", False)
    except Exception:
        mode = "Dynamic" if dynamic else cfg.get("User", "Mode")
        loop = cfg.get("Settings", "ReApply", "0") == "1"
    return PowerState(mode=mode, dynamic=dynamic, loop=loop, interval=interval)


def _refresh_state_from_daemon(state: PowerState, client) -> PowerState:
    try:
        s       = client.status()
        dynamic = s.get("dynamic", state.dynamic)
        return PowerState(
            mode     = "Dynamic" if dynamic else (s.get("mode") or state.mode),
            dynamic  = dynamic,
            loop     = s.get("running_loop", state.loop),
            interval = state.interval,
        )
    except Exception:
        return state


def build_menu_items(state: PowerState) -> list[MenuItem]:
    items: list[MenuItem] = [
        MenuItem("Select preset",    state.mode,                    key="select_preset"),
        MenuItem("Dynamic mode",     "ON" if state.dynamic else "OFF", kind="toggle", key="toggle_dynamic"),
        MenuItem("Custom arguments",                                key="custom_args"),
        MenuItem("─", kind="separator"),
    ]
    if state.loop:
        kind = "disabled" if state.dynamic else "action"
        hint = "[dynamic]" if state.dynamic else ""
        items.append(MenuItem("Stop reapply",    hint, kind,       key="stop_reapply"))
        items.append(MenuItem("Reapply interval", f"{state.interval}s", key="reapply_interval"))
    else:
        items.append(MenuItem("Start reapply",                     key="start_reapply"))
    items += [
        MenuItem("Daemon status",                                   key="daemon_status"),
        MenuItem("Back",                                            key="back"),
    ]
    return items


def set_current_preset(name: str, args: str) -> None:
    cfg.set("User", "Mode", name)
    cfg.set("Settings", "DynamicMode", "0")
    cfg.save()
    apply_smu(args, name, save_to_config=False)


def _toggle_dynamic_state(state: PowerState, client, presets: dict) -> PowerState:
    new_dynamic = not state.dynamic
    cfg.set("Settings", "DynamicMode", "1" if new_dynamic else "0")
    cfg.set("Settings", "ReApply",     "1" if new_dynamic else cfg.get("Settings", "ReApply", "0"))
    cfg.save()

    if not client.ping():
        cfg.set("Settings", "DynamicMode", "1" if state.dynamic else "0")
        cfg.set("Settings", "ReApply",     "1" if state.loop    else "0")
        cfg.save()
        clear()
        print("  Daemon is not running — cannot change dynamic mode.")
        print("  sudo systemctl enable --now uxtu4linux.service")
        pause()
        return state

    if new_dynamic:
        client.apply_saved()
        return PowerState(mode="Dynamic", dynamic=True, loop=True, interval=state.interval)
    else:
        client.apply_saved()
        return PowerState(
            mode     = state.mode,
            dynamic  = False,
            loop     = state.loop,
            interval = state.interval,
        )


def _daemon_status_screen(client) -> None:
    clear()
    if not client.ping():
        print("  Daemon is not running.")
        print("  sudo systemctl enable --now uxtu4linux.service")
    else:
        s = client.status()
        print(f"  Auto reapply : {'ON' if s.get('running_loop') else 'OFF'}")
        print(f"  Preset       : {'Dynamic' if s.get('dynamic') else s.get('mode', 'N/A')}")
        print(f"  Interval     : {s.get('interval', '?')}s")
        print(f"  Power        : {'AC' if s.get('on_ac') else 'Battery'}")
        last = s.get("last_output", "")
        if last:
            print(f"\n  {'─'*30}\n")
            for line in last[:500].splitlines():
                print(f"  {line}")
            print()
    pause()


def _stop_loop_screen(state: PowerState, client) -> PowerState:
    if client.ping():
        client.stop_loop()
    cfg.set("Settings", "ReApply", "0")
    cfg.save()
    return PowerState(
        mode     = state.mode,
        dynamic  = state.dynamic,
        loop     = False,
        interval = state.interval,
    )


def _start_loop_screen(state: PowerState, client) -> PowerState:
    cfg.set("Settings", "ReApply", "1")
    cfg.save()
    if client.ping():
        client.apply_saved()
    return PowerState(
        mode     = state.mode,
        dynamic  = state.dynamic,
        loop     = True,
        interval = state.interval,
    )


def _reapply_interval_menu(state: PowerState, client) -> PowerState:
    clear()
    current = cfg.get("Settings", "Time", str(state.interval))
    val = ask("Reapply interval in seconds", default=current)
    if not update_reapply_interval(val):
        print("\n  Must be a whole number.")
        pause()
        return state
    saved = cfg.parse_interval(cfg.get("Settings", "Time", val), default=3)
    return PowerState(
        mode     = state.mode,
        dynamic  = state.dynamic,
        loop     = state.loop,
        interval = saved,
    )


def _select_preset_menu(presets: dict, names: list, current: str) -> None:
    items = [MenuItem(n, "← current" if n == current else "") for n in names]
    items.append(MenuItem("Back"))
    choice = menu("Select Preset", items)
    if choice == -1 or items[choice].key == "back":
        return
    set_current_preset(names[choice], presets[names[choice]])


def _custom_args_menu(state: PowerState, client) -> PowerState:
    clear()
    args = ask("ryzenadj arguments")
    if args:
        cfg.set("Settings", "DynamicMode", "0")
        cfg.save()
        apply_smu(args, "Custom", save_to_config=True)
    return PowerState(
        mode     = "Custom" if args else state.mode,
        dynamic  = False    if args else state.dynamic,
        loop     = state.loop,
        interval = state.interval,
    )


def preset_menu() -> None:
    from .ipc import get_client

    presets  = get_presets()
    names    = list(presets.keys())
    last_idx = 0
    client   = get_client()
    state    = load_power_state()

    def _do_select_preset(s: PowerState) -> PowerState:
        _select_preset_menu(presets, names, s.mode)
        return s

    def _do_daemon_status(s: PowerState) -> PowerState:
        _daemon_status_screen(client)
        return s

    handlers = {
        "select_preset":    _do_select_preset,
        "toggle_dynamic":   lambda s: _toggle_dynamic_state(s, client, presets),
        "custom_args":      lambda s: _custom_args_menu(s, client),
        "reapply_interval": lambda s: _reapply_interval_menu(s, client),
        "stop_reapply":     lambda s: _stop_loop_screen(s, client),
        "start_reapply":    lambda s: _start_loop_screen(s, client),
        "daemon_status":    _do_daemon_status,
    }

    while True:
        items  = build_menu_items(state)
        choice = menu(
            "Power Management", items,
            selected=min(last_idx, len(items) - 1),
        )
        if choice == -1:
            return

        last_idx = choice
        item     = items[choice]

        if item.key == "back":
            return

        handler = handlers.get(item.key)
        if handler is None:
            continue

        if item.is_disabled:
            continue

        state = handler(state)
        state = _refresh_state_from_daemon(state, client)