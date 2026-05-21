"""
daemon.py
"""
from __future__ import annotations

import json
import logging
import os
import re
import shlex
import signal
import subprocess
import sys
import threading
import zmq
import fcntl
from dataclasses import dataclass

_HERE = os.path.dirname(os.path.realpath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from Assets.Modules import config as cfg

cfg.load()

_AC_TYPES = frozenset({"Mains", "USB", "USB_C", "USB_PD", "USB_PD_DRP", "USB_C_DRP"})

_DMI_ALLOWED_TYPES = frozenset({
    "bios", "system", "baseboard", "chassis", "processor",
    "memory", "cache", "connector", "slot",
    *(str(i) for i in range(42)),
})

_RYZENADJ_TOKEN_RE = re.compile(
    r'^--?[a-zA-Z][a-zA-Z0-9_-]*(=\d+(\.\d+)?)?$'
)

MIN_INTERVAL_SECONDS = cfg.MIN_INTERVAL_SECONDS
MAX_INTERVAL_SECONDS = cfg.MAX_INTERVAL_SECONDS

_STOP_LOOP_TIMEOUT_S: int = 10

_DAEMON_LOCK_FILE = "/run/uxtu4linux_daemon.lock"
_daemon_lock_fh: object = None


def _acquire_daemon_lock() -> bool:
    global _daemon_lock_fh
    try:
        _daemon_lock_fh = open(_DAEMON_LOCK_FILE, "w")
        fcntl.flock(_daemon_lock_fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        _daemon_lock_fh.write(str(os.getpid()))
        _daemon_lock_fh.flush()
        return True
    except (IOError, OSError):
        return False


def _validate_ryzenadj_payload(tokens: list[str]) -> list[str]:
    invalid = [t for t in tokens if not _RYZENADJ_TOKEN_RE.match(t)]
    if invalid:
        raise ValueError(f"invalid ryzenadj arguments: {invalid}")
    return tokens


def _run_cmd(command: str) -> str:
    try:
        args = shlex.split(command)
    except ValueError:
        return ""
    proc = subprocess.Popen(
        args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    stdout, _ = proc.communicate()
    return stdout.decode("utf-8", errors="replace").strip()


def _on_ac() -> bool:
    ac_online           = False
    found_ac            = False
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
                    logging.debug("Failed to read AC online state from %s/online: %s", base, exc)
            elif ptype == "Battery":
                try:
                    with open(f"{base}/status") as f:
                        if f.read().strip().lower() == "discharging":
                            battery_discharging = True
                except OSError as exc:
                    logging.debug("Unable to read battery status from %s/status: %s", base, exc)
    except Exception as exc:
        logging.debug("Unexpected error while detecting AC state: %s", exc)
    if found_ac:
        return ac_online
    return not battery_discharging


def _load_presets() -> dict:
    from Assets.Modules.power import get_presets
    return get_presets()


def _run_ryzenadj(args: str, mode: str) -> str:
    raw_payload = mode.split() if args == "Custom" else args.split()
    try:
        payload = _validate_ryzenadj_payload(raw_payload)
    except ValueError as exc:
        logging.error("%s", exc)
        return ""

    logging.debug("ryzenadj cmd: %s %s", cfg.RYZENADJ, " ".join(payload))

    result = subprocess.run(
        [cfg.RYZENADJ] + payload,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    out = result.stdout.decode(errors="replace")
    if cfg.is_debug() and result.stderr:
        out += result.stderr.decode(errors="replace")
    return out.strip()


@dataclass
class PresetState:
    mode:     str
    args:     str
    dynamic:  bool
    interval: int
    reapply:  bool


def _load_saved_preset() -> PresetState | None:
    cfg.load()
    user_mode = cfg.get("User", "Mode")
    presets   = _load_presets()

    if user_mode == "Custom":
        args = cfg.get("User", "CustomArgs")
    elif user_mode in presets:
        args = presets[user_mode]
    else:
        logging.warning("Saved preset %r not found.", user_mode)
        return None

    reapply     = cfg.get("Settings", "ReApply",     "0") == "1"
    dynamic     = cfg.get("Settings", "DynamicMode", "0") == "1"
    cfg_default = int(cfg.get("Settings", "Time", "3"))
    interval    = cfg.parse_interval(cfg.get("Settings", "Time", str(cfg_default)), cfg_default)

    return PresetState(
        mode=user_mode,
        args=args,
        dynamic=dynamic,
        interval=interval,
        reapply=reapply,
    )


class PowerDaemon:
    def __init__(self) -> None:
        self._lock             = threading.Lock()
        self._loop_thread: threading.Thread | None = None
        self._stop_evt         = threading.Event()
        self._mode             = ""
        self._args             = ""
        self._dynamic          = False
        self._interval         = 3
        self._last_output      = ""
        self._running_loop     = False
        self._last_logged_mode = ""

        self._dispatch = {
            "ping":        self._cmd_ping,
            "apply":       self._cmd_apply,
            "apply_loop":  self._cmd_apply_loop,
            "stop_loop":   self._cmd_stop_loop,
            "status":      self._cmd_status,
            "apply_saved": self._cmd_apply_saved,
            "shutdown":    self._cmd_shutdown,
            "dmidecode":   self._cmd_dmidecode,
            "reload_config": self._cmd_reload_config,
        }

    def _cmd_reload_config(self, _msg: dict) -> dict:
        cfg.load()
        debug = cfg.is_debug()
        logging.info("Config reloaded, debug=%s", debug)          # log first
        logging.getLogger().setLevel(logging.DEBUG if debug else logging.INFO)
        return {"ok": True}

    def _effective_mode_args(
        self, base_mode: str, base_args: str, dynamic: bool
    ) -> tuple[str, str]:
        if not dynamic:
            return base_mode, base_args
        presets = _load_presets()
        mode    = "Extreme" if _on_ac() else "Eco"
        args    = presets.get(mode, base_args)
        return mode, args

    def _apply_once(self, args: str, mode: str, *, log: bool = False) -> str:
        output = _run_ryzenadj(args, mode)
        with self._lock:
            self._mode        = mode
            self._args        = args
            self._last_output = output
        if log:
            logging.info("Applying preset: %s", mode)
        return output

    def _loop_body(self, args: str, mode: str, interval: int, dynamic: bool) -> None:
        self._stop_evt.clear()
        while not self._stop_evt.wait(interval):
            try:
                eff_mode, eff_args = self._effective_mode_args(mode, args, dynamic)
                changed = eff_mode != self._last_logged_mode
                logging.debug(
                    "Loop tick: effective_mode=%s dynamic=%s on_ac=%s changed=%s",
                    eff_mode, dynamic, _on_ac(), changed,
                )
                self._apply_once(eff_args, eff_mode, log=changed)
                if changed:
                    self._last_logged_mode = eff_mode
            except Exception as exc:
                logging.warning("Failed to apply preset in loop: %s", exc)
        with self._lock:
            self._running_loop = False

    def _stop_loop(self) -> None:
        self._stop_evt.set()
        if self._loop_thread and self._loop_thread.is_alive():
            self._loop_thread.join(timeout=_STOP_LOOP_TIMEOUT_S)
            if self._loop_thread.is_alive():
                logging.warning(
                    "Reapply thread did not exit within %ds.", _STOP_LOOP_TIMEOUT_S
                )

    def apply_preset_state_once(self, state: PresetState) -> str:
        return self._apply_once(state.args, state.mode, log=True)

    def start_auto_reapply(self, state: PresetState) -> dict:
        return self._cmd_apply_loop({
            "args":     state.args,
            "mode":     state.mode,
            "interval": state.interval,
            "dynamic":  state.dynamic,
        })

    def _cmd_ping(self, _msg: dict) -> dict:
        return {"ok": True, "version": cfg.LOCAL_VERSION}

    def _cmd_apply(self, msg: dict) -> dict:
        try:
            mode   = msg.get("mode", "Unknown")
            args   = msg.get("args", "")
            output = self._apply_once(args, mode, log=True)
            self._last_logged_mode = mode
            return {"ok": True, "output": output}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def _cmd_apply_loop(self, msg: dict) -> dict:
        args        = msg.get("args", "")
        mode        = msg.get("mode", "Unknown")
        cfg_default = int(cfg.get("Settings", "Time", "3"))
        interval    = cfg.parse_interval(msg.get("interval", cfg_default), cfg_default)
        dynamic     = bool(msg.get("dynamic", False))

        logging.debug(
            "apply_loop requested: mode=%s interval=%ds dynamic=%s",
            mode, interval, dynamic,
        )

        self._stop_loop()

        with self._lock:
            self._dynamic      = dynamic
            self._interval     = interval
            self._running_loop = True

        try:
            eff_mode, eff_args = self._effective_mode_args(mode, args, dynamic)
            self._apply_once(eff_args, eff_mode, log=True)
            self._last_logged_mode = eff_mode
        except Exception as exc:
            with self._lock:
                self._running_loop = False
            return {"ok": False, "error": str(exc)}

        display_mode = "Dynamic mode" if dynamic else mode
        logging.info(
            "Auto-reapply started: %s, every %ds",
            display_mode, interval,
        )

        self._loop_thread = threading.Thread(
            target=self._loop_body,
            args=(args, mode, interval, dynamic),
            daemon=True,
            name="uxtu-reapply",
        )
        self._loop_thread.start()
        return {"ok": True}

    def _cmd_stop_loop(self, _msg: dict) -> dict:
        self._stop_loop()
        with self._lock:
            self._running_loop = False
        logging.info("Auto-reapply stopped.")
        return {"ok": True}

    def _cmd_status(self, _msg: dict) -> dict:
        with self._lock:
            return {
                "ok":           True,
                "running_loop": self._running_loop,
                "mode":         self._mode,
                "args":         self._args,
                "dynamic":      self._dynamic,
                "interval":     self._interval,
                "on_ac":        _on_ac(),
                "last_output":  self._last_output,
            }

    def _cmd_apply_saved(self, _msg: dict) -> dict:
        try:
            state = _load_saved_preset()
        except Exception as exc:
            return {"ok": False, "error": f"Could not load presets: {exc}"}
        if state is None:
            return {"ok": False, "error": "Saved preset not found"}

        self._stop_loop()

        if state.reapply or state.dynamic:
            return self.start_auto_reapply(state)

        output = self.apply_preset_state_once(state)
        return {"ok": True, "output": output}

    def _cmd_shutdown(self, _msg: dict) -> dict:
        self._stop_loop()
        return {"ok": True}

    def _cmd_dmidecode(self, msg: dict) -> dict:
        dmi_type = msg.get("type", "")
        if not dmi_type:
            return {"ok": False, "error": "missing 'type'"}
        if dmi_type not in _DMI_ALLOWED_TYPES:
            return {"ok": False, "error": f"disallowed dmidecode type: {dmi_type!r}"}
        try:
            out = _run_cmd(f"{cfg.DMIDECODE} -t {dmi_type}")
            return {"ok": True, "output": out}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def handle(self, raw: str) -> str:
        try:
            msg  = json.loads(raw)
            cmd  = msg.get("cmd", "")
            func = self._dispatch.get(cmd)
            if func:
                resp = func(msg)
            else:
                resp = {"ok": False, "error": f"unknown command: {cmd!r}"}
        except Exception as exc:
            resp = {"ok": False, "error": str(exc)}
        return json.dumps(resp)

    def run(self, on_ready=None) -> None:
        if os.path.exists(cfg.ZMQ_SOCKET_PATH):
            try:
                os.unlink(cfg.ZMQ_SOCKET_PATH)
                logging.warning("Removed stale IPC socket at %s", cfg.ZMQ_SOCKET_PATH)
            except OSError as exc:
                logging.error("Could not remove stale socket at %s: %s", cfg.ZMQ_SOCKET_PATH, exc)

        ctx  = zmq.Context()
        sock = ctx.socket(zmq.REP)
        try:
            sock.bind(cfg.ZMQ_SOCKET_ADDR)
        except zmq.ZMQError as exc:
            logging.error("Failed to bind ZMQ socket on %s: %s", cfg.ZMQ_SOCKET_ADDR, exc)
            sock.close()
            ctx.term()
            return

        if os.path.exists(cfg.ZMQ_SOCKET_PATH):
            os.chmod(cfg.ZMQ_SOCKET_PATH, 0o666)

        logging.info("Listening on %s", cfg.ZMQ_SOCKET_ADDR)

        def _sig_handler(*_):
            logging.info("Shutting down.")
            self._stop_loop()
            if os.path.exists(cfg.ZMQ_SOCKET_PATH):
                os.unlink(cfg.ZMQ_SOCKET_PATH)
            sock.close()
            ctx.term()
            sys.exit(0)

        signal.signal(signal.SIGTERM, _sig_handler)
        signal.signal(signal.SIGINT,  _sig_handler)

        if on_ready is not None:
            try:
                on_ready()
            except Exception as exc:
                logging.warning("on_ready callback raised: %s", exc)

        while True:
            raw  = sock.recv_string()
            resp = self.handle(raw)
            sock.send_string(resp)
            if json.loads(raw).get("cmd") == "shutdown":
                logging.info("Shutdown command received.")
                break

        if os.path.exists(cfg.ZMQ_SOCKET_PATH):
            os.unlink(cfg.ZMQ_SOCKET_PATH)
        sock.close()
        ctx.term()


def _apply_on_start(daemon: PowerDaemon) -> None:
    try:
        state = _load_saved_preset()
    except Exception as exc:
        logging.warning("Could not load presets: %s", exc)
        return
    if state is None:
        return

    if state.reapply or state.dynamic:
        daemon.start_auto_reapply(state)
        label = "Dynamic mode" if state.dynamic else state.mode
        logging.info("Started: %s (every %ds)", label, state.interval)
    else:
        daemon.apply_preset_state_once(state)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if not _acquire_daemon_lock():
        logging.error("Another daemon instance is already running. Exiting.")
        sys.exit(1)

    cfg.load()
    log_level = logging.DEBUG if cfg.is_debug() else logging.INFO
    logging.getLogger().setLevel(log_level)

    if cfg.get("Info", "Type") == "Intel":
        logging.error("Intel CPUs are not supported.")
        sys.exit(1)

    from Assets.Modules.hardware import _find_dmidecode, ryzen_smu_loaded, secure_boot_enabled

    dmi = _find_dmidecode()
    if dmi is None:
        logging.error("dmidecode not found in PATH — hardware detection will fail.")
        sys.exit(1)
    cfg.DMIDECODE = dmi

    if not ryzen_smu_loaded() and secure_boot_enabled():
        logging.error(
            "ryzen_smu module not loaded — Secure Boot is blocking it. "
            "Preset will not be applied. "
            "Fix: disable Secure Boot or sign the module with your MOK key. "
            "https://github.com/HorizonUnix/UXTU4Linux/wiki/Linux-Troubleshooting#secure-boot-blocking-ryzenadj"
        )
        sys.exit(1)

    logging.info("UXTU4Linux daemon v%s", cfg.LOCAL_VERSION)

    daemon = PowerDaemon()
    on_ready = (
        (lambda: _apply_on_start(daemon))
        if cfg.get("Settings", "ApplyOnStart", "1") == "1"
        else None
    )
    daemon.run(on_ready=on_ready)


if __name__ == "__main__":
    main()
