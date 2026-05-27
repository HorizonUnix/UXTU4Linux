"""
config.py
"""
import os
from configparser import ConfigParser
from pathlib import Path


LOCAL_VERSION = "0.6.03"
LOCAL_BUILD   = "6-linux-27May26-r3"

GITHUB_API_URL = "https://api.github.com/repos/HorizonUnix/UXTU4Linux/releases/latest"
LATEST_VER_URL = "https://github.com/HorizonUnix/UXTU4Linux/releases/latest"

_ROOT      = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
ASSETS_DIR = os.path.join(_ROOT, "Assets")

CONFIG_PATH         = os.path.join(ASSETS_DIR, "config.ini")
CUSTOM_PRESETS_PATH = Path(ASSETS_DIR) / "custom_presets.json"

RYZENADJ = os.path.join(ASSETS_DIR, "Linux", "ryzenadj")
DMIDECODE = "dmidecode"
KERNEL    = os.uname().sysname

VENV_DIR    = "/opt/uxtu4linux/venv"
VENV_PYTHON = os.path.join(VENV_DIR, "bin", "python3")

ZMQ_SOCKET_PATH = "/run/uxtu4linux.sock"
ZMQ_SOCKET_ADDR = f"ipc://{ZMQ_SOCKET_PATH}"

MIN_INTERVAL_SECONDS: int = 1
MAX_INTERVAL_SECONDS: int = 86400

_cfg           = ConfigParser()
_loaded_preset = ""


def parse_interval(raw, default: int = 3) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = default
    return max(MIN_INTERVAL_SECONDS, min(MAX_INTERVAL_SECONDS, value))


def set_loaded_preset(name: str) -> None:
    global _loaded_preset
    _loaded_preset = name


def get_loaded_preset() -> str:
    return _loaded_preset


def load() -> ConfigParser:
    _cfg.read(CONFIG_PATH)
    return _cfg


def get(section: str, key: str, fallback: str = "") -> str:
    return _cfg.get(section, key, fallback=fallback)


def set_config(section: str, key: str, value: str) -> None:
    if not _cfg.has_section(section):
        _cfg.add_section(section)
    _cfg.set(section, key, value)


def save() -> None:
    with open(CONFIG_PATH, "w") as f:
        _cfg.write(f)


def ensure_sections(*sections) -> None:
    for s in sections:
        if not _cfg.has_section(s):
            _cfg.add_section(s)


def is_debug() -> bool:
    return get("Settings", "Debug", "1") == "1"


def instance() -> ConfigParser:
    return _cfg


REQUIRED: dict[str, list[str]] = {
    "User":        ["mode"],
    "Settings":    ["time", "reapply", "applyonstart", "softwareupdate", "debug"],
    "Info":        ["cpu", "signature", "architecture", "family", "type"],
    "Automations": ["enabled", "onac", "onbattery"],
}