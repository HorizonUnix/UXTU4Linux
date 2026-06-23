from __future__ import annotations

import atexit
import json
import logging
import os
import shlex
import signal
import subprocess
import sys
import time
import threading
import zmq
import fcntl
from dataclasses import dataclass, fields as dataclass_fields

_HERE = os.path.dirname(os.path.realpath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from Assets.core import config as cfg

cfg.load()

_AC_TYPES = frozenset({"Mains", "USB", "USB_C", "USB_PD", "USB_PD_DRP", "USB_C_DRP"})

_DMI_ALLOWED_TYPES = frozenset({
    "bios", "system", "baseboard", "chassis", "processor",
    "memory", "cache", "connector", "slot",
    *(str(i) for i in range(42)),
})

MIN_INTERVAL_SECONDS = cfg.MIN_INTERVAL_SECONDS
MAX_INTERVAL_SECONDS = cfg.MAX_INTERVAL_SECONDS

_STOP_LOOP_TIMEOUT_S: int = 10
_POWER_MONITOR_POLL_S: int = 2
_SUSPEND_MONITOR_POLL_S: int = 1
_SUSPEND_GAP_THRESHOLD_S: float = 1.0

_RYZEN_SMU_WIKI = cfg.RYZEN_SMU_WIKI_URL

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
    automation = cfg.get("Automations", "Enabled", "0") == "1"

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


class PowerDaemon:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._loop_thread: threading.Thread | None = None
        self._monitor_thread: threading.Thread | None = None
        self._suspend_thread: threading.Thread | None = None
        self._stop_evt = threading.Event()
        self._stop_monitor_evt = threading.Event()
        self._stop_suspend_evt = threading.Event()
        self._mode = ""
        self._args = ""
        self._automation = False
        self._interval = 3
        self._last_output = ""
        self._last_rejected = False
        self._running_loop = False
        self._last_logged_mode = ""
        self._last_ac_state: bool | None = None
        self._adaptive_thread: threading.Thread | None = None
        self._stop_adaptive_evt = threading.Event()
        self._adaptive_running = False
        self._adaptive_preset_name = ""
        self._adaptive_preset = None
        self._adaptive_state = None
        self._adaptive_caps: set = set()
        self._adaptive_sample = None
        self._adaptive_applied = ""

        self._dispatch = {
            "ping": self._cmd_ping,
            "apply": self._cmd_apply,
            "apply_loop": self._cmd_apply_loop,
            "stop_loop": self._cmd_stop_loop,
            "status": self._cmd_status,
            "apply_saved": self._cmd_apply_saved,
            "shutdown": self._cmd_shutdown,
            "dmidecode": self._cmd_dmidecode,
            "reload_config": self._cmd_reload_config,
            "reset_state": self._cmd_reset_state,
            "adaptive_start": self._cmd_adaptive_start,
            "adaptive_stop": self._cmd_adaptive_stop,
            "adaptive_status": self._cmd_adaptive_status,
        }

    def _cmd_reload_config(self, _msg: dict) -> dict:
        cfg.load()
        debug = cfg.is_debug()
        logging.getLogger().setLevel(logging.DEBUG if debug else logging.INFO)
        log.info("Config reloaded (debug=%s)", debug)
        return {"ok": True}

    def _cmd_reset_state(self, _msg: dict) -> dict:
        self._stop_loop()
        self._stop_monitor()
        with self._lock:
            self._mode = ""
            self._args = ""
            self._automation = False
            self._interval = 3
            self._running_loop = False
            self._last_output = ""
            self._last_rejected = False
        self._last_logged_mode = ""
        cfg.load()
        logging.getLogger().setLevel(logging.DEBUG if cfg.is_debug() else logging.INFO)
        log.info("Daemon state reset to defaults.")
        return {"ok": True}

    def _effective_mode_args(
        self, base_mode: str, base_args: str, automation: bool, on_ac: bool | None = None
    ) -> tuple[str, str]:
        if not automation:
            return base_mode, base_args

        cfg.load()
        current_ac = _on_ac() if on_ac is None else on_ac
        power_state = "AC" if current_ac else "Battery"
        config_key = "OnAC" if current_ac else "OnBattery"
        preset_name = cfg.get("Automations", config_key, "")
        base_mode = base_mode or "Unknown"

        if not preset_name:
            log.debug(
                "Automation slot '%s' is empty — falling back to base preset '%s'.",
                config_key, base_mode,
            )
            if base_args:
                return base_mode, base_args
            other_key = "OnBattery" if current_ac else "OnAC"
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

    def _apply_once(self, args: str, mode: str, *, reason: str = "") -> tuple[str, bool]:
        if not args:
            log.debug("Apply skipped — no args for preset '%s'.", mode)
            return "", False
        output, rejected = _apply_via_smu(args, mode)
        with self._lock:
            self._mode = mode
            self._args = args
            self._last_output = output
            self._last_rejected = rejected
        if reason and not rejected:
            log.info("Applied preset '%s' (%s).", _dn(mode), reason)
        return output, rejected

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
                if self._adaptive_running:
                    continue
                on_ac = _on_ac()
                eff_mode, eff_args = self._effective_mode_args(mode, args, automation, on_ac)
                changed = eff_mode != self._last_logged_mode
                log.debug(
                    "Reapply tick — preset '%s' (power=%s).",
                    eff_mode, "AC" if on_ac else "Battery",
                )
                reason = ""
                if changed:
                    reason = f"automations switched preset, now on {'AC' if on_ac else 'battery'}"
                self._apply_once(eff_args, eff_mode, reason=reason)
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
                if self._adaptive_running:
                    self._last_ac_state = _on_ac()
                    continue
                current_ac = _on_ac()
                if current_ac != self._last_ac_state:
                    prev_state = "AC" if self._last_ac_state else "battery"
                    new_state = "AC" if current_ac else "battery"
                    self._last_ac_state = current_ac
                    eff_mode, eff_args = self._effective_mode_args(
                        mode, args, automation=True, on_ac=current_ac
                    )
                    self._apply_once(
                        eff_args, eff_mode,
                        reason=f"power source changed from {prev_state} to {new_state}",
                    )
                    self._last_logged_mode = eff_mode
            except Exception as exc:
                log.warning("Power-state monitor error: %s", exc)
        log.debug("Power-state monitor exited.")

    def _stop_monitor(self) -> None:
        self._stop_monitor_evt.set()
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=_STOP_LOOP_TIMEOUT_S)

    def _suspend_monitor_body(self) -> None:
        self._stop_suspend_evt.clear()
        try:
            last_gap = _clock_boottime() - time.monotonic()
        except OSError as exc:
            log.warning(
                "CLOCK_BOOTTIME unavailable — suspend/resume detection disabled: %s", exc
            )
            return

        log.debug(
            "Suspend monitor started (poll=%ds, threshold=%.1fs).",
            _SUSPEND_MONITOR_POLL_S, _SUSPEND_GAP_THRESHOLD_S,
        )
        while not self._stop_suspend_evt.wait(_SUSPEND_MONITOR_POLL_S):
            try:
                current_gap = _clock_boottime() - time.monotonic()
                delta = current_gap - last_gap
                if delta > _SUSPEND_GAP_THRESHOLD_S:
                    cfg.load()
                    preset_name = cfg.get("Automations", "OnResume", "")
                    if not preset_name:
                        log.info(
                            "Woke from suspend (slept ~%s) — no On Resume preset configured.",
                            _fmt_duration(delta),
                        )
                    else:
                        result = _resolve_preset_args(preset_name)
                        if result:
                            mode, args = result
                            self._apply_once(
                                args, mode,
                                reason=f"woke from suspend after ~{_fmt_duration(delta)}",
                            )
                            self._last_logged_mode = mode
                        else:
                            log.warning(
                                "Woke from suspend, but the On Resume preset '%s' no longer exists — nothing applied.",
                                _dn(preset_name),
                            )
                last_gap = current_gap
            except Exception as exc:
                log.warning("Suspend monitor tick error: %s", exc)
        log.debug("Suspend monitor exited.")

    def _start_suspend_monitor(self) -> None:
        self._stop_suspend_monitor()
        self._stop_suspend_evt.clear()
        self._suspend_thread = threading.Thread(
            target=self._suspend_monitor_body,
            daemon=True,
            name="uxtu-suspend-monitor",
        )
        self._suspend_thread.start()
        log.info("Watching for suspend/resume.")

    def _stop_suspend_monitor(self) -> None:
        self._stop_suspend_evt.set()
        if self._suspend_thread and self._suspend_thread.is_alive():
            self._suspend_thread.join(timeout=_STOP_LOOP_TIMEOUT_S)

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
        log.info("Watching for AC/battery changes.")

    def apply_preset_state_once(self, state: PresetState, reason: str = "restoring saved settings") -> str:
        output, _ = self._apply_once(state.args, state.mode, reason=reason)
        return output

    def start_auto_reapply(self, state: PresetState) -> dict:
        return self._cmd_apply_loop({
            "args": state.args,
            "mode": state.mode,
            "interval": state.interval,
            "automation": state.automation,
        })

    def _cmd_ping(self, _msg: dict) -> dict:
        return {"ok": True, "version": cfg.LOCAL_VERSION}

    def _cmd_apply(self, msg: dict) -> dict:
        try:
            mode = msg.get("mode", "Unknown")
            args = msg.get("args", "")
            output, rejected = self._apply_once(args, mode, reason="selected in the app")
            self._last_logged_mode = mode
            return {"ok": True, "output": output, "rejected": rejected}
        except Exception as exc:
            log.error("apply command failed: %s", exc)
            return {"ok": False, "error": str(exc)}

    def _cmd_apply_loop(self, msg: dict) -> dict:
        args = msg.get("args", "")
        mode = msg.get("mode", "Unknown")
        interval = cfg.parse_interval(msg.get("interval", cfg.get("Settings", "Time", "3")), default=3)
        automation = bool(msg.get("automation", False))

        log.debug(
            "apply_loop: mode='%s', interval=%ds, automation=%s.",
            mode, interval, automation,
        )

        self._stop_loop()
        self._stop_monitor()

        with self._lock:
            self._automation = automation
            self._interval = interval
            self._running_loop = True

        on_ac = _on_ac()
        eff_mode, eff_args = self._effective_mode_args(mode, args, automation, on_ac)
        try:
            output, rejected = self._apply_once(eff_args, eff_mode, reason="starting auto-reapply")
            self._last_logged_mode = eff_mode
        except Exception as exc:
            with self._lock:
                self._running_loop = False
            log.error("Initial apply failed before starting reapply loop: %s", exc)
            return {"ok": False, "error": str(exc)}

        if automation:
            log.info(
                "Auto-reapply on, every %ds — automations pick the preset (AC: '%s', battery: '%s').",
                interval,
                _dn(cfg.get("Automations", "OnAC", "")),
                _dn(cfg.get("Automations", "OnBattery", "")),
            )
        else:
            log.info("Auto-reapply on — preset '%s' will be re-applied every %ds.", _dn(mode), interval)

        self._loop_thread = threading.Thread(
            target=self._loop_body,
            args=(args, mode, interval, automation),
            daemon=True,
            name="uxtu-reapply",
        )
        self._loop_thread.start()
        return {"ok": True, "output": output, "rejected": rejected}

    def _cmd_stop_loop(self, _msg: dict) -> dict:
        self._stop_loop()
        self._stop_monitor()
        with self._lock:
            self._running_loop = False
            mode = self._mode
            args = self._args
        log.info("Auto-reapply turned off.")
        cfg.load()
        if cfg.get("Automations", "Enabled", "0") == "1":
            self._start_monitor(args, mode)
        return {"ok": True}

    def _cmd_status(self, _msg: dict) -> dict:
        on_ac = _on_ac()
        with self._lock:
            status = {
                "ok": True,
                "running_loop": self._running_loop,
                "mode": self._mode,
                "args": self._args,
                "automation": self._automation,
                "interval": self._interval,
                "on_ac": on_ac,
                "last_output": self._last_output,
                "last_rejected": self._last_rejected,
                "version": cfg.LOCAL_VERSION,
            }
        return status

    def _cmd_apply_saved(self, _msg: dict) -> dict:
        try:
            state = _load_saved_preset()
        except Exception as exc:
            log.error("Failed to load saved preset: %s", exc)
            return {"ok": False, "error": str(exc)}
        self._stop_loop()
        self._stop_monitor()

        if state is None:
            with self._lock:
                self._automation = False
            return {"ok": False, "error": "Saved preset not found"}

        with self._lock:
            self._automation = state.automation

        if state.reapply:
            log.debug(
                "apply_saved: reapply=on, automation=%s → starting loop.",
                state.automation,
            )
            return self.start_auto_reapply(state)

        if state.automation:
            on_ac = _on_ac()
            eff_mode, eff_args = self._effective_mode_args(
                state.mode, state.args, automation=True, on_ac=on_ac
            )
            output, _ = self._apply_once(eff_args, eff_mode, reason="restoring saved settings")
            self._last_logged_mode = eff_mode
            log.debug("apply_saved: reapply=off, automation=on → starting monitor.")
            self._start_monitor(state.args, state.mode)
            return {"ok": True, "output": output}

        log.debug("apply_saved: reapply=off, automation=off → single apply.")
        output = self.apply_preset_state_once(state)
        return {"ok": True, "output": output}

    def _build_adaptive_args(self, state, preset, sample, caps):
        from Assets.engine import adaptive
        is_apu = cfg.get("Info", "Type") == "Amd_Apu"
        if sample.cpu_load is None:
            return ""
        temp = int(sample.cpu_temp) if sample.cpu_temp is not None else 0
        load = int(sample.cpu_load)
        parts = []
        if state.tick < 2:
            cmd = ""
            for _ in range(3):
                step = adaptive.update_power_limit(
                    state, temp, load, preset.power, preset.power - 5, preset.max_temp, is_apu)
                if step:
                    cmd = step
            if cmd:
                parts.append(cmd)
            state.tick += 1
            return " ".join(parts)
        cmd = adaptive.update_power_limit(
            state, temp, load, preset.power, 8, preset.max_temp, is_apu)
        if cmd:
            parts.append(cmd)
        if preset.enable_co:
            cmd = adaptive.curve_optimiser(state, load, preset.co_max)
            if cmd:
                parts.append(cmd)
        if (preset.enable_igpu and sample.igpu_load is not None and sample.igpu_clk is not None
                and sample.mem_clk is not None and sample.cpu_clk is not None):
            cmd = adaptive.update_igpu_clock(
                state, preset.igpu_max, preset.igpu_min, preset.max_temp,
                temp, int(sample.igpu_clk), int(sample.igpu_load), int(sample.mem_clk),
                int(sample.cpu_clk), preset.min_cpu_clk)
            if cmd:
                parts.append(cmd)
        return " ".join(parts)

    def _build_adaptive_static(self, preset):
        parts = []
        if preset.enable_asus:
            parts.append(f"--sys-asus-mode={preset.asus_mode}")
        if preset.enable_nvidia:
            parts.append(
                f"--nvidia-clocks={preset.nv_max_clk},{preset.nv_core_offset},"
                f"{preset.nv_mem_offset},{preset.nv_power_limit}")
        return " ".join(parts)

    def _adaptive_tick_args(self, sample):
        static = self._build_adaptive_static(self._adaptive_preset)
        dynamic = self._build_adaptive_args(
            self._adaptive_state, self._adaptive_preset, sample, self._adaptive_caps)
        return " ".join(part for part in (static, dynamic) if part)

    def _adaptive_body(self, interval):
        from Assets.system import sensors
        self._stop_adaptive_evt.clear()
        log.info("Adaptive loop started (preset='%s', interval=%ds).",
                 self._adaptive_preset_name, interval)
        sensors.sample()
        while not self._stop_adaptive_evt.wait(interval):
            try:
                sample = sensors.sample()
                merged = self._adaptive_tick_args(sample)
                if merged:
                    self._apply_once(merged, "Adaptive", reason="adaptive")
                with self._lock:
                    self._adaptive_sample = sample
                    self._adaptive_applied = merged or self._adaptive_applied
            except Exception as exc:
                log.warning("Adaptive loop error: %s", exc)
        with self._lock:
            self._adaptive_running = False
        log.debug("Adaptive loop exited.")

    def _stop_adaptive(self):
        self._stop_adaptive_evt.set()
        if self._adaptive_thread and self._adaptive_thread.is_alive():
            self._adaptive_thread.join(timeout=_STOP_LOOP_TIMEOUT_S)

    def _adaptive_interval(self):
        try:
            value = float(cfg.get("Adaptive", "interval", "2"))
        except (TypeError, ValueError):
            value = 2.0
        return min(8.0, max(1.0, value))

    def _cmd_adaptive_start(self, msg):
        from Assets.engine import adaptive
        from Assets.system import sensors
        from Assets.tuning import adaptivemanager
        cfg.load()
        name = msg.get("preset", "")
        values = msg.get("values")
        if values is not None:
            known = {f.name for f in dataclass_fields(adaptivemanager.AdaptivePreset)}
            preset = adaptivemanager.AdaptivePreset(
                **{k: v for k, v in values.items() if k in known})
        else:
            preset = adaptivemanager.get(name)
        if preset is None:
            return {"ok": False, "error": f"adaptive preset not found: {name!r}"}
        self._stop_adaptive()
        caps = sensors.capabilities()
        with self._lock:
            self._adaptive_preset_name = name
            self._adaptive_preset = preset
            self._adaptive_state = adaptive.AdaptiveState()
            self._adaptive_caps = caps
            self._adaptive_running = True
            self._adaptive_applied = ""
        interval = self._adaptive_interval()
        static = self._build_adaptive_static(preset)
        if static:
            self._apply_once(static, "Adaptive", reason="adaptive static settings")
        self._adaptive_thread = threading.Thread(
            target=self._adaptive_body, args=(interval,), daemon=True, name="uxtu-adaptive")
        self._adaptive_thread.start()
        return {"ok": True, "caps": sorted(caps)}

    def _cmd_adaptive_stop(self, _msg):
        self._stop_adaptive()
        with self._lock:
            self._adaptive_running = False
        log.info("Adaptive turned off.")
        try:
            revert = self._cmd_apply_saved({})
        except Exception as exc:
            log.warning("Adaptive stop: revert to saved preset failed: %s", exc)
            return {"ok": True, "reverted": False}
        return {"ok": True, "reverted": bool(revert.get("ok"))}

    def _cmd_adaptive_status(self, _msg):
        with self._lock:
            sample = self._adaptive_sample
            data = {}
            if sample is not None:
                data = {
                    "cpu_temp": sample.cpu_temp, "cpu_load": sample.cpu_load,
                    "cpu_power": sample.cpu_power, "cpu_clk": sample.cpu_clk,
                    "igpu_load": sample.igpu_load, "igpu_clk": sample.igpu_clk,
                }
            return {
                "ok": True,
                "running": self._adaptive_running,
                "preset": self._adaptive_preset_name,
                "sample": data,
                "applied": self._adaptive_applied,
                "caps": sorted(self._adaptive_caps),
            }

    def _cmd_shutdown(self, _msg: dict) -> dict:
        self._stop_loop()
        self._stop_monitor()
        self._stop_adaptive()
        self._stop_suspend_monitor()
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

    def handle(self, raw: str) -> str:
        try:
            msg = json.loads(raw)
            cmd = msg.get("cmd", "")
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

        ctx = zmq.Context()
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

        self._start_suspend_monitor()

        def _sig_handler(*_):
            log.info("Signal received — shutting down.")
            self._stop_loop()
            self._stop_monitor()
            self._stop_suspend_monitor()
            if os.path.exists(cfg.ZMQ_SOCKET_PATH):
                os.unlink(cfg.ZMQ_SOCKET_PATH)
            sock.close()
            ctx.term()
            sys.exit(0)

        signal.signal(signal.SIGTERM, _sig_handler)
        signal.signal(signal.SIGINT, _sig_handler)

        if on_ready is not None:
            try:
                on_ready()
            except Exception as exc:
                log.warning("on_ready callback raised: %s", exc)

        log.info("Daemon ready — waiting for commands.")

        while True:
            try:
                raw = sock.recv_string()
            except zmq.ZMQError as exc:
                log.error("ZMQ recv error: %s — shutting down.", exc)
                break
            cmd = None
            try:
                cmd = json.loads(raw).get("cmd")
            except json.JSONDecodeError:
                pass
            resp = self.handle(raw)
            try:
                sock.send_string(resp)
            except zmq.ZMQError as exc:
                log.error("ZMQ send error: %s", exc)
            if cmd == "shutdown":
                log.info("Shutdown command received — exiting.")
                break

        if os.path.exists(cfg.ZMQ_SOCKET_PATH):
            os.unlink(cfg.ZMQ_SOCKET_PATH)
        sock.close()
        ctx.term()
        self._stop_suspend_monitor()


