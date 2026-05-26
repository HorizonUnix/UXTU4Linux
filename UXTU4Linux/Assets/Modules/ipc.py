"""
ipc.py
"""

from __future__ import annotations

import json
import threading
import zmq

from . import config as cfg


class DaemonClient:
    TIMEOUT_MS = 5_000

    def __init__(self, addr: str = cfg.ZMQ_SOCKET_ADDR) -> None:
        self._addr = addr
        self._ctx  = zmq.Context.instance()
        self._sock: zmq.Socket | None = None
        self._lock = threading.Lock()

    def _get_sock(self) -> zmq.Socket:
        if self._sock is None:
            sock = self._ctx.socket(zmq.REQ)
            sock.setsockopt(zmq.RCVTIMEO, self.TIMEOUT_MS)
            sock.setsockopt(zmq.SNDTIMEO, self.TIMEOUT_MS)
            sock.setsockopt(zmq.LINGER,   0)
            sock.connect(self._addr)
            self._sock = sock
        return self._sock

    def _reset_sock(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except zmq.ZMQError:
                pass
            self._sock = None

    def _send(self, cmd: dict) -> dict | None:
        with self._lock:
            try:
                sock = self._get_sock()
                sock.send_string(json.dumps(cmd))
                return json.loads(sock.recv_string())
            except zmq.ZMQError:
                self._reset_sock()
                return None

    def close(self) -> None:
        with self._lock:
            self._reset_sock()

    def ping(self) -> bool:
        r = self._send({"cmd": "ping"})
        return r is not None and r.get("ok", False)

    def apply(self, args: str, mode: str) -> dict:
        return self._send({"cmd": "apply", "args": args, "mode": mode}) \
            or {"ok": False, "error": "daemon not responding"}

    def apply_loop(self, args: str, mode: str, interval: int, automation: bool) -> dict:
        return self._send({
            "cmd":        "apply_loop",
            "args":       args,
            "mode":       mode,
            "interval":   interval,
            "automation": automation,
        }) or {"ok": False, "error": "daemon not responding"}

    def stop_loop(self) -> dict:
        return self._send({"cmd": "stop_loop"}) or {"ok": False}

    def status(self) -> dict:
        return self._send({"cmd": "status"}) or {
            "ok":          False,
            "running_loop": False,
            "mode":        "?",
            "on_ac":       False,
            "automation":  False,
        }

    def apply_saved(self) -> dict:
        return self._send({"cmd": "apply_saved"}) \
            or {"ok": False, "error": "daemon not responding"}

    def shutdown(self) -> dict:
        return self._send({"cmd": "shutdown"}) or {"ok": False}

    def dmidecode(self, dmi_type: str) -> str:
        r = self._send({"cmd": "dmidecode", "type": dmi_type})
        if r and r.get("ok"):
            return r["output"]
        return ""

    def reload_config(self) -> dict:
        return self._send({"cmd": "reload_config"}) or {"ok": False}

    def apply_custom_args(self, args: str) -> dict:
        return self._send({"cmd": "apply_custom_args", "args": args}) \
            or {"ok": False, "error": "daemon not responding"}

    def list_custom_presets(self) -> list[str]:
        r = self._send({"cmd": "list_custom_presets"})
        if r and r.get("ok"):
            return r.get("names", [])
        return []


_client: DaemonClient | None = None


def get_client() -> DaemonClient:
    global _client
    if _client is None:
        _client = DaemonClient()
    return _client


def require_daemon() -> DaemonClient:
    client = get_client()
    if not client.ping():
        raise RuntimeError(
            "Daemon is not running.\n"
            "Enable it with:  sudo systemctl enable --now uxtu4linux.service"
        )
    return client