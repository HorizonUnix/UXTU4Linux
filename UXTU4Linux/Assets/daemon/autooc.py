from __future__ import annotations

import os
import threading
import time

from Assets.daemon.loops import _STOP_LOOP_TIMEOUT_S
from Assets.daemon.util import log, _apply_via_smu

_KMSG_PATH = "/dev/kmsg"
_MAX_CO = 30
_STEP_SIZE = 1
_STABLE_THRESHOLD = 8
_COOLDOWN_THRESHOLD = 4
_STEP_INTERVAL_S = 5


def _is_mce(line: str) -> bool:
    lower = line.lower()
    return "mce:" in lower or "machine check" in lower


def _co_arg(cmd: str, value: int) -> str:
    return f"--{cmd}={0x100000 - value}" if value > 0 else f"--{cmd}=0"


class _Controller:
    def __init__(self):
        self._offset = 0
        self._stable_ticks = 0
        self._cooldown_ticks = 0
        self._instability = False

    def signal_instability(self):
        self._instability = True

    def update(self):
        if self._instability:
            self._instability = False
            if self._offset > 0:
                self._offset = max(0, self._offset - _STEP_SIZE)
            self._stable_ticks = 0
            self._cooldown_ticks = _COOLDOWN_THRESHOLD
            return self._offset, True

        if self._cooldown_ticks > 0:
            self._cooldown_ticks -= 1
            return self._offset, False

        self._stable_ticks += 1
        if self._stable_ticks >= _STABLE_THRESHOLD and self._offset < _MAX_CO:
            self._offset = min(_MAX_CO, self._offset + _STEP_SIZE)
            self._stable_ticks = 0
            return self._offset, True

        return self._offset, False

    def reset(self):
        self._offset = 0
        self._stable_ticks = 0
        self._cooldown_ticks = 0
        self._instability = False

    @property
    def current(self) -> int:
        return self._offset


class AutoOCMixin:
    def _autooc_mce_body(self) -> None:
        try:
            fd = os.open(_KMSG_PATH, os.O_RDONLY | os.O_NONBLOCK)
        except OSError as exc:
            log.warning("AutoOC: cannot open %s — MCE monitoring disabled: %s", _KMSG_PATH, exc)
            return
        try:
            os.lseek(fd, 0, os.SEEK_END)
        except OSError:
            pass

        log.info("AutoOC: MCE monitor started.")
        while not self._stop_autooc_evt.wait(1.0):
            try:
                data = os.read(fd, 8192)
                if data:
                    text = data.decode("utf-8", errors="replace")
                    if _is_mce(text):
                        self._handle_mce(text.strip())
            except BlockingIOError:
                pass
            except OSError as exc:
                log.warning("AutoOC: read error: %s", exc)
                break
        os.close(fd)
        log.debug("AutoOC: MCE monitor exited.")

    def _handle_mce(self, line: str) -> None:
        with self._lock:
            self._autooc_mce_count += 1
            self._autooc_last_mce = time.strftime("%Y-%m-%d %H:%M:%S")
            log.warning("AutoOC: MCE detected — %s", line[:120])
            self._cpu_controller.signal_instability()
            self._igpu_controller.signal_instability()

    def _autooc_step_body(self) -> None:
        from Assets.core import config as cfg
        log.info("AutoOC: CO step loop started.")
        is_apu = cfg.get("Info", "Type") == "Amd_Apu"
        last_cpu = 0
        last_igpu = 0
        while not self._stop_autooc_step_evt.wait(_STEP_INTERVAL_S):
            with self._lock:
                cpu_val, cpu_changed = self._cpu_controller.update()
                igpu_val, igpu_changed = (
                    self._igpu_controller.update() if is_apu else (0, False)
                )

            parts = []
            if cpu_changed and cpu_val != last_cpu:
                last_cpu = cpu_val
                parts.append(_co_arg("set-coall", cpu_val))
            if is_apu and igpu_changed and igpu_val != last_igpu:
                last_igpu = igpu_val
                parts.append(_co_arg("set-cogfx", igpu_val))

            if parts:
                try:
                    output, _ = _apply_via_smu(" ".join(parts), "AutoOC")
                    log.debug("AutoOC: applied CO — %s", output[:80])
                except Exception as exc:
                    log.warning("AutoOC: apply error: %s", exc)

        log.debug("AutoOC: CO step loop exited.")

    def _cmd_autooc_start(self, _msg) -> dict:
        with self._lock:
            if self._autooc_running:
                return {"ok": True, "already": True}

        self._stop_autooc_evt.clear()
        self._stop_autooc_step_evt.clear()

        with self._lock:
            self._autooc_running = True

        self._autooc_mce_thread = threading.Thread(
            target=self._autooc_mce_body, daemon=True, name="uxtu-autooc-mce")
        self._autooc_step_thread = threading.Thread(
            target=self._autooc_step_body, daemon=True, name="uxtu-autooc-step")
        self._autooc_mce_thread.start()
        self._autooc_step_thread.start()
        return {"ok": True}

    def _cmd_autooc_stop(self, _msg) -> dict:
        self._stop_autooc_evt.set()
        self._stop_autooc_step_evt.set()
        if self._autooc_mce_thread and self._autooc_mce_thread.is_alive():
            self._autooc_mce_thread.join(timeout=_STOP_LOOP_TIMEOUT_S)
        if self._autooc_step_thread and self._autooc_step_thread.is_alive():
            self._autooc_step_thread.join(timeout=_STOP_LOOP_TIMEOUT_S)
        with self._lock:
            self._autooc_running = False
        log.info("AutoOC: stopped.")
        return {"ok": True}

    def _cmd_autooc_status(self, _msg) -> dict:
        with self._lock:
            return {
                "ok": True,
                "running": self._autooc_running,
                "mce_count": self._autooc_mce_count,
                "last_mce": self._autooc_last_mce,
                "cpu_offset": self._cpu_controller.current,
                "igpu_offset": self._igpu_controller.current,
            }

    def _cmd_autooc_reset(self, _msg) -> dict:
        with self._lock:
            had_co = self._cpu_controller.current > 0 or self._igpu_controller.current > 0
            self._autooc_mce_count = 0
            self._autooc_last_mce = None
            self._cpu_controller.reset()
            self._igpu_controller.reset()
        if had_co:
            _apply_via_smu("--set-coall=0 --set-cogfx=0", "AutoOC")
        log.info("AutoOC: controllers reset.")
        return {"ok": True}

    def start_autooc_monitor(self) -> None:
        self._cmd_autooc_start({})
