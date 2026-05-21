"""
service.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time

from . import config as cfg
from .ui import clear, menu, pause, MenuItem

SERVICE_NAME = "uxtu4linux.service"
SERVICE_FILE = f"/etc/systemd/system/{SERVICE_NAME}"


def _has_systemctl() -> bool:
    return subprocess.call(
        ["systemctl", "--version"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    ) == 0


def _ensure_venv() -> bool:
    venv_dir    = cfg.VENV_DIR
    venv_python = cfg.VENV_PYTHON

    def _sudo(*args: str) -> int:
        return subprocess.run(["sudo", *args]).returncode

    if not os.path.isfile(venv_python):
        print(f"  Creating venv at {venv_dir} ...")
        print(f"    (to recreate manually: sudo {sys.executable} -m venv --without-pip {venv_dir})")
        _sudo("mkdir", "-p", venv_dir)
        if _sudo(sys.executable, "-m", "venv", "--without-pip", venv_dir) != 0:
            print(f"\n  Failed to create venv at {venv_dir}.")
            print(f"  Try running manually:")
            print(f"    sudo {sys.executable} -m venv --without-pip {venv_dir}")
            pause()
            return False
        if _sudo(venv_python, "-m", "ensurepip", "--upgrade") != 0:
            print(f"\n  Failed to bootstrap pip inside {venv_dir}.")
            print(f"  Try running manually:")
            print(f"    sudo {venv_python} -m ensurepip --upgrade")
            pause()
            return False

    probe = subprocess.run(
        [venv_python, "-c", "import zmq"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    if probe.returncode != 0:
        print(f"  Installing pyzmq into {venv_dir} ...")
        print(f"    (to install manually: sudo {venv_python} -m pip install pyzmq)")
        if _sudo(venv_python, "-m", "pip", "install", "pyzmq", "--quiet") != 0:
            print(f"\n  Failed to install pyzmq.")
            print(f"  Try running manually:")
            print(f"    sudo {venv_python} -m pip install pyzmq")
            pause()
            return False

    return True


def _daemon_script() -> str:
    return os.path.join(os.path.dirname(os.path.realpath(__file__)), "daemon.py")


def _python() -> str:
    return cfg.VENV_PYTHON if os.path.isfile(cfg.VENV_PYTHON) else sys.executable


def _render_unit() -> str:
    return (
        "[Unit]\n"
        "Description=UXTU4Linux Power Management Daemon\n"
        "After=multi-user.target\n\n"
        "[Service]\n"
        "Type=simple\n"
        f"ExecStart={_python()} {_daemon_script()}\n"
        "Restart=on-failure\n"
        "RestartSec=5\n"
        "StandardOutput=journal\n"
        "StandardError=journal\n\n"
        "[Install]\n"
        "WantedBy=multi-user.target\n"
    )


def _sudo_run(*args: str) -> int:
    return subprocess.run(["sudo", *args]).returncode


def _systemctl(*args: str) -> int:
    if not _has_systemctl():
        print("  systemctl is not available on this system.")
        print(f"  Start the daemon manually: sudo {_python()} {_daemon_script()}")
        return 1
    return _sudo_run("systemctl", *args)


def _sudo_write(path: str, content: str) -> bool:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".service", delete=False) as f:
        f.write(content)
        tmp = f.name
    try:
        r = subprocess.run(["sudo", "mv", tmp, path])
        return r.returncode == 0
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def wait_for_daemon(timeout: float = 10.0, interval: float = 0.3) -> bool:
    from .ipc import get_client
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if get_client().ping():
                return True
        except Exception:
            pass
        time.sleep(interval)
    return False


def wait_for_daemon_or_warn(context: str = "") -> bool:
    print("  Waiting for daemon...", end="", flush=True)
    ok = wait_for_daemon()
    if ok:
        print(" ready.")
    else:
        print("\n  Warning: daemon did not start in time.")
        if context == "setup":
            print("  Hardware detection may fail — check logs if issues occur.")
    return ok


def install_service() -> None:
    if not _has_systemctl():
        print("  systemctl is not available — cannot install as a systemd service.")
        print(f"  Run the daemon manually: sudo {_python()} {_daemon_script()}")
        pause()
        return
    if not _ensure_venv():
        print("  Aborting service installation due to venv errors.")
        return
    if not _sudo_write(SERVICE_FILE, _render_unit()):
        print("  Failed to write service file.")
        return
    _systemctl("daemon-reload")
    _systemctl("enable", SERVICE_NAME)
    _systemctl("start",  SERVICE_NAME)


def uninstall_service() -> None:
    _systemctl("stop",    SERVICE_NAME)
    _systemctl("disable", SERVICE_NAME)
    _sudo_run("rm", "-f", SERVICE_FILE)
    _systemctl("daemon-reload")


def service_running() -> bool:
    if not _has_systemctl():
        return False
    return subprocess.call(
        ["systemctl", "is-active", "--quiet", SERVICE_NAME],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    ) == 0


def service_enabled() -> bool:
    if not _has_systemctl():
        return False
    return subprocess.call(
        ["systemctl", "is-enabled", "--quiet", SERVICE_NAME],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    ) == 0


def restart_service() -> None:
    _systemctl("restart", SERVICE_NAME)


def show_logs() -> None:
    subprocess.call(["journalctl", "-u", SERVICE_NAME, "-n", "50", "--no-pager"])


def verify_service_path() -> None:
    if not os.path.isfile(SERVICE_FILE):
        return
    try:
        with open(SERVICE_FILE) as f:
            content = f.read()
    except OSError:
        return

    current_exec  = f"ExecStart={_python()} {_daemon_script()}"
    existing_exec = next(
        (line for line in content.splitlines() if line.startswith("ExecStart=")),
        None,
    )

    if existing_exec == current_exec:
        return

    print("  Service path stale (app was moved).")
    print(f"  Was: {existing_exec}")
    print(f"  Now: {current_exec}")

    if _sudo_write(SERVICE_FILE, _render_unit()):
        _systemctl("daemon-reload")
        _systemctl("restart", SERVICE_NAME)
        print("  Service file regenerated and daemon restarted.")
    else:
        print(f"  Update manually: sudo nano {SERVICE_FILE}")
    pause()


def daemon_menu() -> None:
    if not _has_systemctl():
        clear()
        print("  systemd is not available on this system.\n")
        print("  UXTU4Linux's service management requires systemd.")
        print("  Start the daemon manually:\n")
        print(f"    sudo {_python()} {_daemon_script()}\n")
        print("  To auto-start on boot, consult your init system's documentation.")
        pause()
        return

    while True:
        running  = service_running()
        enabled  = service_enabled()
        subtitle = (
            f"Status: {'Running' if running else 'Stopped'}\n"
            f"{'Enabled on boot' if enabled else 'Not enabled'}"
        )
        items: list[MenuItem] = [
            MenuItem("Install & enable", key="install"),
            MenuItem("Uninstall",        key="uninstall"),
            MenuItem("Restart",          key="restart"),
            MenuItem("View logs",        hint="last 50 lines", key="view_logs"),
            MenuItem("Back",             key="back"),
        ]
        choice = menu("Daemon Service", items, subtitle=subtitle)
        if choice == -1 or items[choice].key == "back":
            return

        key = items[choice].key
        clear()
        if key == "install":
            install_service()
            wait_for_daemon_or_warn()
            pause()
        elif key == "uninstall":
            uninstall_service()
            print("  Service removed.")
            pause()
        elif key == "restart":
            restart_service()
            print("  Service restarted.")
            pause()
        elif key == "view_logs":
            show_logs()
            pause()