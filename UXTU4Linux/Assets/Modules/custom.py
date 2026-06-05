"""
custom.py
"""

from __future__ import annotations

import copy
import json
import sys
from typing import Any

from . import config as cfg
from . import termui
from .ui import _R, _B, _D, _Y, _G

FIELD_DEFS: list[dict[str, Any]] = [
    {
        "key": "tctl_temp", "label": "APU Temp Limit", "arg": "--tctl-temp",
        "unit": "°C", "default": 95, "min": 10, "max": 105, "step": 1,
        "enabled": False, "section": 1,
        "hint": "Temperature limit at which the APU starts soft throttling.",
    },
    {
        "key": "skin_temp_limit", "label": "Skin Temp Limit", "arg": "--skin-temp-limit",
        "unit": "°C", "default": 45, "min": 8, "max": 105, "step": 1,
        "enabled": False, "section": 1,
        "hint": "Laptop chassis temperature limit at which the APU starts throttling.",
    },
    {
        "key": "stapm_limit", "label": "STAPM Power Limit", "arg": "--stapm-limit",
        "unit": "W", "default": 28, "min": 5, "max": 300, "step": 1,
        "enabled": False, "section": 2,
        "hint": "APU's Skin Temperature Aware Power Management power limit.",
    },
    {
        "key": "slow_limit", "label": "Slow Power Limit", "arg": "--slow-limit",
        "unit": "W", "default": 28, "min": 5, "max": 300, "step": 1,
        "enabled": False, "section": 2,
        "hint": "APU's slow boost duration power limit.",
    },
    {
        "key": "slow_time", "label": "Slow Boost Duration", "arg": "--slow-time",
        "unit": "s", "default": 128, "min": 2, "max": 1024, "step": 1,
        "enabled": False, "section": 2,
        "hint": "How long the APU stays within the slow boost power limit.",
    },
    {
        "key": "fast_limit", "label": "Fast Power Limit", "arg": "--fast-limit",
        "unit": "W", "default": 28, "min": 5, "max": 300, "step": 1,
        "enabled": False, "section": 2,
        "hint": "APU's fast boost duration power limit.",
    },
    {
        "key": "stapm_time", "label": "Fast Boost Duration", "arg": "--stapm-time",
        "unit": "s", "default": 64, "min": 2, "max": 1024, "step": 1,
        "enabled": False, "section": 2,
        "hint": "How long the APU stays within the fast boost power limit.",
    },
    {
        "key": "vrm_current", "label": "CPU TDC Limit", "arg": "--vrm-current",
        "unit": "A", "default": 64, "min": 8, "max": 300, "step": 1,
        "enabled": False, "section": 3,
        "hint": "CPU Thermal Design Current limit.",
    },
    {
        "key": "vrmmax_current", "label": "CPU EDC Limit", "arg": "--vrmmax-current",
        "unit": "A", "default": 64, "min": 8, "max": 300, "step": 1,
        "enabled": False, "section": 3,
        "hint": "CPU Electrical Design Current limit.",
    },
    {
        "key": "vrmsoc_current", "label": "SoC TDC Limit", "arg": "--vrmsoc-current",
        "unit": "A", "default": 64, "min": 8, "max": 300, "step": 1,
        "enabled": False, "section": 3,
        "hint": "SoC Thermal Design Current limit.",
    },
    {
        "key": "vrmsocmax_current", "label": "SoC EDC Limit", "arg": "--vrmsocmax-current",
        "unit": "A", "default": 64, "min": 8, "max": 300, "step": 1,
        "enabled": False, "section": 3,
        "hint": "SoC Electrical Design Current limit.",
    },
    {
        "key": "vrmgfx_current", "label": "GFX TDC Limit", "arg": "--vrmgfx-current",
        "unit": "A", "default": 64, "min": 8, "max": 300, "step": 1,
        "enabled": False, "section": 3,
        "hint": "iGPU Thermal Design Current limit.",
    },
    {
        "key": "vrmgfxmax_current", "label": "GFX EDC Limit", "arg": "--vrmgfxmax_current",
        "unit": "A", "default": 64, "min": 8, "max": 300, "step": 1,
        "enabled": False, "section": 3,
        "hint": "iGPU Electrical Design Current limit.",
    },
    {
        "key": "max_gfxclk", "label": "Max iGPU Clock", "arg": "--max-gfxclk",
        "unit": "MHz", "default": 1000, "min": 200, "max": 4000, "step": 50,
        "enabled": False, "section": 4,
        "hint": "Static boost clock ceiling. Requires reboot or sleep to revert.",
    },
    {
        "key": "min_gfxclk", "label": "Min iGPU Clock", "arg": "--min-gfxclk",
        "unit": "MHz", "default": 200, "min": 200, "max": 4000, "step": 50,
        "enabled": False, "section": 4,
        "hint": "Static boost clock floor. Requires reboot or sleep to revert.",
    },
    {
        "key": "coall", "label": "All Core Offset", "arg": "--set-coall",
        "unit": "", "default": 0, "min": -50, "max": 30, "step": 1,
        "enabled": False, "section": 5,
        "hint": "Allows control to change the all core Curve Optimiser Frequency/Voltage curve offset.",
    },
    {
        "key": "cogfx", "label": "iGPU Offset", "arg": "--set-cogfx",
        "unit": "", "default": 0, "min": -50, "max": 30, "step": 1,
        "enabled": False, "section": 5,
        "hint": "Allows control to change the iGPU Curve Optimiser Frequency/Voltage curve offset.",
    },
]

