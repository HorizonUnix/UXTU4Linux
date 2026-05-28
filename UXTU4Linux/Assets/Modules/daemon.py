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
    r'^--?[a-zA-Z][a-zA-Z0-9_-]*(=\-?\d+(\.\d+)?)?$'
)

MIN_INTERVAL_SECONDS = cfg.MIN_INTERVAL_SECONDS
MAX_INTERVAL_SECONDS = cfg.MAX_INTERVAL_SECONDS

_STOP_LOOP_TIMEOUT_S:  int = 10
_POWER_MONITOR_POLL_S: int = 2

_DAEMON_LOCK_FILE = "/run/uxtu4linux_daemon.lock"
_daemon_lock_fh: object = None

log = logging.getLogger("uxtu4linux")


def _acquire_daemon_lock() -> bool:
    global _daemon_lock_fh
    try:
        _daemon_lock_fh = open(_DAEMON_LOCK_FILE, "w")
        fcntl.flock(_daemon_lock_fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        _daemon_lock_fh.write(str(os.getpid()))
        _daemon_lock_fh.flush()
        import atexit
        atexit.register(_daemon_lock_fh.close)
        return True
    except (IOError, OSError):
        if _daemon_lock_fh is not None:
            _daemon_lock_fh.close()
        return False


def _validate_ryzenadj_payload(tokens: list[str]) -> list[str]:
    invalid = [t for t in tokens if not _RYZENADJ_TOKEN_RE.match(t)]
    if invalid:
        raise ValueError(f"Invalid ryzenadj token(s): {invalid}")
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
    from Assets.Modules.power import get_presets
    return get_presets()


def _resolve_preset_args(preset_name: str) -> tuple[str, str] | None:
    presets = _load_builtin_presets()
    if preset_name in presets:
        return preset_name, presets[preset_name]

    base = preset_name.removesuffix("_custom_preset")
    try:
        from Assets.Modules.custom import load_custom_presets, preset_to_args
        for p in load_custom_presets():
            if p["name"] == base:
                return preset_name, preset_to_args(p)
    except Exception as exc:
        log.debug("Failed to load custom preset %r: %s", preset_name, exc)

    return None


def _run_ryzenadj(args: str, mode: str) -> str:
    raw_payload = args.split()
    try:
        payload = _validate_ryzenadj_payload(raw_payload)
    except ValueError as exc:
        log.error("ryzenadj blocked: %s", exc)
        return ""

    log.debug("ryzenadj: %s %s", cfg.RYZENADJ, " ".join(payload))

    result = subprocess.run(
        [cfg.RYZENADJ] + payload,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    out = result.stdout.decode(errors="replace")
    if result.returncode != 0:
        stderr = result.stderr.decode(errors="replace").strip()
        if stderr and "detected compatible ryzen_smu" not in stderr.lower():
            log.debug("ryzenadj stderr (rc=%d): %s", result.returncode, stderr)
    elif cfg.is_debug() and result.stderr:
        out += result.stderr.decode(errors="replace")

    return out.strip()


@dataclass
class PresetState:
    mode:       str
    args:       str
    automation: bool
    interval:   int
    reapply:    bool


def _load_saved_preset() -> PresetState | None:
    cfg.load()
    user_mode  = cfg.get("User", "Mode")
    automation = cfg.get("Automations", "Enabled", "0") == "1"

    if user_mode == "Custom":
        args = cfg.get("User", "CustomArgs")
    else:
        result = _resolve_preset_args(user_mode)
        if result:
            _, args = result
        else:
            if automation:
                args = ""
                log.debug(
                    "Base preset '%s' not found; automation slots will manage switching.",
                    user_mode,
                )
            else:
                log.error("Preset '%s' not found — cannot apply.", user_mode)
                return None

    reapply     = cfg.get("Settings", "ReApply", "0") == "1"
    cfg_default = int(cfg.get("Settings", "Time", "3"))
    interval    = cfg.parse_interval(cfg.get("Settings", "Time", str(cfg_default)), cfg_default)

    return PresetState(
        mode       = user_mode,
        args       = args,
        automation = automation,
        interval   = interval,
        reapply    = reapply,
    )


class PowerDaemon:
    def __init__(self) -> None:
        self._lock             = threading.Lock()
        self._loop_thread: threading.Thread | None    = None
        self._monitor_thread: threading.Thread | None = None
        self._stop_evt         = threading.Event()
        self._stop_monitor_evt = threading.Event()
        self._mode             = ""
        self._args             = ""
        self._automation       = False
        self._interval         = 3
        self._last_output      = ""
        self._running_loop     = False
        self._last_logged_mode = ""
        self._last_ac_state: bool | None = None

        self._dispatch = {
            "ping":                self._cmd_ping,
            "apply":               self._cmd_apply,
            "apply_loop":          self._cmd_apply_loop,
            "stop_loop":           self._cmd_stop_loop,
            "status":              self._cmd_status,
            "apply_saved":         self._cmd_apply_saved,
            "shutdown":            self._cmd_shutdown,
            "dmidecode":           self._cmd_dmidecode,
            "reload_config":       self._cmd_reload_config,
            "apply_custom_args":   self._cmd_apply_custom_args,
            "list_custom_presets": self._cmd_list_custom_presets,
        }

    def _cmd_reload_config(self, _msg: dict) -> dict:
        cfg.load()
        debug = cfg.is_debug()
        logging.getLogger().setLevel(logging.DEBUG if debug else logging.INFO)
        log.info("Config reloaded (debug=%s)", debug)
        return {"ok": True}

    def _effective_mode_args(
        self, base_mode: str, base_args: str, automation: bool, on_ac: bool | None = None
    ) -> tuple[str, str]:
        if not automation:
            return base_mode, base_args

        cfg.load()
        current_ac  = _on_ac() if on_ac is None else on_ac
        power_state = "AC" if current_ac else "Battery"
        config_key  = "OnAC" if current_ac else "OnBattery"
        preset_name = cfg.get("Automations", config_key, "")

        if not preset_name:
            log.debug(
                "Automation slot '%s' is empty — falling back to base preset '%s'.",
                config_key, base_mode,
            )
            if base_args:
                return base_mode, base_args
            other_key  = "OnBattery" if current_ac else "OnAC"
            other_name = cfg.get("Automations", other_key, "")
            if other_name:
                result = _resolve_preset_args(other_name)
                if result:
                    log.debug(
                        "Using other slot '%s' → '%s' as last-resort fallback.",
                        other_key, other_name,
                    )
                    return result
            log.debug("All automation slots empty and no base preset — nothing applied.")
            return base_mode, base_args

        result = _resolve_preset_args(preset_name)
        if result is None:
            log.warning(
                "Automation preset '%s' (slot: %s) not found — falling back to '%s'.",
                preset_name, config_key, base_mode,
            )
            return base_mode, base_args

        log.debug(
            "Automation resolved: slot=%s power=%s → preset='%s'",
            config_key, power_state, preset_name,
        )
        return result

    def _apply_once(self, args: str, mode: str, *, log_apply: bool = False) -> str:
        if not args:
            log.debug("Apply skipped — no args for preset '%s'.", mode)
            return ""
        output = _run_ryzenadj(args, mode)
        with self._lock:
            self._mode        = mode
            self._args        = args
            self._last_output = output
        if log_apply:
            log.info("Preset applied: %s", mode)
        return output

    def _loop_body(
        self, args: str, mode: str, interval: int, automation: bool
    ) -> None:
        self._stop_evt.clear()
        log.debug(
            "Reapply loop started (mode='%s', interval=%ds, automation=%s).",
            mode, interval, automation,
        )
        while not self._stop_evt.wait(interval):
            try:
                on_ac              = _on_ac()
                eff_mode, eff_args = self._effective_mode_args(mode, args, automation, on_ac)
                changed            = eff_mode != self._last_logged_mode
                if changed:
                    log.debug(
                        "Reapply tick — preset changed: '%s' → '%s' (power=%s).",
                        self._last_logged_mode or "none", eff_mode,
                        "AC" if on_ac else "Battery",
                    )
                else:
                    log.debug(
                        "Reapply tick — preset '%s' (power=%s).",
                        eff_mode, "AC" if on_ac else "Battery",
                    )
                self._apply_once(eff_args, eff_mode, log_apply=changed)
                if changed:
                    self._last_logged_mode = eff_mode
            except Exception as exc:
                log.warning("Reapply loop error: %s", exc)
        with self._lock:
            self._running_loop = False
        log.debug("Reapply loop exited.")

    def _stop_loop(self) -> None:
        self._stop_evt.set()
        if self._loop_thread and self._loop_thread.is_alive():
            self._loop_thread.join(timeout=_STOP_LOOP_TIMEOUT_S)
            if self._loop_thread.is_alive():
                log.warning(
                    "Reapply thread did not stop within %ds — may still be running.",
                    _STOP_LOOP_TIMEOUT_S,
                )

    def _monitor_body(self, args: str, mode: str) -> None:
        self._stop_monitor_evt.clear()
        self._last_ac_state = _on_ac()
        log.debug(
            "Power-state monitor started (base='%s', poll=%ds, initial=%s).",
            mode, _POWER_MONITOR_POLL_S,
            "AC" if self._last_ac_state else "Battery",
        )
        while not self._stop_monitor_evt.wait(_POWER_MONITOR_POLL_S):
            try:
                current_ac = _on_ac()
                if current_ac != self._last_ac_state:
                    prev_state         = "AC" if self._last_ac_state else "Battery"
                    new_state          = "AC" if current_ac else "Battery"
                    self._last_ac_state = current_ac
                    cfg.load()
                    eff_mode, eff_args = self._effective_mode_args(
                        mode, args, automation=True, on_ac=current_ac
                    )
                    log.info(
                        "Power source changed: %s → %s — applying preset '%s'.",
                        prev_state, new_state, eff_mode,
                    )
                    self._apply_once(eff_args, eff_mode, log_apply=True)
                    self._last_logged_mode = eff_mode
            except Exception as exc:
                log.warning("Power-state monitor error: %s", exc)
        log.debug("Power-state monitor exited.")

    def _stop_monitor(self) -> None:
        self._stop_monitor_evt.set()
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=_STOP_LOOP_TIMEOUT_S)

    def _start_monitor(self, args: str, mode: str) -> None:
        self._stop_monitor()
        self._stop_monitor_evt.clear()
        self._monitor_thread = threading.Thread(
            target=self._monitor_body,
            args=(args, mode),
            daemon=True,
            name="uxtu-power-monitor",
        )
        self._monitor_thread.start()
        log.info("Power-state monitor active (polling every %ds).", _POWER_MONITOR_POLL_S)

    def apply_preset_state_once(self, state: PresetState) -> str:
        return self._apply_once(state.args, state.mode, log_apply=True)

    def start_auto_reapply(self, state: PresetState) -> dict:
        return self._cmd_apply_loop({
            "args":       state.args,
            "mode":       state.mode,
            "interval":   state.interval,
            "automation": state.automation,
        })

    def _cmd_ping(self, _msg: dict) -> dict:
        return {"ok": True, "version": cfg.LOCAL_VERSION}

    def _cmd_apply(self, msg: dict) -> dict:
        try:
            mode   = msg.get("mode", "Unknown")
            args   = msg.get("args", "")
            output = self._apply_once(args, mode, log_apply=True)
            self._last_logged_mode = mode
            return {"ok": True, "output": output}
        except Exception as exc:
            log.error("apply command failed: %s", exc)
            return {"ok": False, "error": str(exc)}

    def _cmd_apply_loop(self, msg: dict) -> dict:
        args        = msg.get("args", "")
        mode        = msg.get("mode", "Unknown")
        cfg_default = int(cfg.get("Settings", "Time", "3"))
        interval    = cfg.parse_interval(msg.get("interval", cfg_default), cfg_default)
        automation  = bool(msg.get("automation", False))

        log.debug(
            "apply_loop: mode='%s', interval=%ds, automation=%s.",
            mode, interval, automation,
        )

        self._stop_loop()
        self._stop_monitor()

        with self._lock:
            self._automation   = automation
            self._interval     = interval
            self._running_loop = True

        on_ac              = _on_ac()
        eff_mode, eff_args = self._effective_mode_args(mode, args, automation, on_ac)
        try:
            self._apply_once(eff_args, eff_mode, log_apply=True)
            self._last_logged_mode = eff_mode
        except Exception as exc:
            with self._lock:
                self._running_loop = False
            log.error("Initial apply failed before starting reapply loop: %s", exc)
            return {"ok": False, "error": str(exc)}

        if automation:
            log.info(
                "Reapply started — Automations (AC: '%s' / Battery: '%s'), every %ds.",
                cfg.get("Automations", "OnAC", "none"),
                cfg.get("Automations", "OnBattery", "none"),
                interval,
            )
        else:
            log.info("Reapply started — preset '%s', every %ds.", mode, interval)

        self._loop_thread = threading.Thread(
            target=self._loop_body,
            args=(args, mode, interval, automation),
            daemon=True,
            name="uxtu-reapply",
        )
        self._loop_thread.start()
        return {"ok": True}

    def _cmd_stop_loop(self, _msg: dict) -> dict:
        self._stop_loop()
        self._stop_monitor()
        with self._lock:
            self._running_loop = False
            mode = self._mode
            args = self._args
        log.info("Reapply stopped.")
        cfg.load()
        if cfg.get("Automations", "Enabled", "0") == "1":
            self._start_monitor(args, mode)
        return {"ok": True}

    def _cmd_status(self, _msg: dict) -> dict:
        with self._lock:
            return {
                "ok":           True,
                "running_loop": self._running_loop,
                "mode":         self._mode,
                "args":         self._args,
                "automation":   self._automation,
                "interval":     self._interval,
                "on_ac":        _on_ac(),
                "last_output":  self._last_output,
            }

    def _cmd_apply_saved(self, _msg: dict) -> dict:
        try:
            state = _load_saved_preset()
        except Exception as exc:
            log.error("Failed to load saved preset: %s", exc)
            return {"ok": False, "error": str(exc)}
        if state is None:
            return {"ok": False, "error": "Saved preset not found"}

        self._stop_loop()
        self._stop_monitor()

        with self._lock:
            self._automation = state.automation

        if state.reapply:
            log.debug(
                "apply_saved: reapply=on, automation=%s → starting loop.",
                state.automation,
            )
            return self.start_auto_reapply(state)

        if state.automation:
            on_ac              = _on_ac()
            eff_mode, eff_args = self._effective_mode_args(
                state.mode, state.args, automation=True, on_ac=on_ac
            )
            output = self._apply_once(eff_args, eff_mode, log_apply=True)
            self._last_logged_mode = eff_mode
            log.debug("apply_saved: reapply=off, automation=on → starting monitor.")
            self._start_monitor(state.args, state.mode)
            return {"ok": True, "output": output}

        log.debug("apply_saved: reapply=off, automation=off → single apply.")
        output = self.apply_preset_state_once(state)
        return {"ok": True, "output": output}

    def _cmd_shutdown(self, _msg: dict) -> dict:
        self._stop_loop()
        self._stop_monitor()
        return {"ok": True}

    def _cmd_dmidecode(self, msg: dict) -> dict:
        dmi_type = msg.get("type", "")
        if not dmi_type:
            return {"ok": False, "error": "missing 'type'"}
        if dmi_type not in _DMI_ALLOWED_TYPES:
            log.warning("dmidecode: rejected disallowed type %r.", dmi_type)
            return {"ok": False, "error": f"disallowed dmidecode type: {dmi_type!r}"}
        try:
            log.debug("dmidecode -t %s", dmi_type)
            out = _run_cmd(f"{cfg.DMIDECODE} -t {dmi_type}")
            return {"ok": True, "output": out}
        except Exception as exc:
            log.error("dmidecode failed: %s", exc)
            return {"ok": False, "error": str(exc)}

    def _cmd_apply_custom_args(self, msg: dict) -> dict:
        args = msg.get("args", "")
        if not args:
            return {"ok": False, "error": "empty args"}
        try:
            output = self._apply_once(args, "Custom", log_apply=True)
            self._last_logged_mode = "Custom"
            return {"ok": True, "output": output}
        except Exception as exc:
            log.error("apply_custom_args failed: %s", exc)
            return {"ok": False, "error": str(exc)}

    def _cmd_list_custom_presets(self, _msg: dict) -> dict:
        try:
            from Assets.Modules.custom import get_custom_preset_names
            names = get_custom_preset_names()
            log.debug("list_custom_presets: %d preset(s) found.", len(names))
            return {"ok": True, "names": names}
        except Exception as exc:
            log.error("list_custom_presets failed: %s", exc)
            return {"ok": False, "error": str(exc), "names": []}

    def handle(self, raw: str) -> str:
        try:
            msg  = json.loads(raw)
            cmd  = msg.get("cmd", "")
            func = self._dispatch.get(cmd)
            if func is None:
                log.warning("Unknown IPC command: '%s'.", cmd)
                return json.dumps({"ok": False, "error": f"unknown command: {cmd!r}"})
            log.debug("IPC command: '%s'.", cmd)
            resp = func(msg)
        except Exception as exc:
            log.error("IPC handler error: %s", exc)
            resp = {"ok": False, "error": str(exc)}
        return json.dumps(resp)

    def run(self, on_ready=None) -> None:
        if os.path.exists(cfg.ZMQ_SOCKET_PATH):
            try:
                os.unlink(cfg.ZMQ_SOCKET_PATH)
                log.warning("Removed stale socket: %s", cfg.ZMQ_SOCKET_PATH)
            except OSError as exc:
                log.error("Cannot remove stale socket %s: %s", cfg.ZMQ_SOCKET_PATH, exc)

        ctx  = zmq.Context()
        sock = ctx.socket(zmq.REP)
        try:
            sock.bind(cfg.ZMQ_SOCKET_ADDR)
        except zmq.ZMQError as exc:
            log.error("Cannot bind IPC socket %s: %s", cfg.ZMQ_SOCKET_ADDR, exc)
            sock.close()
            ctx.term()
            return

        if os.path.exists(cfg.ZMQ_SOCKET_PATH):
            os.chmod(cfg.ZMQ_SOCKET_PATH, 0o666)

        log.info("IPC socket ready: %s", cfg.ZMQ_SOCKET_ADDR)

        def _sig_handler(*_):
            log.info("Signal received — shutting down.")
            self._stop_loop()
            self._stop_monitor()
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
                log.warning("on_ready callback raised: %s", exc)

        log.info("Daemon ready — waiting for commands.")

        while True:
            raw  = sock.recv_string()
            resp = self.handle(raw)
            sock.send_string(resp)
            if json.loads(raw).get("cmd") == "shutdown":
                log.info("Shutdown command received — exiting.")
                break

        if os.path.exists(cfg.ZMQ_SOCKET_PATH):
            os.unlink(cfg.ZMQ_SOCKET_PATH)
        sock.close()
        ctx.term()


def _apply_on_start(daemon: PowerDaemon) -> None:
    log.info("ApplyOnStart: loading saved preset.")
    try:
        state = _load_saved_preset()
    except Exception as exc:
        log.error("ApplyOnStart: failed to load preset: %s", exc)
        return
    if state is None:
        log.warning("ApplyOnStart: no valid preset found — skipping.")
        return

    if state.reapply:
        log.info(
            "ApplyOnStart: starting reapply loop (automation=%s, interval=%ds).",
            state.automation, state.interval,
        )
        daemon.start_auto_reapply(state)
    elif state.automation:
        on_ac              = _on_ac()
        eff_mode, eff_args = daemon._effective_mode_args(
            state.mode, state.args, automation=True, on_ac=on_ac
        )
        daemon._apply_once(eff_args, eff_mode, log_apply=True)
        daemon._last_logged_mode = eff_mode
        log.info("ApplyOnStart: automations active, reapply off — monitor started.")
        daemon._start_monitor(state.args, state.mode)
    else:
        log.info("ApplyOnStart: single apply, no reapply.")
        daemon.apply_preset_state_once(state)


def main() -> None:
    logging.basicConfig(
        level  = logging.INFO,
        format = "%(levelname)s: %(message)s",
    )

    if not _acquire_daemon_lock():
        log.error("Another daemon instance is already running (lock: %s).", _DAEMON_LOCK_FILE)
        sys.exit(1)

    cfg.load()
    log_level = logging.DEBUG if cfg.is_debug() else logging.INFO
    logging.getLogger().setLevel(log_level)

    log.info("UXTU4Linux daemon v%s", cfg.LOCAL_VERSION)

    if cfg.get("Info", "Type") == "Intel":
        log.error("Intel CPUs are not supported — exiting.")
        sys.exit(1)

    from Assets.Modules.hardware import _find_dmidecode, ryzen_smu_loaded, secure_boot_enabled

    dmi = _find_dmidecode()
    if dmi is None:
        log.error("dmidecode not found in PATH — hardware detection unavailable.")
        sys.exit(1)
    cfg.DMIDECODE = dmi
    log.debug("dmidecode binary: %s", dmi)

    cpu  = cfg.get("Info", "CPU")
    fam  = cfg.get("Info", "Family")
    arch = cfg.get("Info", "Architecture")
    log.info("CPU: %s, Family: %s, Arch: %s", cpu, fam, arch)

    if not ryzen_smu_loaded() and secure_boot_enabled():
        log.error(
            "ryzen_smu kernel module not loaded — Secure Boot is blocking it."
        )
        log.error(
            "Fix: disable Secure Boot in UEFI, or sign the module with your MOK key."
        )
        log.error(
            "See: https://github.com/HorizonUnix/UXTU4Linux/wiki/Linux-Troubleshooting"
            "#secure-boot-blocking-ryzenadj"
        )
        sys.exit(1)

    daemon   = PowerDaemon()
    on_ready = (
        (lambda: _apply_on_start(daemon))
        if cfg.get("Settings", "ApplyOnStart", "1") == "1"
        else None
    )
    if on_ready is None:
        log.info("ApplyOnStart is disabled — no preset applied at startup.")

    daemon.run(on_ready=on_ready)


if __name__ == "__main__":
    main()