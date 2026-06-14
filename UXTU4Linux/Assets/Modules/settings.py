from __future__ import annotations

from . import config as cfg
from .ui import menu, clear, confirm, MenuItem, _G, _R, _Y

_ON  = f"{_R}{_G}● ON{_R}"
_OFF = f"{_R}{_Y}○ OFF{_R}"


def _tog(section: str, key: str, default: str = "0") -> str:
    return _ON if cfg.get(section, key, default) == "1" else _OFF


_TOGGLE_MAP = {
    "Apply preset on daemon start": ("Settings", "ApplyOnStart", "1"),
    "Software update": ("Settings", "SoftwareUpdate", "1"),
    "Debug": ("Settings", "Debug", "1"),
}


def ensure_config_files() -> None:
    cfg.CUSTOM_PRESETS_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not cfg.CUSTOM_PRESETS_PATH.exists():
        cfg.CUSTOM_PRESETS_PATH.write_text("[]")


def _do_toggle(idx: int, items: list) -> None:
    lbl = items[idx].label
    if lbl not in _TOGGLE_MAP:
        return
    section, key, default = _TOGGLE_MAP[lbl]
    was_on = cfg.get(section, key, default) == "1"
    cfg.set_config(section, key, "0" if was_on else "1")
    cfg.save()
    items[idx] = MenuItem(lbl, _OFF if was_on else _ON, "toggle")

    if lbl == "Debug":
        try:
            from .ipc import get_client
            get_client().reload_config()
        except Exception:
            pass


def _settings_items() -> list[MenuItem]:
    from .service import service_running, _has_systemctl
    items: list[MenuItem] = []
    if _has_systemctl():
        running = service_running()
        items.append(MenuItem("Daemon service", f"{_R}{_G}● Running{_R}" if running else f"{_R}{_Y}○ Stopped{_R}"))
        items.append(MenuItem("─", kind="separator"))
    items += [
        MenuItem("Apply preset on daemon start", _tog("Settings", "ApplyOnStart", "1"), "toggle"),
        MenuItem("Software update", _tog("Settings", "SoftwareUpdate", "1"), "toggle"),
        MenuItem("Debug", _tog("Settings", "Debug", "1"), "toggle"),
        MenuItem("─", kind="separator"),
        MenuItem("Re-detect hardware"),
        MenuItem("Reset all", desc="Wipe all settings and custom presets, then re-run setup"),
        MenuItem("Back"),
    ]
    return items


def settings_menu() -> None:
    from .service import daemon_menu

    last_idx = 0
    while True:
        items = _settings_items()
        choice = menu("Settings", items, selected=last_idx, on_toggle=_do_toggle)
        if choice == -1:
            return

        last_idx = choice
        lbl = items[choice].label

        if lbl == "Back":
            return
        elif lbl == "Daemon service":
            daemon_menu()
        elif lbl == "Re-detect hardware":
            _redetect_hardware()
        elif lbl == "Reset all":
            _reset_all()


def _redetect_hardware() -> None:
    from .setup import _run_detect_animated
    from .ipc import get_client
    from .ui import clear, pause, _G, _Y, _R

    if not get_client().ping():
        clear()
        print(f"  {_Y}[!] Daemon is not running.{_R}\n")
        print("  Hardware detection requires the daemon to be active.")
        print("  Start or reinstall the daemon from the daemon menu first.\n")
        pause()
        return

    while True:
        _run_detect_animated(3, 3, title="Your Hardware")

        cpu      = cfg.get("Info", "CPU") or ""
        family   = cfg.get("Info", "Family") or ""
        arch     = cfg.get("Info", "Architecture") or ""
        cpu_type = cfg.get("Info", "Type") or ""

        is_supported = cpu_type in ("Amd_Apu", "Amd_Desktop_Cpu")

        def _row(label: str, value: str, good: bool = True) -> str:
            icon = f"{_G}✓{_R}" if (good and value) else f"{_Y}?{_R}"
            return f"{icon}  {label:<14}{value or 'Unknown'}"

        subtitle_lines = [
            _row("CPU", cpu),
            _row("Family", family),
            _row("Architecture", arch),
            _row("Type", cpu_type, is_supported),
            "",
        ]

        if is_supported:
            from .presets import get_preset_label
            variant = cfg.get("Info", "Variant") or ""
            label   = get_preset_label(cpu_type, family, cpu, cpu, variant)
            subtitle_lines += [
                f"{_G}Hardware is supported.{_R}",
                f"Preset profile:  {label}",
            ]
        else:
            subtitle_lines += [
                f"{_Y}Hardware may not be fully supported.{_R}",
                "Custom presets are still available.",
            ]

        cfg.save()

        items = [
            MenuItem("Done", key="done"),
            MenuItem("Re-detect", key="redetect"),
        ]
        choice = menu(
            "Your Hardware",
            items,
            subtitle="\n".join(subtitle_lines),
        )

        if choice == -1 or items[choice].key == "done":
            return


def _reset_all() -> None:
    clear()
    if confirm("Reset all settings and custom presets? This cannot be undone"):
        cfg.CUSTOM_PRESETS_PATH.unlink(missing_ok=True)
        from .setup import reset_all
        reset_all()