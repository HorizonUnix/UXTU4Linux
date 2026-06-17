from __future__ import annotations

from textual import work
from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Collapsible, Static

from Assets.core import config as cfg


def _rows(pairs: list[tuple[str, str]]) -> str:
    return "\n".join(f"  {label:<14}{value}" for label, value in pairs)


class HardwareTab(VerticalScroll):
    def compose(self) -> ComposeResult:
        with Vertical(classes="settings_card"):
            yield Static("Hardware", classes="card_title")
            yield Collapsible(Static("Loading…", id="hw_device"),
                              title="Device Information", collapsed=False)
            yield Collapsible(Static("Loading…", id="hw_processor"),
                              title="Processor Information", collapsed=False)
            yield Collapsible(Static("Loading…", id="hw_memory"),
                              title="Memory Information", collapsed=False)
            yield Collapsible(Static("", id="hw_battery"),
                              title="Battery", collapsed=False, id="hw_battery_card")

    def on_mount(self) -> None:
        self._load_static()
        self.set_interval(2.0, self.refresh_battery)
        self.refresh_battery()

    @work(thread=True, exclusive=True, group="hw")
    def _load_static(self) -> None:
        from Assets.core import hardware as hw
        dev = hw._parse_device_info()
        proc = hw._parse_processor_dmidecode()
        l1, l2, l3 = hw._parse_cache_sizes()
        mem = hw._parse_memory()
        device = _rows([("Name", dev["name"]), ("Producer", dev["producer"]), ("Model", dev["model"])])
        processor = _rows([
            ("Processor", cfg.get("Info", "CPU")), ("Codename", cfg.get("Info", "Family")),
            ("Architecture", cfg.get("Info", "Architecture")), ("Signature", cfg.get("Info", "Signature")),
            ("Cores", proc["cores"]), ("Threads", proc["threads"]), ("Base clock", proc["base_clock"]),
            ("L1 cache", l1), ("L2 cache", l2), ("L3 cache", l3)])
        memory = _rows([
            ("Memory", mem["summary"]), ("Producer", mem["manufacturer"]),
            ("Model", mem["part_number"]), ("Width", mem["width"]), ("Modules", mem["modules"])])
        self.app.call_from_thread(self.query_one("#hw_device", Static).update, device)
        self.app.call_from_thread(self.query_one("#hw_processor", Static).update, processor)
        self.app.call_from_thread(self.query_one("#hw_memory", Static).update, memory)

    @work(thread=True, exclusive=True, group="hwbat")
    def refresh_battery(self) -> None:
        from Assets.core import hardware as hw
        bat = hw._parse_battery()
        self.app.call_from_thread(self._render_battery, bat)

    def _render_battery(self, bat: dict | None) -> None:
        card = self.query_one("#hw_battery_card", Collapsible)
        if not bat:
            card.display = False
            return
        card.display = True
        self.query_one("#hw_battery", Static).update(_rows([
            ("Health", bat["health"]), ("Cycles", bat["cycles"]),
            ("Full charge", bat["full_charge"]), ("Design cap.", bat["design_cap"]),
            ("Charge rate", bat["charge_rate"])]))
