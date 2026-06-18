from __future__ import annotations

from Assets.core import config as cfg
from Assets.core.ipc import get_client


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
