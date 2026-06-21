from __future__ import annotations

from textual import work
from textual.app import ComposeResult
from textual.containers import Grid, Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Collapsible, Input, Label, Select, Static, Switch

from Assets.core import config as cfg
from Assets.tuning import automations as au, power
from Assets.tuning.custom import (
    APU_SECTION_TITLES, DT_SECTION_TITLES,
    _default_fields_for_current_cpu, _supported_field_keys, _active_sections,
    _section_indices, clamp_field, _enforce_clk_clamp, build_args,
    save_preset, load_preset_fields, delete_preset, get_custom_preset_names, _display_name,
    unique_preset_name,
)
from Assets.tui.modals import ConfirmModal


_COLOR = {"Eco": "eco", "Balance": "balance", "Performance": "perf", "Extreme": "extreme"}

_AUTOMATIONS_ON_MSG = (
    "Automations are on. Turn off Override in the Automations tab to apply a preset manually."
)


class HomeTab(VerticalScroll):
    _NAV = (
        ("Premade Presets", "power"),
        ("Custom Presets", "custom"),
        ("Automations", "automations"),
        ("System Info", "hardware"),
        ("Status", "status"),
        ("Settings", "settings"),
    )

    def compose(self) -> ComposeResult:
        with Vertical(classes="settings_card"):
            yield Static("Home", classes="card_title")
            yield Static("Pick where to go:", classes="field_hint")
            with Grid(classes="home_grid"):
                for label, tab in self._NAV:
                    yield Button(label, id=f"home-{tab}", variant="primary")
            yield Button("About", id="home-about", classes="home_about")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "home-about":
            self.app.action_about()
        elif bid.startswith("home-"):
            self.app.set_focus(None)
            self.app.action_show_tab(bid[len("home-"):])


class PowerTab(VerticalScroll):
    def compose(self) -> ComposeResult:
        self._presets = power.get_presets()
        with Vertical(classes="settings_card"):
            yield Static("Premade Presets", classes="card_title")
            with Horizontal(id="preset_buttons"):
                for name in self._presets:
                    yield Button(name, id=f"pbtn-{name}",
                                 classes=f"preset_btn {_COLOR.get(name, '')}".strip())
        yield Static("", id="preset_detail")
        with Vertical(classes="settings_card", id="preset_command_card"):
            yield Static("UXTU Command Output:", classes="card_title")
            yield Static("", id="preset_command")
            yield Static(
                "Note: Some commands may not be supported on every CPU family.",
                classes="field_hint", id="preset_command_note",
            )

    def on_mount(self) -> None:
        self._sync_active()

    def on_show(self) -> None:
        self._sync_active()

    def _sync_active(self) -> None:
        if au.automation_enabled():
            self._highlight("")
            self._clear_detail()
            return
        active = cfg.get("User", "Mode")
        self._highlight(active)
        if active in self._presets:
            self._show_detail(active)
        else:
            self._clear_detail()

    def _highlight(self, active: str) -> None:
        for name in self._presets:
            self.query_one(f"#pbtn-{name}", Button).set_class(name == active, "active")

    def _clear_detail(self) -> None:
        self.query_one("#preset_detail", Static).update("")
        self.query_one("#preset_command", Static).update("")
        self.query_one("#preset_command_card").display = False

    def _show_detail(self, name: str) -> None:
        desc = power._PRESET_HINTS.get(name, "")
        self.query_one("#preset_detail", Static).update(f"[b]{name} Preset[/]\n\n{desc}")
        self.query_one("#preset_command", Static).update(self._presets.get(name, ""))
        self.query_one("#preset_command_card").display = True

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if not bid.startswith("pbtn-"):
            return
        if au.automation_enabled():
            self.app.notify(_AUTOMATIONS_ON_MSG, title="Automations active", severity="warning")
            return
        name = bid[len("pbtn-"):]
        self._show_detail(name)
        self._highlight(name)
        self.apply_preset_worker(self._presets[name], name)

    @work(thread=True, exclusive=True, group="apply")
    def apply_preset_worker(self, args: str, mode: str) -> None:
        from Assets.tui.helpers import do_apply
        result = do_apply(args, mode)
        self.app.call_from_thread(self._notify_result, mode, result)

    def _notify_result(self, mode: str, result: dict) -> None:
        if not result.get("ok"):
            self.app.notify(result.get("error", "Failed to apply preset."),
                            title="Apply failed", severity="error")
            return
        if result.get("rejected"):
            self.app.notify(
                f"Preset '{mode}' applied, but some commands were rejected by the SMU. "
                "See the Status tab for details.",
                title="Applied with warnings", severity="warning")
        else:
            self.app.notify(f"Preset '{mode}' applied successfully.",
                            title="Applied", severity="information")


