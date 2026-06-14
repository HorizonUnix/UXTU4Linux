import glob, os, shutil, subprocess
from . import config as cfg
from .ui import clear, pause, _B, _D, _R, _SEP_W
from .termui import HIDE_CURSOR, SHOW_CURSOR


_SBIN_PATHS = "/usr/sbin:/usr/bin:/sbin:/bin:/usr/local/sbin:/usr/local/bin"


def _find_dmidecode() -> str | None:
    user_path = os.environ.get("PATH", "")
    parts = [p for p in (user_path.split(":") if user_path else []) + _SBIN_PATHS.split(":") if p]
    return shutil.which("dmidecode", path=":".join(dict.fromkeys(parts)))


def check_binaries() -> None:
    dmi = _find_dmidecode()
    if dmi is None:
        print(
            "\n  dmidecode is not installed.\n\n"
            f"  Debian/Ubuntu : {_B}sudo apt install dmidecode{_R}\n"
            f"  Fedora/RHEL   : {_B}sudo dnf install dmidecode{_R}\n"
            f"  Arch          : {_B}sudo pacman -S dmidecode{_R}\n"
            f"  openSUSE      : {_B}sudo zypper install dmidecode{_R}\n\n"
            f"  Install guide: {_B}{cfg.INSTALL_WIKI_URL}{_R}\n"
        )
        raise SystemExit(1)
    cfg.DMIDECODE = dmi


_SMU_INSTALL_GUIDE = f"  Install guide: {_B}{cfg.RYZEN_SMU_WIKI_URL}{_R}\n"


def check_ryzen_smu() -> None:
    from . import smu

    if smu.is_available():
        if not smu.version_ok():
            ver = smu.get_version()
            req = smu.version_str(smu.MIN_VERSION)
            print(
                f"\n  ryzen_smu version {ver} is too old (minimum required: {req}).\n\n"
                f"{_SMU_INSTALL_GUIDE}"
            )
            raise SystemExit(1)
        return

    installed = ryzen_smu_installed()
    signed = ryzen_smu_signed()
    sb = secure_boot_enabled()

    if not installed:
        print(f"\n  ryzen_smu kernel module is not installed.\n\n{_SMU_INSTALL_GUIDE}")
        raise SystemExit(1)

    if sb and not signed:
        print(
            f"\n  ryzen_smu is installed but not signed for Secure Boot.\n\n"
            f"{_SMU_INSTALL_GUIDE}"
        )
        raise SystemExit(1)

    print(
        f"\n  ryzen_smu is installed but not loaded.\n\n"
        f"{_SMU_INSTALL_GUIDE}"
    )
    raise SystemExit(1)


def secure_boot_enabled() -> bool:
    for path in glob.glob("/sys/firmware/efi/efivars/SecureBoot-*"):
        try:
            with open(path, "rb") as f:
                data = f.read()
            if len(data) >= 5 and data[4] == 1:
                return True
        except OSError:
            pass
    try:
        out = subprocess.run(
            ["mokutil", "--sb-state"],
            capture_output=True, text=True, timeout=3,
        ).stdout.lower()
        return "enabled" in out
    except Exception:
        pass
    return False


def ryzen_smu_installed() -> bool:
    try:
        return subprocess.run(
            ["modinfo", "ryzen_smu"],
            capture_output=True, timeout=5,
        ).returncode == 0
    except Exception:
        return False


def ryzen_smu_signed() -> bool:
    try:
        out = subprocess.run(
            ["modinfo", "ryzen_smu"],
            capture_output=True, text=True, timeout=5,
        ).stdout
        return "sig_id:" in out or "signer:" in out
    except Exception:
        return False


def _dmi_raw(dmi_type: str) -> str:
    from .ipc import get_client
    return get_client().dmidecode(dmi_type)


def _dmi(field: str) -> str:
    for line in _dmi_raw("processor").splitlines():
        s = line.strip()
        if s.startswith(f"{field}:"):
            return s.split(":", 1)[-1].strip()
    return ""


def _extract(raw: str, field: str) -> str:
    for line in raw.splitlines():
        s = line.strip()
        if s.startswith(f"{field}:"):
            return s.split(":", 1)[-1].strip()
    return "N/A"


def _read_sysfs(path: str) -> str | None:
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return None


