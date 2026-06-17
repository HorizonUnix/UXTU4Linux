#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="/opt/uxtu4linux"
VENV_DIR="$INSTALL_DIR/venv"
VENV_PYTHON="$VENV_DIR/bin/python3"
SRC_DIR="$INSTALL_DIR/src"
BIN_WRAPPER="/usr/local/bin/uxtu4linux"
SERVICE_NAME="uxtu4linux.service"
SERVICE_FILE="/etc/systemd/system/$SERVICE_NAME"
RELEASE_URL="https://github.com/HorizonUnix/UXTU4Linux/releases/latest/download/UXTU4Linux.zip"
TMP_DIR="$(mktemp -d)"

_R='\033[0m'; _B='\033[1m'; _D='\033[2m'; _G='\033[32m'; _Y='\033[33m'; _E='\033[31m'

info() { echo -e "  ${_D}· $*${_R}"; }
ok()   { echo -e "  ${_G}✓${_R} $*"; }
warn() { echo -e "  ${_Y}!${_R} $*"; }
die()  { echo -e "\n  ${_E}✗${_R} $*\n"; exit 1; }
hr()   { echo -e "  ${_D}$(printf '─%.0s' {1..58})${_R}"; }

trap '[[ -n "$TMP_DIR" && ( "$TMP_DIR" == /tmp/* || "$TMP_DIR" == /var/tmp/* ) ]] && rm -rf -- "$TMP_DIR"' EXIT

[[ $EUID -eq 0 ]] && die "Do not run as root — run as your normal user:  bash install.sh"

CURRENT_USER="$(whoami)"
CURRENT_GROUP="$(id -gn)"

resolve_release_tag() {
    local tag=""
    if command -v curl &>/dev/null; then
        tag="$(curl -fsSL -o /dev/null -w '%{url_effective}' \
            "https://github.com/HorizonUnix/UXTU4Linux/releases/latest" 2>/dev/null \
            | sed 's|.*/tag/||')" || true
    elif command -v wget &>/dev/null; then
        tag="$(wget -q --server-response --spider \
            "https://github.com/HorizonUnix/UXTU4Linux/releases/latest" 2>&1 \
            | awk '/Location:/{print $2}' | tail -1 | sed 's|.*/tag/||')" || true
    fi
    echo "${tag:-latest}"
}

detect_pm() {
    if   command -v apt-get &>/dev/null; then echo "apt"
    elif command -v dnf     &>/dev/null; then echo "dnf"
    elif command -v yum     &>/dev/null; then echo "yum"
    elif command -v pacman  &>/dev/null; then echo "pacman"
    elif command -v zypper  &>/dev/null; then echo "zypper"
    else die "Unsupported distro — see manual installation: https://github.com/HorizonUnix/UXTU4Linux/wiki/Linux-Installation"
    fi
}

check_systemd() {
    if ! command -v systemctl &>/dev/null; then
        echo ""
        warn "systemd is not available on this system."
        info "This installer requires systemd to manage the background daemon."
        info "For non-systemd systems, see the manual installation guide:"
        info "https://github.com/HorizonUnix/UXTU4Linux/wiki/Linux-Installation"
        echo ""
        die "Unsupported init system."
    fi
    ok "systemd detected."
}