_HELP = (
    "Automations keep the right preset applied on their own, so you can set things up "
    "once and forget about them.\n"
    "\n"
    "[b]Override[/b]\n"
    "Switch presets automatically based on whether you're plugged in or running on "
    "battery. Choose a preset for each state:\n"
    "\n"
    "  Battery Charge    applies when you plug in the charger\n"
    "  Battery Discharge applies when you unplug it\n"
    "\n"
    "UXTU4Linux watches your power source and switches the moment it changes. Leave a "
    "slot on None to keep whatever preset is already active for that state. You'll need "
    "at least one slot set before you can turn Override on.\n"
    "\n"
    "[b]System Resume[/b]\n"
    "Re-applies the preset you choose every time your machine wakes from sleep, suspend "
    "or hibernation. It's worth setting because some hardware forgets its tuning after "
    "sleeping. This works on its own and doesn't need Override turned on."
)


class AutomationsTab(VerticalScroll):
    _SLOTS = (
        ("ac", "Preset on Battery Charge",
         "Applied automatically when you plug in the charger.",
         au.get_ac_preset, au.set_ac_preset),
        ("battery", "Preset on Battery Discharge",
         "Applied automatically when you unplug and run on battery.",
         au.get_battery_preset, au.set_battery_preset),
        ("resume", "Preset on System Resume",
         "Provides the ability to set a preset to apply on system resume from sleep/hibernation.",
         au.get_resume_preset, au.set_resume_preset),
    )

    def _slot_options(self) -> list[tuple[str, str]]:
        from Assets.tuning.power import get_presets
        from Assets.tuning.custom import get_custom_preset_names, _display_name
        opts = [("None", "")]
        opts += [(f"PM - {n} Preset", n) for n in get_presets()]
        opts += [(_display_name(n), n) for n in get_custom_preset_names()]
        return opts

    def compose(self) -> ComposeResult:
        options = self._slot_options()
        valid = {v for _, v in options}
        with Vertical(classes="settings_card"):
            yield Static("Automations", classes="card_title")
            with Horizontal(classes="setrow"):
                yield Switch(value=au.automation_enabled(), id="auto_switch")
                yield Label("Override (Battery Charge / Discharge)", classes="set_label")
            for slot_id, label, desc, getter, _ in self._SLOTS:
                cur = getter() or ""
                with Vertical(classes="auto_slot"):
                    yield Static(label, classes="field_name")
                    yield Static(desc, classes="field_hint")
                    yield Select(list(options), value=cur if cur in valid else "",
                                 allow_blank=False, id=f"slot-{slot_id}")
            with Collapsible(title="How automations work", collapsed=True):
                yield Static(_HELP, id="auto_help")

    def on_show(self) -> None:
        self.run_worker(self.recompose())

    def on_switch_changed(self, event: Switch.Changed) -> None:
        if event.value:
            if not (au.get_ac_preset() or au.get_battery_preset()):
                event.switch.value = False
                self.app.notify("Set a Battery Charge or Battery Discharge preset before "
                                "enabling Override.", title="Automations", severity="warning")
                return
            au.enable_automations()
        else:
            au.disable_automations()
        self._notify()

    def on_select_changed(self, event: Select.Changed) -> None:
        sid = event.control.id or ""
        if not sid.startswith("slot-"):
            return
        slot_id = sid[len("slot-"):]
        slot = next(s for s in self._SLOTS if s[0] == slot_id)
        getter, setter = slot[3], slot[4]
        value = event.value if isinstance(event.value, str) else ""
        if value == getter():
            return
        setter(value)
        if slot_id in ("ac", "battery") and not value:
            other = au.get_battery_preset() if slot_id == "ac" else au.get_ac_preset()
            if not other:
                au.disable_automations()
                self.query_one("#auto_switch", Switch).value = False
        if slot_id == "resume":
            self._reload()
        elif au.automation_enabled():
            self._notify()

    @work(thread=True, exclusive=True, group="auto")
    def _notify(self) -> None:
        au._notify_daemon()

    @work(thread=True, exclusive=True, group="auto")
    def _reload(self) -> None:
        from Assets.core.ipc import get_client
        client = get_client()
        if client.ping():
            client.reload_config()


