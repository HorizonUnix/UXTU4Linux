from Assets.core import config as cfg

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
