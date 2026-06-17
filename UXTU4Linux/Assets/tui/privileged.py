from __future__ import annotations


async def ensure_sudo(app) -> bool:
    from Assets.daemon.service import sudo_available
    if sudo_available():
        return True
    from Assets.tui.sudo_modal import SudoModal
    return bool(await app.push_screen_wait(SudoModal()))