def _parse_battery() -> dict | None:
    bat_path = None
    try:
        for entry in sorted(os.listdir("/sys/class/power_supply")):
            base = f"/sys/class/power_supply/{entry}"
            if _read_sysfs(f"{base}/type") != "Battery":
                continue
            if _read_sysfs(f"{base}/charge_full") or _read_sysfs(f"{base}/energy_full"):
                bat_path = base
                break
    except OSError:
        return None

    if bat_path is None:
        return None

    def r(name: str) -> str | None:
        return _read_sysfs(f"{bat_path}/{name}")

    full = design = None
    cap_unit = ""

    try:
        ef = r("energy_full")
        efd = r("energy_full_design")
        if ef and efd:
            full, design, cap_unit = int(ef) / 1000, int(efd) / 1000, "mWh"
    except ValueError:
        pass

    if full is None:
        try:
            cf = r("charge_full")
            cfd = r("charge_full_design")
            volt = r("voltage_min_design") or r("voltage_now")
            if cf and cfd and volt:
                v = int(volt) / 1e6
                full = (int(cf)  / 1e6) * v * 1000
                design = (int(cfd) / 1e6) * v * 1000
                cap_unit = "mWh"
        except ValueError:
            pass

    if full is None:
        try:
            cf = r("charge_full")
            cfd = r("charge_full_design")
            if cf and cfd:
                full, design, cap_unit = int(cf) / 1000, int(cfd) / 1000, "mAh"
        except ValueError:
            pass

    health_str = "N/A"
    if full is not None and design and design > 0:
        health_str = f"{min(full / design * 100, 100.0):.1f}%"

    status = r("status") or "Unknown"
    rate_w = None
    power_now = r("power_now")
    curr_now = r("current_now")
    volt_now = r("voltage_now")

    try:
        if power_now:
            rate_w = int(power_now) / 1e6
        elif curr_now and volt_now:
            rate_w = (int(curr_now) * int(volt_now)) / 1e12
    except ValueError:
        pass

    if rate_w is not None:
        suffix = (
            " (charging)" if status.lower() == "charging" else
            " (discharging)" if status.lower() == "discharging" else ""
        )
        rate_str = f"{rate_w:.1f} W{suffix}"
    else:
        rate_str = "N/A"

    return {
        "health": health_str,
        "cycles": r("cycle_count") or "N/A",
        "full_charge": f"{full:.0f} {cap_unit}"  if full is not None else "N/A",
        "design_cap": f"{design:.0f} {cap_unit}" if design is not None else "N/A",
        "charge_rate": rate_str,
    }


def _parse_device_info() -> dict[str, str]:
    sys_raw = _dmi_raw("system")
    board_raw = _dmi_raw("baseboard")
    return {
        "name": _extract(sys_raw, "Product Name"),
        "producer": _extract(sys_raw, "Manufacturer"),
        "model": _extract(board_raw, "Product Name"),
    }


def _parse_processor_dmidecode() -> dict[str, str]:
    raw = _dmi_raw("processor")
    speed = _extract(raw, "Current Speed")
    if speed == "N/A":
        speed = _extract(raw, "Max Speed")
    return {
        "manufacturer": _extract(raw, "Manufacturer"),
        "cores": _extract(raw, "Core Count"),
        "threads": _extract(raw, "Thread Count"),
        "base_clock": speed,
    }


def _format_cache(size_str: str) -> str:
    parts = size_str.split()
    if len(parts) < 2:
        return size_str
    try:
        value = float(parts[0])
        unit = parts[1].lower()
        if unit in ("k", "kb", "kib"):
            mb = value / 1024
            return f"{mb:.2f} MB" if mb < 1 else f"{mb:.0f} MB"
        if unit in ("m", "mb", "mib"):
            return f"{value:.0f} MB"
        if unit in ("g", "gb", "gib"):
            return f"{value * 1024:.0f} MB"
    except (ValueError, IndexError):
        pass
    return size_str


def _parse_cache_sizes() -> tuple[str, str, str]:
    raw = _dmi_raw("cache")
    l1 = l2 = l3 = "N/A"
    level: str | None = None
    for line in raw.splitlines():
        s = line.strip()
        if s.startswith("Socket Designation:"):
            val = s.split(":", 1)[-1].strip().upper()
            level = "L1" if "L1" in val else "L2" if "L2" in val else "L3" if "L3" in val else None
        elif s.startswith("Installed Size:") and level:
            fmt = _format_cache(s.split(":", 1)[-1].strip())
            if level == "L1": l1 = fmt
            elif level == "L2": l2 = fmt
            elif level == "L3": l3 = fmt
    return l1, l2, l3


