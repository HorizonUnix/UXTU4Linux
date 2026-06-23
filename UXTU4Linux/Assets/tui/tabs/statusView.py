from __future__ import annotations

from textual import work
from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Static

from Assets.core import config as cfg


def _strip(name: str) -> str:
    return (name or "").removesuffix("_custom_preset")


def _fmt_metric(value, unit: str) -> str:
    if value is None:
        return "[dim]—[/]"
    return f"{round(value)} {unit}"


class StatusTab(VerticalScroll):
    def compose(self) -> ComposeResult:
        with Vertical(id="status_panel"):
            yield Static("Daemon status", classes="card_title")
            yield Static("", id="status_info")
        with Vertical(id="status_adaptive_card"):
            yield Static("Adaptive Mode", classes="card_title")
            yield Static("", id="status_adaptive")
        with Vertical(id="status_smu_card"):
            yield Static("SMU output", id="status_smu_head", classes="card_title")
            yield Static("", id="status_smu")

    def on_mount(self) -> None:
        self._timer = None
        self._watch = None
        self._adaptive_timer = None
        self._last_ac = None
        self.refresh_status()
        self.refresh_adaptive()

    def on_show(self) -> None:
        self.refresh_status()
        self.refresh_adaptive()
        self._reschedule()

    def on_hide(self) -> None:
        self._stop_timers()

    def _stop_timers(self) -> None:
        for t in (self._timer, self._watch, self._adaptive_timer):
            if t is not None:
                t.stop()
        self._timer = None
        self._watch = None
        self._adaptive_timer = None

    def _reschedule(self) -> None:
        from Assets.tui.helpers import on_ac
        self._stop_timers()
        self._last_ac = on_ac()
        self._watch = self.set_interval(2.0, self._check_power)
        self._adaptive_timer = self.set_interval(1.5, self.refresh_adaptive)
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

    @work(thread=True, exclusive=True, group="status_adaptive")
    def refresh_adaptive(self) -> None:
        from Assets.core.ipc import get_client
        st = get_client().adaptive_status()
        self.app.call_from_thread(self._update_adaptive, st)

    def _update_adaptive(self, st: dict) -> None:
        try:
            panel = self.query_one("#status_adaptive", Static)
        except Exception:
            return
        if not st.get("running"):
            panel.update("Adaptive       [dim]OFF[/]")
            return
        self.refresh_status()
        sample = st.get("sample") or {}
        rows = [
            "Adaptive       [green]ON[/]",
            f"Preset         {st.get('preset') or '—'}",
            f"CPU temp       {_fmt_metric(sample.get('cpu_temp'), '°C')}",
            f"CPU load       {_fmt_metric(sample.get('cpu_load'), '%')}",
            f"CPU power      {_fmt_metric(sample.get('cpu_power'), 'W')}",
            f"CPU clock      {_fmt_metric(sample.get('cpu_clk'), 'MHz')}",
            f"iGPU load      {_fmt_metric(sample.get('igpu_load'), '%')}",
            f"iGPU clock     {_fmt_metric(sample.get('igpu_clk'), 'MHz')}",
        ]
        applied = st.get("applied")
        if applied:
            rows.append(f"Applied        {applied}")
        panel.update("\n".join(rows))
