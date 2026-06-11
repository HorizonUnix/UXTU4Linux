#!/usr/bin/env python3
import atexit, os, sys

_ROOT = os.path.dirname(os.path.realpath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import fcntl as _fcntl
from Assets.Modules import config as cfg
from Assets.Modules.hardware import check_binaries, check_ryzen_smu, show_info as hardware_info
from Assets.Modules.power import get_presets, preset_menu
from Assets.Modules.settings import settings_menu, ensure_config_files
from Assets.Modules.automations import automations_menu
from Assets.Modules.custom import custom_preset_menu
from Assets.Modules.setup import check_integrity
from Assets.Modules.service import verify_service_path, daemon_menu
from Assets.Modules.updater import check_updates
from Assets.Modules.ui import clear, pause, quit_app, menu, about_menu, MenuItem


cfg.load()
_TUI_LOCK_FILE = "/tmp/uxtu4linux_tui.lock"
_tui_lock_fh = None


def _acquire_single_instance() -> bool:
    global _tui_lock_fh
    try:
        _tui_lock_fh = open(_TUI_LOCK_FILE, "w")
        _fcntl.flock(_tui_lock_fh, _fcntl.LOCK_EX | _fcntl.LOCK_NB)
        _tui_lock_fh.write(str(os.getpid()))
        _tui_lock_fh.flush()
        atexit.register(_tui_lock_fh.close)
        return True
    except (IOError, OSError):
        if _tui_lock_fh is not None:
            _tui_lock_fh.close()
        return False


def _require_daemon() -> None:
    from Assets.Modules.ipc import get_client
    client = get_client()
    if client.ping():
        return
    clear()
    print("  The UXTU4Linux daemon is not running.\n")
    print("  It needs to be installed as a system service.\n")
    pause("Press Enter to open the daemon setup menu...")
    daemon_menu()
    if not client.ping():
        clear()
        print("  Daemon still not running. Exiting.")
        pause()
        sys.exit(1)


def _apply_if_idle() -> None:
    from Assets.Modules.ipc import get_client
    client = get_client()
    if not client.status().get("mode"):
        client.apply_saved()


def main() -> None:
    if not _acquire_single_instance():
        print("\n  UXTU4Linux is already running.\n  Close the other instance first.\n")
        sys.exit(1)

    ensure_config_files()
    check_binaries()
    check_integrity()
    cfg.load()

    cpu_type = cfg.get("Info", "Type")
    if cpu_type == "Intel":
        print("\n  Intel CPUs are not supported.\n")
        sys.exit(1)
    if cpu_type == "Unknown":
        print("\n  Your hardware was not recognised. UXTU4Linux supports AMD Ryzen APUs and desktop CPUs only.\n")
        sys.exit(1)
    check_ryzen_smu()

    verify_service_path()
    _require_daemon()

    if cfg.get("Settings", "SoftwareUpdate", "0") == "1":
        check_updates()

    try:
        get_presets()
    except Exception as exc:
        print(f"  Warning: failed to preload presets: {exc}")
        pause()

    _apply_if_idle()

    entries: list[tuple[str, str, object]] = [
        ("Power Management", "power", preset_menu),
        ("Custom Preset", "custom", custom_preset_menu),
        ("Automations", "automations", automations_menu),
        ("Hardware Information", "hardware", hardware_info),
        ("Settings", "settings", settings_menu),
        ("About", "about", about_menu),
        ("Quit", "quit", quit_app),
    ]

    while True:
        items = [MenuItem(label, key=key) for label, key, _ in entries]
        choice = menu("Menu", items)
        if choice == -1:
            quit_app()
        entries[choice][2]()


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        sys.stderr.write(f"\n  Error: {exc}\n")
        sys.exit(1)