ensure_python310() {
    local py=""
    for candidate in python3.14 python3.13 python3.12 python3.11 python3.10 python3; do
        if command -v "$candidate" &>/dev/null; then
            if "$candidate" -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" 2>/dev/null; then
                py="$candidate"
                break
            fi
        fi
    done

    if [[ -n "$py" ]]; then
        ok "Python: $($py --version)"
        return
    fi

    warn "Python 3.10+ not found — installing..."
    case "$1" in
        apt)
            if grep -qi "ubuntu" /etc/os-release 2>/dev/null; then
                sudo apt-get install -y -qq software-properties-common &>/dev/null
                sudo add-apt-repository -y ppa:deadsnakes/ppa &>/dev/null
                sudo apt-get update -qq &>/dev/null
            fi
            local best=""
            for v in 3.14 3.13 3.12 3.11 3.10; do
                if sudo apt-get install -y -qq --dry-run "python${v}" "python${v}-venv" &>/dev/null; then
                    best="$v"; break
                fi
            done
            [[ -n "$best" ]] || die "No Python 3.10+ package found in apt repos."
            sudo apt-get install -y -qq "python${best}" "python${best}-venv" &>/dev/null \
                || die "Failed to install python${best}."
            ;;
        dnf)
            sudo dnf install -y -q python3 python3-pip &>/dev/null \
                || die "Failed to install Python via dnf."
            ;;
        yum)
            sudo yum install -y -q python3 python3-pip &>/dev/null \
                || die "Failed to install Python via yum."
            ;;
        pacman)
            sudo pacman -Sy --noconfirm --quiet python &>/dev/null \
                || die "Failed to install Python via pacman."
            ;;
        zypper)
            sudo zypper install -y --quiet python3 python3-pip &>/dev/null \
                || die "Failed to install Python via zypper."
            ;;
    esac

    for candidate in python3.14 python3.13 python3.12 python3.11 python3.10 python3; do
        if command -v "$candidate" &>/dev/null; then
            if "$candidate" -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" 2>/dev/null; then
                ok "Python: $($candidate --version)"
                return
            fi
        fi
    done

    die "Could not install Python 3.10+. Install it manually and re-run."
}

install_deps() {
    info "Installing system dependencies..."
    case "$1" in
        apt)
            export DEBIAN_FRONTEND=noninteractive
            sudo apt-get update -qq &>/dev/null
            sudo apt-get install -y -qq --no-install-recommends \
                python3 python3-venv python3-pip \
                dmidecode wget unzip curl &>/dev/null
            ;;
        dnf)
            sudo dnf install -y -q \
                python3 python3-pip \
                dmidecode wget unzip curl &>/dev/null
            ;;
        yum)
            sudo yum install -y -q \
                python3 python3-pip \
                dmidecode wget unzip curl &>/dev/null
            ;;
        pacman)
            sudo pacman -Sy --noconfirm --quiet \
                python python-pip \
                dmidecode wget unzip curl &>/dev/null
            ;;
        zypper)
            sudo zypper install -y --quiet \
                python3 python3-pip \
                dmidecode wget unzip curl &>/dev/null
            ;;
    esac
    ok "Dependencies installed."
}

download_release() {
    info "Downloading release..."
    local err="$TMP_DIR/dl.err"
    if command -v wget &>/dev/null; then
        local -a wget_progress_flag=()
        if ! wget --version 2>&1 | grep -q "GNU Wget2"; then
            wget_progress_flag+=(--show-progress)
        fi
        wget -q "${wget_progress_flag[@]}" -O "$TMP_DIR/release.zip" "$RELEASE_URL" 2>"$err" \
            || { cat "$err" >&2; die "Download failed."; }
    elif command -v curl &>/dev/null; then
        curl -fsSL -o "$TMP_DIR/release.zip" "$RELEASE_URL" 2>"$err" \
            || { cat "$err" >&2; die "Download failed."; }
    else
        die "Neither wget nor curl found."
    fi
    ok "Download complete."
}

install_files() {
    info "Extracting files..."
    unzip -q "$TMP_DIR/release.zip" -d "$TMP_DIR/extracted" || die "Failed to extract archive."
    local src
    src="$(find "$TMP_DIR/extracted" -maxdepth 1 -mindepth 1 -type d | head -1)"
    [[ -d "$src" ]] || die "Could not find source directory in archive."

    sudo mkdir -p "$INSTALL_DIR"
    sudo chown "$CURRENT_USER:$CURRENT_GROUP" "$INSTALL_DIR"

    sudo rm -rf "$SRC_DIR"
    cp -r "$src" "$SRC_DIR"
    ok "Installed to $SRC_DIR"
}

