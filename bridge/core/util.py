import hashlib
import json
import os
from typing import Any


def stable_local_sid(cwd: str) -> str:
    key = (cwd or os.getcwd()).encode("utf-8")
    return f"local_{hashlib.sha256(key).hexdigest()[:12]}"


def _clip(value: Any, n: int) -> str:
    return str(value or "").replace("\n", " ")[:n]


def encode_line(obj: dict[str, Any]) -> bytes:
    return (json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def chunk_bytes(data: bytes, max_size: int):
    if max_size <= 0:
        raise ValueError("max_size must be positive")
    for start in range(0, len(data), max_size):
        yield data[start:start + max_size]
