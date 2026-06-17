from __future__ import annotations

from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static


class SudoModal(ModalScreen[bool]):
    def compose(self) -> ComposeResult:
        with Vertical(id="sudo_dialog"):
            yield Static("Administrator access required", classes="dialog_title")
            yield Static(
                "Enter your password to install or manage the system daemon.",
                id="sudo_desc")
            yield Input(password=True, placeholder="Password", id="sudo_pw")
            yield Static("", id="sudo_error")
            with Horizontal(id="sudo_buttons"):
                yield Button("Authenticate", id="sudo_ok", variant="primary")
                yield Button("Cancel", id="sudo_cancel")

    def on_mount(self) -> None:
        self.query_one("#sudo_pw", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._submit()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "sudo_cancel":
            self.dismiss(False)
        elif event.button.id == "sudo_ok":
            self._submit()

    def _submit(self) -> None:
        pw = self.query_one("#sudo_pw", Input).value
        if not pw:
            self.query_one("#sudo_error", Static).update("[red]Enter a password.[/]")
            return
        self.query_one("#sudo_error", Static).update("Authenticating…")
        self.query_one("#sudo_ok", Button).disabled = True
        self._authenticate(pw)

    @work(thread=True, exclusive=True, group="sudo")
    def _authenticate(self, password: str) -> None:
        from Assets.daemon.service import prime_sudo
        ok = prime_sudo(password)
        self.app.call_from_thread(self._result, ok)

    def _result(self, ok: bool) -> None:
        if ok:
            self.dismiss(True)
            return
        self.query_one("#sudo_error", Static).update("[red]Incorrect password — try again.[/]")
        pw = self.query_one("#sudo_pw", Input)
        pw.value = ""
        pw.focus()
        self.query_one("#sudo_ok", Button).disabled = False
