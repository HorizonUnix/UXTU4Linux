import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile

from . import config as cfg
from .ui import clear, pause, confirm, _B, _D, _Y, _R, _SEP_W
from .service import restart_service, service_running

_STABLE_URL = "https://github.com/HorizonUnix/UXTU4Linux/releases/latest/download/UXTU4Linux.zip"
_BETA_URL = "https://github.com/HorizonUnix/UXTU4Linux/releases/download/U4L-Beta/UXTU4Linux.zip"


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


def get_beta_commit() -> str | None:
    req = urllib.request.Request(
        "https://api.github.com/repos/HorizonUnix/UXTU4Linux/git/ref/tags/U4L-Beta",
        headers={"Accept": "application/vnd.github+json"},
    )
    data = json.loads(urllib.request.urlopen(req, timeout=5).read())
    sha = data.get("object", {}).get("sha", "")
    return sha[:7] if sha else None


def _do_update(url: str = _STABLE_URL) -> None:

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
        return subprocess.run(["sudo", *args]).returncode

    try:
        if os.path.exists(config_src):
            shutil.copy2(config_src, config_bak)
        if os.path.exists(presets_src):
            shutil.copy2(presets_src, presets_bak)

        print("  Downloading update...")
        urllib.request.urlretrieve(url, zip_path)

        print("  Extracting...")
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(new_folder)

        src_bak = src_dir + ".bak"
        if _sudo("mv", src_dir, src_bak) != 0:
            raise PermissionError(f"Could not back up {src_dir} — try running with sudo")

        inner = os.path.join(new_folder, "UXTU4Linux")
        if _sudo("mv", inner, src_dir) != 0:
            _sudo("mv", src_bak, src_dir)
            raise PermissionError(f"Could not move new release into {src_dir}")

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

        print("  Restarting daemon...")
        if service_running():
            restart_service()

        print("  Update complete. Relaunching — please close this window.")
        os.execv(sys.executable, [sys.executable, launch])

    except Exception as e:
        print(f"  Update failed: {e}")
        pause()


def show_updater() -> None:
    try:
        latest = get_latest_version()
        changelog = get_changelog()
    except Exception as e:
        clear()
        print(f"  Could not fetch release info: {e}")
        pause()
        return
    subtitle = (
        f"{_B}Software Update{_R}\n\n"
        f"A new update is available!\n"
        f"Latest version : {latest}\n\n"
        f"{_B}Changelog{_R}\n"
        f"{_D}{'─' * _SEP_W}{_R}\n"
        f"{changelog}"
    )
    if confirm("Update now?", subtitle=subtitle):
        _do_update()


def show_beta_updater() -> None:
    subtitle = (
        f"{_Y}Warning{_R}\n\n"
        "This will replace your current installation with the latest beta build.\n"
        "Beta builds are unstable and may be incomplete or broken."
    )
    if confirm("Switch to beta build?", subtitle=subtitle):
        _do_update(_BETA_URL)


def check_updates() -> None:
    MAX_RETRIES = 2
    clear()
    latest = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            latest = get_latest_version()
            break
        except Exception as e:
            print(f"  Could not fetch version (attempt {attempt}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES:
                time.sleep(2)

    if latest is None:
        return

    local = _ver_tuple(cfg.LOCAL_VERSION)
    remote = _ver_tuple(latest)

    if local < remote:
        show_updater()
    elif local > remote:
        subtitle = (
            f"{_B}Beta Program{_R}\n\n"
            "This build is newer than the latest release.\n"
            "It may be unstable and is intended for testing only."
        )
        if not confirm("Continue?", subtitle=subtitle):
            sys.exit("Quitting.")