#!/usr/bin/env python3
import os, sys

_ROOT = os.path.dirname(os.path.realpath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import fcntl as _fcntl
from Assets.Modules import config as cfg
cfg.load()

from Assets.Modules.hardware  import check_binaries, check_system_compat, show_info as hardware_info
from Assets.Modules.power     import get_presets, preset_menu
from Assets.Modules.settings  import settings_menu
from Assets.Modules.setup     import check_integrity, ensure_binaries_executable
from Assets.Modules.service   import verify_service_path, daemon_menu
from Assets.Modules.updater   import check_updates
from Assets.Modules.ui        import clear, pause, quit_app, menu, about_menu, MenuItem

_TUI_LOCK_FILE = "/tmp/uxtu4linux_tui.lock"
_tui_lock_fh   = None


def _acquire_single_instance() -> bool:
    global _tui_lock_fh
    try:
        _tui_lock_fh = open(_TUI_LOCK_FILE, "w")
        _fcntl.flock(_tui_lock_fh, _fcntl.LOCK_EX | _fcntl.LOCK_NB)
        import os as _os
        _tui_lock_fh.write(str(_os.getpid()))
        _tui_lock_fh.flush()
        return True
    except (IOError, OSError):
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
    check_integrity()
    check_binaries()
    ensure_binaries_executable()
    check_system_compat()

    verify_service_path()
    _require_daemon()

    if cfg.get("Settings", "SoftwareUpdate", "0") == "1":
        check_updates()

    try:
        get_presets()
    except Exception as exc:
        print(f"  Warning: failed to preload presets: {exc}")

    _apply_if_idle()

    items: list[MenuItem] = [
        MenuItem("Power Management"),
        MenuItem("Settings"),
        MenuItem("Hardware Information"),
        MenuItem("About"),
        MenuItem("Quit"),
    ]

    actions = [preset_menu, settings_menu, hardware_info, about_menu, quit_app]

    while True:
        choice = menu("Menu", items)
        if choice == -1:
            quit_app()
        actions[choice]()


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        sys.stderr.write(f"\n  Error: {exc}\n")
        sys.exit(1)