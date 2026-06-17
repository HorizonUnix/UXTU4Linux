from __future__ import annotations

import webbrowser

from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static

from Assets.core import config as cfg


class AboutModal(ModalScreen):
    BINDINGS = [("escape", "close", "Close")]

    def compose(self) -> ComposeResult:
        with Vertical(id="about_dialog"):
            yield Label("About UXTU4Linux", classes="dialog_title")
            yield Static(
                f"Version     [b]v{cfg.LOCAL_VERSION}[/]\n"
                f"Build       {cfg.LOCAL_BUILD}\n\n"
                "Maintainer  oxGorou\n"
                "Advisor     NotchApple1703", id="about_info")
            with Horizontal(id="about_buttons"):
                yield Button("GitHub", id="about_github", classes="about_btn github_btn")
                yield Button("Check updates", id="about_update",
                             variant="primary", classes="about_btn")
                yield Button("Close", id="about_close", classes="about_btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "about_github":
            webbrowser.open("https://github.com/HorizonUnix/UXTU4Linux")
        elif event.button.id == "about_update":
            self.app.push_screen(UpdaterModal())
        else:
            self.dismiss()

    def action_close(self) -> None:
        self.dismiss()


class UpdaterModal(ModalScreen):
    BINDINGS = [("escape", "close", "Close")]

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label("Software Update", classes="dialog_title")
            yield Static(f"Current version: v{cfg.LOCAL_VERSION}")
            yield Static("Checking for updates…", id="upd_status")
            with VerticalScroll(id="upd_changelog_scroll"):
                yield Static("", id="upd_changelog")
            with Horizontal(id="upd_buttons"):
                yield Button("Update now", id="upd_do", variant="success", disabled=True)
                yield Button("Switch to beta", id="upd_beta", variant="warning")
                yield Button("Close", id="upd_close", variant="primary")

    def on_mount(self) -> None:
        self._check()

    @work(thread=True, exclusive=True, group="updater")
    def _check(self) -> None:
        from Assets.flows.updater import get_latest_version, get_changelog
        try:
            latest = get_latest_version()
            changelog = get_changelog()
        except Exception as exc:
            self.app.call_from_thread(
                self.query_one("#upd_status", Static).update, f"Could not check for updates: {exc}")
            return
        self.app.call_from_thread(self._show, latest, changelog)

    def _show(self, latest: str, changelog: str) -> None:
        from Assets.flows.updater import _ver_tuple
        up_to_date = _ver_tuple(cfg.LOCAL_VERSION) >= _ver_tuple(latest)
        self.query_one("#upd_status", Static).update(
            "You are on the latest version." if up_to_date else f"Update available: {latest}")
        self.query_one("#upd_changelog", Static).update(changelog)
        btn = self.query_one("#upd_do", Button)
        btn.label = "Reinstall" if up_to_date else "Update now"
        btn.disabled = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        from Assets.flows.updater import _STABLE_URL, _BETA_URL
        if event.button.id == "upd_do":
            self.app.push_screen(UpdateProgressModal(_STABLE_URL))
        elif event.button.id == "upd_beta":
            from Assets.tui.modals import ConfirmModal
            self.app.push_screen(
                ConfirmModal("Switch to the beta build? Beta builds are unstable and may be broken."),
                lambda ok: self.app.push_screen(UpdateProgressModal(_BETA_URL)) if ok else None)
        else:
            self.dismiss()

    def action_close(self) -> None:
        self.dismiss()


class UpdateProgressModal(ModalScreen):
    def __init__(self, url: str) -> None:
        super().__init__()
        self._url = url

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label("Updating UXTU4Linux", classes="dialog_title")
            yield Static("Preparing…", id="update_status")
            with Horizontal(id="dialog_buttons"):
                yield Button("Close", id="update_close", disabled=True)

    def on_mount(self) -> None:
        self._run()

    @work
    async def _run(self) -> None:
        import asyncio
        from Assets.tui.privileged import ensure_sudo
        from Assets.flows.updater import perform_update

        status = self.query_one("#update_status", Static)
        if not await ensure_sudo(self.app):
            status.update("[yellow]Administrator access not granted.[/]")
            self.query_one("#update_close", Button).disabled = False
            return

        def report(msg: str) -> None:
            self.app.call_from_thread(status.update, msg)

        result = await asyncio.to_thread(perform_update, self._url, report)
        if result.get("ok"):
            self.app.exit("relaunch")
        else:
            status.update(f"[red]Update failed:[/] {result.get('error', 'unknown error')}")
            self.query_one("#update_close", Button).disabled = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss()
