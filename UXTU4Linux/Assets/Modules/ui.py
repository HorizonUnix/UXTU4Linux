from __future__ import annotations
import re, sys
from dataclasses import dataclass
from typing import Literal
from . import config as cfg
from . import termui

_ANSI_ESC = re.compile(r"\x1b\[[^m]*m")

BANNER = r"""
+----------------------------------------------------------+
|  _   ___  _______ _   _ _  _   _     _                   |
| | | | \ \/ /_   _| | | | || | | |   (_)_ __  _   ___  __ |
| | | | |\  /  | | | | | | || |_| |   | | '_ \| | | \ \/ / |
| | |_| |/  \  | | | |_| |__   _| |___| | | | | |_| |>  <  |
|  \___//_/\_\ |_|  \___/   |_| |_____|_|_| |_|\__,_/_/\_\ |
+----------------------------------------------------------+
"""

_SEP_W = len(next(l for l in BANNER.splitlines() if l)) - 4


def _vlen(s: str) -> int:
    return len(_ANSI_ESC.sub("", s))


def _wrap(text: str, width: int) -> list[str]:
    if width <= 0:
        return []
    result: list[str] = []
    for paragraph in text.split("\n"):
        words = paragraph.split()
        if not words:
            result.append("")
            continue
        line = ""
        for word in words:
            if not line:
                line = word
            elif _vlen(line) + 1 + _vlen(word) <= width:
                line += " " + word
            else:
                result.append(line)
                line = word
        if line:
            result.append(line)
    while result and result[-1] == "":
        result.pop()
    return result or [""]

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
    sys.stdout.write("\x1b[H\x1b[2J\x1b[3J")
    sys.stdout.flush()
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


def _render_confirm(prompt: str, subtitle: str, selected: bool) -> list[str]:
    yes = f"{_B}▶{_R} {_B}Yes{_R}" if selected     else f"  {_D}Yes{_R}"
    no  = f"{_B}▶{_R} {_B}No{_R}"  if not selected else f"  {_D}No{_R}"
    lines: list[str] = []
    if subtitle:
        lines.extend(f"  {line}" for line in subtitle.splitlines())
        lines.append("")
    lines += [
        f"  {_B}{prompt}{_R}",
        "",
        f"  {yes}    {no}",
        "",
        f"  {_D}←/→ to choose, Enter to confirm, Esc to cancel{_R}",
    ]
    return lines


def confirm(prompt: str, subtitle: str = "") -> bool:
    clear()
    sys.stdout.write(termui.HIDE_CURSOR)
    sys.stdout.flush()
    selected = True
    prev = 0
    try:
        while True:
            prev = termui.draw_lines(_render_confirm(prompt, subtitle, selected), prev)
            key = termui.get_key()
            if key in (termui.LEFT, termui.RIGHT):
                selected = not selected
            elif key in (termui.ENTER, b"\n"):
                return selected
            elif key == termui.ESC:
                return False
            elif key == b"\x03":
                sys.stdout.write(termui.SHOW_CURSOR + "\n")
                sys.exit(0)
    finally:
        sys.stdout.write(termui.SHOW_CURSOR + "\n")
        sys.stdout.flush()


def ask(prompt: str, default: str = "") -> str:
    hint = f" [{default}]" if default else ""
    val = input(f"  {prompt}{_D}{hint}{_R}: ").strip()
    return val or default


def quit_app() -> None:
    sys.stdout.write(termui.SHOW_CURSOR)
    sys.stdout.flush()
    print("\n  Thanks for using UXTU4Linux\n  Have a nice day!\n")
    sys.exit(0)


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
        lines.append("")
        lines.extend(f"  {_D}{line}{_R}" for line in subtitle.split("\n"))
    lines.append("")
    max_label_w = max(
        (_vlen(item.label) for item in items if item.hint and not item.is_separator),
        default=0,
    )
    for i, item in enumerate(items):
        if item.is_separator:
            lines.append(f"  {_D}{'─' * _SEP_W}{_R}")
            continue
        label_w = max_label_w if item.hint else _vlen(item.label)
        hint_w = _SEP_W - 6 - label_w
        hint_lines = _wrap(item.hint, hint_w) if item.hint else []
        prefix = f"  {_B}▶{_R} {_B}" if i == idx else "    "
        hd     = "" if i == idx else _D
        pad    = " " * (label_w - _vlen(item.label))
        if hint_lines:
            first = f"  {hd}{hint_lines[0]}{_R}"
            suffix = f"{_R}{first}" if i == idx else first
            lines.append(f"{prefix}{item.label}{pad}{suffix}")
            for hl in hint_lines[1:]:
                lines.append(f"    {hd}{hl}{_R}")
        else:
            lines.append(f"{prefix}{item.label}{_R if i == idx else ''}")
    active_desc = items[idx].desc if 0 <= idx < len(items) else ""
    if active_desc:
        lines.append("")
        for dl in _wrap(active_desc, _SEP_W - 2):
            lines.append(f"  {_D}{dl}{_R}")
    lines.append("")
    lines.append(f"  {_D}↑/↓ to navigate, Enter to select, Esc to go back{_R}")
    return lines


def menu(
    title: str,
    items: list[MenuItem],
    *,
    subtitle: str = "",
    selected: int = 0,
    on_toggle = None,
) -> int:
    clear()
    sys.stdout.write(termui.HIDE_CURSOR)
    sys.stdout.flush()
    idx = _clamp_skip(selected, items)
    prev = 0
    try:
        while True:
            prev = termui.draw_lines(render_menu(title, subtitle, items, idx), prev)
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
                    return idx
            elif key == termui.ESC:
                return -1
    finally:
        sys.stdout.write(termui.SHOW_CURSOR + "\n")
        sys.stdout.flush()


def open_url(url: str) -> None:
    import shutil, subprocess
    opener = shutil.which("xdg-open")
    if opener:
        subprocess.Popen(
            [opener, url],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
        return
    import webbrowser
    webbrowser.open(url)


def about_menu() -> None:
    from .updater import get_latest_version, show_updater, show_beta_updater, get_beta_commit

    while True:
        items: list[MenuItem] = [
            MenuItem("Open GitHub page", key="github"),
            MenuItem("Force update",     key="force_update"),
            MenuItem("Back",             key="back"),
        ]

        subtitle = "Maintainer: oxGorou\nAdvisor: NotchApple1703"
        choice = menu("About UXTU4Linux", items, subtitle=subtitle)

        if choice == -1:
            return

        item = items[choice]
        if item.key == "back":
            return
        elif item.key == "github":
            open_url("https://github.com/HorizonUnix/UXTU4Linux")
        elif item.key == "force_update":
            latest = None
            beta_commit = None
            try:
                latest = get_latest_version()
            except Exception:
                pass
            try:
                beta_commit = get_beta_commit()
            except Exception:
                pass
            sub_items = [
                MenuItem("Latest", hint=f"→ {latest}"      if latest      else "", key="latest"),
                MenuItem("Beta",   hint=f"→ {beta_commit}" if beta_commit else "", key="beta"),
                MenuItem("Back",   key="back"),
            ]
            sub = menu("Force Update", sub_items)
            if sub == -1 or sub_items[sub].key == "back":
                continue
            if sub_items[sub].key == "latest":
                show_updater()
            elif sub_items[sub].key == "beta":
                show_beta_updater()
            return
