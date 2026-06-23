from __future__ import annotations

import atexit
import fcntl
import logging
import os
import shlex
import subprocess
import time
from dataclasses import dataclass

from Assets.core import config as cfg


_AC_TYPES = frozenset({"Mains", "USB", "USB_C", "USB_PD", "USB_PD_DRP", "USB_C_DRP"})

_DAEMON_LOCK_FILE = "/run/uxtu4linux_daemon.lock"
_daemon_lock_fh: object = None

log = logging.getLogger("uxtu4linux")


def _clock_boottime() -> float:
    return time.clock_gettime(time.CLOCK_BOOTTIME)


def _acquire_daemon_lock() -> bool:
    global _daemon_lock_fh
    try:
        _daemon_lock_fh = open(_DAEMON_LOCK_FILE, "w")
        fcntl.flock(_daemon_lock_fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        _daemon_lock_fh.write(str(os.getpid()))
        _daemon_lock_fh.flush()
        atexit.register(_daemon_lock_fh.close)
        return True
    except (IOError, OSError):
        if _daemon_lock_fh is not None:
            _daemon_lock_fh.close()
        return False


def _run_cmd(command: str, timeout: float = 10.0) -> str:
    try:
        args = shlex.split(command)
    except ValueError:
        return ""
    proc = subprocess.Popen(
        args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    try:
        stdout, _ = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate()
        log.warning("Command timed out after %.0fs: %s", timeout, args[0])
        return ""
    return stdout.decode("utf-8", errors="replace").strip()


def _on_ac() -> bool:
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
                except OSError as exc:
                    log.debug("power_supply/%s: cannot read 'online': %s", entry, exc)
            elif ptype == "Battery":
                try:
                    with open(f"{base}/status") as f:
                        if f.read().strip().lower() == "discharging":
                            battery_discharging = True
                except OSError as exc:
                    log.debug("power_supply/%s: cannot read 'status': %s", entry, exc)
    except Exception as exc:
        log.debug("AC detection failed unexpectedly: %s", exc)
    if found_ac:
        return ac_online
    return not battery_discharging


def _load_builtin_presets() -> dict:
    from Assets.tuning.power import get_presets
    return get_presets()


def _resolve_preset_args(preset_name: str) -> tuple[str, str] | None:
    presets = _load_builtin_presets()
    if preset_name in presets:
        return preset_name, presets[preset_name]

    base = preset_name.removesuffix("_custom_preset")
    try:
        from Assets.tuning.custom import load_custom_presets, preset_to_args
        for p in load_custom_presets():
            if p["name"] == base:
                return preset_name, preset_to_args(p)
    except Exception as exc:
        log.debug("Failed to load custom preset %r: %s", preset_name, exc)

    return None


def _dn(name: str) -> str:
    return name.removesuffix("_custom_preset") if name else "none"


def _fmt_duration(seconds: float) -> str:
    if seconds < 90:
        return f"{seconds:.0f}s"
    if seconds < 5400:
        return f"{seconds / 60:.0f}m"
    return f"{seconds / 3600:.1f}h"


_smu_blocked_warned = False


def _smu_blocked() -> str | None:
    from Assets.amd import smu
    if not smu.is_available():
        return "ryzen_smu is not available"
    if not smu.version_ok():
        return f"ryzen_smu {smu.get_version()} is too old (minimum: {smu.version_str(smu.MIN_VERSION)})"
    return None


def _apply_via_smu(args: str, mode: str) -> tuple[str, bool]:
    global _smu_blocked_warned
    family = cfg.get("Info", "Family")
    if not args.strip():
        return "", False
    if not family:
        log.error("Cannot apply preset: CPU family not set in config — was hardware detected?")
        return "", False
    blocked = _smu_blocked()
    if blocked:
        if not _smu_blocked_warned:
            _smu_blocked_warned = True
            log.error("%s — presets cannot be applied.\nInstall guide: %s", blocked, cfg.RYZEN_SMU_WIKI_URL)
        return f"{blocked} — preset not applied", False
    if _smu_blocked_warned:
        _smu_blocked_warned = False
        log.info("ryzen_smu is available again — presets can be applied.")
    try:
        from Assets.engine import runner
        output, rejected = runner.apply_args(args, family)
        if rejected:
            log.warning(
                "Preset '%s' applied, but the SMU rejected one or more commands:\n%s",
                _dn(mode), output,
            )
        else:
            log.debug("SMU apply (%s/%s):\n%s", mode, family, output)
        return output, rejected
    except Exception as exc:
        log.error("Failed to apply preset '%s': %s", _dn(mode), exc)
        return "", False


@dataclass
class PresetState:
    mode: str
    args: str
    automation: bool
    interval: int
    reapply: bool


def _load_saved_preset() -> PresetState | None:
    cfg.load()
    user_mode = cfg.get("User", "Mode")
    automation = bool(cfg.get("Automations", "OnAC", "") or cfg.get("Automations", "OnBattery", ""))

    result = _resolve_preset_args(user_mode)
    if result:
        _, args = result
    elif automation:
        args = ""
        log.debug(
            "Base preset '%s' not found; automation slots will manage switching.",
            user_mode,
        )
    else:
        log.error("Preset '%s' not found — cannot apply.", user_mode)
        return None

    reapply = cfg.get("Settings", "ReApply", "0") == "1"
    interval = cfg.parse_interval(cfg.get("Settings", "Time", "3"), default=3)

    return PresetState(
        mode=user_mode,
        args=args,
        automation=automation,
        interval=interval,
        reapply=reapply,
    )

