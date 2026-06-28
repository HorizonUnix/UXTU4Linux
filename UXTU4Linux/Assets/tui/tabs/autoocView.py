from __future__ import annotations

from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Static


class AutoOCTab(VerticalScroll):
    def compose(self) -> ComposeResult:
        with Vertical(classes="settings_card"):
            yield Static("AutoOC — CO Crash Protection", classes="card_title")
            yield Static(
                "AutoOC automatically backs off the Curve Optimiser limit when a "
                "Machine Check Exception (MCE) is detected in the kernel log.\n\n"
                "When Adaptive Mode is running with Curve Optimiser enabled, any MCE "
                "reduces the CO ceiling by 5 steps, protecting system stability.",
                classes="field_hint",
            )
        with Vertical(classes="settings_card"):
            yield Static("MCE Monitor", classes="card_title")
            yield Static("", id="autooc_status")
            with Horizontal(classes="card_controls"):
                yield Button("Stop Monitor", id="autooc_toggle", variant="error")
                yield Button("Reset Ceiling", id="autooc_reset", variant="default")
        with Vertical(classes="settings_card"):
            yield Static("CO Safety Ceiling", classes="card_title")
            yield Static(
                "The ceiling is established when the first MCE is detected. "
                "Adaptive Mode will not raise the CO limit above this value. "
                "Reset to remove the ceiling and allow Adaptive to use the full preset range.",
                classes="field_hint",
            )
            yield Static("", id="autooc_ceiling")

    def on_mount(self) -> None:
        self._refresh()
        self.set_interval(2.0, self._refresh)

    def on_show(self) -> None:
        self._refresh()

    def _refresh(self) -> None:
        self._fetch_status()

    @work(thread=True, exclusive=True, group="autooc_status")
    def _fetch_status(self) -> None:
        from Assets.core.ipc import get_client
        st = get_client().autooc_status()
        self.app.call_from_thread(self._render, st)

    def _render(self, st: dict) -> None:
        running = st.get("running", False)
        stable_co = st.get("stable_co")
        mce_count = st.get("mce_count", 0)
        last_mce = st.get("last_mce")

        btn = self.query_one("#autooc_toggle", Button)
        if running:
            status_lines = [
                "  Monitor     [green]Running[/]",
                f"  MCE Events  {mce_count}",
            ]
            if last_mce:
                status_lines.append(f"  Last MCE     {last_mce}")
            btn.label = "Stop Monitor"
            btn.variant = "error"
        else:
            status_lines = ["  Monitor     [dim]Stopped[/]"]
            btn.label = "Start Monitor"
            btn.variant = "success"

        self.query_one("#autooc_status", Static).update("\n".join(status_lines))

        if stable_co is not None:
            ceiling_text = (
                f"[b]CO ceiling: {stable_co}[/]\n"
                f"[dim]Adaptive CO will not exceed {stable_co}[/]"
            )
        else:
            ceiling_text = "[dim]No ceiling established — no MCEs detected yet.[/]"
        self.query_one("#autooc_ceiling", Static).update(ceiling_text)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "autooc_toggle":
            self._toggle()
        elif bid == "autooc_reset":
            self._reset_ceiling()

    @work(thread=True, exclusive=True, group="autooc_cmd")
    def _toggle(self) -> None:
        from Assets.core.ipc import get_client
        client = get_client()
        st = client.autooc_status()
        if st.get("running"):
            client.autooc_stop()
            self.app.call_from_thread(
                self.app.notify, "MCE monitor stopped.", title="AutoOC")
        else:
            client.autooc_start()
            self.app.call_from_thread(
                self.app.notify, "MCE monitor started.", title="AutoOC")
        new_st = client.autooc_status()
        self.app.call_from_thread(self._render, new_st)

    @work(thread=True, exclusive=True, group="autooc_cmd")
    def _reset_ceiling(self) -> None:
        from Assets.core.ipc import get_client
        client = get_client()
        client.autooc_reset()
        self.app.call_from_thread(
            self.app.notify, "CO ceiling reset — Adaptive can now use the full preset range.",
            title="AutoOC")
        new_st = client.autooc_status()
        self.app.call_from_thread(self._render, new_st)
