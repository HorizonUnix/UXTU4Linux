"""
updater.py
"""
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile

from . import config as cfg
from .ui import clear, pause
from .service import restart_service, service_running


def _ver_tuple(v: str) -> tuple:
    try:
        return tuple(int(x) for x in v.strip().lstrip("v").split("."))
    except ValueError:
        return (0,)


def get_latest_version() -> str:
    url = urllib.request.urlopen(cfg.LATEST_VER_URL).geturl()
    return url.rstrip("/").split("/")[-1]


def get_changelog() -> str:
    req  = urllib.request.Request(cfg.GITHUB_API_URL)
    data = json.loads(urllib.request.urlopen(req).read())
    return data.get("body", "No changelog available.")


def _do_update() -> None:
    url = "https://github.com/HorizonUnix/UXTU4Linux/releases/latest/download/UXTU4Linux.zip"

    script_dir  = os.path.dirname(os.path.realpath(__file__))
    assets_dir  = os.path.dirname(script_dir)
    src_dir     = os.path.dirname(assets_dir)
    install_dir = os.path.dirname(src_dir)

    zip_path   = os.path.join(install_dir, "UXTU4Linux.zip")
    new_folder = os.path.join(install_dir, "UXTU4Linux_new")
    config_bak = os.path.join(install_dir, "config.ini.bak")

    def _sudo(*args: str) -> int:
        return subprocess.run(["sudo", *args]).returncode

    try:
        if os.path.exists(cfg.CONFIG_PATH):
            shutil.copy2(cfg.CONFIG_PATH, config_bak)

        print("Downloading update...")
        urllib.request.urlretrieve(url, zip_path)

        print("Extracting...")
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(new_folder)

        if _sudo("rm", "-rf", src_dir) != 0:
            raise PermissionError(f"Could not remove {src_dir} — try running with sudo")

        inner = os.path.join(new_folder, "UXTU4Linux")
        if _sudo("mv", inner, src_dir) != 0:
            raise PermissionError(f"Could not move new release into {src_dir}")

        _sudo("rm", "-rf", new_folder)

        launch = os.path.join(src_dir, "UXTU4Linux.py")
        ryzen  = os.path.join(src_dir, "Assets", "Linux", "ryzenadj")
        for path in (launch, ryzen):
            if os.path.exists(path):
                subprocess.run(["chmod", "+x", path], check=True)

        new_config = os.path.join(src_dir, "Assets", "config.ini")
        if os.path.exists(config_bak):
            shutil.move(config_bak, new_config)

        if os.path.exists(zip_path):
            os.remove(zip_path)

        print("Restarting daemon...")
        if service_running():
            restart_service()

        print("Update complete. Relaunching - please close this window.")
        os.execv(sys.executable, [sys.executable, launch])

    except Exception as e:
        print(f"Update failed: {e}")
        pause()
        

def show_updater() -> None:
    while True:
        clear()
        try:
            latest    = get_latest_version()
            changelog = get_changelog()
        except Exception as e:
            print(f"Could not fetch release info: {e}")
            pause()
            return
        print("─" * 15 + " Software Update " + "─" * 15)
        print("A new update is available!\n")
        print(f"Latest version : {latest}")
        print(f"\nChangelog:\n{changelog}\n")
        c = input("Update now? (y/n): ").strip().lower()
        if c == "y":
            _do_update()
            raise SystemExit
        elif c == "n":
            print("Skipping update.")
            break
        else:
            print("Please enter 'y' or 'n'.")


def check_updates() -> None:
    MAX_RETRIES = 10
    clear()
    latest = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            latest = get_latest_version()
            break
        except Exception as e:
            print(f"Could not fetch version (attempt {attempt}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES:
                time.sleep(5)

    if latest is None:
        clear()
        print("Failed to fetch the latest version after multiple retries.")
        if input("Skip the update check and continue? (y/n): ").strip().lower() != "y":
            sys.exit("Quitting.")
        return

    local  = _ver_tuple(cfg.LOCAL_VERSION)
    remote = _ver_tuple(latest)

    if local < remote:
        show_updater()
    elif local > remote:
        clear()
        print("─" * 15 + " Beta Program " + "─" * 15)
        print("This build is newer than the latest release.")
        print("It may be unstable and is intended for testing only.\n")
        if input("Continue? (y/n): ").strip().lower() != "y":
            sys.exit("Quitting.")