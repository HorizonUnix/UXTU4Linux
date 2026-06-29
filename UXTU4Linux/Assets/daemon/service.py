from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time

from Assets.core import config as cfg

SERVICE_NAME = "uxtu4linux.service"
SERVICE_FILE = f"/etc/systemd/system/{SERVICE_NAME}"

_systemctl_available: bool | None = None


def sudo_available() -> bool:
    return subprocess.run(
        ["sudo", "-n", "-v"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    ).returncode == 0


def prime_sudo(password: str) -> bool:
    return subprocess.run(
        ["sudo", "-S", "-p", "", "-v"],
        input=password + "\n", text=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    ).returncode == 0


def has_systemctl() -> bool:
    global _systemctl_available
    if _systemctl_available is None:
        _systemctl_available = subprocess.call(
            ["systemctl", "--version"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        ) == 0
    return _systemctl_available


def _ensure_venv() -> bool:
    venv_dir = cfg.VENV_DIR
    venv_python = cfg.VENV_PYTHON

    if not os.path.isfile(venv_python):
        _sudo_run("mkdir", "-p", venv_dir)
        if _sudo_run(sys.executable, "-m", "venv", "--without-pip", venv_dir) != 0:
            return False
        if _sudo_run(venv_python, "-m", "ensurepip", "--upgrade") != 0:
            return False

    probe = subprocess.run(
        [venv_python, "-c", "import zmq; import textual; import textual_plotext"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    if probe.returncode != 0:
        if _sudo_run(venv_python, "-m", "pip", "install", "pyzmq", "textual", "textual-plotext", "--quiet") != 0:
            return False

    return True


def _daemon_script() -> str:
    return os.path.join(os.path.dirname(os.path.realpath(__file__)), "daemon.py")


def _python() -> str:
    return cfg.VENV_PYTHON if os.path.isfile(cfg.VENV_PYTHON) else sys.executable


def manual_start_command() -> str:
    return f"sudo {_python()} {_daemon_script()}"


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
    return subprocess.run(["sudo", "-n", *args]).returncode


def _systemctl(*args: str) -> int:
    if not has_systemctl():
        return 1
    return _sudo_run("systemctl", *args)


def _sudo_write(path: str, content: str) -> bool:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".service", delete=False) as f:
        f.write(content)
        tmp = f.name
    try:
        r = subprocess.run(["sudo", "-n", "mv", tmp, path])
        return r.returncode == 0
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def wait_for_daemon(timeout: float = 10.0, interval: float = 0.3) -> bool:
    from Assets.core.ipc import get_client
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if get_client().ping():
                return True
        except Exception:
            pass
        time.sleep(interval)
    return False


def install_service() -> dict:
    if not has_systemctl():
        return {"ok": False, "manual": True,
                "error": f"systemctl is not available. Start the daemon manually:\n"
                         f"{manual_start_command()}"}
    if not sudo_available():
        return {"ok": False, "error": "Administrator access is required."}
    if not _ensure_venv():
        return {"ok": False, "error": "Could not prepare the daemon environment."}
    if not _sudo_write(SERVICE_FILE, _render_unit()):
        return {"ok": False, "error": "Failed to write the service file."}
    _systemctl("daemon-reload")
    warning = ""
    if _systemctl("enable", SERVICE_NAME) != 0:
        warning = "Daemon installed, but it could not be enabled to start on boot."
    if _systemctl("start", SERVICE_NAME) != 0:
        return {"ok": False, "error": "Daemon installed, but the service failed to start."}
    return {"ok": True, "warning": warning}


def uninstall_service() -> dict:
    if not sudo_available():
        return {"ok": False, "error": "Administrator access is required."}
    _systemctl("stop", SERVICE_NAME)
    _systemctl("disable", SERVICE_NAME)
    _sudo_run("rm", "-f", SERVICE_FILE)
    _systemctl("daemon-reload")
    return {"ok": True}


def service_running() -> bool:
    if not has_systemctl():
        return False
    return subprocess.call(
        ["systemctl", "is-active", "--quiet", SERVICE_NAME],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    ) == 0


def service_enabled() -> bool:
    if not has_systemctl():
        return False
    return subprocess.call(
        ["systemctl", "is-enabled", "--quiet", SERVICE_NAME],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    ) == 0


def restart_service() -> dict:
    if not sudo_available():
        return {"ok": False, "error": "Administrator access is required."}
    if _systemctl("restart", SERVICE_NAME) != 0:
        return {"ok": False, "error": "Failed to restart the service."}
    return {"ok": True}


def read_logs(lines: int = 200) -> str:
    if not has_systemctl():
        return "journalctl is not available on this system."
    try:
        out = subprocess.run(
            ["journalctl", "-u", SERVICE_NAME, "-n", str(lines), "--no-pager",
             "-o", "short-precise"],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return f"Could not read daemon logs: {exc}"
    text = (out.stdout or "").strip()
    if not text:
        return out.stderr.strip() or "No daemon logs yet."
    return text


def service_path_stale() -> bool:
    if not os.path.isfile(SERVICE_FILE):
        return False
    try:
        with open(SERVICE_FILE) as f:
            content = f.read()
    except OSError:
        return False
    current_exec = f"ExecStart={_python()} {_daemon_script()}"
    existing_exec = next(
        (line for line in content.splitlines() if line.startswith("ExecStart=")),
        None,
    )
    return existing_exec is not None and existing_exec != current_exec


def regenerate_service() -> dict:
    if not sudo_available():
        return {"ok": False, "error": "Administrator access is required."}
    if not _sudo_write(SERVICE_FILE, _render_unit()):
        return {"ok": False, "error": "Failed to write the service file."}
    _systemctl("daemon-reload")
    if _systemctl("restart", SERVICE_NAME) != 0:
        return {"ok": False, "error": "Service file updated, but the daemon failed to restart."}
    return {"ok": True}