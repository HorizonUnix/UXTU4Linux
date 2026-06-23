from __future__ import annotations

import os

from Assets.core import config as cfg
from Assets.core.ipc import get_client


_AC_TYPES = frozenset({"Mains", "USB", "USB_C", "USB_PD", "USB_PD_DRP", "USB_C_DRP"})


def on_ac() -> bool:
    ac_online = False
    found_ac = False
    battery_discharging = False
    try:
        for entry in os.listdir("/sys/class/power_supply"):
            base = f"/sys/class/power_supply/{entry}"
            try:
                with open(f"{base}/type") as f:
                    ptype = f.read().strip()
            except OSError:
                continue
            if ptype in _AC_TYPES:
                found_ac = True
                try:
                    with open(f"{base}/online") as f:
                        if f.read().strip() == "1":
                            ac_online = True
                except OSError:
                    pass
            elif ptype == "Battery":
                try:
                    with open(f"{base}/status") as f:
                        if f.read().strip().lower() == "discharging":
                            battery_discharging = True
                except OSError:
                    pass
    except Exception:
        pass
    if found_ac:
        return ac_online
    return not battery_discharging


WORDMARK = "◆ UXTU4Linux"

BANNER = r"""
+----------------------------------------------------------+
|  _   ___  _______ _   _ _  _   _     _                   |
| | | | \ \/ /_   _| | | | || | | |   (_)_ __  _   ___  __ |
| | | | |\  /  | | | | | | || |_| |   | | '_ \| | | \ \/ / |
| | |_| |/  \  | | | |_| |__   _| |___| | | | | |_| |>  <  |
|  \___//_/\_\ |_|  \___/   |_| |_____|_|_| |_|\__,_/_/\_\ |
+----------------------------------------------------------+
""".strip("\n")


def status_line() -> str:
    cpu = cfg.get("Info", "CPU")
    family = cfg.get("Info", "Family")
    if cpu and family:
        return f"{cpu} [dim]{family}[/]"
    return cpu


def fetch_status() -> dict:
    return get_client().status()


def do_apply(args: str, mode: str) -> dict:
    from Assets.tuning.power import apply_preset
    return apply_preset(args, mode)


async def ensure_sudo(app) -> bool:
    from Assets.daemon.service import sudo_available
    if sudo_available():
        return True
    from Assets.tui.modals import SudoModal
    return bool(await app.push_screen_wait(SudoModal()))

