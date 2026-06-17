from __future__ import annotations

from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Static

from Assets.core import config as cfg
from Assets.tuning import automations as au, power

_COLOR = {"Eco": "eco", "Balance": "balance", "Performance": "perf", "Extreme": "extreme"}

_AUTOMATIONS_ON_MSG = (
    "Automations are on. Turn off Override in the Automations tab to apply a preset manually."
)


class PowerTab(Vertical):
    def compose(self) -> ComposeResult:
        self._presets = power.get_presets()
        with Vertical(classes="settings_card"):
            yield Static("Premade Preset", classes="card_title")
            with Horizontal(id="preset_buttons"):
                for name in self._presets:
                    yield Button(name, id=f"pbtn-{name}",
                                 classes=f"preset_btn {_COLOR.get(name, '')}".strip())
        yield Static("", id="preset_detail")

    def on_mount(self) -> None:
        self._sync_active()

    def on_show(self) -> None:
        self._sync_active()

    def _sync_active(self) -> None:
        if au.automation_enabled():
            self._highlight("")
            self.query_one("#preset_detail", Static).update("")
            return
        active = cfg.get("User", "Mode")
        self._highlight(active)
        if active in self._presets:
            self._show_detail(active)
        else:
            self.query_one("#preset_detail", Static).update("")

    def _highlight(self, active: str) -> None:
        for name in self._presets:
            self.query_one(f"#pbtn-{name}", Button).set_class(name == active, "active")

    def _show_detail(self, name: str) -> None:
        desc = power._PRESET_HINTS.get(name, "")
        self.query_one("#preset_detail", Static).update(f"[b]{name} Preset[/]\n\n{desc}")

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
        from Assets.tui.ipc_worker import do_apply
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