patch_entry_point() {
    info "Configuring entry point..."
    [[ -f "$SRC_DIR/UXTU4Linux.py" ]] || die "UXTU4Linux.py not found in $SRC_DIR"
    sed -i "1s|.*|#!${VENV_PYTHON}|" "$SRC_DIR/UXTU4Linux.py" || die "Failed to patch shebang."
    python3 - "$SRC_DIR/UXTU4Linux.py" "${VENV_PYTHON}" <<'PYEOF' || die "Guard injection failed."
import sys
path, venv = sys.argv[1], sys.argv[2]
guard = (
    "import sys as _sys, os as _os\n"
    f"_venv = '{venv}'\n"
    "if _os.path.isfile(_venv) and _os.path.realpath(_sys.executable) != _os.path.realpath(_venv):\n"
    "    _os.execv(_venv, [_venv] + _sys.argv)\n"
)
with open(path, "r") as f:
    lines = f.readlines()
lines.insert(1, guard)
with open(path, "w") as f:
    f.writelines(lines)
PYEOF
    ok "Entry point configured."
}

find_python_executable() {
    command -v python3.14 || command -v python3.13 || command -v python3.12 || \
    command -v python3.11 || command -v python3.10 || command -v python3 || true
}

setup_venv() {
    info "Setting up Python environment..."
    local py
    py="$(find_python_executable)"
    [[ -n "$py" ]] || die "python3 not found."

    if [[ -d "$VENV_DIR" ]] && ! "$VENV_PYTHON" -c "" &>/dev/null; then
        warn "Broken venv — recreating..."
        rm -rf "$VENV_DIR"
    fi

    if [[ ! -d "$VENV_DIR" ]]; then
        "$py" -m venv --without-pip "$VENV_DIR" &>/dev/null \
            || "$py" -m venv "$VENV_DIR" &>/dev/null \
            || die "Failed to create virtual environment."
        "$VENV_PYTHON" -m ensurepip --upgrade --default-pip &>/dev/null || true
    fi

    "$VENV_PYTHON" -m pip install --quiet --no-cache-dir --upgrade pip &>/dev/null || true

    if [[ -f "$SRC_DIR/requirements.txt" ]]; then
        "$VENV_PYTHON" -m pip install --quiet --no-cache-dir -r "$SRC_DIR/requirements.txt" &>/dev/null \
            || die "Failed to install Python requirements."
    else
        "$VENV_PYTHON" -m pip install --quiet --no-cache-dir pyzmq textual &>/dev/null \
            || die "Failed to install pyzmq, textual."
    fi
    ok "Python environment ready."
}

set_permissions() {
    info "Setting permissions..."
    chmod +x "$SRC_DIR/UXTU4Linux.py"
    ok "Permissions set."
}

install_wrapper() {
    info "Installing launcher..."
    sudo tee "$BIN_WRAPPER" > /dev/null <<EOF
#!/usr/bin/env bash
exec "$VENV_PYTHON" "$SRC_DIR/UXTU4Linux.py" "\$@"
EOF
    sudo chmod +x "$BIN_WRAPPER"
    [[ -x "$BIN_WRAPPER" ]] || die "Failed to install launcher at $BIN_WRAPPER"
    ok "Launcher installed: $BIN_WRAPPER"
}

daemon_is_installed() {
    [[ -f "$SERVICE_FILE" ]]
}

restart_daemon() {
    info "Restarting daemon..."
    sudo systemctl daemon-reload
    sudo systemctl restart "$SERVICE_NAME" \
        && ok "Daemon restarted." \
        || warn "Could not restart daemon — run: sudo systemctl status $SERVICE_NAME"
}