APU_PER_CORE_CO = [
    {"ccd": 0, "core": i, "key": f"co_ccd1_core{i + 1}", "label": f"CCD1 Core {i + 1}", "section": 6} for i in range(12)
] + [
    {"ccd": 1, "core": i, "key": f"co_ccd2_core{i + 1}", "label": f"CCD2 Core {i + 1}", "section": 6} for i in range(12)
]

for entry in APU_PER_CORE_CO:
    FIELD_DEFS.append({
        "key": entry["key"],
        "label": entry["label"],
        "arg": "--set-coper",
        "unit": "",
        "default": 0,
        "min": -50,
        "max": 30,
        "step": 1,
        "enabled": False,
        "section": entry["section"],
        "hint": "Per-core Curve Optimiser offset.",
        "ccd": entry["ccd"],
        "core": entry["core"],
    })

_SECTION_NAMES = {1: "Temp", 2: "Power", 3: "VRM", 4: "iGPU", 5: "CO", 6: "CO Per-Core"}
_SECTION_TITLES = {
    1: "APU Temperature Tuning",
    2: "APU Power Tuning",
    3: "APU VRM Tuning",
    4: "iGPU Tuning",
    5: "Curve Optimiser",
    6: "Curve Optimiser Per-Core",
}

APU_PER_CORE_SECTION = 6
APU_PER_CORE_KEYS = [f"co_ccd1_core{i + 1}" for i in range(12)] + [f"co_ccd2_core{i + 1}" for i in range(12)]


def _display_name(internal_name: str) -> str:
    return internal_name.removesuffix("_custom_preset")


def default_fields(include_ccd2: bool = True) -> list[dict]:
    fields = []
    for f in FIELD_DEFS:
        if not include_ccd2 and f.get("section") == APU_PER_CORE_SECTION and int(f.get("ccd", 0)) == 1:
            continue
        d = dict(f)
        d["value"] = f["default"]
        fields.append(d)
    return fields


def _supports_ccd2_apu() -> bool:
    family = cfg.get("Info", "Family")
    cpu = cfg.get("Info", "CPU")
    return family in {"DragonRange", "FireRange", "StrixHalo", "KrackanPoint"} and ("Ryzen 9" in cpu or "395" in cpu or "390" in cpu)