def _parse_memory() -> dict[str, str]:
    raw = _dmi_raw("memory")
    total_mb = 0
    mem_type = "Unknown"
    speed = "Unknown"
    manufacturer = "Unknown"
    part_number = "Unknown"
    module_width = 64
    module_count = 0
    current: dict[str, str] = {}
    in_device = False

    def _flush(d: dict) -> None:
        nonlocal total_mb, mem_type, speed, manufacturer, part_number, module_width, module_count
        raw_size = d.get("Size", "")
        if not raw_size or "No Module" in raw_size or "Not Installed" in raw_size:
            return
        parts = raw_size.split()
        try:
            sz = int(parts[0])
            unit = parts[1].upper() if len(parts) > 1 else "MB"
            if unit == "GB": sz *= 1024
        except (ValueError, IndexError):
            return
        total_mb += sz
        module_count += 1
        if d.get("Type", "Unknown") not in ("Unknown", ""):
            mem_type = d["Type"]
        for k in ("Configured Memory Speed", "Speed"):
            if d.get(k, "Unknown") not in ("Unknown", ""):
                speed = d[k]; break
        if d.get("Manufacturer", "Unknown") not in ("Unknown", ""):
            manufacturer = d["Manufacturer"]
        if d.get("Part Number", "Unknown") not in ("Unknown", ""):
            part_number = d["Part Number"].strip()
        try:
            module_width = int(d.get("Data Width", "64").split()[0])
        except ValueError:
            pass

    for line in raw.splitlines():
        s = line.strip()
        if s == "Memory Device":
            if in_device: _flush(current)
            current = {}; in_device = True
        elif in_device and ":" in s:
            k, _, v = s.partition(":")
            current[k.strip()] = v.strip()
    if in_device:
        _flush(current)

    total_str = f"{total_mb // 1024} GB" if total_mb >= 1024 else f"{total_mb} MB"
    spd_fmt = speed if speed != "Unknown" else ""
    summary = f"{total_str} {mem_type}" + (f" @ {spd_fmt}" if spd_fmt else "")
    total_bus = module_width * module_count

    return {
        "summary": summary,
        "manufacturer": manufacturer,
        "part_number": part_number,
        "width": f"{total_bus} bit",
        "modules": f"{module_count} * {module_width} bit",
    }


def _resolve_codename(cpu: str, cpu_family: int, cpu_model: int) -> tuple[str, str]:
    if cpu == "Intel":
        return "Intel", "Intel"

    arch, family = "Unknown", "Unknown"

    if cpu_family == 23:
        arch = "Zen 1 - Zen 2"
        match cpu_model:
            case 1: family = "SummitRidge"
            case 8: family = "PinnacleRidge"
            case 17 | 18: family = "RavenRidge"
            case 24: family = "Picasso"
            case 32: family = "Pollock" if any(s in cpu for s in ("15e", "15Ce", "20e")) else "Dali"
            case 80: family = "FireFlight"
            case 96: family = "Renoir"
            case 104: family = "Lucienne"
            case 113: family = "Matisse"
            case 144 | 145: family = "VanGogh"
            case 160: family = "Mendocino"

    elif cpu_family == 25:
        arch = "Zen 3 - Zen 4"
        match cpu_model:
            case 33: family = "Vermeer"
            case 63 | 68: family = "Rembrandt"
            case 80: family = "Cezanne_Barcelo"
            case 97: family = "DragonRange" if "HX" in cpu else "Raphael"
            case 116: family = "PhoenixPoint"
            case 120: family = "PhoenixPoint2"
            case 117: family = "HawkPoint"
            case 124: family = "HawkPoint2"

    elif cpu_family == 26:
        arch = "Zen 5 - Zen 6"
        match cpu_model:
            case 68: family = "FireRange" if "HX" in cpu else "GraniteRidge"
            case 96: family = "KrackanPoint"
            case 104: family = "KrackanPoint2"
            case 32 | 36: family = "StrixPoint"
            case 112: family = "StrixHalo"

    return arch, family


_DESKTOP_FAMILIES = {
    "SummitRidge", "PinnacleRidge", "Matisse",
    "Vermeer", "Raphael", "GraniteRidge",
}


def _cpu_type(family: str, arch: str) -> str:
    if family in _DESKTOP_FAMILIES: return "Amd_Desktop_Cpu"
    if arch == "Intel": return "Intel"
    if arch == "Unknown": return "Unknown"
    return "Amd_Apu"


def _lspci_vga() -> str:
    try:
        result = subprocess.run(
            ["lspci"],
            capture_output=True, text=True, timeout=5,
        )
        lines = [l for l in result.stdout.splitlines() if "VGA" in l or "Display" in l]
        return "\n".join(lines).lower()
    except Exception:
        return ""


def _has_discrete_rx7700s() -> bool:
    vga = _lspci_vga()
    return "7700s" in vga or "rx 7700s" in vga


