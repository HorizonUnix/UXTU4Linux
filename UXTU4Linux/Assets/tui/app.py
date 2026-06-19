from __future__ import annotations

import asyncio
import threading
import time

from textual import work
from textual.app import App, ComposeResult
from textual.widgets import Static, TabbedContent, TabPane, Footer

from Assets.core import config as cfg
from Assets.tui import helpers as banner
from Assets.tui.tabs import (
    HomeTab, PowerTab, CustomEditor, AutomationsTab, SettingsTab, HardwareTab, StatusTab)

_PAGES = ["home", "power", "custom", "automations", "hardware", "status", "settings"]


class U4LApp(App):
    CSS_PATH = "app.tcss"
    TITLE = "UXTU4Linux"

    def __init__(self, first_run: bool = False, dep_error: str | None = None,
                 path_stale: bool = False) -> None:
        super().__init__()
        self._first_run = first_run
        self._dep_error = dep_error
        self._path_stale = path_stale

    BINDINGS = [
        ("h", "show_tab('home')", "Home"),
        ("1", "show_tab('power')", "Premade"),
        ("2", "show_tab('custom')", "Custom"),
        ("3", "show_tab('automations')", "Auto"),
        ("4", "show_tab('hardware')", "Info"),
        ("5", "show_tab('status')", "Status"),
        ("6", "show_tab('settings')", "Settings"),
        ("question_mark", "about", "About"),
        ("escape", "focus_tabs", "Tabs"),
        ("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Static(banner.BANNER, id="banner")
        yield Static(banner.status_line(), id="hwline")
        yield Static("", id="statusline")
        with TabbedContent(initial="home", id="tabs"):
            with TabPane("Home", id="home"):
                yield HomeTab()
            with TabPane("Premade", id="power"):
                yield PowerTab()
            with TabPane("Custom", id="custom"):
                yield CustomEditor()
            with TabPane("Auto", id="automations"):
                yield AutomationsTab()
            with TabPane("Info", id="hardware"):
                yield HardwareTab()
            with TabPane("Status", id="status"):
                yield StatusTab()
            with TabPane("Settings", id="settings"):
                yield SettingsTab()
        yield Static("", id="too_small")
        yield Footer()

    def on_mount(self) -> None:
        self._apply_theme()
        self.set_interval(1.5, self.refresh_status)
        self._start_toast_reaper()
        self.refresh_status()
        self._check_size(self.size)
        if self._dep_error:
            from Assets.tui.modals import FatalErrorModal
            self.push_screen(FatalErrorModal(self._dep_error))
            return
        if self._first_run:
            from Assets.tui.wizard import SetupWizard
            self.push_screen(SetupWizard())
        elif self._path_stale:
            from Assets.tui.modals import StalePathModal
            self.push_screen(StalePathModal())
        elif cfg.get("Settings", "SoftwareUpdate", "0") == "1":
            self._startup_update_check()

    _theme_subscribed = False

    DEFAULT_THEME = "textual-dark"

    def _apply_theme(self) -> None:
        saved = cfg.get("Settings", "Theme", self.DEFAULT_THEME)
        self.theme = saved if saved in self.available_themes else self.DEFAULT_THEME
        if not self._theme_subscribed:
            self._theme_subscribed = True
            self.theme_changed_signal.subscribe(self, self._save_theme)

    def _save_theme(self, theme) -> None:
        name = getattr(theme, "name", theme)
        if name != cfg.get("Settings", "Theme", ""):
            cfg.set_config("Settings", "Theme", name)
            cfg.save()

    def action_show_tab(self, tab: str) -> None:
        if tab in _PAGES:
            self.query_one("#tabs", TabbedContent).active = tab

    def action_focus_tabs(self) -> None:
        from textual.widgets import Tabs
        try:
            self.set_focus(self.query_one(Tabs))
        except Exception:
            pass

    def action_about(self) -> None:
        from Assets.tui.modals import AboutModal
        self.push_screen(AboutModal())

    def on_resize(self, event) -> None:
        self._check_size(event.size)

    def _check_size(self, size) -> None:
        too_small = size.width < 50 or size.height < 25
        self.query_one("#too_small", Static).display = too_small
        self.query_one("#banner").display = not too_small
        self.query_one("#tabs").display = not too_small
        if too_small:
            self.query_one("#too_small", Static).update("Terminal too small — minimum is 50×25.")
            return
        self.query_one("#banner", Static).update(
            banner.WORDMARK if size.width < 62 else banner.BANNER)

    _reaper_stop = False
    _reaper_started = False
    _flush_ticks = 0

    def _start_toast_reaper(self) -> None:
        if self._reaper_started:
            return
        self._reaper_started = True
        loop = asyncio.get_running_loop()

        def _reap() -> None:
            while not self._reaper_stop:
                time.sleep(0.5)
                try:
                    loop.call_soon_threadsafe(self._reap_toasts)
                except RuntimeError:
                    break

        threading.Thread(target=_reap, name="toast-reaper", daemon=True).start()

    def _reap_toasts(self) -> None:
        self._refresh_notifications()
        if len(self._notifications):
            self._flush_ticks = 2
        if self._flush_ticks > 0:
            self._flush_ticks -= 1
            self.refresh()

    def on_unmount(self) -> None:
        self._reaper_stop = True

    @work(thread=True, exclusive=True, group="status")
    def refresh_status(self) -> None:
        from Assets.tui.helpers import fetch_status
        st = fetch_status()
        self.call_from_thread(self._render_status, st)

    _warned_offline = False

    def _render_status(self, st: dict) -> None:
        from textual.css.query import NoMatches
        try:
            line = self.query_one("#statusline", Static)
        except NoMatches:
            return
        if not st.get("ok"):
            from Assets.tui.wizard import SetupWizard
            in_setup = isinstance(self.screen, SetupWizard)
            line.display = not in_setup
            line.update("[yellow]Daemon offline — install or start it from the Settings tab.[/]")
            if not self._warned_offline and not in_setup:
                self._warned_offline = True
                self.notify("Install or start it from the Settings tab.",
                            title="Daemon offline", severity="warning")
            return
        self._warned_offline = False
        line.display = False

    @work(thread=True, exclusive=True, group="startup_update")
    def _startup_update_check(self) -> None:
        from Assets.flows.updater import is_beta_build, get_latest_version, _ver_tuple
        try:
            if is_beta_build():
                self.call_from_thread(self._prompt_startup_update, "beta", "")
            else:
                latest = get_latest_version()
                if _ver_tuple(cfg.LOCAL_VERSION) < _ver_tuple(latest):
                    self.call_from_thread(self._prompt_startup_update, "stable", latest)
        except Exception:
            return

    def _prompt_startup_update(self, channel: str, version: str) -> None:
        from Assets.tui.modals import ConfirmModal
        from Assets.tui.modals import UpdateProgressModal
        from Assets.flows.updater import _STABLE_URL, _BETA_URL
        if isinstance(self.screen, ConfirmModal):
            return
        if channel == "beta":
            message = ("You are running a beta build.\n\n"
                       "Reinstall the latest beta build? Beta builds are unstable and may "
                       "change without notice.")
            url = _BETA_URL
        else:
            message = f"A new version is available: {version}\n\nUpdate now?"
            url = _STABLE_URL
        self.push_screen(ConfirmModal(message),
                         lambda ok: self.push_screen(UpdateProgressModal(url)) if ok else None)


def run(first_run: bool = False, dep_error: str | None = None, path_stale: bool = False):
    return U4LApp(first_run=first_run, dep_error=dep_error, path_stale=path_stale).run()