class CustomEditor(VerticalScroll):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.fields = _default_fields_for_current_cpu()
        self.family = cfg.get("Info", "Family")
        self._cpu_type = cfg.get("Info", "Type")
        self._all_sections = DT_SECTION_TITLES if self._cpu_type == "Amd_Desktop_Cpu" else APU_SECTION_TITLES
        self.supported = _supported_field_keys(self.family, self.fields)
        self.sections = _active_sections(self._all_sections, self.fields, self.supported)
        self.preset_name = ""
        self._loaded_name = ""

    def compose(self) -> ComposeResult:
        names = [_display_name(n) for n in get_custom_preset_names()]
        sel_kwargs = {"value": self.preset_name} if self.preset_name in names else {}
        with Vertical(id="editor_topbar"):
            yield Static("Custom Presets", classes="card_title")
            with Horizontal(classes="topbar_row"):
                yield Select([(n, n) for n in names], prompt="Saved Presets",
                             id="preset_select", allow_blank=True, **sel_kwargs)
                yield Input(value=self.preset_name, placeholder="New preset name", id="new_name")
            with Horizontal(classes="topbar_row"):
                yield Button("Save", id="ed_save", variant="primary")
                yield Button("Apply", id="ed_apply", variant="success")
                yield Button("Duplicate", id="ed_duplicate")
                yield Button("Delete", id="ed_delete", variant="error")
        with Vertical(classes="settings_card"):
            for s in sorted(self.sections):
                rows = [self._field_row(fi) for fi in _section_indices(self.fields, s, self.supported)]
                yield Collapsible(*rows, title=self.sections[s], collapsed=True)

    def _field_row(self, fi: int) -> Vertical:
        f = self.fields[fi]
        head = Static(f["label"], classes="field_name", markup=False)
        desc = Static(f.get("hint", ""), classes="field_hint", markup=False)
        toggle = Switch(value=f["enabled"], id=f"fcb-{fi}")
        if "choices" in f:
            control = Select([(c, i) for i, c in enumerate(f["choices"])],
                             value=f["value"], allow_blank=False, id=f"fsel-{fi}",
                             disabled=not f["enabled"])
            row = Horizontal(toggle, control, classes="card_controls")
        else:
            box = Input(value=str(f["value"]), type="integer", restrict=r"-?\d*",
                        id=f"fval-{fi}", classes="card_value", disabled=not f["enabled"])
            unit = Static(f.get("unit", ""), classes="unit")
            row = Horizontal(toggle, box, unit, classes="card_controls")
        return Vertical(head, desc, row, classes="field_card")

    def on_switch_changed(self, event: Switch.Changed) -> None:
        cid = event.control.id or ""
        if cid.startswith("fcb-"):
            fi = int(cid[4:])
            self.fields[fi]["enabled"] = event.value
            for wid in (f"#fval-{fi}", f"#fsel-{fi}"):
                try:
                    self.query_one(wid).disabled = not event.value
                except Exception:
                    pass

    def on_select_changed(self, event: Select.Changed) -> None:
        sid = event.control.id or ""
        if sid == "preset_select":
            if isinstance(event.value, str) and event.value != self.preset_name:
                self.run_worker(self._load_preset(event.value))
        elif sid.startswith("fsel-") and isinstance(event.value, int):
            self.fields[int(sid[5:])]["value"] = event.value

    def on_input_submitted(self, event: Input.Submitted) -> None:
        iid = event.control.id or ""
        if iid.startswith("fval-"):
            self._commit_input(int(iid[5:]), event.value, event.control)

    def _commit_input(self, fi: int, raw: str, widget: Input) -> None:
        try:
            value = int(raw)
        except (TypeError, ValueError):
            return
        f = self.fields[fi]
        value = clamp_field(value, f)
        f["value"] = value
        _enforce_clk_clamp(self.fields, f["key"])
        widget.value = str(value)

    def _sync_inputs(self) -> None:
        for inp in self.query(Input):
            iid = inp.id or ""
            if iid.startswith("fval-"):
                fi = int(iid[5:])
                try:
                    self.fields[fi]["value"] = clamp_field(int(inp.value), self.fields[fi])
                except (TypeError, ValueError):
                    pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "ed_save":
            self._sync_inputs()
            name = self.query_one("#new_name", Input).value.strip() or self.preset_name
            if not name:
                self.app.notify("Enter a preset name first.", title="Save preset",
                                severity="warning")
                return
            replace = self._loaded_name if self._loaded_name and self._loaded_name != name else None
            self.preset_name = name
            self._do_save(name, replace)
        elif bid == "ed_apply":
            from Assets.tuning import automations as au
            if au.automation_enabled():
                self.app.notify(
                    "Automations are on. Turn off Override in the Automations tab to "
                    "apply a preset manually.",
                    title="Automations active", severity="warning")
                return
            self._sync_inputs()
            self._do_apply()
        elif bid == "ed_duplicate":
            self._sync_inputs()
            source = self.query_one("#new_name", Input).value.strip() or self.preset_name
            new_name = unique_preset_name(source)
            self.preset_name = new_name
            self._do_save(new_name)
            self.app.notify(f"Duplicated to '{new_name}'.", title="Duplicate preset",
                            severity="information")
        elif bid == "ed_delete":
            sel = self.query_one("#preset_select", Select)
            if not isinstance(sel.value, str):
                self.app.notify("Select a saved preset to delete.", title="Delete preset",
                                severity="warning")
                return
            name = sel.value
            self.app.push_screen(ConfirmModal(f"Delete preset '{name}'?"),
                                 lambda ok, n=name: self._do_delete(n) if ok else None)

    async def _load_preset(self, name: str) -> None:
        fields = load_preset_fields(name)
        if fields is None:
            self.app.notify(f"Preset '{name}' not found.", title="Load preset", severity="error")
            return
        self.fields = fields
        self.preset_name = name
        self._loaded_name = name
        self.supported = _supported_field_keys(self.family, self.fields)
        self.sections = _active_sections(self._all_sections, self.fields, self.supported)
        await self.recompose()

    @work(thread=True, exclusive=True, group="custom")
    def _do_save(self, name: str, replace: str | None = None) -> None:
        save_preset(name, self.fields, replace)
        self.app.call_from_thread(self._after_save, name)

    @work(thread=True, exclusive=True, group="custom")
    def _do_apply(self) -> None:
        args = build_args(self.fields, self._cpu_type)
        if not args.strip():
            self.app.call_from_thread(
                lambda: self.app.notify("No parameters are enabled.", title="Apply preset",
                                        severity="warning"))
            return
        from Assets.tuning.power import apply_preset
        name = self.preset_name or "Custom"
        result = apply_preset(args, name)
        if result.get("ok"):
            self.app.call_from_thread(self.app.notify, f"Preset '{name}' applied successfully.",
                                      title="Applied", severity="information")
        else:
            err = result.get("error", "apply failed")
            self.app.call_from_thread(
                lambda: self.app.notify(err, title="Apply failed", severity="error"))

    @work(thread=True, exclusive=True, group="custom")
    def _do_delete(self, name: str) -> None:
        delete_preset(name)
        self.app.call_from_thread(self._after_delete, name)

    def _after_save(self, name: str) -> None:
        self._loaded_name = name
        self._refresh_presets(name)

    def _after_delete(self, name: str) -> None:
        self.run_worker(self._reset_to_default())

    async def _reset_to_default(self) -> None:
        self.preset_name = ""
        self._loaded_name = ""
        self.fields = _default_fields_for_current_cpu()
        self.supported = _supported_field_keys(self.family, self.fields)
        self.sections = _active_sections(self._all_sections, self.fields, self.supported)
        await self.recompose()

    def _refresh_presets(self, select: str | None) -> None:
        names = [_display_name(n) for n in get_custom_preset_names()]
        sel = self.query_one("#preset_select", Select)
        sel.set_options([(n, n) for n in names])
        if select and select in names:
            sel.value = select
            self.query_one("#new_name", Input).value = select


