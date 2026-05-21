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

_R='\033[0m'; _C='\033[0;96m'; _G='\033[0;32m'; _Y='\033[1;33m'; _E='\033[0;31m'
info() { echo -e "${_C}  ·${_R} $*"; }
ok()   { echo -e "${_G}  ✓${_R} $*"; }
warn() { echo -e "${_Y}  !${_R} $*"; }
die()  { echo -e "${_E}  ✗${_R} $*"; exit 1; }
hr()   { echo -e "  $(printf '─%.0s' {1..58})"; }

trap '[[ -n "$TMP_DIR" && ( "$TMP_DIR" == /tmp/* || "$TMP_DIR" == /var/tmp/* ) ]] && rm -rf -- "$TMP_DIR"' EXIT

[[ $EUID -eq 0 ]] && die "Do not run as root. Run as your normal user:  bash install.sh"

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
    else die "Unsupported distro — https://github.com/HorizonUnix/UXTU4Linux/wiki/Linux-Installation#manual-installation"
    fi
}

check_systemd() {
    if ! command -v systemctl &>/dev/null; then
        echo ""
        warn "systemd is not available on this system."
        echo ""
        echo "  This installer requires systemd to manage the daemon service."
        echo "  For non-systemd distros, follow the manual installation guide:"
        echo ""
        echo -e "  ${_C}https://github.com/HorizonUnix/UXTU4Linux/wiki/Linux-Installation#manual-installation${_R}"
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
        ok "Python OK: $($py --version)"
        return
    fi

    warn "Python 3.10+ not found — installing latest available..."
    case "$1" in
        apt)
            if grep -qi "ubuntu" /etc/os-release 2>/dev/null; then
                sudo apt-get install -y -qq software-properties-common 2>/dev/null
                sudo add-apt-repository -y ppa:deadsnakes/ppa 2>/dev/null
                sudo apt-get update -qq 2>/dev/null
            fi
            local best=""
            for v in 3.14 3.13 3.12 3.11 3.10; do
                if sudo apt-get install -y -qq --dry-run "python${v}" "python${v}-venv" \
                        &>/dev/null 2>&1; then
                    best="$v"; break
                fi
            done
            [[ -n "$best" ]] || die "No Python 3.10+ package found in apt repos."
            sudo apt-get install -y -qq "python${best}" "python${best}-venv" 2>/dev/null \
                || die "Failed to install python${best}."
            ;;
        dnf)
            sudo dnf install -y -q python3 python3-pip 2>/dev/null \
                || die "Failed to install Python via dnf."
            ;;
        yum)
            sudo yum install -y -q python3 python3-pip 2>/dev/null \
                || die "Failed to install Python via yum."
            ;;
        pacman)
            sudo pacman -Sy --noconfirm --quiet python 2>/dev/null \
                || die "Failed to install Python via pacman."
            ;;
        zypper)
            sudo zypper install -y --quiet python3 python3-pip 2>/dev/null \
                || die "Failed to install Python via zypper."
            ;;
    esac

    for candidate in python3.14 python3.13 python3.12 python3.11 python3.10 python3; do
        if command -v "$candidate" &>/dev/null; then
            if "$candidate" -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" 2>/dev/null; then
                ok "Python OK: $($candidate --version)"
                return
            fi
        fi
    done

    die "Could not install Python 3.10+. Install it manually and re-run."
}

install_deps() {
    info "Installing dependencies (requires sudo)..."
    case "$1" in
        apt)
            export DEBIAN_FRONTEND=noninteractive
            sudo apt-get update -qq 2>/dev/null
            sudo apt-get install -y -qq --no-install-recommends \
                python3 python3-venv python3-pip \
                dmidecode wget unzip curl \
                2>/dev/null
            ;;
        dnf)
            sudo dnf install -y -q python3 python3-pip \
                dmidecode wget unzip curl \
                2>/dev/null
            ;;
        yum)
            sudo yum install -y -q python3 python3-pip \
                dmidecode wget unzip curl \
                2>/dev/null
            ;;
        pacman)
            sudo pacman -Sy --noconfirm --quiet \
                python python-pip \
                dmidecode wget unzip curl \
                2>/dev/null
            ;;
        zypper)
            sudo zypper install -y --quiet python3 python3-pip \
                dmidecode wget unzip curl \
                2>/dev/null
            ;;
    esac
    ok "Done."
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
    ok "Done."
}

install_files() {
    info "Extracting..."
    unzip -q "$TMP_DIR/release.zip" -d "$TMP_DIR/extracted" || die "Failed to extract."
    local src
    src="$(find "$TMP_DIR/extracted" -maxdepth 1 -mindepth 1 -type d | head -1)"
    [[ -d "$src" ]] || die "Couldn't find source dir in zip."

    sudo mkdir -p "$INSTALL_DIR"
    sudo chown "$CURRENT_USER:$CURRENT_GROUP" "$INSTALL_DIR"

    sudo rm -rf "$SRC_DIR"
    cp -r "$src" "$SRC_DIR"
    ok "Installed to $SRC_DIR"
}

