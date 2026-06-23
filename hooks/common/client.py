import os


def bridge_url() -> str:
    return (
        os.environ.get("BUDDY_BRIDGE_URL")
        or os.environ.get("CURSOR_BUDDY_BRIDGE_URL")
        or "http://127.0.0.1:9876"
    )
