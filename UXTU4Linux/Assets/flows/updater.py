import json
import os
import shutil
import subprocess
import urllib.request
import zipfile

from Assets.core import config as cfg
from Assets.daemon.service import restart_service, service_running

_STABLE_URL = "https://github.com/HorizonUnix/UXTU4Linux/releases/latest/download/UXTU4Linux.zip"
_BETA_URL = "https://github.com/HorizonUnix/UXTU4Linux/releases/download/U4L-Beta/UXTU4Linux.zip"


def release_url(channel: str = "stable") -> str:
    return _BETA_URL if channel == "beta" else _STABLE_URL


def _ver_tuple(v: str) -> tuple:
    try:
        base = v.strip().lstrip("v")
        base = base.split("-", 1)[0].split("+", 1)[0]
        parts = [int(p) for p in base.split(".") if p != ""]
        return tuple(parts) if parts else (0,)
    except ValueError:
        return (0,)


def _release_url(url: str) -> str:
    return url.rstrip("/").split("/")[-1]


def get_latest_version() -> str:
    tag = _release_url(urllib.request.urlopen(cfg.LATEST_VER_URL, timeout=5).geturl())
    if not tag or not tag.lstrip("v")[:1].isdigit():
        raise ValueError(f"Unexpected version tag: {tag!r}")
    return tag


def get_changelog() -> str:
    req = urllib.request.Request(cfg.GITHUB_API_URL)
    data = json.loads(urllib.request.urlopen(req, timeout=5).read())
    return data.get("body", "No changelog available.")


def is_beta_build() -> bool:
    return "beta" in (cfg.LOCAL_BUILD or "").lower()


def beta_available() -> bool:
    api = cfg.GITHUB_API_URL.replace("/releases/latest", "/releases/tags/U4L-Beta")
    try:
        with urllib.request.urlopen(api, timeout=5) as resp:
            return resp.status == 200
    except Exception:
        return False


def perform_update(url: str = _STABLE_URL, status=None) -> dict:
    notify = status or (lambda _msg: None)

    script_dir = os.path.dirname(os.path.realpath(__file__))
    assets_dir = os.path.dirname(script_dir)
    src_dir = os.path.dirname(assets_dir)
    install_dir = os.path.dirname(src_dir)

    zip_path = os.path.join(install_dir, "UXTU4Linux.zip")
    new_folder = os.path.join(install_dir, "UXTU4Linux_new")
    config_bak = os.path.join(install_dir, "config.ini.bak")
    presets_bak = os.path.join(install_dir, "custom.json.bak")
    config_src = os.path.join(assets_dir, "config.ini")
    presets_src = os.path.join(assets_dir, "custom.json")

    def _sudo(*args: str) -> int:
        return subprocess.run(["sudo", "-n", *args]).returncode

    try:
        if os.path.exists(config_src):
            shutil.copy2(config_src, config_bak)
        if os.path.exists(presets_src):
            shutil.copy2(presets_src, presets_bak)

        notify("Downloading update…")
        urllib.request.urlretrieve(url, zip_path)

        notify("Extracting…")
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(new_folder)

        notify("Installing…")
        src_bak = src_dir + ".bak"
        if _sudo("mv", src_dir, src_bak) != 0:
            raise PermissionError(f"Could not back up {src_dir}.")

        inner = os.path.join(new_folder, "UXTU4Linux")
        if _sudo("mv", inner, src_dir) != 0:
            _sudo("mv", src_bak, src_dir)
            raise PermissionError(f"Could not install the new release into {src_dir}.")

        _sudo("rm", "-rf", src_bak)
        _sudo("rm", "-rf", new_folder)

        launch = os.path.join(src_dir, "UXTU4Linux.py")
        if os.path.exists(launch):
            subprocess.run(["chmod", "+x", launch], check=True)

        new_assets = os.path.join(src_dir, "Assets")
        if os.path.exists(config_bak):
            shutil.move(config_bak, os.path.join(new_assets, "config.ini"))
        if os.path.exists(presets_bak):
            shutil.move(presets_bak, os.path.join(new_assets, "custom.json"))

        if os.path.exists(zip_path):
            os.remove(zip_path)

        if service_running():
            notify("Restarting daemon…")
            restart_service()

        notify("Update complete. Relaunching…")
        return {"ok": True}

    except Exception as e:
        return {"ok": False, "error": str(e)}