def _special_coper_family() -> bool:
    return cfg.get("Info", "Family") in {"DragonRange", "FireRange", "StrixHalo"}


def _coper_visible_fields() -> list[dict]:
    fields = _default_fields_for_current_cpu()
    if not _ccd2_visible():
        fields = [f for f in fields if not (f.get("section") == APU_PER_CORE_SECTION and int(f.get("ccd", 0)) == 1)]
    return fields


def _default_fields_for_current_cpu() -> list[dict]:
    return default_fields(include_ccd2=_supports_ccd2_apu())


def _apu_per_core_fields() -> list[dict]:
    return _coper_visible_fields()


def _ccd2_visible() -> bool:
    return _supports_ccd2_apu()

def _special_core_pack() -> bool:
    return _special_coper_family()


def clamp_field(value: int, fdef: dict) -> int:
    return max(fdef["min"], min(fdef["max"], value))


def _section_indices(fields: list[dict], section: int) -> list[int]:
    return [i for i, f in enumerate(fields) if f["section"] == section]


def _enforce_igpu_clamp(fields: list[dict], changed_key: str) -> None:
    by_key = {f["key"]: f for f in fields}
    mn = by_key.get("min_gfxclk")
    mx = by_key.get("max_gfxclk")
    if mn is None or mx is None:
        return
    if changed_key == "min_gfxclk" and mn["value"] > mx["value"]:
        mx["value"] = mn["value"]
    elif changed_key == "max_gfxclk" and mx["value"] < mn["value"]:
        mn["value"] = mx["value"]


def _ryzenadj_value(f: dict) -> int:
    unit = f["unit"]
    val = f["value"]
    if unit in ("W", "A"):
        return val * 1000
    if f.get("section") == 5 and val < 0:
        return 0x100000 + val
    return val


def _coper_value(f: dict) -> int:
    offset = max(-50, min(30, int(f["value"])))
    magnitude = min(abs(offset), 0xFFFFF)
    encoded = (0x100000 - magnitude) & 0xFFFFF if offset < 0 else magnitude & 0xFFFFF
    prefix = (((int(f.get("ccd", 0)) << 4) | 0) << 4 | (int(f.get("core", 0)) % 8 & 15)) << 20
    return prefix | encoded


def build_args(fields: list[dict]) -> str:
    parts = []
    for f in fields:
        if not f["enabled"]:
            continue
        if f["arg"] == "--set-coper":
            if _special_core_pack():
                parts.append(f"--set-coper={_coper_value(f)}")
            else:
                core = int(f.get("core", 0))
                encoded = ((core if core < 8 else 7) << 20) | (int(f["value"]) & 0xFFFF)
                parts.append(f"--set-coper={encoded}")
        else:
            parts.append(f"{f['arg']}={_ryzenadj_value(f)}")
    return " ".join(parts)


def load_custom_presets() -> list[dict]:
    try:
        data = json.loads(cfg.CUSTOM_PRESETS_PATH.read_text())
        return data if isinstance(data, list) else []
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return []


def _save_custom_presets(presets: list[dict]) -> None:
    cfg.CUSTOM_PRESETS_PATH.parent.mkdir(parents=True, exist_ok=True)
    cfg.CUSTOM_PRESETS_PATH.write_text(json.dumps(presets, indent=2))


def fields_to_record(base_name: str, fields: list[dict]) -> dict:
    record: dict = {"name": base_name}
    for f in fields:
        record[f["key"]] = {"enabled": f["enabled"], "value": f["value"]}
    return record


def record_to_fields(record: dict) -> list[dict]:
    fields = _default_fields_for_current_cpu()
    known = {f["key"] for f in fields}
    for key, entry in record.items():
        if key == "name" or key not in known or not isinstance(entry, dict):
            continue
        for f in fields:
            if f["key"] == key:
                f["enabled"] = bool(entry.get("enabled", f["enabled"]))
                try:
                    f["value"] = clamp_field(int(entry.get("value", f["default"])), f)
                except (TypeError, ValueError):
                    f["value"] = f["default"]
                break
    return fields