patch_entry_point() {
    info "Patching entry point..."
    [[ -f "$SRC_DIR/UXTU4Linux.py" ]] || die "UXTU4Linux.py not found in $SRC_DIR"
    sed -i "1s|.*|#!${VENV_PYTHON}|" "$SRC_DIR/UXTU4Linux.py" || die "sed failed."
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
    ok "Done."
}

find_python_executable() {
    command -v python3.14 || command -v python3.13 || command -v python3.12 || command -v python3.11 || command -v python3.10 || command -v python3 || true
}

setup_venv() {
    info "Setting up Python venv..."
    local py
    py="$(find_python_executable)"
    [[ -n "$py" ]] || die "python3 not found."

    if [[ -d "$VENV_DIR" ]] && ! "$VENV_PYTHON" -c "" &>/dev/null 2>&1; then
        warn "Broken venv — recreating..."
        rm -rf "$VENV_DIR"
    fi

    if [[ ! -d "$VENV_DIR" ]]; then
        "$py" -m venv --without-pip "$VENV_DIR" 2>/dev/null \
            || "$py" -m venv "$VENV_DIR" 2>/dev/null \
            || die "Failed to create venv."
        "$VENV_PYTHON" -m ensurepip --upgrade --default-pip 2>/dev/null || true
    fi

    "$VENV_PYTHON" -m pip install --quiet --no-cache-dir --upgrade pip 2>/dev/null || true

    if [[ -f "$SRC_DIR/requirements.txt" ]]; then
        "$VENV_PYTHON" -m pip install --quiet --no-cache-dir -r "$SRC_DIR/requirements.txt" 2>/dev/null \
            || die "Failed to install requirements."
    else
        warn "No requirements.txt — installing known deps."
        "$VENV_PYTHON" -m pip install --quiet --no-cache-dir pyzmq 2>/dev/null \
            || die "Failed to install deps."
    fi
    ok "Done."
}

set_permissions() {
    info "Setting permissions..."
    chmod +x "$SRC_DIR/UXTU4Linux.py"
    [[ -f "$SRC_DIR/Assets/Linux/ryzenadj" ]] && chmod +x "$SRC_DIR/Assets/Linux/ryzenadj"
    ok "Done."
}

install_wrapper() {
    info "Installing launcher..."
    sudo tee "$BIN_WRAPPER" > /dev/null <<EOF
#!/usr/bin/env bash
exec "$VENV_PYTHON" "$SRC_DIR/UXTU4Linux.py" "\$@"
EOF
    sudo chmod +x "$BIN_WRAPPER"
    [[ -x "$BIN_WRAPPER" ]] || die "Failed to install launcher at $BIN_WRAPPER"
    ok "Launcher → $BIN_WRAPPER"
}

daemon_is_installed() {
    [[ -f "$SERVICE_FILE" ]]
}

restart_daemon() {
    info "Restarting daemon service..."
    sudo systemctl daemon-reload
    sudo systemctl restart "$SERVICE_NAME" \
        && ok "Daemon restarted." \
        || warn "Could not restart daemon — check: sudo systemctl status $SERVICE_NAME"
}

run_setup() {
    echo ""
    hr
    ok "Installation complete!"
    hr
    echo ""

    if daemon_is_installed; then
        restart_daemon
        echo ""
    fi

    info "Launching UXTU4Linux..."
    echo ""
    exec "$BIN_WRAPPER" </dev/tty
}

print_banner() {
    local tag="$1"
    clear
    echo ""
    echo -e "${_C}+----------------------------------------------------------+"
    echo -e "|  _   ___  _______ _   _ _  _   _     _                   |"
    echo -e "| | | | \ \/ /_   _| | | | || | | |   (_)_ __  _   ___  __ |"
    echo -e "| | | | |\  /  | | | | | | || |_| |   | | '_ \| | | \ \/ / |"
    echo -e "| | |_| |/  \  | | | |_| |__   _| |___| | | | | |_| |>  <  |"
    echo -e "|  \___//_/\_\ |_|  \___/   |_| |_____|_|_| |_|\__,_/_/\_\ |"
    echo -e "+----------------------------------------------------------+${_R}"
    echo ""
    echo -e "                      ${_Y}Installer  ·  ${tag}${_R}"
    hr
    echo "  Install path  : $INSTALL_DIR"
    echo "  venv          : $VENV_DIR"
    echo "  Source        : $SRC_DIR"
    echo "  Launcher      : $BIN_WRAPPER"
    echo "  Release       : $RELEASE_URL"
    hr
    echo ""
}

main() {
    local tag
    tag="$(resolve_release_tag)"

    print_banner "$tag"

    local pm
    pm="$(detect_pm)"
    info "Package manager : $pm"
    
    check_systemd
    echo ""
        
    if daemon_is_installed; then
        warn "Existing installation detected — updating files and restarting daemon."
    fi
    echo ""

    ensure_python310 "$pm"
    echo ""
    install_deps "$pm"
    echo ""
    download_release
    echo ""
    install_files
    echo ""
    patch_entry_point
    echo ""
    setup_venv
    echo ""
    set_permissions
    echo ""
    install_wrapper
    echo ""

    run_setup
}

main "$@"
