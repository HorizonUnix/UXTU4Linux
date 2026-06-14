from __future__ import annotations

import os
import sys
import time
import threading

from . import config as cfg
from . import termui
from .hardware import detect as detect_hardware
from .ui import clear, menu, pause, MenuItem, _B, _R, _D, _G, _Y


def _apply_defaults() -> None:
    cfg.ensure_sections("User", "Settings", "Info", "Automations")
    defaults = {
        ("User", "Mode"): "Balance",
        ("Settings", "Time"): "3",
        ("Settings", "SoftwareUpdate"): "1",
        ("Settings", "ReApply"): "0",
        ("Settings", "ApplyOnStart"): "0    ",
        ("Settings", "Debug"): "0",
        ("Automations", "Enabled"): "0",
        ("Automations", "OnAC"): "",
        ("Automations", "OnBattery"): "",
        ("Automations", "OnResume"): "",
    }
    for (section, key), value in defaults.items():
        if not cfg.get(section, key):
            cfg.set_config(section, key, value)


def _ensure_custom_presets_file() -> None:
    cfg.CUSTOM_PRESETS_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not cfg.CUSTOM_PRESETS_PATH.exists():
        cfg.CUSTOM_PRESETS_PATH.write_text("[]")


def _pbar(step: int, total: int) -> str:
    return "──".join("●" if i <= step else "○" for i in range(1, total + 1))


def _step_title(label: str, step: int, total: int) -> str:
    return f"{label}   {_D}{_pbar(step, total)}  {step}/{total}{_R}"



def _step_welcome(total: int) -> None:
    items = [
        MenuItem(
            "Begin setup",
            key="begin",
        ),
    ]
    subtitle = (
        "Universal x86 Tuning Utility for AMD Zen CPUs on Linux\n"
        "Ported from the original Universal x86 Tuning Utility for Windows\n"
        "Built on a root daemon, IPC architecture, and Python"
    )
    while True:
        choice = menu(_step_title("Welcome", 1, total), items, subtitle=subtitle)
        if choice != -1:
            return


def _step_daemon_systemd(step: int, total: int) -> bool:
    from .service import (
        install_service, restart_service, service_running,
        wait_for_daemon_or_warn,
    )

    while True:
        running = service_running()
        status = f"{_G}● running{_R}" if running else f"{_Y}○ not running{_R}"
        subtitle = (
            "The daemon is required. It runs as root in the background and is\n"
            "the only process allowed to apply tuning settings to your hardware.\n"
            "Without it, nothing works — the TUI is just a frontend that talks to it.\n"
            f"\n"
            f"Status:  {status}"
        )

        if running:
            items = [
                MenuItem("Continue", key="continue"),
                MenuItem("Reinstall / restart", key="reinstall"),
            ]
        else:
            items = [
                MenuItem("Install and enable", key="install"),
            ]

        choice = menu(_step_title("Background Daemon", step, total), items, subtitle=subtitle)
        if choice == -1:
            continue

        key = items[choice].key
        if key == "continue":
            return True

        clear()
        if key == "reinstall" and running:
            restart_service()
        else:
            install_service()

        ok = wait_for_daemon_or_warn(context="setup")
        if ok:
            print(f"\n  {_G}✓ Daemon is running.{_R}")
        else:
            print(f"\n  {_Y}[!] Daemon did not start. Check logs:{_R}")
            print(f"    {_D}journalctl -u uxtu4linux.service -n 20 --no-pager{_R}")
        pause()
        if ok:
            return True


def _step_daemon_manual(step: int, total: int) -> bool:
    from .service import _daemon_script, _python, _ensure_venv

    _ensure_venv()

    while True:
        clear()
        print(f"  {_B}{_step_title('Background Daemon', step, total)}{_R}\n")
        print(f"  {_D}systemd is not available — start the daemon in another terminal:{_R}\n")
        print(f"    {_B}sudo {_python()} {_daemon_script()}{_R}\n")
        print(f"  Waiting up to 2 minutes for daemon to connect...\n", flush=True)

        deadline = time.monotonic() + 120.0
        ok = False
        while time.monotonic() < deadline:
            try:
                from .ipc import get_client
                if get_client().ping():
                    ok = True
                    break
            except Exception:
                pass
            remaining = int(deadline - time.monotonic())
            sys.stdout.write(f"\r  {_D}Waiting... {remaining}s  {_R}   ")
            sys.stdout.flush()
            time.sleep(1.0)

        print()
        if ok:
            print(f"\n  {_G}✓ Daemon is running.{_R}\n")
            pause()
            return True
        print(f"\n  {_Y}Daemon did not respond within 2 minutes.{_R}")
        print("  Start it in another terminal and press Enter to try again.\n")
        pause()


