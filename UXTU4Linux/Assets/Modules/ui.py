"""
ui.py
"""
from __future__ import annotations
import subprocess, sys
from dataclasses import dataclass
from typing import Literal
from . import config as cfg
from . import termui

BANNER = r"""
+----------------------------------------------------------+
|  _   ___  _______ _   _ _  _   _     _                   |
| | | | \ \/ /_   _| | | | || | | |   (_)_ __  _   ___  __ |
| | | | |\  /  | | | | | | || |_| |   | | '_ \| | | \ \/ / |
| | |_| |/  \  | | | |_| |__   _| |___| | | | | |_| |>  <  |
|  \___//_/\_\ |_|  \___/   |_| |_____|_|_| |_|\__,_/_/\_\ |
+----------------------------------------------------------+
"""

_R = "\033[0m"
_B = "\033[1m"
_D = "\033[2m"
_Y = "\033[33m"
_G = "\033[32m"

Kind = Literal["action", "toggle", "separator", "disabled"]

@dataclass
class MenuItem:
    label: str
    hint: str = ""
    kind: Kind = "action"
    key: str | None = None
    desc: str = ""

    def __post_init__(self) -> None:
        if self.key is None:
            self.key = self.label.lower().replace(" ", "_")

    @property
    def is_separator(self) -> bool:
        return self.kind == "separator"

    @property
    def is_toggle(self) -> bool:
        return self.kind == "toggle"

    @property
    def is_disabled(self) -> bool:
        return self.kind == "disabled"

    @property
    def is_selectable(self) -> bool:
        return not (self.is_separator or self.is_disabled)


def clear() -> None:
    subprocess.run("clear", shell=True)
    print(f"{_B}{BANNER}{_R}")
    cpu = cfg.get("Info", "CPU")
    family = cfg.get("Info", "Family")
    loaded = cfg.get_loaded_preset()
    if cpu and family:
        print(f"  {_B}{cpu}{_R} {_D}{family}{_R}")
    if loaded:
        print(f"  {_D}Preset : {loaded}{_R}")
    if cfg.is_debug():
        print(f"  {_D}Build  : {cfg.LOCAL_BUILD}{_R}")
    print(f"  {_D}v{cfg.LOCAL_VERSION} by HorizonUnix{_R}\n")


def pause(msg: str = "Press Enter to continue...") -> None:
    input(f"  {_D}{msg}{_R} ")


def confirm(prompt: str) -> bool:
    return input(f"  {prompt} (y/n): ").strip().lower() == "y"


def ask(prompt: str, default: str = "") -> str:
    hint = f" [{default}]" if default else ""
    val = input(f"  {prompt}{_D}{hint}{_R}: ").strip()
    return val or default


def quit_app() -> None:
    sys.stdout.write(termui.SHOW_CURSOR)
    sys.exit(f"\n  Thanks for using UXTU4Linux\n  Have a nice day!\n")


def _clamp_skip(idx: int, items: list[MenuItem]) -> int:
    n = len(items)
    if n == 0:
        return 0
    idx = max(0, min(idx, n - 1))
    for delta in range(n):
        i = (idx + delta) % n
        if items[i].is_selectable:
            return i
    return idx


def _nav_step(idx: int, d: int, items: list[MenuItem]) -> int:
    n = len(items)
    for _ in range(n):
        idx = (idx + d) % n
        if items[idx].is_selectable:
            return idx
    return idx


def render_menu(title: str, subtitle: str, items: list[MenuItem], idx: int) -> list[str]:
    lines: list[str] = [f"  {_B}{title}{_R}"]
    if subtitle:
        for line in subtitle.split("\n"):
            lines.append(f"  {_D}{line}{_R}")
    lines.append("")
    for i, item in enumerate(items):
        if item.is_separator:
            lines.append(f"  {_D}{'─' * 40}{_R}")
            continue
        h = f"  {_D}{item.hint}{_R}" if item.hint else ""
        if i == idx:
            lines.append(f"  {_B}▶{_R} {_B}{item.label}{_R}{h}")
        else:
            lines.append(f"    {_D}{item.label}{_R}{h}")
    active_desc = items[idx].desc if 0 <= idx < len(items) else ""
    if active_desc:
        lines.append("")
        lines.append(f"  {_D}{active_desc}{_R}")
    lines.append("")
    lines.append(f"  {_D}↑/↓ to navigate, Enter to select, Esc to go back{_R}")
    return lines


def _simple_menu(
    title: str,
    items: list[MenuItem],
    *,
    subtitle: str = "",
    on_toggle = None,
) -> int:
    while True:
        clear()
        print(f"  {_B}{title}{_R}")
        if subtitle:
            for line in subtitle.split("\n"):
                print(f"  {_D}{line}{_R}")
        print()
        numbered: list[int] = []
        for i, item in enumerate(items):
            if item.is_separator:
                print(f"  {_D}{'-' * 40}{_R}")
                continue
            if item.is_disabled:
                continue
            n = len(numbered) + 1
            numbered.append(i)
            hint = f"  {_D}{item.hint}{_R}" if item.hint else ""
            print(f"  {n}. {item.label}{hint}")
        print()
        try:
            raw = input("  Select option (or Enter to go back): ").strip()
        except EOFError:
            return -1
        if not raw:
            return -1
        if not raw.isdigit():
            continue
        n = int(raw)
        if 1 <= n <= len(numbered):
            i = numbered[n - 1]
            if on_toggle and items[i].is_toggle:
                on_toggle(i, items)
                continue
            return i


def menu(
    title: str,
    items: list[MenuItem],
    *,
    subtitle: str = "",
    selected: int = 0,
    on_toggle = None,
) -> int:
    if not termui.is_tty():
        return _simple_menu(title, items, subtitle=subtitle, on_toggle=on_toggle)

    clear()
    sys.stdout.write(termui.HIDE_CURSOR)
    sys.stdout.flush()
    idx = _clamp_skip(selected, items)
    prev = 0
    try:
        while True:
            lines = render_menu(title, subtitle, items, idx)
            prev = termui.draw_lines(lines, prev)
            key = termui.get_key()
            if key == b"\x03":
                sys.stdout.write(termui.SHOW_CURSOR + "\n")
                sys.exit(0)
            elif key == termui.UP:
                idx = _nav_step(idx, -1, items)
            elif key == termui.DOWN:
                idx = _nav_step(idx, +1, items)
            elif key in (termui.ENTER, b"\n"):
                if on_toggle and items[idx].is_toggle:
                    on_toggle(idx, items)
                    clear()
                    sys.stdout.write(termui.HIDE_CURSOR)
                    sys.stdout.flush()
                    prev = 0
                else:
                    sys.stdout.write("\n")
                    return idx
            elif key == termui.ESC:
                sys.stdout.write("\n")
                return -1
    finally:
        sys.stdout.write(termui.SHOW_CURSOR)
        sys.stdout.flush()


def about_menu() -> None:
    from .updater import get_latest_version, show_updater

    while True:
        latest = None
        try:
            latest = get_latest_version()
        except Exception:
            latest = None

        items: list[MenuItem] = []
        if latest:
            items.append(MenuItem("Force update", hint=f"→ {latest}", key="force_update"))
        items.append(MenuItem("Back", key="back"))

        subtitle = "Maintainer: oxGorou\nAdvisor: NotchApple1703"
        choice = menu("About UXTU4Linux", items, subtitle=subtitle)

        if choice == -1:
            return

        item = items[choice]
        if item.key == "back":
            return
        elif item.key == "force_update" and latest:
            show_updater()
            return