def _rows(pairs: list[tuple[str, str]]) -> str:
    return "\n".join(f"  {label:<14}{value}" for label, value in pairs)


class HardwareTab(VerticalScroll):
    def compose(self) -> ComposeResult:
        with Vertical(classes="settings_card"):
            yield Static("System Info", classes="card_title")
            yield Collapsible(Static("Loading…", id="hw_device"),
                              title="Device Information", collapsed=False)
            yield Collapsible(Static("Loading…", id="hw_processor"),
                              title="Processor Information", collapsed=False)
            yield Collapsible(Static("Loading…", id="hw_memory"),
                              title="Memory Information", collapsed=False)
            yield Collapsible(Static("", id="hw_battery"),
                              title="Battery Information", collapsed=False, id="hw_battery_card")

    def on_mount(self) -> None:
        self._load_static()
        self.set_interval(2.0, self.refresh_battery)
        self.refresh_battery()

    @work(thread=True, exclusive=True, group="hw")
    def _load_static(self) -> None:
        from Assets.core import hardware as hw
        dev = hw._parse_device_info()
        proc = hw._parse_processor_dmidecode()
        l1, l2, l3 = hw._parse_cache_sizes()
        mem = hw._parse_memory()
        device = _rows([("Name", dev["name"]), ("Producer", dev["producer"]), ("Model", dev["model"])])
        processor = _rows([
            ("Processor", cfg.get("Info", "CPU")), ("Codename", cfg.get("Info", "Family")),
            ("Architecture", cfg.get("Info", "Architecture")), ("Signature", cfg.get("Info", "Signature")),
            ("Cores", proc["cores"]), ("Threads", proc["threads"]), ("Base clock", proc["base_clock"]),
            ("L1 cache", l1), ("L2 cache", l2), ("L3 cache", l3)])
        memory = _rows([
            ("Memory", mem["summary"]), ("Producer", mem["manufacturer"]),
            ("Model", mem["part_number"]), ("Width", mem["width"]), ("Modules", mem["modules"])])
        self.app.call_from_thread(self.query_one("#hw_device", Static).update, device)
        self.app.call_from_thread(self.query_one("#hw_processor", Static).update, processor)
        self.app.call_from_thread(self.query_one("#hw_memory", Static).update, memory)

    @work(thread=True, exclusive=True, group="hwbat")
    def refresh_battery(self) -> None:
        from Assets.core import hardware as hw
        bat = hw._parse_battery()
        self.app.call_from_thread(self._render_battery, bat)

    def _render_battery(self, bat: dict | None) -> None:
        card = self.query_one("#hw_battery_card", Collapsible)
        if not bat:
            card.display = False
            return
        card.display = True
        self.query_one("#hw_battery", Static).update(_rows([
            ("Health", bat["health"]), ("Cycles", bat["cycles"]),
            ("Full charge", bat["full_charge"]), ("Design cap.", bat["design_cap"]),
            ("Charge rate", bat["charge_rate"])]))


