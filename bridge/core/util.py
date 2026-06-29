import hashlib
import json
import os
from typing import Any


def stable_local_sid(cwd: str) -> str:
    key = (cwd or os.getcwd()).encode("utf-8")
    return f"local_{hashlib.sha256(key).hexdigest()[:12]}"


def is_ignored_workspace(cwd: str) -> bool:
    """True for Cursor/IDE config dirs — not real coding projects."""
    if not cwd:
        return False
    try:
        norm = os.path.realpath(os.path.expanduser(cwd))
    except OSError:
        return False
    home_cursor = os.path.realpath(os.path.expanduser("~/.cursor"))
    if norm == home_cursor or norm.startswith(home_cursor + os.sep):
        return True
    base = os.path.basename(norm.rstrip(os.sep))
    if base in (".cursor", ".vscode", ".claude"):
        return True
    return False


def _clip(value: Any, n: int) -> str:
    return str(value or "").replace("\n", " ")[:n]


def ide_bucket(model: str) -> str:
    """Map bridge session `model` to a stable IDE id (trae/cursor/claude)."""
    m = str(model or "").strip().lower()
    if not m:
        return ""
    if "trae" in m:
        return "trae"
    if "cursor" in m:
        return "cursor"
    if "claude" in m or "codex" in m:
        return "claude"
    return ""


def normalize_session_model(incoming: str, previous: str = "") -> str:
    """Keep IDE bucket when hooks send LLM ids or omit model on later events."""
    inc = _clip(incoming, 24)
    prev = _clip(previous, 24)
    bucket = ide_bucket(inc)
    if bucket:
        return bucket
    bucket = ide_bucket(prev)
    if bucket:
        return bucket
    return inc or prev or "codex"


def encode_line(obj: dict[str, Any]) -> bytes:
    return (json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def chunk_bytes(data: bytes, max_size: int):
    if max_size <= 0:
        raise ValueError("max_size must be positive")
    for start in range(0, len(data), max_size):
        yield data[start:start + max_size]
