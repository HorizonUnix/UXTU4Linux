"""
setup.py
"""

from __future__ import annotations

import os
import subprocess

from . import config as cfg
from .hardware import detect as detect_hardware
from .ui import clear, confirm, pause, _B, _R


def ensure_binaries_executable() -> None:
    for path in [cfg.RYZENADJ]:
        if path and os.path.isfile(path) and not os.access(path, os.X_OK):
            try:
                subprocess.run(["chmod", "+x", path], check=True)
            except subprocess.CalledProcessError as exc:
                print(f"  Warning: could not mark '{path}' as executable: {exc}")


def _apply_defaults() -> None:
    cfg.ensure_sections("User", "Settings", "Info", "Automations")
    if not cfg.get("User", "Mode"):
        cfg.set_config("User", "Mode", "Balance")
    cfg.set_config("Settings", "Time", "3")
    cfg.set_config("Settings", "SoftwareUpdate", "1")
    cfg.set_config("Settings", "ReApply", "0")
    cfg.set_config("Settings", "ApplyOnStart", "1")
    cfg.set_config("Settings", "Debug", "0")
    cfg.set_config("Automations", "Enabled", "0")
    cfg.set_config("Automations", "OnAC", "")
    cfg.set_config("Automations", "OnBattery", "")


def _ensure_custom_presets_file() -> None:
    cfg.CUSTOM_PRESETS_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not cfg.CUSTOM_PRESETS_PATH.exists():
        cfg.CUSTOM_PRESETS_PATH.write_text("[]")


def _step(n: int, total: int, title: str) -> None:
    clear()
    print(f"  Step {n}/{total}  —  {title}\n")


def run_welcome() -> None:
    from .service import _has_systemctl, install_service, restart_service, wait_for_daemon_or_warn, wait_for_daemon, service_running
    from .ipc import get_client

    if cfg.KERNEL not in ("Linux",):
        clear()
        print(f"  Unsupported OS: {cfg.KERNEL}")
        return

    cfg.ensure_sections("User", "Settings", "Info", "Automations")
    has_systemd = _has_systemctl()
    TOTAL = 3 if has_systemd else 2

    _step(1, TOTAL, "Welcome")
    print("  UXTU4Linux — AMD Zen power management for Linux")
    print("  Built on RyzenAdj and inspired by UXTU\n")
    pause()

    _apply_defaults()
    _ensure_custom_presets_file()
    ensure_binaries_executable()
    cfg.save()

    if has_systemd:
        _step(2, TOTAL, "Daemon service")
        print("  The power daemon runs in the background keeping your preset active.")
        print("  It is required for UXTU4Linux to work properly.")
        print()
        if confirm("Install and enable daemon service"):
            if service_running():
                restart_service()
            else:
                install_service()
            wait_for_daemon_or_warn(context="setup")
        else:
            print("\n  Daemon is required. Exiting setup.")
            pause()
            return
        pause()
    else:
        _step(2, TOTAL, "Daemon service")
        from .service import _daemon_script, _python, _ensure_venv
        _ensure_venv()
        print("  systemd is not available on this system.")
        print("  Start the daemon in a separate terminal:\n")
        print(f"    sudo {_B}{_python()} {_daemon_script()}{_R}\n")
        print("  Waiting for the daemon to become available...")
        print("  (start it now, then come back here)\n")
        if not wait_for_daemon(timeout=120.0, interval=1.0):
            print("\n  Daemon did not start within 2 minutes.")
            print("  Start it manually and re-run UXTU4Linux.")
            pause()
            return
        print("  Daemon is running.\n")
        pause()

    _step(TOTAL, TOTAL, "Hardware detection")
    print("  Detecting hardware...\n")
    detect_hardware()

    cpu = cfg.get("Info", "CPU")
    family = cfg.get("Info", "Family")
    arch = cfg.get("Info", "Architecture")
    cpu_type = cfg.get("Info", "Type")
    sig = cfg.get("Info", "Signature")

    W = 14

    def row(label: str, value: str) -> None:
        print(f"  \033[2m{label:<{W}}\033[0m  {value}")

    row("CPU", cpu or "Not detected")
    row("Family", family or "Unknown")
    row("Arch", arch or "Unknown")
    row("Type", cpu_type or "Unknown")
    row("Signature", sig or "Unknown")
    print()
    pause()

    clear()
    print("  Setup complete. UXTU4Linux is ready.")
    print("  Go to Power Management to pick your preset.\n")
    pause()


def check_integrity() -> None:
    if not os.path.isfile(cfg.CONFIG_PATH) or os.stat(cfg.CONFIG_PATH).st_size == 0:
        run_welcome()
        return

    cfg.load()

    broken = (
        any(not cfg.instance().has_section(s) for s in cfg.REQUIRED)
        or any(
            k not in cfg.instance()[s]
            for s, keys in cfg.REQUIRED.items()
            if cfg.instance().has_section(s)
            for k in keys
        )
    )
    if broken:
        reset_all()


def reset_all() -> None:
    if os.path.isfile(cfg.CONFIG_PATH):
        os.remove(cfg.CONFIG_PATH)
    cfg.load()
    run_welcome()