def _strip(name: str) -> str:
    return (name or "").removesuffix("_custom_preset")


class StatusTab(VerticalScroll):
    def compose(self) -> ComposeResult:
        with Vertical(id="status_panel"):
            yield Static("Daemon status", classes="card_title")
            yield Static("", id="status_info")
        with Vertical(id="status_smu_card"):
            yield Static("SMU output", id="status_smu_head", classes="card_title")
            yield Static("", id="status_smu")

    def on_mount(self) -> None:
        self._timer = None
        self._watch = None
        self._last_ac = None
        self.refresh_status()

    def on_show(self) -> None:
        self.refresh_status()
        self._reschedule()

    def on_hide(self) -> None:
        self._stop_timers()

    def _stop_timers(self) -> None:
        for t in (self._timer, self._watch):
            if t is not None:
                t.stop()
        self._timer = None
        self._watch = None

    def _reschedule(self) -> None:
        from Assets.tui.helpers import on_ac
        self._stop_timers()
        self._last_ac = on_ac()
        self._watch = self.set_interval(2.0, self._check_power)
        if cfg.get("Settings", "ReApply", "0") == "1":
            interval = cfg.parse_interval(cfg.get("Settings", "Time", "3"))
            self._timer = self.set_interval(interval, self.refresh_status)

    def _check_power(self) -> None:
        from Assets.tui.helpers import on_ac
        ac = on_ac()
        if ac != self._last_ac:
            self._last_ac = ac
            self.refresh_status()

    @work(thread=True, exclusive=True, group="status_tab")
    def refresh_status(self) -> None:
        from Assets.core.ipc import get_client
        st = get_client().status()
        self.app.call_from_thread(self._update_panel, st)

    def _update_panel(self, st: dict) -> None:
        panel = self.query_one("#status_info", Static)
        head = self.query_one("#status_smu_head", Static)
        smu = self.query_one("#status_smu", Static)

        if not st.get("ok"):
            panel.update("Daemon         [yellow]Stopped[/]\n"
                         "Install or start it from the Settings tab.")
            head.update("SMU output")
            smu.update("")
            return

        on_ac = st.get("on_ac")
        loop = st.get("running_loop")
        automation = st.get("automation")
        mode = _strip(st.get("mode") or "")
        interval = st.get("interval", "?")
        profile = cfg.get_loaded_preset()

        rows = ["Daemon         [green]Running[/]"]
        if profile:
            rows.append(f"Profile        {profile}")
        rows += [
            f"Power source   {'AC' if on_ac else 'Battery'}",
            f"Active preset  {mode or '[dim]—[/]'}",
            f"Auto-reapply   {f'[green]ON[/] (every {interval}s)' if loop else '[dim]OFF[/]'}",
        ]
        if automation:
            ac = _strip(cfg.get("Automations", "OnAC", ""))
            bat = _strip(cfg.get("Automations", "OnBattery", ""))
            rows.append("Automations    [green]ON[/]")
            if ac:
                rows.append(f"  On Charge    {ac}")
            if bat:
                rows.append(f"  On Discharge {bat}")
        else:
            rows.append("Automations    [dim]OFF[/]")
        resume = _strip(cfg.get("Automations", "OnResume", ""))
        if resume:
            rows.append(f"  On Resume    {resume}")
        panel.update("\n".join(rows))

        out = st.get("last_output") or ""
        if not out:
            head.update("SMU output")
            smu.update("[dim]No preset applied yet.[/]")
            return
        head.update("[yellow]SMU output — some commands were rejected[/]"
                    if st.get("last_rejected") else "[green]SMU output — OK[/]")
        smu.update(out)


