from __future__ import annotations
import os, re, select, sys, termios, tty

HIDE_CURSOR = "\033[?25l"
SHOW_CURSOR = "\033[?25h"

UP = b"\x1b[A"
DOWN = b"\x1b[B"
RIGHT = b"\x1b[C"
LEFT = b"\x1b[D"
ENTER = b"\r"
ESC = b"\x1b"

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[mKHJA-Za-z]")


def _physical_rows(lines: list[str], width: int) -> int:
    if width <= 0:
        return len(lines)
    return sum(max(1, (len(_ANSI_RE.sub("", line)) + width - 1) // width) for line in lines)


def get_key(timeout: float | None = None) -> bytes | None:
    if not sys.stdin.isatty():
        raise RuntimeError(
            "stdin is not a TTY — UXTU4Linux requires an interactive terminal.\n"
            "Do not pipe input or run from a non-interactive shell."
        )
    fd  = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        if timeout is not None:
            r, _, _ = select.select([fd], [], [], timeout)
            if not r:
                return None
        while True:
            try:
                ch = os.read(fd, 1)
                break
            except InterruptedError:
                continue
        if ch == b"\x1b":
            r, _, _ = select.select([fd], [], [], 0.05)
            if r:
                ch += os.read(fd, 4)
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def draw_lines(lines: list[str], prev: int) -> int:
    try:
        sz = os.get_terminal_size()
        width = sz.columns
        height = sz.lines
    except OSError:
        width = 80
        height = 24
    if prev:
        if prev >= height:
            sys.stdout.write("\x1b[2J\x1b[H")
        else:
            sys.stdout.write(f"\x1b[{prev}A\x1b[J")
    sys.stdout.write("\n".join(lines) + "\n")
    sys.stdout.flush()
    return _physical_rows(lines, width)