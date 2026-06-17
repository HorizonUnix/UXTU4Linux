from Assets.core.ipc import get_client


def fetch_status() -> dict:
    return get_client().status()


def do_apply(args: str, mode: str) -> dict:
    from Assets.tuning.power import apply_preset
    return apply_preset(args, mode)
