from __future__ import annotations

from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Select, Static

from Assets.tuning import automations as au


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
            for slot_id, label, desc, getter, _ in self._SLOTS:
                cur = getter() or ""
                with Vertical(classes="auto_slot"):
                    yield Static(label, classes="field_name")
                    yield Static(desc, classes="field_hint")
                    yield Select(list(options), value=cur if cur in valid else "",
                                 allow_blank=False, id=f"slot-{slot_id}")
        with Vertical(classes="settings_card"):
            yield Static("AutoOC — Auto Curve Optimiser", classes="card_title")
            yield Static(
                "Proactively steps the Curve Optimiser toward the maximum safe undervolt. "
                "Works with all preset types. Backs off automatically if a Machine Check "
                "Exception (MCE) is detected in the kernel log.",
                classes="field_hint",
            )
            yield Static("", id="autooc_status", classes="field_hint")
            yield Static("", id="autooc_offsets", classes="field_hint")
            with Horizontal(classes="row daemon_buttons"):
                yield Button("Start", id="autooc_toggle", variant="success")
                yield Button("Reset", id="autooc_reset")

    def on_mount(self) -> None:
        self._refresh_autooc()
        self.set_interval(2.0, self._refresh_autooc)

    def _refresh_autooc(self) -> None:
        self._fetch_autooc_status()

    @work(thread=True, exclusive=True, group="autooc_poll")
    def _fetch_autooc_status(self) -> None:
        from Assets.core.ipc import get_client
        st = get_client().autooc_status()
        self.app.call_from_thread(self._render_autooc, st)

    def _render_autooc(self, st: dict) -> None:
        from textual.css.query import NoMatches
        try:
            status_w = self.query_one("#autooc_status", Static)
            offsets_w = self.query_one("#autooc_offsets", Static)
            btn = self.query_one("#autooc_toggle", Button)
        except NoMatches:
            return
        running = st.get("running", False)
        mce_count = st.get("mce_count", 0)
        last_mce = st.get("last_mce")
        cpu_offset = st.get("cpu_offset", 0)
        igpu_offset = st.get("igpu_offset", 0)
        if running:
            count_str = f"{mce_count} MCE{'s' if mce_count != 1 else ''}"
            status = f"[green]Running[/] · {count_str}"
            if last_mce:
                status += f" · last: {last_mce}"
            btn.label = "Stop"
            btn.variant = "error"
        else:
            status = "[dim]Stopped[/]"
            btn.label = "Start"
            btn.variant = "success"
        status_w.update(status)
        if running:
            offsets_w.update(
                f"CPU CO: [b]{cpu_offset}[/] steps · iGPU CO: [b]{igpu_offset}[/] steps"
                f" (max {30})")
        else:
            offsets_w.update("")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "autooc_toggle":
            self._autooc_toggle()
        elif bid == "autooc_reset":
            self._autooc_reset_ceiling()

    @work(thread=True, exclusive=True, group="autooc_cmd")
    def _autooc_toggle(self) -> None:
        from Assets.core.ipc import get_client
        client = get_client()
        if client.autooc_status().get("running"):
            client.autooc_stop()
            self.app.call_from_thread(
                self.app.notify, "AutoOC stopped.", title="AutoOC")
        else:
            client.autooc_start()
            self.app.call_from_thread(
                self.app.notify, "AutoOC started — stepping CO toward max safe undervolt.", title="AutoOC")
        self.app.call_from_thread(self._render_autooc, client.autooc_status())

    @work(thread=True, exclusive=True, group="autooc_cmd")
    def _autooc_reset_ceiling(self) -> None:
        from Assets.core.ipc import get_client
        client = get_client()
        client.autooc_reset()
        self.app.call_from_thread(
            self.app.notify,
            "AutoOC reset — CO offsets cleared, controllers restarted from 0.",
            title="AutoOC")
        self.app.call_from_thread(self._render_autooc, client.autooc_status())

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
        if slot_id == "resume":
            self._reload()
        else:
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
