from __future__ import annotations

from textual import work
from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, ContentSwitcher, Static

from Assets.core import config as cfg


_SUPPORTED = ("Amd_Apu", "Amd_Desktop_Cpu")


class SetupWizard(ModalScreen):
    def compose(self) -> ComposeResult:
        with Vertical(id="setup_dialog"):
            yield Static("First-time setup", classes="dialog_title")
            yield Static("", id="setup_progress")
            with ContentSwitcher(initial="welcome", id="setup_switcher"):
                with Vertical(id="welcome"):
                    yield Static("Welcome", classes="setup_step_title")
                    yield Static(
                        "Universal x86 Tuning Utility for AMD Zen CPUs on Linux.\n"
                        "Ported from the original Universal x86 Tuning Utility for Windows.\n"
                        "Tune power, clocks and the Curve Optimiser through a root daemon.",
                        classes="setup_body")
                    with Horizontal(classes="setup_buttons"):
                        yield Button("Begin setup", id="setup_begin", variant="primary")
                with Vertical(id="daemon"):
                    yield Static("Background daemon", classes="setup_step_title")
                    yield Static(
                        "The daemon runs as root and is the only process allowed to apply\n"
                        "tuning to your hardware. It is required.",
                        classes="setup_body")
                    yield Static("", id="setup_daemon_status")
                    with Horizontal(classes="setup_buttons"):
                        yield Button("Install / enable daemon", id="setup_install", variant="primary")
                        yield Button("Continue", id="setup_daemon_continue", disabled=True)
                with Vertical(id="hardware"):
                    yield Static("Detect hardware", classes="setup_step_title")
                    yield Static(
                        "Detect your processor so the matching preset profile can load.\n"
                        "This requires the daemon to be running.",
                        classes="setup_body")
                    yield Static("", id="setup_hw_result")
                    with Horizontal(classes="setup_buttons"):
                        yield Button("Detect hardware", id="setup_detect", variant="primary")
                        yield Button("Finish", id="setup_finish", disabled=True, variant="success")

    def on_mount(self) -> None:
        self._set_step(1)

    def _set_step(self, n: int) -> None:
        dots = "  ".join("[#2f81f7]●[/]" if i <= n else "[dim]○[/]" for i in range(1, 4))
        self.query_one("#setup_progress", Static).update(f"{dots}    [dim]Step {n} of 3[/]")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "setup_begin":
            self.query_one(ContentSwitcher).current = "daemon"
            self._set_step(2)
            self._refresh_daemon()
        elif bid == "setup_install":
            self._install_daemon()
        elif bid == "setup_daemon_continue":
            self.query_one(ContentSwitcher).current = "hardware"
            self._set_step(3)
        elif bid == "setup_detect":
            self.query_one("#setup_hw_result", Static).update("Detecting hardware…")
            self._detect()
        elif bid == "setup_finish":
            cfg.save()
            self.app.exit("setup-done")

    @work(group="setup_install")
    async def _install_daemon(self) -> None:
        import asyncio
        from Assets.daemon import service
        from Assets.tui.helpers import ensure_sudo

        if not await ensure_sudo(self.app):
            self.query_one("#setup_daemon_status", Static).update(
                "[yellow]Administrator access not granted.[/]")
            return
        self.query_one("#setup_install", Button).disabled = True
        self.query_one("#setup_daemon_status", Static).update("Installing daemon…")
        result = await asyncio.to_thread(service.install_service)
        if result.get("ok"):
            await asyncio.to_thread(service.wait_for_daemon)
        self.query_one("#setup_install", Button).disabled = False
        if not result.get("ok"):
            self.query_one("#setup_daemon_status", Static).update(
                f"[red]{result.get('error', 'Installation failed.')}[/]")
            return
        self._refresh_daemon()

    @work(thread=True, exclusive=True, group="setup")
    def _refresh_daemon(self) -> None:
        from Assets.core.ipc import get_client
        running = get_client().ping()
        self.app.call_from_thread(self._render_daemon, running)

    def _render_daemon(self, running: bool) -> None:
        if running:
            self.query_one("#setup_daemon_status", Static).update("Daemon: [green]running[/]")
        else:
            self.query_one("#setup_daemon_status", Static).update("Daemon: [yellow]not running[/]")
        self.query_one("#setup_daemon_continue", Button).disabled = not running

    @work(thread=True, exclusive=True, group="setup")
    def _detect(self) -> None:
        from Assets.core.hardware import detect
        try:
            detect()
            cfg.save()
            err = None
        except Exception as exc:
            err = str(exc)
        self.app.call_from_thread(self._render_hardware, err)

    def _render_hardware(self, err: str | None) -> None:
        result = self.query_one("#setup_hw_result", Static)
        if err:
            result.update(f"[red]Detection failed:[/] {err}")
            return
        cpu = cfg.get("Info", "CPU") or "Unknown"
        family = cfg.get("Info", "Family") or "Unknown"
        arch = cfg.get("Info", "Architecture") or "Unknown"
        cpu_type = cfg.get("Info", "Type") or "Unknown"
        supported = cpu_type in _SUPPORTED
        lines = [
            f"  CPU           {cpu}",
            f"  Family        {family}",
            f"  Architecture  {arch}",
            f"  Type          {cpu_type}",
            "",
        ]
        if supported:
            from Assets.engine.presets import get_preset_label
            variant = cfg.get("Info", "Variant") or ""
            label = get_preset_label(cpu_type, family, cpu, cpu, variant)
            lines.append("  [green]Hardware is supported.[/]")
            lines.append(f"  Preset profile  {label}")
        else:
            lines.append("  [yellow]Hardware may not be fully supported.[/]")
            lines.append("  Custom presets are still available.")
        result.update("\n".join(lines))
        self.query_one("#setup_finish", Button).disabled = False
