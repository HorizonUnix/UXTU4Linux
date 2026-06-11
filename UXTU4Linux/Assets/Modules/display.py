from __future__ import annotations

import json
import os
import re
import shutil
import subprocess

_TIMEOUT_S = 5
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

_backend: str | None = None
_probed = False


def _run(*argv: str) -> str | None:
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=_TIMEOUT_S)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0:
        return None
    return r.stdout


def _is_wayland() -> bool:
    if os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland":
        return True
    return bool(os.environ.get("WAYLAND_DISPLAY"))


def _pick_name(names: list[str]) -> str | None:
    for n in names:
        if n.upper().startswith("EDP"):
            return n
    for n in names:
        if n.upper().startswith("LVDS"):
            return n
    return names[0] if names else None


def parse_xrandr(text: str) -> tuple[str, str, list[int]] | None:
    outputs: dict[str, list[str]] = {}
    current: list[str] | None = None
    for line in text.splitlines():
        if " connected" in line:
            name = line.split()[0]
            outputs[name] = []
            current = outputs[name]
        elif line[:1].isspace() and current is not None:
            current.append(line)
        else:
            current = None

    name = _pick_name(list(outputs.keys()))
    if name is None:
        return None

    for line in outputs[name]:
        if "*" not in line:
            continue
        m = re.match(r"\s*(\d+x\d+i?)\s", line)
        if not m:
            continue
        res = m.group(1)
        rates = sorted(
            {round(float(r)) for r in re.findall(r"(\d+\.\d+)", line) if float(r) > 0},
            reverse=True,
        )
        return name, res, rates
    return None


def _xrandr_rates() -> list[int]:
    out = _run("xrandr", "--query")
    parsed = parse_xrandr(out) if out else None
    return parsed[2] if parsed else []


def _xrandr_set(hz: int) -> bool:
    out = _run("xrandr", "--query")
    parsed = parse_xrandr(out) if out else None
    if not parsed:
        return False
    name, res, _ = parsed
    return _run("xrandr", "--output", name, "--mode", res, "--rate", str(hz)) is not None


def parse_wlr(raw: str) -> tuple[str, int, int, list[tuple[float, int]]] | None:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    names = [o.get("name", "") for o in data if o.get("enabled")]
    name = _pick_name(names)
    if name is None:
        return None
    output = next(o for o in data if o.get("name") == name)
    modes = output.get("modes", [])
    cur = next((m for m in modes if m.get("current")), None)
    if cur is None:
        return None
    w, h = cur["width"], cur["height"]
    rates = [
        (m["refresh"], round(m["refresh"]))
        for m in modes
        if m.get("width") == w and m.get("height") == h
    ]
    return name, w, h, rates


def _wlr_rates() -> list[int]:
    out = _run("wlr-randr", "--json")
    parsed = parse_wlr(out) if out else None
    if not parsed:
        return []
    return sorted({r for _, r in parsed[3]}, reverse=True)


def _wlr_set(hz: int) -> bool:
    out = _run("wlr-randr", "--json")
    parsed = parse_wlr(out) if out else None
    if not parsed:
        return False
    name, w, h, rates = parsed
    if not rates:
        return False
    exact = min(rates, key=lambda p: abs(p[0] - hz))[0]
    mode = f"{w}x{h}@{exact:.3f}Hz"
    return _run("wlr-randr", "--output", name, "--mode", mode) is not None