def _apply_on_start(daemon: PowerDaemon) -> None:
    try:
        state = _load_saved_preset()
    except Exception as exc:
        log.error("Could not restore saved settings at startup: %s", exc)
        return
    if state is None:
        log.warning("No saved preset to restore at startup — skipping.")
        return

    if state.reapply:
        daemon.start_auto_reapply(state)
    elif state.automation:
        on_ac = _on_ac()
        eff_mode, eff_args = daemon._effective_mode_args(
            state.mode, state.args, automation=True, on_ac=on_ac
        )
        daemon._apply_once(eff_args, eff_mode, reason="restoring saved settings at startup")
        daemon._last_logged_mode = eff_mode
        daemon._start_monitor(state.args, state.mode)
    else:
        daemon.apply_preset_state_once(state, reason="restoring saved settings at startup")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    if not _acquire_daemon_lock():
        log.error("Another daemon instance is already running (lock: %s).", _DAEMON_LOCK_FILE)
        sys.exit(1)

    cfg.load()
    log_level = logging.DEBUG if cfg.is_debug() else logging.INFO
    logging.getLogger().setLevel(log_level)

    log.info("UXTU4Linux daemon v%s", cfg.LOCAL_VERSION)

    if cfg.get("Info", "Type") == "Intel":
        log.warning("Intel CPU detected — SMU control is not supported; presets will not be applied.")

    from Assets.core.hardware import _find_dmidecode, secure_boot_enabled
    from Assets.amd import smu

    dmi = _find_dmidecode()
    if dmi is None:
        log.error("dmidecode not found in PATH — hardware detection unavailable.")
        sys.exit(1)
    cfg.DMIDECODE = dmi
    log.debug("dmidecode binary: %s", dmi)

    cpu = cfg.get("Info", "CPU")
    fam = cfg.get("Info", "Family")
    arch = cfg.get("Info", "Architecture")
    log.info("CPU: %s, Family: %s, Arch: %s", cpu, fam, arch)

    if not smu.is_available():
        from Assets.core.hardware import ryzen_smu_installed, ryzen_smu_signed
        installed = ryzen_smu_installed()
        sb = secure_boot_enabled()
        if not installed:
            log.error("ryzen_smu not installed.\nInstall guide: %s", _RYZEN_SMU_WIKI)
        elif sb and not ryzen_smu_signed():
            log.error("ryzen_smu installed but not signed for Secure Boot.\nInstall guide: %s", _RYZEN_SMU_WIKI)
        else:
            log.error("ryzen_smu installed but not loaded.\nInstall guide: %s", _RYZEN_SMU_WIKI)
        log.warning("Running without SMU access — presets will not be applied until ryzen_smu is working.")
    elif not smu.version_ok():
        log.error(
            "ryzen_smu version %s is too old (minimum: %s).\nInstall guide: %s",
            smu.get_version(), smu.version_str(smu.MIN_VERSION), _RYZEN_SMU_WIKI,
        )
        log.warning("Running without SMU access — presets will not be applied until ryzen_smu is updated.")
    else:
        log.info("ryzen_smu driver ready (version %s).", smu.get_version())
        log.debug("SMN interface available: %s", smu.has_smn())

    daemon = PowerDaemon()

    def _on_ready():
        if cfg.get("Settings", "ApplyOnStart", "0") == "1":
            _apply_on_start(daemon)
        else:
            log.info("ApplyOnStart is disabled — no preset applied at startup.")
        auto_adaptive = (cfg.get("Adaptive", "enabled", "0") == "1"
                         or cfg.get("Settings", "AutoStartAdaptive", "0") == "1")
        if auto_adaptive:
            preset = cfg.get("Adaptive", "preset", "")
            if preset:
                log.info("Auto-starting Adaptive preset '%s' at startup.", preset)
                daemon._cmd_adaptive_start({"preset": preset})
            else:
                log.info("Auto Start Adaptive is on but no Adaptive preset is saved yet.")

    daemon.run(on_ready=_on_ready)


if __name__ == "__main__":
    main()