def preset_to_args(record: dict) -> str:
    return build_args(record_to_fields(record))


def get_custom_preset_names() -> list[str]:
    return [p["name"] + "_custom_preset" for p in load_custom_presets()]


def save_preset(base_name: str, fields: list[dict]) -> str:
    presets = load_custom_presets()
    presets = [p for p in presets if p["name"] != base_name]
    presets.append(fields_to_record(base_name, fields))
    _save_custom_presets(presets)

    internal_name = base_name + "_custom_preset"
    active_mode = cfg.get("User", "Mode")
    ac_slot = cfg.get("Automations", "OnAC", "")
    bat_slot = cfg.get("Automations", "OnBattery", "")
    in_use = (
        active_mode in (base_name, internal_name)
        or ac_slot in (base_name, internal_name)
        or bat_slot in (base_name, internal_name)
    )
    if in_use:
        try:
            from .ipc import get_client
            client = get_client()
            if client.ping():
                client.apply_saved()
        except Exception:
            pass

    return internal_name


def delete_preset(display_name: str) -> None:
    base = display_name.removesuffix("_custom_preset")
    internal_name = base + "_custom_preset"
    presets = [p for p in load_custom_presets() if p["name"] != base]
    _save_custom_presets(presets)

    changed = False

    if cfg.get("User", "Mode") in (internal_name, base):
        cfg.set_config("User", "Mode", "Balance")
        changed = True

    ac_slot = cfg.get("Automations", "OnAC", "")
    bat_slot = cfg.get("Automations", "OnBattery", "")

    if ac_slot in (internal_name, base):
        cfg.set_config("Automations", "OnAC", "")
        ac_slot = ""
        changed = True

    if bat_slot in (internal_name, base):
        cfg.set_config("Automations", "OnBattery", "")
        bat_slot = ""
        changed = True

    if not ac_slot and not bat_slot:
        cfg.set_config("Automations", "Enabled", "0")
        changed = True

    if changed:
        cfg.save()
        try:
            from .ipc import get_client
            client = get_client()
            if client.ping():
                client.apply_saved()
        except Exception:
            pass


def load_preset_fields(display_name: str) -> list[dict] | None:
    base = display_name.removesuffix("_custom_preset")
    presets = load_custom_presets()
    for p in presets:
        if p.get("name") == base:
            return record_to_fields(p)
    return None


def _render_editor(
    fields: list[dict],
    section: int,
    row: int,
    dirty: bool,
    preset_name: str,
) -> list[str]:
    name_display = preset_name or "(unnamed)"
    dirty_mark = f"  {_Y}[*]{_R}" if dirty else ""
    lines: list[str] = [
        f"  {_B}Custom Preset Editor{_R}",
        f"  Name: {_B}{name_display}{_R}{dirty_mark}",
        "",
    ]

    tabs1 = "  "
    for s in range(1, 4):
        n = _SECTION_NAMES[s]
        if s == section:
            tabs1 += f"{_B}[{s}] {n}{_R}  "
        else:
            tabs1 += f"{_D}[{s}] {n}{_R}  "
    tabs2 = "  "
    for s in range(4, 7):
        n = _SECTION_NAMES[s]
        if s == section:
            tabs2 += f"{_B}[{s}] {n}{_R}  "
        else:
            tabs2 += f"{_D}[{s}] {n}{_R}  "
    lines.append(tabs1.rstrip())
    lines.append(tabs2.rstrip())
    lines.append(f"  {'─' * 48}")
    lines.append(f"  {_B}{_SECTION_TITLES[section]}{_R}")
    lines.append("")

    sec_rows = _section_indices(fields, section)
    active_hint = ""
    for r, gi in enumerate(sec_rows):
        f = fields[gi]
        tog = f"{_G}[✓]{_R}" if f["enabled"] else f"{_D}[ ]{_R}"
        lbl = f"{f['label']:<22}"
        vstr = f"{f['value']:>5} {f['unit']:<4}"
        rng = f"[{f['min']} – {f['max']}]"
        if r == row:
            active_hint = f.get("hint", "")
            lines.append(f"  {_B}▶{_R} {tog} {_B}{lbl}{_R}  {_B}{vstr}{_R}  {_D}{rng}{_R}")
        else:
            if f["enabled"]:
                lines.append(f"    {tog} {lbl}  {_D}{vstr}  {rng}{_R}")
            else:
                lines.append(f"    {tog} {_D}{lbl}  {vstr}  {rng}{_R}")

    lines.append("")
    if active_hint:
        lines.append(f"  {_D}{active_hint}{_R}")
    lines += [
        f"  {'─' * 48}",
        f"  {_D}[S] Save  [L] Load  [D] Delete{_R}",
        f"  {_D}Space to toggle, ←/→ to adjust, ↑/↓ to navigate, Esc to go back{_R}",
    ]
    return lines