def parse_kscreen(text: str) -> tuple[str, str, str, list[tuple[str, int]]] | None:
    text = _ANSI_RE.sub("", text)
    blocks: list[tuple[str, str, str]] = []
    for m in re.finditer(r"Output:\s+(\d+)\s+(\S+)", text):
        start = m.end()
        nxt = text.find("Output:", start)
        body = text[start: nxt if nxt != -1 else len(text)]
        blocks.append((m.group(1), m.group(2), body))
    if not blocks:
        return None

    name = _pick_name([b[1] for b in blocks])
    out_idx, _, body = next(b for b in blocks if b[1] == name)

    modes = re.findall(r"(\d+):(\d+x\d+)@(\d+(?:\.\d+)?)(\*?)", body)
    cur_res = next((res for _, res, _, star in modes if star), None)
    if cur_res is None:
        return None
    rate_list = [
        (idx, round(float(hz)))
        for idx, res, hz, _ in modes
        if res == cur_res
    ]
    return out_idx, name, cur_res, rate_list


def _kscreen_rates() -> list[int]:
    out = _run("kscreen-doctor", "-o")
    parsed = parse_kscreen(out) if out else None
    if not parsed:
        return []
    return sorted({r for _, r in parsed[3]}, reverse=True)


def _kscreen_set(hz: int) -> bool:
    out = _run("kscreen-doctor", "-o")
    parsed = parse_kscreen(out) if out else None
    if not parsed:
        return False
    out_idx, _, _, rate_list = parsed
    match = next((idx for idx, r in rate_list if r == hz), None)
    if match is None:
        return False
    return _run("kscreen-doctor", f"output.{out_idx}.mode.{match}") is not None


def parse_gdctl(text: str) -> tuple[str, str, list[tuple[str, int]]] | None:
    text = re.sub(r"[│├└─]", " ", text)
    monitors = re.findall(r"Monitor\s+(\S+)", text)
    name = _pick_name(monitors)
    if name is None:
        return None
    modes = re.findall(r"(\d+x\d+)@(\d+(?:\.\d+)?)", text)
    if not modes:
        return None
    cur_m = re.search(r"(\d+x\d+)@(\d+(?:\.\d+)?)[^\n]*\*", text)
    cur_res = cur_m.group(1) if cur_m else max(
        {res for res, _ in modes}, key=lambda r: sum(1 for res, _ in modes if res == r)
    )
    rate_list = [
        (f"{res}@{hz}", round(float(hz)))
        for res, hz in modes
        if res == cur_res
    ]
    return name, cur_res, rate_list


def _gdctl_rates() -> list[int]:
    out = _run("gdctl", "show", "-v")
    parsed = parse_gdctl(out) if out else None
    if not parsed:
        return []
    return sorted({r for _, r in parsed[2]}, reverse=True)


def _gdctl_set(hz: int) -> bool:
    out = _run("gdctl", "show", "-v")
    parsed = parse_gdctl(out) if out else None
    if not parsed:
        return False
    name, _, rate_list = parsed
    mode = next((m for m, r in rate_list if r == hz), None)
    if mode is None:
        return False
    return _run(
        "gdctl", "set", "--logical-monitor", "--primary", "--monitor", name, "--mode", mode
    ) is not None


_BACKENDS: dict[str, tuple] = {
    "wlr-randr": (_wlr_rates, _wlr_set),
    "gdctl": (_gdctl_rates, _gdctl_set),
    "kscreen-doctor": (_kscreen_rates, _kscreen_set),
    "xrandr": (_xrandr_rates, _xrandr_set),
}


def _probe() -> str | None:
    order = (
        ["wlr-randr", "gdctl", "kscreen-doctor", "xrandr"]
        if _is_wayland()
        else ["xrandr"]
    )
    for tool in order:
        if shutil.which(tool) is None:
            continue
        rates_fn, _ = _BACKENDS[tool]
        if rates_fn():
            return tool
    return None


def backend() -> str | None:
    global _backend, _probed
    if not _probed:
        _backend = _probe()
        _probed = True
    return _backend


def available() -> bool:
    return backend() is not None


def get_rates() -> list[int]:
    b = backend()
    if b is None:
        return []
    return _BACKENDS[b][0]()


def set_rate(hz: int) -> bool:
    b = backend()
    if b is None:
        return False
    return _BACKENDS[b][1](hz)
