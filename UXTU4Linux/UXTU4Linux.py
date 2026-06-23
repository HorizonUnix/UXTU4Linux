#!/usr/bin/env python3
import atexit, os, sys

_ROOT = os.path.dirname(os.path.realpath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import fcntl as _fcntl
from Assets.core import config as cfg
from Assets.core.hardware import check_binaries, check_ryzen_smu, ensure_max_clock
from Assets.tuning.power import get_presets
from Assets.flows.setup import check_integrity, init_config, needs_setup, ensure_custom_presets_file
from Assets.daemon.service import service_path_stale


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


def _apply_if_idle() -> None:
    from Assets.core.ipc import get_client
    client = get_client()
    if not client.status().get("mode"):
        client.apply_saved()


def main() -> None:
    if not _acquire_single_instance():
        from Assets.tui.app import run as run_textual
        run_textual(dep_error="UXTU4Linux is already running.\n\nClose the other instance first.")
        sys.exit(1)

    ensure_custom_presets_file()
    dep_error = check_binaries()

    first_run = needs_setup()
    if first_run:
        init_config()
    else:
        check_integrity()
    cfg.load()

    if not first_run:
        ensure_max_clock()

    if not dep_error and cfg.get("Info", "Type") == "Intel":
        dep_error = "Intel CPUs are not supported.\n\nUXTU4Linux only supports AMD Ryzen APUs and desktop CPUs."
    if not dep_error:
        dep_error = check_ryzen_smu()

    path_stale = service_path_stale()

    try:
        get_presets()
    except Exception:
        pass
    _apply_if_idle()

    from Assets.tui.app import run as run_textual
    result = run_textual(first_run=first_run, dep_error=dep_error, path_stale=path_stale)
    if result in ("setup-done", "relaunch"):
        os.execv(sys.executable, [sys.executable, *sys.argv])
    elif result == "reset":
        from Assets.flows.setup import reset_all
        try:
            from Assets.core.ipc import get_client
            client = get_client()
            if client.ping():
                client.reset_state()
        except Exception:
            pass
        reset_all()
        os.execv(sys.executable, [sys.executable, *sys.argv])


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        sys.stderr.write(f"\n  Error: {exc}\n")
        sys.exit(1)