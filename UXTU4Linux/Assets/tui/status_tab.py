from __future__ import annotations

from textual import work
from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Static

from Assets.core import config as cfg


def _strip(name: str) -> str:
    return (name or "").removesuffix("_custom_preset")


class StatusTab(Vertical):
    def compose(self) -> ComposeResult:
        with Vertical(id="status_panel"):
            yield Static("Daemon status", classes="card_title")
            yield Static("", id="status_info")
        with Vertical(id="status_smu_card"):
            yield Static("SMU output (live)", id="status_smu_head", classes="card_title")
            with VerticalScroll(id="status_smu_scroll"):
                yield Static("", id="status_smu")

    def on_mount(self) -> None:
        self._last_smu = ""
        self.refresh_status()
        self.set_interval(1.5, self.refresh_status)

    def on_show(self) -> None:
        scroll = self.query_one("#status_smu_scroll", VerticalScroll)
        self.call_after_refresh(scroll.scroll_end, animate=False)

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
            head.update("SMU output (live)")
            smu.update("")
            return

        on_ac = st.get("on_ac")
        loop = st.get("running_loop")
        automation = st.get("automation")
        mode = _strip(st.get("mode") or "") or "none"
        interval = st.get("interval", "?")
        profile = cfg.get_loaded_preset()

        rows = ["Daemon         [green]Running[/]"]
        if profile:
            rows.append(f"Preset profile {profile}")
        rows += [
            f"Power source   {'AC' if on_ac else 'Battery'}",
            f"Active preset  {mode}",
            f"Auto-reapply   {f'[green]ON[/] (every {interval}s)' if loop else '[dim]OFF[/]'}",
        ]
        if automation:
            ac = _strip(cfg.get("Automations", "OnAC", "")) or "(Power Management preset)"
            bat = _strip(cfg.get("Automations", "OnBattery", "")) or "(Power Management preset)"
            rows.append("Automations    [green]ON[/]")
            rows.append(f"  On AC        {ac}")
            rows.append(f"  On Battery   {bat}")
        else:
            rows.append("Automations    [dim]OFF[/]")
        panel.update("\n".join(rows))

        out = st.get("last_output") or ""
        if not out:
            head.update("SMU output (live)")
            smu.update("[dim]No preset applied yet.[/]")
            return
        head.update("[yellow]SMU output — some commands were rejected[/]"
                    if st.get("last_rejected") else "[green]SMU output — OK[/]")
        smu.update(out)
        if out != self._last_smu:
            self._last_smu = out
            scroll = self.query_one("#status_smu_scroll", VerticalScroll)
            self.call_after_refresh(scroll.scroll_end, animate=False)