def _run_detect_animated(step: int, total: int, title: str | None = None) -> None:
    frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    done = threading.Event()

    def _worker():
        detect_hardware()
        done.set()

    t = threading.Thread(target=_worker, daemon=True)
    t.start()

    clear()
    sys.stdout.write(termui.HIDE_CURSOR)
    sys.stdout.flush()
    resolved = title if title is not None else _step_title("Your Hardware", step, total)
    title_line = f"  {_B}{resolved}{_R}"
    prev = 0
    frame_idx = 0
    try:
        while not done.is_set():
            lines = [
                title_line,
                "",
                f"  {_D}{frames[frame_idx % len(frames)]}  Detecting hardware...{_R}",
                "",
            ]
            prev = termui.draw_lines(lines, prev)
            frame_idx += 1
            time.sleep(0.08)
    finally:
        sys.stdout.write(termui.SHOW_CURSOR)
        sys.stdout.flush()
    t.join()


def _step_hardware(step: int, total: int) -> bool:
    while True:
        from .ipc import get_client
        if not get_client().ping():
            clear()
            print(f"  {_Y}[!] Daemon is not running.{_R}\n")
            print("  Hardware detection requires the daemon to be active.")
            print("  Go back and complete the daemon setup step first.\n")
            pause()
            return False

        _run_detect_animated(step, total)

        cpu      = cfg.get("Info", "CPU") or ""
        family   = cfg.get("Info", "Family") or ""
        arch     = cfg.get("Info", "Architecture") or ""
        cpu_type = cfg.get("Info", "Type") or ""

        is_supported = cpu_type in ("Amd_Apu", "Amd_Desktop_Cpu")

        def _row(label: str, value: str, good: bool = True) -> str:
            icon = f"{_G}✓{_R}" if (good and value) else f"{_Y}?{_R}"
            return f"{icon}  {label:<14}{value or 'Unknown'}"

        subtitle_lines = [
            _row("CPU", cpu),
            _row("Family", family),
            _row("Architecture", arch),
            _row("Type", cpu_type, is_supported),
            "",
        ]

        if is_supported:
            from .presets import get_preset_label
            variant  = cfg.get("Info", "Variant") or ""
            raw_cpu  = cpu
            label    = get_preset_label(cpu_type, family, raw_cpu, raw_cpu, variant)
            subtitle_lines += [
                f"{_G}Hardware is supported.{_R}",
                f"Preset profile:  {label}",
            ]
        else:
            subtitle_lines += [
                f"{_Y}Hardware may not be fully supported.{_R}",
                "Custom presets are still available.",
            ]

        items = [
            MenuItem("Continue", key="continue"),
            MenuItem("Re-detect", key="redetect"),
        ]
        choice = menu(
            _step_title("Your Hardware", step, total),
            items,
            subtitle="\n".join(subtitle_lines),
        )

        if choice == -1:
            return False
        if items[choice].key == "redetect":
            continue
        return True


def _step_done() -> None:
    subtitle = (
        f"{_G}✓ UXTU4Linux is ready.{_R}\n"
        "\n"
        "Go to Power Management to pick and apply a preset.\n"
        "Enable Automations to auto-switch presets on AC / battery."
    )
    menu("Setup Complete", [MenuItem("Go to main menu", key="main")], subtitle=subtitle)


def run_welcome() -> None:
    from .service import _has_systemctl

    if cfg.KERNEL not in ("Linux",):
        clear()
        print(f"  Unsupported OS: {cfg.KERNEL}")
        return

    cfg.ensure_sections("User", "Settings", "Info", "Automations")
    has_systemd = _has_systemctl()
    total = 3

    _apply_defaults()
    _ensure_custom_presets_file()
    cfg.save()

    _step_welcome(total)
    if has_systemd:
        if not _step_daemon_systemd(2, total):
            return
    else:
        if not _step_daemon_manual(2, total):
            return
    if not _step_hardware(3, total):
        return

    cfg.save()
    _step_done()


_CFG_DEFAULTS: dict[str, dict[str, str]] = {
    "User": {"mode": "Balance"},
    "Settings": {"time": "3", "reapply": "0", "applyonstart": "0", "softwareupdate": "1", "debug": "0"},
    "Automations": {"enabled": "0", "onac": "", "onbattery": "", "onresume": ""},
}


def check_integrity() -> None:
    if not os.path.isfile(cfg.CONFIG_PATH) or os.stat(cfg.CONFIG_PATH).st_size == 0:
        run_welcome()
        return

    cfg.load()

    info_ok = cfg.instance().has_section("Info") and all(
        k in cfg.instance()["Info"] for k in cfg.REQUIRED.get("Info", [])
    )
    if not info_ok:
        reset_all()
        return

    repaired = False
    for s, keys in cfg.REQUIRED.items():
        if s == "Info":
            continue
        if not cfg.instance().has_section(s):
            cfg.instance().add_section(s)
            repaired = True
        for k in keys:
            if k not in cfg.instance()[s]:
                cfg.instance().set(s, k, _CFG_DEFAULTS.get(s, {}).get(k, ""))
                repaired = True
    if repaired:
        cfg.save()


def reset_all() -> None:
    if os.path.isfile(cfg.CONFIG_PATH):
        os.remove(cfg.CONFIG_PATH)
    if cfg.CUSTOM_PRESETS_PATH.exists():
        cfg.CUSTOM_PRESETS_PATH.unlink(missing_ok=True)
    cfg.instance().clear()
    run_welcome()