_TOGGLES = (
    ("applyonstart", "Apply preset on daemon start", "Settings", "ApplyOnStart"),
    ("softwareupdate", "Software update", "Settings", "SoftwareUpdate"),
    ("debug", "Debug logging", "Settings", "Debug"),
)


class SettingsTab(VerticalScroll):
    def compose(self) -> ComposeResult:
        with Vertical(classes="settings_card"):
            yield Static("General", classes="card_title")
            for cid, label, section, key in _TOGGLES:
                with Horizontal(classes="setrow"):
                    yield Switch(value=cfg.get(section, key, "0") == "1", id=f"set-{cid}")
                    yield Label(label, classes="set_label")
            with Horizontal(classes="setrow"):
                yield Switch(value=cfg.get("Settings", "ReApply", "0") == "1", id="set-reapply")
                yield Label("Reapply preset periodically", classes="set_label")
            with Horizontal(classes="setrow"):
                yield Input(value=cfg.get("Settings", "Time", "3"), type="integer",
                            id="reapply_interval", restrict=r"\d*")
                yield Label("Reapply interval (seconds)", classes="set_label")

        with Vertical(classes="settings_card"):
            yield Static("Daemon service", classes="card_title")
            yield Static("", id="daemon_status")
            with Grid(classes="daemon_grid"):
                yield Button("Install / repair", id="daemon_install")
                yield Button("Restart", id="daemon_restart")
                yield Button("View logs", id="daemon_logs")
                yield Button("Uninstall", id="daemon_uninstall", variant="error")

        with Vertical(classes="settings_card"):
            yield Static("Hardware & reset", classes="card_title")
            with Horizontal(classes="row daemon_buttons"):
                yield Button("Re-detect hardware", id="redetect")
                yield Button("Reset all settings", id="reset_all", variant="error")

    def on_mount(self) -> None:
        self._refresh_daemon_status()

    def on_switch_changed(self, event: Switch.Changed) -> None:
        cid = event.control.id.split("-", 1)[1]
        if cid == "reapply":
            cfg.set_config("Settings", "ReApply", "1" if event.value else "0")
            cfg.save()
            self._apply_reapply(event.value)
            return
        _, _, section, key = next(t for t in _TOGGLES if t[0] == cid)
        cfg.set_config(section, key, "1" if event.value else "0")
        cfg.save()
        if cid == "debug":
            self._reload_config()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "reapply_interval":
            return
        if not power.update_reapply_interval(event.value):
            return
        clamped = cfg.get("Settings", "Time", "3")
        event.input.value = clamped
        self.app.notify(f"Reapply interval set to {clamped}s.", title="Reapply")
        if cfg.get("Settings", "ReApply", "0") == "1":
            self._apply_reapply(True)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "redetect":
            self._redetect()
        elif bid == "reset_all":
            from Assets.tui.modals import ConfirmModal
            self.app.push_screen(
                ConfirmModal("Reset all settings and custom presets? This cannot be undone."),
                lambda ok: self.app.exit("reset") if ok else None)
        elif bid == "daemon_install":
            from Assets.daemon.service import has_systemctl
            if not has_systemctl():
                from Assets.tui.modals import ManualDaemonModal
                self.app.push_screen(ManualDaemonModal(),
                                     lambda _=None: self._refresh_daemon_status())
            else:
                self._daemon_action("install")
        elif bid == "daemon_restart":
            self._daemon_action("restart")
        elif bid == "daemon_uninstall":
            self._daemon_action("uninstall")
        elif bid == "daemon_logs":
            from Assets.tui.modals import DaemonLogModal
            self.app.push_screen(DaemonLogModal())

    @work(group="settings_daemon")
    async def _daemon_action(self, kind: str) -> None:
        import asyncio
        from Assets.daemon import service
        from Assets.tui.helpers import ensure_sudo

        if kind == "uninstall":
            from Assets.tui.modals import ConfirmModal
            if not await self.app.push_screen_wait(ConfirmModal("Uninstall the daemon service?")):
                return

        if not await ensure_sudo(self.app):
            self.app.notify("Cancelled — administrator access not granted.",
                            title="Daemon", severity="warning")
            return

        fn = {"install": service.install_service,
              "restart": service.restart_service,
              "uninstall": service.uninstall_service}[kind]
        verb = {"install": "Installing", "restart": "Restarting", "uninstall": "Uninstalling"}[kind]
        self.app.notify(f"{verb} daemon…", title="Daemon")
        result = await asyncio.to_thread(fn)
        if kind != "uninstall" and result.get("ok"):
            await asyncio.to_thread(service.wait_for_daemon)
        self._refresh_daemon_status()
        if not result.get("ok"):
            self.app.notify(result.get("error", "Action failed."),
                            title="Daemon", severity="error")
        elif result.get("warning"):
            self.app.notify(result["warning"], title="Daemon", severity="warning")
        else:
            done = {"install": "Daemon installed.", "restart": "Daemon restarted.",
                    "uninstall": "Daemon uninstalled."}[kind]
            self.app.notify(done, title="Daemon")

    @work(group="settings_redetect")
    async def _redetect(self) -> None:
        import asyncio
        from Assets.core.ipc import get_client
        if not get_client().ping():
            self.app.notify("Daemon is not running — cannot detect hardware.",
                            title="Hardware detection", severity="warning")
            return
        from Assets.core.hardware import detect
        await asyncio.to_thread(detect)
        cfg.save()
        from Assets.tui.modals import HardwareInfoModal
        self.app.push_screen(HardwareInfoModal())

    @work(thread=True, exclusive=True, group="settings")
    def _apply_reapply(self, on: bool) -> None:
        from Assets.core.ipc import get_client
        client = get_client()
        if not client.ping():
            self.app.call_from_thread(self.app.notify, "Daemon is not running.",
                                      title="Reapply", severity="warning")
            return
        if on:
            result = client.apply_saved()
            if not result.get("ok"):
                self.app.call_from_thread(
                    self.app.notify, "Select a preset in the Premade Presets tab first.",
                    title="Reapply", severity="warning")
        else:
            client.stop_loop()

    @work(thread=True, exclusive=True, group="settings_status")
    def _refresh_daemon_status(self) -> None:
        from Assets.daemon.service import service_running, service_enabled, has_systemctl
        if not has_systemctl():
            from Assets.core.ipc import get_client
            if get_client().ping():
                text = "Service: [green]Running[/] ([dim]started manually[/])"
            else:
                text = "Service: [dim]Not running[/] ([dim]no systemctl — start manually[/])"
        elif service_running():
            boot = "enabled" if service_enabled() else "disabled"
            text = f"Service: [green]Running[/] ([dim]start on boot: {boot}[/])"
        else:
            text = "Service: [dim]Stopped[/]"
        self.app.call_from_thread(self.query_one("#daemon_status", Static).update, text)

    @work(thread=True, exclusive=True, group="settings")
    def _reload_config(self) -> None:
        from Assets.core.ipc import get_client
        client = get_client()
        if client.ping():
            client.reload_config()
