"""
termui.py
"""

from __future__ import annotations
import os, select, sys, termios, tty

HIDE_CURSOR = "\033[?25l"
SHOW_CURSOR = "\033[?25h"

UP    = b"\x1b[A"
DOWN  = b"\x1b[B"
ENTER = b"\r"
ESC   = b"\x1b"


def is_tty() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def get_key() -> bytes:
    if not sys.stdin.isatty():
        raise RuntimeError(
            "stdin is not a TTY — UXTU4Linux requires an interactive terminal.\n"
            "Do not pipe input or run from a non-interactive shell."
        )
    fd  = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = os.read(fd, 1)
        if ch == b"\x1b":
            r, _, _ = select.select([fd], [], [], 0.05)
            if r:
                ch += os.read(fd, 3)
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def draw_lines(lines: list[str], prev: int) -> int:
    if prev:
        sys.stdout.write(f"\x1b[{prev}A\x1b[J")
    sys.stdout.write("\n".join(lines) + "\n")
    sys.stdout.flush()
    return len(lines)