print_logo() {
    echo ""
    echo -e "${_B}+----------------------------------------------------------+"
    echo -e "|  _   ___  _______ _   _ _  _   _     _                   |"
    echo -e "| | | | \ \/ /_   _| | | | || | | |   (_)_ __  _   ___  __ |"
    echo -e "| | | | |\  /  | | | | | | || |_| |   | | '_ \| | | \ \/ / |"
    echo -e "| | |_| |/  \  | | | |_| |__   _| |___| | | | | |_| |>  <  |"
    echo -e "|  \___//_/\_\ |_|  \___/   |_| |_____|_|_| |_|\__,_/_/\_\ |"
    echo -e "+----------------------------------------------------------+${_R}"
    echo ""
}

print_banner() {
    local tag="$1"
    clear
    print_logo
    echo -e "  ${_D}Installer  ·  ${tag}${_R}"
    hr
    echo -e "  ${_D}Install  : $INSTALL_DIR${_R}"
    echo -e "  ${_D}Source   : $SRC_DIR${_R}"
    echo -e "  ${_D}Launcher : $BIN_WRAPPER${_R}"
    hr
    echo ""
}

uninstall() {
    clear
    print_logo
    echo -e "  ${_D}Uninstaller${_R}"
    hr
    echo ""
    warn "This will completely remove UXTU4Linux:"
    info "Service  : $SERVICE_FILE"
    info "Launcher : $BIN_WRAPPER"
    info "Files    : $INSTALL_DIR"
    echo ""
    read -rp "  Continue? [y/N] " reply
    [[ "$reply" =~ ^[Yy]$ ]] || { echo ""; info "Cancelled."; echo ""; exit 0; }
    echo ""
    hr
    echo ""

    if command -v systemctl &>/dev/null && [[ -f "$SERVICE_FILE" ]]; then
        info "Removing daemon service..."
        sudo systemctl stop "$SERVICE_NAME" 2>/dev/null || true
        sudo systemctl disable "$SERVICE_NAME" 2>/dev/null || true
        sudo rm -f "$SERVICE_FILE"
        sudo systemctl daemon-reload 2>/dev/null || true
        ok "Daemon service removed."
    else
        info "No daemon service to remove."
    fi

    if [[ -e "$BIN_WRAPPER" ]]; then
        sudo rm -f "$BIN_WRAPPER"
        ok "Launcher removed: $BIN_WRAPPER"
    else
        info "No launcher to remove."
    fi

    if [[ -d "$INSTALL_DIR" ]]; then
        sudo rm -rf "$INSTALL_DIR"
        ok "Files removed: $INSTALL_DIR"
    else
        info "No installation files to remove."
    fi

    sudo rm -f /run/uxtu4linux.sock /run/uxtu4linux_daemon.lock 2>/dev/null || true
    rm -f /tmp/uxtu4linux_tui.lock 2>/dev/null || true

    echo ""
    hr
    ok "UXTU4Linux has been uninstalled."
    hr
    echo ""
}

run_setup() {
    echo ""
    hr
    ok "Installation complete."
    hr
    echo ""

    if daemon_is_installed; then
        restart_daemon
        echo ""
    fi

    echo -e "  ${_G}Done!${_R} Run the app with:"
    echo ""
    echo -e "    ${_B}uxtu4linux${_R}"
    echo ""
}

main() {
    case "${1:-}" in
        --uninstall|-u)
            uninstall
            return
            ;;
        --help|-h)
            echo "Usage: bash install.sh [--uninstall]"
            echo "  (no args)      Install or update UXTU4Linux."
            echo "  --uninstall    Remove UXTU4Linux (service, launcher, and files)."
            return
            ;;
    esac

    local tag
    tag="$(resolve_release_tag)"
    print_banner "$tag"

    local pm
    pm="$(detect_pm)"
    info "Package manager: $pm"
    check_systemd

    if daemon_is_installed; then
        echo ""
        warn "Existing installation found — updating files and restarting daemon."
    fi

    hr
    echo ""

    ensure_python310 "$pm"
    install_deps "$pm"
    download_release
    install_files
    patch_entry_point
    setup_venv
    set_permissions
    install_wrapper

    run_setup
}

main "$@"