def _detect_framework_variant() -> str:
    sys_raw = _dmi_raw("system")
    product = _extract(sys_raw, "Product Name").lower()
    mfr = _extract(sys_raw, "Manufacturer").lower()

    if "framework" not in mfr:
        return ""

    if "laptop 16" in product and "7040" in product:
        if _has_discrete_rx7700s():
            return "AMDFrameworkLaptop16Ryzen7040_RX7700S"
        return "AMDFrameworkLaptop16Ryzen7040"

    if "laptop 13" in product and ("7040" in product or "ai 300" in product or "ryzen ai 300" in product):
        return "AMDFrameworkLaptop13Ryzen7040_RyzenAI300"

    return ""


def detect() -> None:
    for key, field in {"CPU": "Version", "Signature": "Signature"}.items():
        cfg.set_config("Info", key, _dmi(field))
    _compute_codename()

    variant = _detect_framework_variant()
    cfg.set_config("Info", "Variant", variant)

    cfg.save()


def _compute_codename() -> None:
    raw_cpu = cfg.get("Info", "CPU")
    signature = cfg.get("Info", "Signature")
    try:
        words = signature.split()
        cpu_family = int(words[words.index("Family") + 1].rstrip(","))
        cpu_model = int(words[words.index("Model") + 1].rstrip(","))
    except (ValueError, IndexError):
        cfg.set_config("Info", "Architecture", "Unknown")
        cfg.set_config("Info", "Family", "Unknown")
        cfg.set_config("Info", "Type", "Unknown")
        return
    from .runner import has_smu_support
    arch, family = _resolve_codename(raw_cpu, cpu_family, cpu_model)
    cpu_type = _cpu_type(family, arch)
    if cpu_type in ("Amd_Apu", "Amd_Desktop_Cpu") and not has_smu_support(family):
        cpu_type = "Unknown"
    cfg.set_config("Info", "Architecture", arch)
    cfg.set_config("Info", "Family", family)
    cfg.set_config("Info", "Type", cpu_type)


def show_info() -> None:
    import sys
    from . import termui

    W = 14

    def row(label: str, value: str) -> str:
        return f"  {_D}{label:<{W}}{_R}  {value}"

    def sep(title: str) -> list[str]:
        return [f"  {_B}{title}{_R}", f"  {_D}{'─' * _SEP_W}{_R}"]

    dev = _parse_device_info()
    proc = _parse_processor_dmidecode()
    l1, l2, l3 = _parse_cache_sizes()
    mem = _parse_memory()

    static: list[str] = [f"  {_B}Hardware Information{_R}", ""]
    static += sep("Device")
    static += [row("Name", dev["name"]), row("Producer", dev["producer"]), row("Model", dev["model"]), ""]
    static += sep("Processor")
    static += [
        row("CPU", cfg.get("Info", "CPU")),
        row("Producer", proc["manufacturer"]),
        row("Codename", cfg.get("Info", "Family")),
        row("Signature", cfg.get("Info", "Signature")),
        row("Cores", proc["cores"]),
        row("Threads", proc["threads"]),
        row("Base clock", proc["base_clock"]),
        row("L1 cache", l1),
        row("L2 cache", l2),
        row("L3 cache", l3),
        "",
    ]
    static += sep("Memory")
    static += [
        row("Memory", mem["summary"]),
        row("Producer", mem["manufacturer"]),
        row("Model", mem["part_number"]),
        row("Bus width", mem["width"]),
        row("Modules", mem["modules"]),
    ]

    def _battery_lines() -> list[str]:
        bat = _parse_battery()
        if not bat:
            return []
        lines: list[str] = [""] + sep("Battery")
        lines += [
            row("Health", bat["health"]),
            row("Cycles", bat["cycles"]),
            row("Full charge", bat["full_charge"]),
            row("Design cap.", bat["design_cap"]),
            row("Charge rate", bat["charge_rate"]),
        ]
        return lines

    if not sys.stdin.isatty():
        clear()
        for line in static + _battery_lines():
            print(line)
        print()
        pause()
        return

    sys.stdout.write(HIDE_CURSOR)
    sys.stdout.flush()
    try:
        while True:
            content = static + _battery_lines() + ["", f"  {_D}Press Esc to go back{_R}"]
            clear()
            sys.stdout.write("\n".join(content))
            sys.stdout.flush()

            key = termui.get_key(timeout=3.0)
            if key == termui.ESC:
                break
    finally:
        sys.stdout.write(SHOW_CURSOR)
        sys.stdout.flush()