def _prompt_name(current: str) -> str | None:
    from .ui import ask, clear
    clear()
    print(f"  {_B}Preset Name{_R}")
    print(f"  {_D}Will be stored as: {current or '<name>'}{_R}\n")
    name = ask("Preset name", default=current)
    return name.strip() or None


def _confirm_overwrite(name: str) -> bool:
    from .ui import confirm
    return confirm(f"Overwrite '{name}'?")


def _do_save(fields: list[dict], preset_name: str) -> tuple[str, bool]:
    if not any(f["enabled"] for f in fields):
        from .ui import clear, pause
        clear()
        print("  Cannot save — no parameters are enabled.")
        print("  Enable at least one parameter with Space before saving.")
        pause()
        return preset_name, False

    name = preset_name or ""
    if not name:
        name = _prompt_name("") or ""
        if not name:
            return preset_name, False

    existing = [p["name"] for p in load_custom_presets()]
    if name in existing and not _confirm_overwrite(name):
        return name, False

    save_preset(name, fields)
    return name, True


def _do_load(fields: list[dict], dirty: bool) -> tuple[list[dict], str, bool] | None:
    names = get_custom_preset_names()
    if not names:
        from .ui import clear, pause
        clear()
        print("  No saved custom presets.")
        pause()
        return None

    if dirty:
        from .ui import confirm
        ok = confirm("Discard unsaved changes and load another preset?")
        if not ok:
            return None

    choice = _arrow_pick("Load Preset", names)
    if choice is None:
        return None

    loaded = load_preset_fields(choice)
    if loaded is None:
        return None

    base_name = choice.removesuffix("_custom_preset")
    return loaded, base_name, False


def _do_delete() -> str | None:
    names = get_custom_preset_names()
    if not names:
        from .ui import clear, pause
        clear()
        print("  No saved custom presets.")
        pause()
        return None

    choice = _arrow_pick("Delete Preset", names)
    if choice:
        from .ui import confirm
        if confirm(f"Delete '{_display_name(choice)}'? This cannot be undone"):
            delete_preset(choice)
            return choice
    return None


def _arrow_pick(title: str, names: list[str]) -> str | None:
    from .ui import menu, MenuItem
    items = [MenuItem(_display_name(n), key=n) for n in names]
    items += [MenuItem("─", kind="separator"), MenuItem("Back", key="back")]
    choice = menu(title, items)
    if choice == -1 or items[choice].key == "back":
        return None
    return items[choice].key


