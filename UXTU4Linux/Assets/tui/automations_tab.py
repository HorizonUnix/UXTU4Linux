from __future__ import annotations

from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Collapsible, Label, Select, Static, Switch

from Assets.tuning import automations as au


_HELP = (
    "[b]Override[/b]\n"
    "When ON, the daemon automatically switches presets based on your power source:\n"
    "  • On Battery  — applied when you unplug the charger\n"
    "  • On AC Power — applied when you plug it back in\n"
    "Leave a slot on None to keep using your current Power Management preset for\n"
    "that state. You need at least one of On AC / On Battery set to turn Override on.\n"
    "\n"
    "[b]On Resume[/b]\n"
    "Applied once each time the machine wakes from sleep or suspend. This works on\n"
    "its own — Override does not need to be ON for it to take effect."
)


class AutomationsTab(VerticalScroll):
    _SLOTS = (
        ("battery", "On Battery", au.get_battery_preset, au.set_battery_preset),
        ("ac", "On AC Power", au.get_ac_preset, au.set_ac_preset),
        ("resume", "On Resume", au.get_resume_preset, au.set_resume_preset),
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
                yield Label("Override (AC / Battery)", classes="set_label")
            for slot_id, label, getter, _ in self._SLOTS:
                cur = getter() or ""
                with Horizontal(classes="row"):
                    yield Label(label, classes="auto_label")
                    yield Select(list(options), value=cur if cur in valid else "",
                                 allow_blank=False, id=f"slot-{slot_id}")
            with Collapsible(title="How automations work", collapsed=True):
                yield Static(_HELP, id="auto_help")

    def on_switch_changed(self, event: Switch.Changed) -> None:
        if event.value:
            if not (au.get_ac_preset() or au.get_battery_preset()):
                event.switch.value = False
                self.app.notify("Configure an On AC or On Battery preset before enabling Override.",
                                severity="warning")
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
        getter, setter = slot[2], slot[3]
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