def run_editor(
    initial_fields: list[dict] | None = None,
    initial_name: str = "",
) -> None:
    fields = copy.deepcopy(initial_fields) if initial_fields else _apu_per_core_fields()
    preset_name = initial_name
    section = 1
    row = 0
    dirty = False
    prev = 0
    needs_clear = False

    def clamp_row() -> None:
        nonlocal row
        n = len(_section_indices(fields, section))
        row = max(0, min(row, n - 1)) if n else 0

    sys.stdout.write(termui.HIDE_CURSOR)
    sys.stdout.flush()

    try:
        while True:
            clamp_row()

            if needs_clear:
                from .ui import clear as ui_clear
                ui_clear()
                sys.stdout.write(termui.HIDE_CURSOR)
                sys.stdout.flush()
                prev = 0
                needs_clear = False

            lines = _render_editor(fields, section, row, dirty, preset_name)
            prev = termui.draw_lines(lines, prev)
            key = termui.get_key()

            if key in (b"1", b"2", b"3", b"4", b"5", b"6"):
                new_sec = int(key)
                if new_sec != section:
                    section = new_sec
                    row = 0
                continue

            sec_rows = _section_indices(fields, section)

            if key == termui.UP:
                if row > 0:
                    row -= 1
                continue

            if key == termui.DOWN:
                if row < len(sec_rows) - 1:
                    row += 1
                continue

            if key == b" " and sec_rows:
                f = fields[sec_rows[row]]
                f["enabled"] = not f["enabled"]
                dirty = True
                continue

            if key == termui.LEFT and sec_rows:
                f = fields[sec_rows[row]]
                f["value"] = clamp_field(f["value"] - f["step"], f)
                _enforce_igpu_clamp(fields, f["key"])
                dirty = True
                continue

            if key == termui.RIGHT and sec_rows:
                f = fields[sec_rows[row]]
                f["value"] = clamp_field(f["value"] + f["step"], f)
                _enforce_igpu_clamp(fields, f["key"])
                dirty = True
                continue

            if key in (b"s", b"S"):
                needs_clear = True
                preset_name, saved = _do_save(fields, preset_name)
                if saved:
                    dirty = False
                continue

            if key in (b"l", b"L"):
                needs_clear = True
                result = _do_load(fields, dirty)
                if result is not None:
                    fields, preset_name, dirty = result
                continue

            if key in (b"d", b"D"):
                needs_clear = True
                deleted = _do_delete()
                if deleted and deleted.removesuffix("_custom_preset") == preset_name:
                    preset_name = ""
                    fields = default_fields()
                    dirty = False
                continue

            if key == termui.ESC:
                if dirty:
                    needs_clear = True
                    sys.stdout.write(termui.SHOW_CURSOR)
                    sys.stdout.flush()
                    from .ui import confirm
                    ok = confirm("Discard unsaved changes?")
                    sys.stdout.write(termui.HIDE_CURSOR)
                    sys.stdout.flush()
                    if not ok:
                        continue
                break

            if key in (b"\x03", b"\x04"):
                break

    finally:
        sys.stdout.write(termui.SHOW_CURSOR + "\n")
        sys.stdout.flush()


def custom_preset_menu() -> None:
    from .ui import clear, pause, menu, MenuItem

    cpu_type = cfg.get("Info", "Type")
    if cpu_type != "Amd_Apu":
        clear()
        print("  Custom Preset editor is only supported on AMD APUs.")
        pause()
        return

    saved = load_custom_presets()
    if saved:
        names = get_custom_preset_names()
        items = [MenuItem(_display_name(n), key=n) for n in names]
        items += [
            MenuItem("─", kind="separator"),
            MenuItem("Create new preset", key="new"),
            MenuItem("Back", key="back"),
        ]
        choice = menu("Custom Preset", items)
        if choice == -1 or items[choice].key == "back":
            return
        if items[choice].key == "new":
            fields, name = _apu_per_core_fields(), ""
        else:
            selected = items[choice].key
            fields = load_preset_fields(selected) or _apu_per_core_fields()
            name = selected.removesuffix("_custom_preset")
    else:
        fields, name = _apu_per_core_fields(), ""

    clear()
    run_editor(initial_fields=fields, initial_name=name)